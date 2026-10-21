"""Items (sparks, questions, tasks) and the decisions log.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21 13:27:12.436001
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('items',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=True),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('closed_note', sa.Text(), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('source', sa.String(length=40), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('spark', 'question', 'task', 'experiment')", name='ck_items_kind'),
    sa.CheckConstraint("status IN ('open', 'accepted', 'rejected', 'harvested', 'deferred')", name='ck_items_status'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_items_project_id'), 'items', ['project_id'], unique=False)
    op.create_index(op.f('ix_items_world_id'), 'items', ['world_id'], unique=False)
    op.create_table('decisions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=True),
    sa.Column('decided_on', sa.Date(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_decisions_project_id'), 'decisions', ['project_id'], unique=False)
    op.create_index(op.f('ix_decisions_world_id'), 'decisions', ['world_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_decisions_world_id'), table_name='decisions')
    op.drop_index(op.f('ix_decisions_project_id'), table_name='decisions')
    op.drop_table('decisions')
    op.drop_index(op.f('ix_items_world_id'), table_name='items')
    op.drop_index(op.f('ix_items_project_id'), table_name='items')
    op.drop_table('items')
