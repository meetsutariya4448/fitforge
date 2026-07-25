"""
Retrieval evaluation — P@5, R@5, MRR, p50/p95 latency across five conditions.

Conditions:
  1. sparse_only        — Postgres FTS only
  2. dense_ctx          — dense_only with contextual embedding (default)
  3. dense_raw          — dense_only with raw (non-contextualised) embedding (ablation)
  4. hybrid             — RRF fusion, no cross-encoder reranking
  5. hybrid_rerank      — full pipeline (RRF + cross-encoder rerank) — production default

Reads: backend/eval/eval_set.json
Writes: backend/eval/results.md  (creates or overwrites retrieval section)

Usage (from backend/):
    python -m eval.run_retrieval_eval
"""

import json
import os
import statistics
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Eval config
# ---------------------------------------------------------------------------

CONDITIONS = [
    {"label": "sparse_only",   "mode": "sparse_only",   "use_raw": False},
    {"label": "dense_ctx",     "mode": "dense_only",    "use_raw": False},
    {"label": "dense_raw",     "mode": "dense_only",    "use_raw": True},
    {"label": "hybrid",        "mode": "hybrid",        "use_raw": False},
    {"label": "hybrid_rerank", "mode": "hybrid_rerank", "use_raw": False},
]

EVAL_SET_PATH = Path(__file__).parent / "eval_set.json"
RESULTS_PATH  = Path(__file__).parent / "results.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_onboarding(ctx: dict):
    from app.schemas.workout import (
        OnboardingData, FitnessGoal, FitnessLevel, Equipment,
    )
    return OnboardingData(
        name="EvalUser",
        age=25,
        fitness_goal=FitnessGoal(ctx["fitness_goal"]),
        fitness_level=FitnessLevel(ctx["fitness_level"]),
        available_equipment=[Equipment(e) for e in ctx["available_equipment"]],
        days_per_week=3,
    )


