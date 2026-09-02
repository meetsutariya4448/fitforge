from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    eval_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    retrieval_config: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    n_queries: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Retrieval metrics
    recall_at_5: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision_at_5: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mrr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Generation / judge metrics
    faithfulness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    answer_relevancy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Agent metrics
    agent_rejection_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    refinement_improvement_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Cost / latency
    avg_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p50_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p95_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_prompt_tokens: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_completion_tokens: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_results_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
