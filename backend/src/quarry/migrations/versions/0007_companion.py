"""The writing companion: resolutions of findings, and session notes for getting back into a chapter.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-22 04:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('resolutions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('rule', sa.String(length=40), nullable=False),
    sa.Column('key', sa.String(length=300), nullable=False),
    sa.Column('outcome', sa.String(length=20), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("outcome IN ('intentional', 'later', 'not_connected')", name='ck_resolutions_outcome'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('world_id', 'rule', 'key', name='uq_resolutions_world_rule_key')
    )
    op.create_index(op.f('ix_resolutions_world_id'), 'resolutions', ['world_id'], unique=False)
    op.create_table('session_notes',
    sa.Column('chapter_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('cursor', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('chapter_id', 'user_id')
    )


def downgrade() -> None:
    op.drop_table('session_notes')
    op.drop_index(op.f('ix_resolutions_world_id'), table_name='resolutions')
    op.drop_table('resolutions')
