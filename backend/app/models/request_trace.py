from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RequestTrace(Base):
    __tablename__ = "request_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    endpoint: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    total_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    retrieval_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rerank_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    retrieval_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    low_confidence: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    num_chunks_retrieved: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
