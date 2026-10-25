"""Names shared by two entries (SPEC §14.10): a mention can be "ambiguous" (a shared name no choice line settles,
one row per claimant), and each world remembers which version of the matcher its mentions were worked out with.

Existing data: every world starts at version 0, so its mentions are worked out again once when Quarry starts (a few
hundred milliseconds per world). A bare first name two characters share, which matched nobody before, then shows as
ambiguous for both; an other name given to two entries, which went to whichever came first, becomes ambiguous until a
choice line in the text settles it. Nothing else changes.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-29 09:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_mentions_kind', 'mentions', type_='check')
    op.create_check_constraint('ck_mentions_kind', 'mentions', "kind IN ('exact', 'alias', 'near_miss', 'ambiguous')")
    op.add_column('worlds', sa.Column('mentions_version', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('worlds', 'mentions_version')
    op.execute("DELETE FROM mentions WHERE kind = 'ambiguous'")
    op.drop_constraint('ck_mentions_kind', 'mentions', type_='check')
    op.create_check_constraint('ck_mentions_kind', 'mentions', "kind IN ('exact', 'alias', 'near_miss')")
