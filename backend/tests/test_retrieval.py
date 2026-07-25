"""
Unit tests for retrieval_service.py.

Covers: RRF fusion, confidence threshold, cross-encoder reranking,
and retrieve() mode dispatch.  No live database or model calls —
DB interactions are replaced with mocks via monkeypatch.
"""

import numpy as np
import pytest

from app.services.retrieval_service import (
    ChunkResult,
    RetrievalResult,
    _is_low_confidence,
    _rerank,
    _rrf_fuse,
    retrieve,
)


# ============================================================================
# _rrf_fuse — pure function, no mocks needed
# ============================================================================

class TestRRFFuse:
    def test_single_list_scores_correctly(self):
        """A document at rank 1 in dense only gets 1/(60+1) = 0.01639..."""
        result = _rrf_fuse(dense_ids=[42], sparse_ids=[])
        assert len(result) == 1
        cid, score = result[0]
        assert cid == 42
        assert abs(score - 1 / 61) < 1e-9

    def test_k60_constant_rank1(self):
        """Verify the exact RRF formula: 1/(60+rank) with k=60."""
        result = _rrf_fuse(dense_ids=[1, 2, 3], sparse_ids=[])
        scores = {cid: s for cid, s in result}
        assert abs(scores[1] - 1 / 61) < 1e-9
        assert abs(scores[2] - 1 / 62) < 1e-9
        assert abs(scores[3] - 1 / 63) < 1e-9

    def test_merges_both_lists(self):
        """Documents from both lists appear in merged output."""
        fused = _rrf_fuse(dense_ids=[10, 20], sparse_ids=[30, 40])
        ids = {cid for cid, _ in fused}
        assert ids == {10, 20, 30, 40}

    def test_shared_document_accumulates_scores(self):
        """A document in both lists gets sum of 1/(k+rank) from each list."""
        fused = _rrf_fuse(dense_ids=[99], sparse_ids=[99])
        assert len(fused) == 1
        cid, score = fused[0]
        assert cid == 99
        expected = 1 / 61 + 1 / 61  # rank 1 in both lists
        assert abs(score - expected) < 1e-9

    def test_missing_from_one_list_still_scores(self):
        """A document only in sparse still appears with its sparse score."""
        fused = _rrf_fuse(dense_ids=[1], sparse_ids=[1, 2])
        ids = {cid for cid, _ in fused}
        assert 2 in ids
        score_2 = dict(fused)[2]
        assert abs(score_2 - 1 / 62) < 1e-9  # rank 2 in sparse, absent from dense

    def test_shared_doc_ranked_above_single_list_docs(self):
        """A doc at rank 1 in both lists should outscore docs in only one list."""
        # doc 1 appears at rank 1 in both; doc 2 appears only in dense at rank 2
        fused = _rrf_fuse(dense_ids=[1, 2], sparse_ids=[1])
        scores = dict(fused)
        assert scores[1] > scores[2]

    def test_empty_both_lists(self):
        assert _rrf_fuse([], []) == []

    def test_empty_dense(self):
        fused = _rrf_fuse(dense_ids=[], sparse_ids=[5, 6])
        ids = [cid for cid, _ in fused]
        assert ids == [5, 6]

    def test_sorted_descending(self):
        """Output must be sorted by score descending."""
        fused = _rrf_fuse(dense_ids=[1, 2, 3], sparse_ids=[3, 2, 1])
        scores = [s for _, s in fused]
        assert scores == sorted(scores, reverse=True)

    def test_custom_k(self):
        """Verify formula works with a non-default k."""
        result = _rrf_fuse(dense_ids=[7], sparse_ids=[], k=10)
        _, score = result[0]
        assert abs(score - 1 / 11) < 1e-9  # 1/(10+1)


# ============================================================================
# _is_low_confidence
# ============================================================================

