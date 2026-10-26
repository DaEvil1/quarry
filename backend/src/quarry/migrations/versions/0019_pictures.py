"""Pictures (SPEC §17): pictures in a world, their files (kept in Postgres, not compressed again), and entries'
galleries.

Existing data: no pictures. Nothing else changes.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-26 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('pictures',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('format', sa.String(length=10), nullable=False),
    sa.Column('width', sa.Integer(), nullable=False),
    sa.Column('height', sa.Integer(), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("format IN ('jpeg', 'png', 'webp')", name='ck_pictures_format'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pictures_world_id'), 'pictures', ['world_id'], unique=False)
    op.create_table('picture_files',
    sa.Column('picture_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.CheckConstraint("kind IN ('full', 'view', 'thumb')", name='ck_picture_files_kind'),
    sa.ForeignKeyConstraint(['picture_id'], ['pictures.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('picture_id', 'kind')
    )
    # the files are JPEG, PNG and WebP: compressed already, so Postgres keeps them out of line without trying again
    op.execute("ALTER TABLE picture_files ALTER COLUMN data SET STORAGE EXTERNAL")
    op.create_table('entity_pictures',
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('picture_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('caption', sa.Text(), server_default='', nullable=False),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['picture_id'], ['pictures.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('entity_id', 'picture_id')
    )
    op.create_index(op.f('ix_entity_pictures_picture_id'), 'entity_pictures', ['picture_id'], unique=False)


def downgrade() -> None:
    op.drop_table('entity_pictures')
    op.drop_table('picture_files')
    op.drop_table('pictures')
