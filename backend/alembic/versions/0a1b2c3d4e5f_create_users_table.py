"""create users table

Revision ID: 0a1b2c3d4e5f
Revises:
Create Date: 2026-09-07

The users table had no migration. Every other table hangs a foreign key off it,
so `alembic upgrade head` failed on a fresh database at the very first step:

    (psycopg2.errors.UndefinedTable) relation "users" does not exist
    [SQL: CREATE TABLE workout_plans ( ... REFERENCES users (id) ... )]

It existed in deployed environments only because app/main.py calls
Base.metadata.create_all() at startup, which quietly created it outside the
migration chain. That masked the gap until CI first ran `alembic upgrade head`
against an empty database.

This becomes the new root of the chain, ahead of c733e5383e14. Databases that
already have the table — anything created by create_all() — are left untouched,
so this is safe to apply to existing deployments.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0a1b2c3d4e5f"
down_revision = None
branch_labels = None
depends_on = None


def _users_table_exists() -> bool:
    return "users" in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # Deployed databases already have this table courtesy of create_all(), and
    # re-creating it would fail the upgrade for exactly the environments that
    # most need the chain to become consistent.
    if _users_table_exists():
        return

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_index("ix_users_email", "users")
    op.drop_index("ix_users_id", "users")
    op.drop_table("users")