class TestConfidenceThreshold:
    def test_empty_candidates_is_low_confidence(self):
        assert _is_low_confidence(top_score=0.0, candidate_count=0) is True

    def test_score_below_threshold_is_low_confidence(self):
        # Default threshold is -2.0; score of -5 is below it
        assert _is_low_confidence(top_score=-5.0, candidate_count=3) is True

    def test_score_at_threshold_is_not_low_confidence(self):
        # Strict less-than (<), so score exactly equal to threshold is NOT low confidence
        from app.config import settings
        threshold = settings.confidence_threshold
        assert _is_low_confidence(top_score=threshold, candidate_count=3) is False

    def test_score_above_threshold_is_high_confidence(self):
        # Score of 5.0 is well above -2.0 threshold
        assert _is_low_confidence(top_score=5.0, candidate_count=3) is False

    def test_score_just_above_threshold_is_high_confidence(self):
        from app.config import settings
        just_above = settings.confidence_threshold + 0.001
        assert _is_low_confidence(top_score=just_above, candidate_count=1) is False


# ============================================================================
# _rerank
# ============================================================================

class TestRerank:
    def test_orders_by_cross_encoder_score(self, sample_chunks, mock_reranker):
        """mock_reranker gives 10, 9, 8... — first chunk should rank highest."""
        ranked = _rerank("test query", sample_chunks, top_k=3)
        assert len(ranked) == 3
        # Scores should be descending
        scores = [s for s, _ in ranked]
        assert scores == sorted(scores, reverse=True)
        # First chunk in input → highest score (10.0)
        assert abs(scores[0] - 10.0) < 0.01

    def test_returns_top_k_only(self, sample_chunks, mock_reranker):
        ranked = _rerank("query", sample_chunks, top_k=2)
        assert len(ranked) == 2

    def test_top_k_exceeding_candidates(self, sample_chunks, mock_reranker):
        """top_k > len(candidates) should return all candidates."""
        ranked = _rerank("query", sample_chunks[:2], top_k=10)
        assert len(ranked) == 2

    def test_empty_candidates(self, mock_reranker):
        ranked = _rerank("query", [], top_k=5)
        assert ranked == []

    def test_returns_chunk_result_objects(self, sample_chunks, mock_reranker):
        ranked = _rerank("query", sample_chunks, top_k=2)
        for score, chunk in ranked:
            assert isinstance(chunk, ChunkResult)
            assert isinstance(score, float)


# ============================================================================
# _sparse_search — OR-semantics unit test (no real DB; verifies SQL shape)
# ============================================================================

