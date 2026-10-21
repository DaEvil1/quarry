"""The manuscript: chapters, revisions and harvest notes; links and mentions can point at chapters.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21 16:41:25.294187
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('revisions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('doc_table', sa.String(length=20), nullable=False),
    sa.Column('doc_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('reason', sa.String(length=20), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("doc_table IN ('chapter')", name='ck_revisions_doc'),
    sa.CheckConstraint("reason IN ('autosnap', 'checkpoint', 'state', 'restore', 'conflict')", name='ck_revisions_reason'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_revisions_doc', 'revisions', ['doc_table', 'doc_id', 'created_at'], unique=False)
    op.create_table('chapters',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('pov_entity_id', sa.UUID(), nullable=True),
    sa.Column('experiment_item_id', sa.UUID(), nullable=True),
    sa.Column('replaces_id', sa.UUID(), nullable=True),
    sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("state IN ('current', 'experiment', 'retired')", name='ck_chapters_state'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['experiment_item_id'], ['items.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['pov_entity_id'], ['entities.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['replaces_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chapters_project_id'), 'chapters', ['project_id'], unique=False)
    op.create_table('harvest_notes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('chapter_id', sa.UUID(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_harvest_notes_chapter_id'), 'harvest_notes', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_harvest_notes_world_id'), 'harvest_notes', ['world_id'], unique=False)
    # check constraints are not compared by autogenerate: widened by hand
    op.drop_constraint('ck_item_links_target', 'item_links', type_='check')
    op.create_check_constraint('ck_item_links_target', 'item_links', "target_table IN ('entity', 'chapter')")
    op.drop_constraint('ck_mentions_source', 'mentions', type_='check')
    op.create_check_constraint('ck_mentions_source', 'mentions',
                               "source_table IN ('item', 'decision', 'entity', 'journal', 'chapter')")


def downgrade() -> None:
    op.execute("DELETE FROM mentions WHERE source_table = 'chapter'")
    op.execute("DELETE FROM item_links WHERE target_table = 'chapter'")
    op.drop_constraint('ck_mentions_source', 'mentions', type_='check')
    op.create_check_constraint('ck_mentions_source', 'mentions', "source_table IN ('item', 'decision', 'entity', 'journal')")
    op.drop_constraint('ck_item_links_target', 'item_links', type_='check')
    op.create_check_constraint('ck_item_links_target', 'item_links', "target_table IN ('entity')")
    op.drop_index(op.f('ix_harvest_notes_world_id'), table_name='harvest_notes')
    op.drop_index(op.f('ix_harvest_notes_chapter_id'), table_name='harvest_notes')
    op.drop_table('harvest_notes')
    op.drop_index(op.f('ix_chapters_project_id'), table_name='chapters')
    op.drop_table('chapters')
    op.drop_index('ix_revisions_doc', table_name='revisions')
    op.drop_table('revisions')
