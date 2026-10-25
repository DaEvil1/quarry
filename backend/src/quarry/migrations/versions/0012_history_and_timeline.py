"""History and the Timeline (SPEC §13.2): when an event happens (in a chapter, a time, or outside time), an era's
colour, and the tellings recorded from the prose.

Nothing changes for existing data: every event starts "not placed yet" and no era has a colour until it is given one
(an event whose type is "era" takes the next colour not yet used when it becomes one). Existing "when" facts stay as
facts.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-26 09:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None

COLOURS = "era_colour IN ('amber', 'moss', 'teal', 'sky', 'indigo', 'plum', 'rose', 'rust')"


def upgrade() -> None:
    op.add_column('entities', sa.Column('time_at', sa.Numeric(), nullable=True))
    op.add_column('entities', sa.Column('time_end', sa.Numeric(), nullable=True))
    op.add_column('entities', sa.Column('time_label', sa.String(length=200), nullable=True))
    op.add_column('entities', sa.Column('time_approx', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('entities', sa.Column('outside_time', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('entities', sa.Column('time_chapter_id', sa.UUID(), nullable=True))
    op.add_column('entities', sa.Column('era_colour', sa.String(length=20), nullable=True))
    op.create_foreign_key('entities_time_chapter_id_fkey', 'entities', 'chapters', ['time_chapter_id'], ['id'],
                          ondelete='SET NULL')
    op.create_check_constraint('ck_entities_era_colour', 'entities', COLOURS)
    op.create_check_constraint('ck_entities_outside_time', 'entities', 'NOT outside_time OR time_at IS NULL')
    op.create_check_constraint('ck_entities_time_chapter', 'entities',
                               'time_chapter_id IS NULL OR (time_at IS NULL AND NOT outside_time)')
    op.create_table('tellings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('event_id', sa.UUID(), nullable=False),
    sa.Column('chapter_id', sa.UUID(), nullable=True),
    sa.Column('passage', sa.Text(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['event_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tellings_chapter_id'), 'tellings', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_tellings_event_id'), 'tellings', ['event_id'], unique=False)
    op.create_index(op.f('ix_tellings_world_id'), 'tellings', ['world_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tellings_world_id'), table_name='tellings')
    op.drop_index(op.f('ix_tellings_event_id'), table_name='tellings')
    op.drop_index(op.f('ix_tellings_chapter_id'), table_name='tellings')
    op.drop_table('tellings')
    op.drop_constraint('ck_entities_time_chapter', 'entities', type_='check')
    op.drop_constraint('ck_entities_outside_time', 'entities', type_='check')
    op.drop_constraint('ck_entities_era_colour', 'entities', type_='check')
    op.drop_constraint('entities_time_chapter_id_fkey', 'entities', type_='foreignkey')
    for col in ('era_colour', 'time_chapter_id', 'outside_time', 'time_approx', 'time_label', 'time_end', 'time_at'):
        op.drop_column('entities', col)
