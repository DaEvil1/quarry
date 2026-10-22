"""Presence: where an entry is in a chapter ("is at").

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-22 03:20:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('presence',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('place_id', sa.UUID(), nullable=False),
    sa.Column('chapter_id', sa.UUID(), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['place_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entity_id', 'chapter_id', name='uq_presence_entity_chapter')
    )
    op.create_index(op.f('ix_presence_chapter_id'), 'presence', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_presence_world_id'), 'presence', ['world_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_presence_world_id'), table_name='presence')
    op.drop_index(op.f('ix_presence_chapter_id'), table_name='presence')
    op.drop_table('presence')
