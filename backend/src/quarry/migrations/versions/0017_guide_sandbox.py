"""The Guide (SPEC §15): a world can be a sandbox, a copy of the demo world made for one walkthrough.

Existing data: every world is not a sandbox. Nothing else changes.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-25 09:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('worlds', sa.Column('sandbox', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.execute("DELETE FROM worlds WHERE sandbox")
    op.drop_column('worlds', 'sandbox')
