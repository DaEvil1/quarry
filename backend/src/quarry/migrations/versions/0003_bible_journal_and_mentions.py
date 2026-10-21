"""The bible (entities), item links, the journal, mentions and "not a typo" words.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21 16:01:15.881762
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('entities',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('aliases', sa.ARRAY(sa.String(length=200)), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('character', 'place', 'term', 'faction', 'object', 'other')", name='ck_entities_kind'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_entities_world_id'), 'entities', ['world_id'], unique=False)
    op.create_index('uq_entities_world_name', 'entities', ['world_id', sa.text("lower(name)")], unique=True)
    op.create_table('name_ignores',
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('token', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('world_id', 'token')
    )
    op.create_table('journal',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=True),
    sa.Column('entry_date', sa.Date(), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_journal_project_id'), 'journal', ['project_id'], unique=False)
    op.create_index(op.f('ix_journal_world_id'), 'journal', ['world_id'], unique=False)
    op.create_table('mentions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('source_table', sa.String(length=20), nullable=False),
    sa.Column('source_id', sa.UUID(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('start', sa.Integer(), nullable=False),
    sa.Column('end', sa.Integer(), nullable=False),
    sa.Column('matched_text', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.CheckConstraint("kind IN ('exact', 'alias', 'near_miss')", name='ck_mentions_kind'),
    sa.CheckConstraint("source_table IN ('item', 'decision', 'entity', 'journal')", name='ck_mentions_source'),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mentions_entity_id'), 'mentions', ['entity_id'], unique=False)
    op.create_index('ix_mentions_source', 'mentions', ['source_table', 'source_id'], unique=False)
    op.create_index(op.f('ix_mentions_world_id'), 'mentions', ['world_id'], unique=False)
    op.create_table('item_links',
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('target_table', sa.String(length=20), nullable=False),
    sa.Column('target_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("target_table IN ('entity')", name='ck_item_links_target'),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('item_id', 'target_table', 'target_id')
    )
    op.create_index(op.f('ix_item_links_target_id'), 'item_links', ['target_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_item_links_target_id'), table_name='item_links')
    op.drop_table('item_links')
    op.drop_index(op.f('ix_mentions_world_id'), table_name='mentions')
    op.drop_index('ix_mentions_source', table_name='mentions')
    op.drop_index(op.f('ix_mentions_entity_id'), table_name='mentions')
    op.drop_table('mentions')
    op.drop_index(op.f('ix_journal_world_id'), table_name='journal')
    op.drop_index(op.f('ix_journal_project_id'), table_name='journal')
    op.drop_table('journal')
    op.drop_table('name_ignores')
    op.drop_index('uq_entities_world_name', table_name='entities')
    op.drop_index(op.f('ix_entities_world_id'), table_name='entities')
    op.drop_table('entities')
