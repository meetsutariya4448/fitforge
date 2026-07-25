"""
RAG retrieval service.

Public API:
    retrieve(query, onboarding_data, k=5, retrieval_mode=None, db=None)
        -> RetrievalResult(chunks, scores, low_confidence, retrieval_mode)

retrieval_mode values (also accepted as settings.retrieval_mode default):
    "sparse_only"    — Postgres FTS only
    "dense_only"     — pgvector cosine only (uses contextualized embedding)
    "hybrid"         — dense + sparse fused via RRF (no reranking)
    "hybrid_rerank"  — hybrid + cross-encoder rerank to top-k (default)

The dense search can also be directed at raw_embedding (non-contextualised)
by passing use_raw_embedding=True to _dense_search; this is the toggle used
by the Phase 4 ablation study.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ChunkResult:
    chunk_id: int
    raw_content: str
    contextualized_content: str
    metadata: dict
    score: float = 0.0


@dataclass
class RetrievalResult:
    chunks: List[ChunkResult]
    scores: List[float]
    low_confidence: bool
    retrieval_mode: str


# ---------------------------------------------------------------------------
# Lazy model singletons — loaded once per process, reused across requests.
# Call _get_embed_model() / _get_reranker() in main.py lifespan to pre-load
# and avoid ~30 s cold-start latency on the first plan generation request.
# ---------------------------------------------------------------------------

_embed_model = None
_reranker = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        log.info("Loading embedding model: %s", settings.embed_model_name)
        _embed_model = SentenceTransformer(settings.embed_model_name)
        log.info("Embedding model ready.")
    return _embed_model


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        log.info("Loading cross-encoder: cross-encoder/ms-marco-MiniLM-L-6-v2")
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        log.info("Cross-encoder ready.")
    return _reranker


# ---------------------------------------------------------------------------
# Metadata filter
# ---------------------------------------------------------------------------

def _build_metadata_filter(onboarding_data) -> tuple[str, dict]:
    """Return (WHERE-clause fragment, params-dict) for a metadata-filtered query.

    Match logic (each dimension uses OR-with-universal):
      - A chunk passes goal filter if   fitness_goals == []  OR  goal is in array
      - A chunk passes level filter if  fitness_levels == [] OR  level is in array
      - A chunk passes equip filter if  equipment_tags == [] OR  ANY user equipment matches
    """
    goal = onboarding_data.fitness_goal.value
    level = onboarding_data.fitness_level.value
    equipment = [e.value for e in onboarding_data.available_equipment]

    goal_clause = (
        "(metadata->'fitness_goals' = '[]'::jsonb "
        " OR metadata @> jsonb_build_object('fitness_goals', jsonb_build_array(:goal)))"
    )
    level_clause = (
        "(metadata->'fitness_levels' = '[]'::jsonb "
        " OR metadata @> jsonb_build_object('fitness_levels', jsonb_build_array(:level)))"
    )

    equip_parts = ["metadata->'equipment_tags' = '[]'::jsonb"]
    equip_params: dict = {}
    for i, eq in enumerate(equipment):
        param = f"eq{i}"
        equip_parts.append(
            f"metadata @> jsonb_build_object('equipment_tags', jsonb_build_array(:{param}))"
        )
        equip_params[param] = eq
    equip_clause = "(" + " OR ".join(equip_parts) + ")"

    where = f"{goal_clause} AND {level_clause} AND {equip_clause}"
    params = {"goal": goal, "level": level, **equip_params}
    return where, params


# ---------------------------------------------------------------------------
# Dense retrieval — pgvector cosine similarity
# ---------------------------------------------------------------------------

def _dense_search(
    db: Session,
    query_embedding: list,
    onboarding_data,
    limit: int = 20,
    use_raw_embedding: bool = False,
) -> list[ChunkResult]:
    """Return top-`limit` chunks ordered by cosine similarity.

    use_raw_embedding=True switches from the contextualized embedding column
    to raw_embedding — used by the Phase 4 ablation study only.
    """
    emb_col = "raw_embedding" if use_raw_embedding else "embedding"
    meta_where, meta_params = _build_metadata_filter(onboarding_data)

    # CAST(:query_vec AS vector) avoids the :: cast syntax that SQLAlchemy
    # text() misparses as a named bindparam (same fix as in ingest_kb.py).
    sql = text(f"""
        SELECT id, raw_content, contextualized_content, metadata,
               1 - ({emb_col} <=> CAST(:query_vec AS vector)) AS cosine_sim
        FROM kb_chunks
        WHERE {meta_where}
        ORDER BY {emb_col} <=> CAST(:query_vec AS vector)
        LIMIT :limit
    """)

    params = {
        "query_vec": str(query_embedding),
        "limit": limit,
        **meta_params,
    }

    rows = db.execute(sql, params).fetchall()
    return [
        ChunkResult(
            chunk_id=r.id,
            raw_content=r.raw_content,
            contextualized_content=r.contextualized_content,
            metadata=r.metadata,
            score=float(r.cosine_sim),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Sparse retrieval — Postgres full-text search
# ---------------------------------------------------------------------------

def _sparse_search(
    db: Session,
    query: str,
    onboarding_data,
    limit: int = 20,
) -> list[ChunkResult]:
    """Return top-`limit` chunks ranked by ts_rank_cd (cover-density FTS rank).

    Query construction: plainto_tsquery normalises the user string into stems and
    drops stop-words, but it AND-joins every term.  Multi-word conversational
    queries (e.g. "how many sets per week should a beginner do for muscle growth?")
    require every stemmed term to co-occur in the same chunk, so many relevant
    chunks return zero matches.

    Fix: cast the plainto_tsquery result to text, swap ' & ' for ' | ', then
    re-parse with to_tsquery.  This reuses Postgres's own stemming/stop-word
    pipeline while turning the match condition into an OR (any term matches).
    ts_rank_cd still rewards chunks that match *more* terms, so a chunk
    containing four of six query terms still outranks one matching only one.

    websearch_to_tsquery is NOT used here: for plain text without quotes, "or",
    or "-" syntax it produces the same AND-joined query as plainto_tsquery and
    would not fix the problem.
    """
    meta_where, meta_params = _build_metadata_filter(onboarding_data)

    sql = text(f"""
        WITH or_query AS (
            SELECT to_tsquery('english',
                replace(
                    plainto_tsquery('english', :query)::text,
                    ' & ', ' | '
                )
            ) AS q
        )
        SELECT id, raw_content, contextualized_content, metadata,
               ts_rank_cd(search_vector, (SELECT q FROM or_query)) AS fts_rank
        FROM kb_chunks, or_query
        WHERE search_vector @@ or_query.q
          AND {meta_where}
        ORDER BY fts_rank DESC
        LIMIT :limit
    """)

    params = {"query": query, "limit": limit, **meta_params}
    rows = db.execute(sql, params).fetchall()
    return [
        ChunkResult(
            chunk_id=r.id,
            raw_content=r.raw_content,
            contextualized_content=r.contextualized_content,
            metadata=r.metadata,
            score=float(r.fts_rank),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Fetch chunks by ID list (used after RRF to hydrate fused result set)
# ---------------------------------------------------------------------------

def _fetch_chunks_by_ids(db: Session, ids: list[int]) -> list[ChunkResult]:
    if not ids:
        return []
    sql = text("""
        SELECT id, raw_content, contextualized_content, metadata
        FROM kb_chunks
        WHERE id = ANY(:ids)
    """)
    rows = db.execute(sql, {"ids": ids}).fetchall()
    # Preserve the RRF-fused order (rows come back in DB order)
    row_map = {r.id: r for r in rows}
    return [
        ChunkResult(
            chunk_id=cid,
            raw_content=row_map[cid].raw_content,
            contextualized_content=row_map[cid].contextualized_content,
            metadata=row_map[cid].metadata,
            score=0.0,
        )
        for cid in ids
        if cid in row_map
    ]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def _rrf_fuse(
    dense_ids: list[int],
    sparse_ids: list[int],
    k: int = 60,
) -> list[tuple[int, float]]:
    """Fuse two ranked lists with Reciprocal Rank Fusion (Cormack et al. 2009).

    RRF(d) = sum_r [ 1 / (k + rank_r(d)) ]

    k=60 is the empirically optimal constant from the original paper
    (tested against k ∈ {10, 20, 30, 60}; 60 generalises best).
    Rank is 1-indexed. Documents absent from a list contribute 0 from that list.
    """
    scores: dict[int, float] = {}
    for rank, cid in enumerate(dense_ids, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    for rank, cid in enumerate(sparse_ids, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: -x[1])


# ---------------------------------------------------------------------------
# Cross-encoder reranking
# ---------------------------------------------------------------------------

def _rerank(
    query: str,
    candidates: list[ChunkResult],
    top_k: int = 5,
) -> list[tuple[float, ChunkResult]]:
    """Score (query, passage) pairs with cross-encoder; return top-k by score.

    cross-encoder/ms-marco-MiniLM-L-6-v2 outputs raw logit-like scores
    (not probabilities). Typical range: highly relevant ≈ 6–10,
    irrelevant ≈ −5 to −8.
    """
    reranker = _get_reranker()
    pairs = [(query, c.raw_content) for c in candidates]
    scores = reranker.predict(pairs)  # numpy array, shape (len(candidates),)
    ranked = sorted(zip(scores.tolist(), candidates), key=lambda x: -x[0])
    return ranked[:top_k]


# ---------------------------------------------------------------------------
# Confidence threshold
# ---------------------------------------------------------------------------

def _is_low_confidence(top_score: float, candidate_count: int) -> bool:
    """Return True when retrieval quality is below the configured threshold.

    The threshold (-2.0 default) is empirical: after running the Phase 4 eval,
    plot top-1 cross-encoder score distributions for relevant vs irrelevant
    queries and pick the crossing point.  Exposed as a config variable so it
    can be tuned without redeployment.
    """
    if candidate_count == 0:
        return True
    return top_score < settings.confidence_threshold


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    onboarding_data,
    k: int = 5,
    retrieval_mode: Optional[str] = None,
    db: Optional[Session] = None,
    use_raw_embedding: bool = False,
) -> RetrievalResult:
    """Retrieve the top-k most relevant knowledge base chunks for a query.

    Args:
        query:           Natural-language query string (e.g. "how many sets
                         per week for a beginner building muscle").
        onboarding_data: OnboardingData — used for metadata filtering.
        k:               Number of chunks to return (default 5).
        retrieval_mode:  One of sparse_only / dense_only / hybrid /
                         hybrid_rerank.  Defaults to settings.retrieval_mode.
        db:              SQLAlchemy Session.  Must be provided.
        use_raw_embedding: If True, dense search uses raw_embedding column
                           instead of embedding (ablation study only).

    Returns:
        RetrievalResult with .chunks, .scores, .low_confidence, .retrieval_mode.
    """
    mode = retrieval_mode or settings.retrieval_mode

    # ── Dense branch ──────────────────────────────────────────────────────────
    dense_results: list[ChunkResult] = []
    if mode in ("dense_only", "hybrid", "hybrid_rerank"):
        query_emb = _get_embed_model().encode(
            query, normalize_embeddings=True
        ).tolist()
        dense_results = _dense_search(
            db, query_emb, onboarding_data, limit=20,
            use_raw_embedding=use_raw_embedding,
        )

    # ── Sparse branch ─────────────────────────────────────────────────────────
    sparse_results: list[ChunkResult] = []
    if mode in ("sparse_only", "hybrid", "hybrid_rerank"):
        sparse_results = _sparse_search(db, query, onboarding_data, limit=20)

    # ── Candidate selection ───────────────────────────────────────────────────
    if mode == "dense_only":
        candidates = dense_results[:20]
    elif mode == "sparse_only":
        candidates = sparse_results[:20]
    else:  # hybrid or hybrid_rerank
        fused = _rrf_fuse(
            [c.chunk_id for c in dense_results],
            [c.chunk_id for c in sparse_results],
        )
        fused_ids = [cid for cid, _ in fused[:20]]
        candidates = _fetch_chunks_by_ids(db, fused_ids)

    # ── Reranking + confidence ────────────────────────────────────────────────
    if mode == "hybrid_rerank":
        ranked = _rerank(query, candidates, top_k=k) if candidates else []
        final_scores = [s for s, _ in ranked]
        final_chunks = [c for _, c in ranked]
        # Attach the reranker score to each chunk for downstream inspection
        for chunk, score in zip(final_chunks, final_scores):
            chunk.score = score
        # Check confidence even on empty candidate set — no hits → low confidence
        low_conf = _is_low_confidence(
            final_scores[0] if final_scores else -999.0, len(final_chunks)
        )
    else:
        final_chunks = candidates[:k]
        final_scores = [c.score for c in final_chunks]
        # No reliable scalar score for non-reranked modes — always confident
        low_conf = False

    return RetrievalResult(
        chunks=final_chunks,
        scores=final_scores,
        low_confidence=low_conf,
        retrieval_mode=mode,
    )