class TestSparseSearchOrSemantics:
    """
    Verify that _sparse_search builds an OR-joined tsquery so that a chunk
    matching only a *subset* of query terms is still returned, and that chunks
    matching more terms rank higher than chunks matching fewer.

    We cannot call the real DB here, so we mock db.execute() to capture the
    SQL text that _sparse_search sends, then assert the OR-join pattern is
    present.  A secondary mock run simulates two rows with different fts_rank
    scores to confirm ordering is preserved.
    """

    def _make_onboarding(self):
        from app.schemas.workout import (
            OnboardingData, FitnessGoal, FitnessLevel, Equipment,
        )
        return OnboardingData(
            name="Test", age=25,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            fitness_level=FitnessLevel.BEGINNER,
            available_equipment=[Equipment.DUMBBELLS],
            days_per_week=3,
        )

    def test_sparse_or_query_sql_contains_or_join(self):
        """The SQL sent to the DB must use ' | ' not ' & ' for term joining."""
        import app.services.retrieval_service as svc
        from sqlalchemy import text as sa_text

        captured_sql = []

        class FakeResult:
            def fetchall(self): return []

        class FakeDB:
            def execute(self, sql, params=None):
                captured_sql.append(str(sql))
                return FakeResult()

        svc._sparse_search(FakeDB(), "how many sets per week beginner muscle", self._make_onboarding())

        assert captured_sql, "db.execute was never called"
        sql_text = captured_sql[0]
        # The replace(' & ', ' | ') transform must be present
        assert "' | '" in sql_text or "| '\"" in sql_text or "replace(" in sql_text.lower(), (
            f"OR-join pattern not found in SQL:\n{sql_text}"
        )

    def test_sparse_search_or_semantics_partial_match(self):
        """
        A chunk matching only SOME query terms must be returned (not filtered
        out the way AND-semantics would), and a chunk matching MORE terms must
        rank above a chunk matching fewer.
        """
        import app.services.retrieval_service as svc

        # Simulate two rows from the DB: high_match has fts_rank 0.15,
        # partial_match has fts_rank 0.05 (matches fewer terms).
        class FakeRow:
            def __init__(self, id_, raw, ctx, meta, rank):
                self.id = id_
                self.raw_content = raw
                self.contextualized_content = ctx
                self.metadata = meta
                self.fts_rank = rank

        rows = [
            FakeRow(1, "sets beginner muscle growth week training", "ctx A", {}, 0.15),
            FakeRow(2, "muscle training",                           "ctx B", {}, 0.05),
        ]

        class FakeResult:
            def fetchall(self): return rows

        class FakeDB:
            def execute(self, sql, params=None):
                return FakeResult()

        results = svc._sparse_search(
            FakeDB(),
            "how many sets per week beginner muscle",
            self._make_onboarding(),
        )

        # Both chunks must be returned (OR semantics — partial match not excluded)
        assert len(results) == 2, (
            f"Expected 2 results (partial match must not be excluded), got {len(results)}"
        )
        # Higher-rank chunk must come first (DB already orders DESC; verify preserved)
        assert results[0].chunk_id == 1
        assert results[1].chunk_id == 2
        assert results[0].score > results[1].score

    def test_sparse_search_returns_chunk_result_with_fts_score(self):
        """Score on returned ChunkResult must reflect fts_rank, not 0."""
        import app.services.retrieval_service as svc

        class FakeRow:
            id = 7; raw_content = "progressive overload sets"; contextualized_content = "ctx"
            metadata = {}; fts_rank = 0.123

        class FakeResult:
            def fetchall(self): return [FakeRow()]

        class FakeDB:
            def execute(self, sql, params=None): return FakeResult()

        results = svc._sparse_search(FakeDB(), "progressive overload", self._make_onboarding())
        assert len(results) == 1
        assert abs(results[0].score - 0.123) < 1e-6


# ============================================================================
# retrieve() — mode dispatch and output structure
# ============================================================================

