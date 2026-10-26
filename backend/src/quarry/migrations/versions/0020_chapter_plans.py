"""A chapter's plan (SPEC §18): a journal entry can be marked as a plan and linked to the chapters it is for.

Existing data: no entry is a plan and nothing is linked. Nothing else changes.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-26 18:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('journal', sa.Column('is_plan', sa.Boolean(), server_default='false', nullable=False))
    op.create_table('chapter_plans',
    sa.Column('chapter_id', sa.UUID(), nullable=False),
    sa.Column('journal_id', sa.UUID(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['journal_id'], ['journal.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('chapter_id', 'journal_id')
    )
    op.create_index(op.f('ix_chapter_plans_journal_id'), 'chapter_plans', ['journal_id'], unique=False)


def downgrade() -> None:
    op.drop_table('chapter_plans')
    op.drop_column('journal', 'is_plan')
