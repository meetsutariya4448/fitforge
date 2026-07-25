"""
FitForge FastAPI application entry point.

Registers all routers, configures CORS, and sets up OpenAPI documentation.
Run with: uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import workout, auth, sessions

# Import all models so Base.metadata is populated before create_all()
import app.models  # noqa: F401


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Run once on startup: ensure all database tables exist, then pre-load
    the RAG embedding and reranking models so the first plan-generation
    request doesn't incur a ~30 s cold-start delay.
    """
    Base.metadata.create_all(bind=engine)
    # Pre-load sentence-transformer models (downloads once, then cached)
    from app.services.retrieval_service import _get_embed_model, _get_reranker
    _get_embed_model()
    _get_reranker()
    yield


# ── App instance ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="FitForge API",
    description="AI-powered fitness platform — workout plans, progress tracking, personal records.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://fitforge-six.vercel.app",
        "https://fitforge-nqlh9it75-meetsutariya4448s-projects.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(workout.router, prefix="/api/workout", tags=["Workout"])
app.include_router(sessions.router, prefix="/api", tags=["Sessions"])


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    """Simple liveness probe used by deployment platforms."""
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
