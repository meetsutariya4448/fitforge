from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

from app.database import Base


class KBChunk(Base):
    __tablename__ = "kb_chunks"

    id = Column(Integer, primary_key=True, index=True)
    # SHA-256 hex of raw_content — idempotency key for ingestion
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    raw_content = Column(Text, nullable=False)
    contextualized_content = Column(Text, nullable=False)
    # "metadata" is a Python built-in; map via the column name string
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    # all-MiniLM-L6-v2 outputs 384-dimensional embeddings
    embedding = Column(Vector(384), nullable=False)
    # raw_content embedding — used in ablation study (contextual vs non-contextual)
    raw_embedding = Column(Vector(384), nullable=False)
    # Postgres GENERATED ALWAYS AS column — read-only from Python; never written
    search_vector = Column(TSVECTOR, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
