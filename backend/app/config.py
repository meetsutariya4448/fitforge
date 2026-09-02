"""
Application configuration loaded from environment variables.
Uses pydantic-settings for type-safe config with .env file support.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────
    app_name: str = "FitForge"
    app_env: str = "development"
    app_port: int = 8000

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "postgresql://postgres:password@localhost:5432/fitforge"

    # ── JWT ──────────────────────────────────────────────────────
    secret_key: str = "change-this-secret-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # ── Groq ─────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_context_model: str = "llama-3.1-8b-instant"

    # ── RAG / retrieval ──────────────────────────────────────────
    embed_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Cross-encoder confidence threshold (hybrid_rerank mode only).
    # Calibrated for ms-marco-MiniLM-L-6-v2 logit-like scores (~-10 to +10).
    # Do NOT reuse for RRF scores — completely different scale.
    confidence_threshold: float = -2.0

    # RRF confidence threshold (hybrid mode only).  Cross-encoder logit-like
    # scores (confidence_threshold) are on a completely different scale.
    # RRF(k=60, 2 lists of 20) produces top-1 scores in 0.031–0.033 for
    # queries that retrieve a relevant chunk (30-query eval, eval/results.md).
    # 0.020 is set conservatively below the observed minimum (0.031) so none
    # of the eval queries trigger the fallback.  Recalibrate from production
    # query logs once sufficient off-topic-query examples are available.
    rrf_confidence_threshold: float = 0.020

    # Changed from "hybrid_rerank" to "hybrid" after Phase 4 eval (eval/results.md):
    # cross-encoder reranking regressed R@5 on 5/30 queries vs improving 1/30,
    # at +330ms median latency per request.  hybrid_rerank remains a valid mode
    # and can be re-enabled by setting RETRIEVAL_MODE=hybrid_rerank in .env.
    retrieval_mode: str = "hybrid"

    # ── LangGraph agent ──────────────────────────────────────────
    # refine cycles allowed per request; 0 = generate + critique only (no refine)
    agent_max_iterations: int = 2
    # score >= threshold AND no equipment violation → accepted; otherwise refine
    agent_critique_threshold: float = 0.75

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Single settings instance imported everywhere
settings = Settings()