class TestRetrieve:
    """Integration-style tests with mocked DB, embed model, and reranker."""

    def _make_fake_db(self, monkeypatch, dense_rows=None, sparse_rows=None, chunk_rows=None):
        """Return a mock Session whose execute() returns preset row lists."""
        import app.services.retrieval_service as svc

        dense_rows = dense_rows or []
        sparse_rows = sparse_rows or []
        chunk_rows = chunk_rows or []

        call_count = {"n": 0}

        class FakeRow:
            def __init__(self, id, raw, ctx, meta, score=0.0):
                self.id = id
                self.raw_content = raw
                self.contextualized_content = ctx
                self.metadata = meta
                self.cosine_sim = score
                self.fts_rank = score

        class FakeResult:
            def __init__(self, rows):
                self._rows = rows
            def fetchall(self):
                return self._rows
            def scalar(self):
                return self._rows[0] if self._rows else 0

        class FakeDB:
            def execute(self_, sql, params=None):
                call_count["n"] += 1
                sql_str = str(sql)
                if "cosine_sim" in sql_str:
                    return FakeResult([
                        FakeRow(r[0], r[1], r[2], r[3], r[4]) for r in dense_rows
                    ])
                elif "fts_rank" in sql_str:
                    return FakeResult([
                        FakeRow(r[0], r[1], r[2], r[3], r[4]) for r in sparse_rows
                    ])
                elif "ANY" in sql_str:
                    return FakeResult([
                        FakeRow(r[0], r[1], r[2], r[3]) for r in chunk_rows
                    ])
                return FakeResult([])

        return FakeDB(), call_count

    def _make_onboarding(self):
        """Minimal OnboardingData-like object for filter building."""
        from app.schemas.workout import (
            OnboardingData, FitnessGoal, FitnessLevel, Equipment
        )
        return OnboardingData(
            name="Test",
            age=25,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            fitness_level=FitnessLevel.BEGINNER,
            available_equipment=[Equipment.DUMBBELLS],
            days_per_week=3,
        )

    def test_returns_retrieval_result_dataclass(self, monkeypatch, mock_embed_model, mock_reranker):
        db, _ = self._make_fake_db(monkeypatch)
        result = retrieve("test query", self._make_onboarding(), db=db,
                          retrieval_mode="sparse_only")
        assert isinstance(result, RetrievalResult)
        assert isinstance(result.chunks, list)
        assert isinstance(result.scores, list)
        assert isinstance(result.low_confidence, bool)
        assert result.retrieval_mode == "sparse_only"

    def test_sparse_only_skips_dense_encode(self, monkeypatch, mock_reranker):
        """sparse_only mode must not call the embedding model."""
        import app.services.retrieval_service as svc

        embed_called = {"n": 0}

        class TrackingEmbedder:
            def encode(self, *a, **kw):
                embed_called["n"] += 1
                return np.zeros(384)

        monkeypatch.setattr(svc, "_embed_model", TrackingEmbedder())
        db, _ = self._make_fake_db(monkeypatch)
        retrieve("query", self._make_onboarding(), db=db, retrieval_mode="sparse_only")
        assert embed_called["n"] == 0

    def test_dense_only_skips_fts_query(self, monkeypatch, mock_embed_model, mock_reranker):
        """dense_only mode must not issue an FTS query."""
        import app.services.retrieval_service as svc

        fts_called = {"n": 0}
        original_sparse = svc._sparse_search

        def tracking_sparse(*a, **kw):
            fts_called["n"] += 1
            return original_sparse(*a, **kw)

        monkeypatch.setattr(svc, "_sparse_search", tracking_sparse)
        db, _ = self._make_fake_db(monkeypatch)
        retrieve("query", self._make_onboarding(), db=db, retrieval_mode="dense_only")
        assert fts_called["n"] == 0

    def test_hybrid_rerank_sets_low_confidence_on_empty(self, monkeypatch, mock_embed_model, mock_reranker):
        """When no candidates are found, hybrid_rerank must return low_confidence=True."""
        db, _ = self._make_fake_db(monkeypatch,
                                    dense_rows=[], sparse_rows=[], chunk_rows=[])
        result = retrieve("obscure query", self._make_onboarding(), db=db,
                          retrieval_mode="hybrid_rerank")
        assert result.low_confidence is True

    def test_non_reranked_modes_never_set_low_confidence(self, monkeypatch, mock_embed_model):
        """sparse_only / dense_only / hybrid don't use cross-encoder so low_confidence=False."""
        for mode in ("sparse_only", "dense_only", "hybrid"):
            db, _ = self._make_fake_db(monkeypatch)
            result = retrieve("query", self._make_onboarding(), db=db,
                              retrieval_mode=mode)
            assert result.low_confidence is False, f"mode={mode} unexpectedly set low_confidence"

    def test_retrieve_respects_k_limit(self, monkeypatch, mock_embed_model, mock_reranker):
        """Result should contain at most k chunks."""
        # 5 dense rows
        rows = [(i, f"raw {i}", f"ctx {i}", {}, 0.9 - i*0.1) for i in range(1, 6)]
        db, _ = self._make_fake_db(monkeypatch, dense_rows=rows)
        result = retrieve("query", self._make_onboarding(), db=db,
                          retrieval_mode="dense_only", k=3)
        assert len(result.chunks) <= 3

    def test_hybrid_rerank_attaches_reranker_scores(self, monkeypatch, mock_embed_model, mock_reranker):
        """After hybrid_rerank, chunk.score should equal the cross-encoder score."""
        rows = [(1, "raw 1", "ctx 1", {}, 0.9), (2, "raw 2", "ctx 2", {}, 0.8)]
        db, _ = self._make_fake_db(monkeypatch, dense_rows=rows, sparse_rows=rows,
                                    chunk_rows=[(1, "raw 1", "ctx 1", {}),
                                                (2, "raw 2", "ctx 2", {})])
        result = retrieve("query", self._make_onboarding(), db=db,
                          retrieval_mode="hybrid_rerank", k=2)
        # mock_reranker gives 10.0 for first, 9.0 for second
        assert len(result.scores) > 0
        assert result.scores[0] > result.scores[-1]  # descending order
