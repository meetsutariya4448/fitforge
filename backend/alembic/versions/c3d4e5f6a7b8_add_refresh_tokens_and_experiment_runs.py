"""add refresh_tokens and experiment_runs

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-16

refresh_tokens — persistent server-side sessions for rotating refresh-token auth.
    Stores a SHA-256 hash of the raw token (never the token itself).
    On each /auth/refresh call the old row is revoked and a new one is inserted.

experiment_runs — time-series log of eval runs, one row per execution of
    run_retrieval_eval.py, run_generation_eval.py, or eval_agent.py.
    Lets you compare prompt/model/config changes over time without reading raw JSONs.
"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # SHA-256 hex digest of the raw token string — 64 hex chars.
        # The raw token is never stored; only its hash is kept here.
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("device_info", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
    )
    op.create_index("ix_refresh_tokens_id", "refresh_tokens", ["id"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "experiment_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # What kind of eval: "retrieval", "generation", "agent"
        sa.Column("eval_type", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        # JSON blob: {"mode": "hybrid", "k": 5, "rerank": false, ...}
        sa.Column("retrieval_config", sa.JSON(), nullable=True),
        sa.Column("n_queries", sa.Integer(), nullable=True),
        # Retrieval metrics
        sa.Column("recall_at_5", sa.Float(), nullable=True),
        sa.Column("precision_at_5", sa.Float(), nullable=True),
        sa.Column("mrr", sa.Float(), nullable=True),
        # Generation / judge metrics
        sa.Column("faithfulness", sa.Float(), nullable=True),
        sa.Column("answer_relevancy", sa.Float(), nullable=True),
        # Agent metrics
        sa.Column("agent_rejection_rate", sa.Float(), nullable=True),
        sa.Column("refinement_improvement_rate", sa.Float(), nullable=True),
        # Cost / latency
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("p50_latency_ms", sa.Float(), nullable=True),
        sa.Column("p95_latency_ms", sa.Float(), nullable=True),
        sa.Column("avg_prompt_tokens", sa.Float(), nullable=True),
        sa.Column("avg_completion_tokens", sa.Float(), nullable=True),
        sa.Column("avg_cost_usd", sa.Float(), nullable=True),
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
        # Free-form notes and pointer to the raw .jsonl output file
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_results_path", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiment_runs_id", "experiment_runs", ["id"])
    op.create_index("ix_experiment_runs_eval_type", "experiment_runs", ["eval_type"])


def downgrade() -> None:
    op.drop_index("ix_experiment_runs_eval_type", "experiment_runs")
    op.drop_index("ix_experiment_runs_id", "experiment_runs")
    op.drop_table("experiment_runs")
    op.drop_index("ix_refresh_tokens_user_id", "refresh_tokens")
    op.drop_index("ix_refresh_tokens_id", "refresh_tokens")
    op.drop_table("refresh_tokens")
