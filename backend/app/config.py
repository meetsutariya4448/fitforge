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
    access_token_expire_minutes: int = 1440

    # ── Groq ─────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_context_model: str = "llama-3.1-8b-instant"

    # ── RAG / retrieval ──────────────────────────────────────────
    embed_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    confidence_threshold: float = -2.0
    # Changed from "hybrid_rerank" to "hybrid" after Phase 4 eval (eval/results.md):
    # cross-encoder reranking regressed R@5 on 5/30 queries vs improving 1/30,
    # at +330ms median latency per request.  hybrid_rerank remains a valid mode
    # and can be re-enabled by setting RETRIEVAL_MODE=hybrid_rerank in .env.
    retrieval_mode: str = "hybrid"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Single settings instance imported everywhere
settings = Settings()
