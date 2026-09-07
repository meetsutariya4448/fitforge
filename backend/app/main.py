"""
FitForge FastAPI application entry point.

Registers all routers, configures CORS, and sets up OpenAPI documentation.
Run with: uvicorn app.main:app --reload --port 8000
"""

import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine, Base
from app.limiter import limiter
from app.routers import workout, auth, sessions
from app.tracing import set_trace, get_trace

# Import all models so Base.metadata is populated before create_all()
import app.models  # noqa: F401

log = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Run once on startup: ensure all database tables exist.

    ML models (embedding model and cross-encoder) are loaded lazily on first
    use via _get_embed_model() / _get_reranker() in retrieval_service.py.
    The first plan-generation request after a cold boot pays the load cost
    (~5–15 s); subsequent requests reuse the cached singletons.

    Pre-loading at startup was removed because loading ~175 MB of model
    weights before the health-check window closes causes 503s on memory-
    constrained hosts (e.g. Render free tier at 512 MB).
    """
    Base.metadata.create_all(bind=engine)
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

app.state.limiter = limiter

# ── Structured error responses ────────────────────────────────────────────────

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_HTTP_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # An exception may carry a more specific code than the status alone implies
    # (e.g. REFRESH_RACE vs REFRESH_REUSE, both 401) — prefer it when present so
    # clients can branch on the reason rather than parsing the message.
    code = getattr(exc, "error_code", None) or _HTTP_CODE_MAP.get(
        exc.status_code, f"HTTP_{exc.status_code}"
    )
    body: dict = {"error": {"code": code, "message": exc.detail or ""}}
    if exc.status_code == 429:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        if retry_after:
            body["error"]["retry_after"] = int(retry_after)
    # Headers set on the exception must survive: dropping them silently stripped
    # WWW-Authenticate from every 401, which RFC 7235 requires on that status.
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Rate-limit rejections, in the same envelope as every other error.

    slowapi's stock handler answers with {"error": "<string>"} while the rest of
    the API answers with {"error": {"code", "message"}}.  A client cannot parse
    both shapes with one schema, so this re-wraps it — and still runs slowapi's
    header injection so Retry-After / X-RateLimit-* survive.
    """
    response = JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": f"Rate limit exceeded: {exc.detail}",
            }
        },
    )
    return limiter._inject_headers(response, request.state.view_rate_limit)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request body is invalid.",
                "details": exc.errors(),
            }
        },
    )


# ── Request tracing middleware ─────────────────────────────────────────────────

@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    trace_id = str(uuid4())
    trace: dict = {"trace_id": trace_id}
    set_trace(trace)

    t0 = time.perf_counter()
    response = await call_next(request)
    total_ms = round((time.perf_counter() - t0) * 1000, 1)

    # Only persist traces for AI generation endpoints — other routes have no
    # retrieval/LLM fields to populate, so sparse rows add no analytical value.
    path = request.url.path
    if "/generate" in path:
        trace.update(
            endpoint=path,
            method=request.method,
            status_code=response.status_code,
            total_ms=total_ms,
        )
        try:
            from app.database import SessionLocal
            from app.models.request_trace import RequestTrace
            db = SessionLocal()
            try:
                row = RequestTrace(
                    trace_id=trace.get("trace_id", trace_id),
                    user_id=trace.get("user_id"),
                    endpoint=trace.get("endpoint"),
                    method=trace.get("method"),
                    status_code=trace.get("status_code"),
                    total_ms=trace.get("total_ms"),
                    retrieval_ms=trace.get("retrieval_ms"),
                    rerank_ms=trace.get("rerank_ms"),
                    llm_ms=trace.get("llm_ms"),
                    retrieval_mode=trace.get("retrieval_mode"),
                    model=trace.get("model"),
                    prompt_tokens=trace.get("prompt_tokens"),
                    completion_tokens=trace.get("completion_tokens"),
                    low_confidence=trace.get("low_confidence"),
                    num_chunks_retrieved=trace.get("num_chunks_retrieved"),
                )
                db.add(row)
                db.commit()
            finally:
                db.close()
        except Exception:
            log.exception("Failed to write request trace")

    return response


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
