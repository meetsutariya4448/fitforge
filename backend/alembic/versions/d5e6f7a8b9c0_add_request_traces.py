"""add request_traces

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-08-16

Per-request AI pipeline traces written by HTTP middleware after each
/generate or /generate-agent call.  Enables p50/p95 latency breakdowns
by retrieval mode from real traffic, not synthetic evals.
"""

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "request_traces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trace_id", sa.String(36), nullable=False),  # UUID string
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("endpoint", sa.String(100), nullable=True),
        sa.Column("method", sa.String(10), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("total_ms", sa.Float(), nullable=True),
        sa.Column("retrieval_ms", sa.Float(), nullable=True),
        sa.Column("rerank_ms", sa.Float(), nullable=True),
        sa.Column("llm_ms", sa.Float(), nullable=True),
        sa.Column("retrieval_mode", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("low_confidence", sa.Boolean(), nullable=True),
        sa.Column("num_chunks_retrieved", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_request_traces_id", "request_traces", ["id"])
    op.create_index("ix_request_traces_user_id", "request_traces", ["user_id"])
    op.create_index("ix_request_traces_endpoint", "request_traces", ["endpoint"])
    op.create_index("ix_request_traces_created_at", "request_traces", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_request_traces_created_at", "request_traces")
    op.drop_index("ix_request_traces_endpoint", "request_traces")
    op.drop_index("ix_request_traces_user_id", "request_traces")
    op.drop_index("ix_request_traces_id", "request_traces")
    op.drop_table("request_traces")
