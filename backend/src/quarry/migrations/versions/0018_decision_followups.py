"""Decisions with follow-ups (SPEC §16): a table of links from a decision to the planned facts, relationships and
tasks that carry it out.

Existing data: no decision has a follow-up, so every decision reads as settled, as before. Nothing else changes.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-25 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('decision_followups',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('decision_id', sa.UUID(), nullable=False),
    sa.Column('fact_id', sa.UUID(), nullable=True),
    sa.Column('relationship_id', sa.UUID(), nullable=True),
    sa.Column('item_id', sa.UUID(), nullable=True),
    sa.Column('what', sa.Text(), nullable=False),
    sa.Column('dropped_on', sa.Date(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('num_nonnulls(fact_id, relationship_id, item_id) <= 1', name='ck_decision_followups_one_row'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['decision_id'], ['decisions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['fact_id'], ['facts.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['relationship_id'], ['relationships.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('decision_id', 'fact_id', name='uq_decision_followups_fact'),
    sa.UniqueConstraint('decision_id', 'item_id', name='uq_decision_followups_item'),
    sa.UniqueConstraint('decision_id', 'relationship_id', name='uq_decision_followups_relationship')
    )
    for col in ('decision_id', 'fact_id', 'relationship_id', 'item_id'):
        op.create_index(op.f(f'ix_decision_followups_{col}'), 'decision_followups', [col], unique=False)


def downgrade() -> None:
    op.drop_table('decision_followups')
