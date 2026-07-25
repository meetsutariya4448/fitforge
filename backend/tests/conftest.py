"""
Shared pytest fixtures for the FitForge RAG test suite.
"""

import numpy as np
import pytest

from app.services.retrieval_service import ChunkResult


# ---------------------------------------------------------------------------
# Sample ChunkResult fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_chunks():
    return [
        ChunkResult(
            chunk_id=1,
            raw_content="Progressive overload is the key principle for strength gains.",
            contextualized_content="Context blurb A. Progressive overload is the key principle.",
            metadata={"topic": "progressive_overload", "fitness_goals": [], "fitness_levels": []},
            score=0.9,
        ),
        ChunkResult(
            chunk_id=2,
            raw_content="ACSM recommends 3-5 sets per muscle group per week for beginners.",
            contextualized_content="Context blurb B. ACSM recommends 3-5 sets for beginners.",
            metadata={"topic": "resistance_training", "fitness_goals": ["build_muscle"], "fitness_levels": ["beginner"]},
            score=0.8,
        ),
        ChunkResult(
            chunk_id=3,
            raw_content="Rest 2-5 minutes between heavy compound sets.",
            contextualized_content="Context blurb C. Rest 2-5 minutes between heavy sets.",
            metadata={"topic": "resistance_training", "fitness_goals": [], "fitness_levels": []},
            score=0.7,
        ),
        ChunkResult(
            chunk_id=4,
            raw_content="Protein intake should be 1.6-2.2g per kg bodyweight.",
            contextualized_content="Context blurb D. Protein 1.6-2.2g/kg for muscle building.",
            metadata={"topic": "nutrition", "fitness_goals": ["build_muscle"], "fitness_levels": []},
            score=0.6,
        ),
        ChunkResult(
            chunk_id=5,
            raw_content="Deload weeks reduce volume by 40-50% to dissipate fatigue.",
            contextualized_content="Context blurb E. Deload weeks reduce volume to aid recovery.",
            metadata={"topic": "progressive_overload", "fitness_goals": [], "fitness_levels": []},
            score=0.5,
        ),
    ]


@pytest.fixture
def mock_embed_model(monkeypatch):
    """Patch _get_embed_model to return a mock that yields zero vectors."""
    import app.services.retrieval_service as svc

    class FakeEmbedder:
        def encode(self, text, normalize_embeddings=False):
            return np.zeros(384, dtype=np.float32)

    fake = FakeEmbedder()
    monkeypatch.setattr(svc, "_embed_model", fake)
    return fake


@pytest.fixture
def mock_reranker(monkeypatch):
    """Patch _get_reranker to return a mock that scores by reverse-insertion-order."""
    import app.services.retrieval_service as svc

    class FakeReranker:
        def predict(self, pairs):
            # Return descending scores so first pair gets the highest score
            return np.array([10.0 - i for i in range(len(pairs))], dtype=np.float32)

    fake = FakeReranker()
    monkeypatch.setattr(svc, "_reranker", fake)
    return fake