def _metrics(retrieved_ids: list[int], expected_ids: list[int], k: int = 5):
    """Return (precision_at_k, recall_at_k, reciprocal_rank)."""
    expected = set(expected_ids)
    hits = [1 if cid in expected else 0 for cid in retrieved_ids[:k]]
    precision = sum(hits) / k
    recall    = sum(hits) / len(expected) if expected else 0.0
    rr        = next((1.0 / (i + 1) for i, h in enumerate(hits) if h), 0.0)
    return precision, recall, rr


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Pre-load models once to avoid timing cold-start against the first query.
    print("Pre-loading embedding model and cross-encoder …")
    from app.services.retrieval_service import _get_embed_model, _get_reranker
    _get_embed_model()
    _get_reranker()
    print("Models ready.\n")

    from app.database import SessionLocal
    from app.services.retrieval_service import retrieve

    eval_set = json.loads(EVAL_SET_PATH.read_text())
    print(f"Loaded {len(eval_set)} eval queries from {EVAL_SET_PATH.name}\n")

    # condition_label → list of per-query dicts
    all_results: dict[str, list[dict]] = {c["label"]: [] for c in CONDITIONS}

    db = SessionLocal()
    try:
        for ci, cond in enumerate(CONDITIONS):
            label = cond["label"]
            print(f"[{ci+1}/{len(CONDITIONS)}] Running condition: {label}")

            for q in eval_set:
                onboarding = _make_onboarding(q["onboarding_context"])

                t0 = time.perf_counter()
                try:
                    result = retrieve(
                        q["query"],
                        onboarding,
                        k=5,
                        retrieval_mode=cond["mode"],
                        use_raw_embedding=cond["use_raw"],
                        db=db,
                    )
                    latency_ms = (time.perf_counter() - t0) * 1000

                    retrieved_ids = [c.chunk_id for c in result.chunks]
                except Exception as exc:
                    print(f"  WARN {q['query_id']}: {exc}")
                    retrieved_ids = []
                    latency_ms = 0.0

                p5, r5, rr = _metrics(retrieved_ids, q["expected_chunk_ids"])
                all_results[label].append({
                    "query_id":  q["query_id"],
                    "p5": p5, "r5": r5, "rr": rr,
                    "latency_ms": latency_ms,
                    "retrieved": retrieved_ids,
                    "expected":  q["expected_chunk_ids"],
                })

            # Per-condition summary
            rows = all_results[label]
            mean_p5  = statistics.mean(r["p5"]         for r in rows)
            mean_r5  = statistics.mean(r["r5"]         for r in rows)
            mean_mrr = statistics.mean(r["rr"]         for r in rows)
            lats     = sorted(r["latency_ms"] for r in rows)
            p50_ms   = statistics.median(lats)
            p95_ms   = lats[max(0, int(len(lats) * 0.95) - 1)]

            print(
                f"  P@5={mean_p5:.3f}  R@5={mean_r5:.3f}  MRR={mean_mrr:.3f}"
                f"  p50={p50_ms:.0f}ms  p95={p95_ms:.0f}ms\n"
            )
    finally:
        db.close()

    # ── Build results markdown ───────────────────────────────────────────────

    rows_md = []
    for cond in CONDITIONS:
        label = cond["label"]
        rows  = all_results[label]
        if not rows:
            continue
        mean_p5  = statistics.mean(r["p5"] for r in rows)
        mean_r5  = statistics.mean(r["r5"] for r in rows)
        mean_mrr = statistics.mean(r["rr"] for r in rows)
        lats     = sorted(r["latency_ms"] for r in rows)
        p50_ms   = statistics.median(lats)
        p95_ms   = lats[max(0, int(len(lats) * 0.95) - 1)]

        rows_md.append(
            f"| {label:<20} | {mean_p5:.3f} | {mean_r5:.3f} | {mean_mrr:.3f}"
            f" | {p50_ms:>7.0f} | {p95_ms:>7.0f} |"
        )

    # Find best row for the summary note
    best_label = max(
        all_results,
        key=lambda lbl: statistics.mean(r["rr"] for r in all_results[lbl]) if all_results[lbl] else 0,
    )

    retrieval_section = f"""## Retrieval Evaluation

**Dataset**: {len(eval_set)} hand-curated queries across 11 topic areas
**Metrics**: P@5 (precision at 5), R@5 (recall at 5), MRR (mean reciprocal rank)
**Latency**: wall-clock per query, models pre-loaded; includes DB round-trip

| Condition            | P@5   | R@5   | MRR   | p50 (ms) | p95 (ms) |
|----------------------|-------|-------|-------|----------|----------|
{chr(10).join(rows_md)}

**Best MRR**: `{best_label}`

### Per-query breakdown (hybrid_rerank)

| query_id | P@5 | R@5 | RR  | retrieved_ids |
|----------|-----|-----|-----|---------------|
"""
    for row in all_results["hybrid_rerank"]:
        ret_str = str(row["retrieved"])
        retrieval_section += (
            f"| {row['query_id']} | {row['p5']:.2f} | {row['r5']:.2f}"
            f" | {row['rr']:.2f} | {ret_str} |\n"
        )

    # Write / update results.md  ──────────────────────────────────────────────
    if RESULTS_PATH.exists():
        existing = RESULTS_PATH.read_text()
        # Replace the retrieval section if it already exists
        marker = "## Retrieval Evaluation"
        if marker in existing:
            gen_marker = "\n## Generation Evaluation"
            if gen_marker in existing:
                # Keep generation section
                gen_part = existing[existing.index(gen_marker):]
                new_content = retrieval_section + "\n---\n" + gen_part.lstrip()
            else:
                new_content = retrieval_section
        else:
            new_content = existing.rstrip() + "\n\n---\n\n" + retrieval_section
    else:
        new_content = f"# FitForge RAG — Evaluation Results\n\n{retrieval_section}"

    RESULTS_PATH.write_text(new_content)
    print(f"Results written to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
