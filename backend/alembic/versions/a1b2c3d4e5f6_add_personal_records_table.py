"""add personal_records table

Revision ID: a1b2c3d4e5f6
Revises: fd36015012f2
Create Date: 2026-05-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'fd36015012f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'personal_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('exercise_name', sa.String(), nullable=False),
        sa.Column('max_weight_kg', sa.Float(), nullable=True),
        sa.Column('max_reps', sa.Integer(), nullable=True),
        sa.Column('achieved_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'exercise_name', name='uq_user_exercise_pr'),
    )
    op.create_index('ix_personal_records_id', 'personal_records', ['id'], unique=False)
    op.create_index('ix_personal_records_user_id', 'personal_records', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_personal_records_user_id', table_name='personal_records')
    op.drop_index('ix_personal_records_id', table_name='personal_records')
    op.drop_table('personal_records')
