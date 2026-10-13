"""Store timed exercises as duration, not repetitions.

Revision ID: f7a4d8c3e901
Revises: e6f7a8b9c0d1
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a4d8c3e901"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("exercise_logs", "reps_completed", existing_type=sa.Integer(), nullable=True)
    op.add_column("exercise_logs", sa.Column("duration_seconds", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_exercise_logs_one_measure",
        "exercise_logs",
        "(reps_completed IS NOT NULL AND duration_seconds IS NULL) OR "
        "(reps_completed IS NULL AND duration_seconds IS NOT NULL)",
    )


def downgrade():
    if op.get_bind().execute(sa.text("SELECT 1 FROM exercise_logs WHERE reps_completed IS NULL LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade while timed exercise logs exist; export or migrate them first")
    op.drop_constraint("ck_exercise_logs_one_measure", "exercise_logs", type_="check")
    op.drop_column("exercise_logs", "duration_seconds")
    op.alter_column("exercise_logs", "reps_completed", existing_type=sa.Integer(), nullable=False)
