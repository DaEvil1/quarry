"""Getting back in and checking (SPEC §14.4–§14.9): a world's premise, the note for next time in a journal entry, an
entry that is more than one kind, and each person's focus per world.

Existing data: no world has a premise, no journal entry has a note, every entry is only its own kind, and every
member's focus is "writing", the default, so every world opens and orders its nav as before.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-28 09:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('worlds', sa.Column('premise', sa.String(length=300), nullable=True))
    op.add_column('world_members', sa.Column('focus', sa.String(length=20), server_default='writing', nullable=False))
    op.create_check_constraint('ck_world_members_focus', 'world_members', "focus IN ('writing', 'planning')")
    op.add_column('entities', sa.Column('also_kinds', postgresql.ARRAY(sa.String(length=20)), server_default='{}',
                                        nullable=False))
    op.create_table('journal_notes',
    sa.Column('journal_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('cursor', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['journal_id'], ['journal.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('journal_id', 'user_id')
    )


def downgrade() -> None:
    op.drop_table('journal_notes')
    op.drop_column('entities', 'also_kinds')
    op.drop_constraint('ck_world_members_focus', 'world_members', type_='check')
    op.drop_column('world_members', 'focus')
    op.drop_column('worlds', 'premise')
