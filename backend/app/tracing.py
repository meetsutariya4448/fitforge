"""
Per-request trace context using Python's contextvars.

Each HTTP request gets a fresh dict set by the trace middleware.
Service-layer code (ai_service, retrieval_service) populates it with
inner timings and AI metadata without needing the request object.

Usage:
    # In service code:
    from app.tracing import update_trace
    update_trace(retrieval_ms=142.3, num_chunks_retrieved=5)

    # In middleware (reads after the response):
    from app.tracing import get_trace
    trace = get_trace()  # dict with all populated fields, or None
"""

from contextvars import ContextVar
from typing import Optional

_trace_ctx: ContextVar[Optional[dict]] = ContextVar("request_trace", default=None)


def set_trace(data: dict) -> None:
    _trace_ctx.set(data)


def get_trace() -> Optional[dict]:
    return _trace_ctx.get()


def update_trace(**kwargs) -> None:
    t = _trace_ctx.get()
    if t is not None:
        t.update(kwargs)
