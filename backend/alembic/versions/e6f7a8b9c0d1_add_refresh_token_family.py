"""add refresh token family lineage

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-07

Adds family_id + replaced_by to refresh_tokens so rotation can be made
atomic and replay can be distinguished from theft:

  family_id   — shared by every token descended from one login.  A replayed
                token that is outside the benign-race grace window revokes
                the whole family, cutting off an attacker holding a stolen
                copy along with the legitimate session.
  replaced_by — the token minted when this one was redeemed.  Its presence
                marks a redemption as legitimately completed, which is how a
                concurrent double-submit is told apart from a reuse attack.

Existing rows are backfilled one-family-per-row: each pre-existing token
becomes its own family root, so no historical session is retroactively
linked to another.
"""

from alembic import op
import sqlalchemy as sa

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("family_id", sa.String(36), nullable=True))
    op.add_column("refresh_tokens", sa.Column("replaced_by", sa.Integer(), nullable=True))

    # Backfill: every existing token becomes the root of its own family.
    # gen_random_uuid() is built into PostgreSQL 13+ (pgcrypto not required).
    op.execute("UPDATE refresh_tokens SET family_id = gen_random_uuid()::text WHERE family_id IS NULL")

    op.alter_column("refresh_tokens", "family_id", nullable=False)

    op.create_foreign_key(
        "fk_refresh_tokens_replaced_by",
        "refresh_tokens",
        "refresh_tokens",
        ["replaced_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_family_id", "refresh_tokens")
    op.drop_constraint("fk_refresh_tokens_replaced_by", "refresh_tokens", type_="foreignkey")
    op.drop_column("refresh_tokens", "replaced_by")
    op.drop_column("refresh_tokens", "family_id")
