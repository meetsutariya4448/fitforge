"""
FitForge FastAPI application entry point.

Registers all routers, configures CORS, and sets up OpenAPI documentation.
Run with: uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import workout, auth

# ── App instance ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="FitForge API",
    description="AI-powered fitness platform — workout plans, progress tracking, social features.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow requests from the React dev server (and production frontend URL).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(workout.router, prefix="/api/workout", tags=["Workout"])


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    """Simple liveness probe used by deployment platforms."""
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
