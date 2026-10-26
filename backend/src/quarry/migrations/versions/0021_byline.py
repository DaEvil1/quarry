"""A byline (SPEC §19): one optional line under a project's title.

Existing data: no project has a byline. Nothing else changes.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-26 20:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('byline', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'byline')
