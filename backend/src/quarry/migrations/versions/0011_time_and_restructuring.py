"""Story time on one axis and restructuring (SPEC §13.1, §13.6): the world's unit of time, a time and a mark on
chapters, time bounds and "outside time" on facts and relationships, experiments over a range of chapters (or adding
at a place), and the reviews made before chapters are retired.

Every existing experiment's `replaces_id` becomes a range of that one chapter; the column goes. Nothing else changes:
no chapter gets a time or a mark, no bound changes, so every world reads exactly as before.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-25 18:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def _bounds(table: str) -> None:
    op.add_column(table, sa.Column('from_time', sa.Numeric(), nullable=True))
    op.add_column(table, sa.Column('from_approx', sa.Boolean(), server_default='false', nullable=False))
    op.add_column(table, sa.Column('until_time', sa.Numeric(), nullable=True))
    op.add_column(table, sa.Column('until_approx', sa.Boolean(), server_default='false', nullable=False))
    op.add_column(table, sa.Column('outside_time', sa.Boolean(), server_default='false', nullable=False))
    op.create_check_constraint(f'ck_{table}_from', table, 'from_chapter_id IS NULL OR from_time IS NULL')
    op.create_check_constraint(f'ck_{table}_until', table, 'until_chapter_id IS NULL OR until_time IS NULL')


def upgrade() -> None:
    op.add_column('worlds', sa.Column('time_unit', sa.String(length=40), server_default='year', nullable=False))
    op.add_column('worlds', sa.Column('time_units', sa.String(length=40), server_default='years', nullable=False))

    op.add_column('chapters', sa.Column('time_at', sa.Numeric(), nullable=True))
    op.add_column('chapters', sa.Column('time_end', sa.Numeric(), nullable=True))
    op.add_column('chapters', sa.Column('time_label', sa.String(length=200), nullable=True))
    op.add_column('chapters', sa.Column('time_approx', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('chapters', sa.Column('outside_time', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('chapters', sa.Column('told_as', sa.String(length=20), nullable=True))
    op.create_check_constraint('ck_chapters_told_as', 'chapters', "told_as IN ('flashback', 'tale')")
    op.create_check_constraint('ck_chapters_outside_time', 'chapters', 'NOT outside_time OR time_at IS NULL')

    _bounds('facts')
    _bounds('relationships')

    op.add_column('items', sa.Column('insert_at_chapter_id', sa.UUID(), nullable=True))
    op.add_column('items', sa.Column('insert_side', sa.String(length=10), nullable=True))
    op.create_foreign_key('items_insert_at_chapter_id_fkey', 'items', 'chapters', ['insert_at_chapter_id'], ['id'],
                          ondelete='SET NULL')
    op.create_check_constraint('ck_items_insert_side', 'items', "insert_side IN ('before', 'after')")

    op.create_table('experiment_ranges',
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('chapter_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('item_id', 'chapter_id')
    )
    op.create_index(op.f('ix_experiment_ranges_chapter_id'), 'experiment_ranges', ['chapter_id'], unique=False)
    # each existing experiment's draft replaced one chapter: that is its range
    op.execute("INSERT INTO experiment_ranges (item_id, chapter_id, position) "
               "SELECT DISTINCT experiment_item_id, replaces_id, 0 FROM chapters "
               "WHERE experiment_item_id IS NOT NULL AND replaces_id IS NOT NULL "
               "ON CONFLICT DO NOTHING")
    op.drop_constraint('chapters_replaces_id_fkey', 'chapters', type_='foreignkey')
    op.drop_column('chapters', 'replaces_id')

    op.create_table('retire_reviews',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('chapter_ids', postgresql.ARRAY(sa.UUID()), nullable=False),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_retire_reviews_world_id'), 'retire_reviews', ['world_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_retire_reviews_world_id'), table_name='retire_reviews')
    op.drop_table('retire_reviews')
    op.add_column('chapters', sa.Column('replaces_id', sa.UUID(), nullable=True))
    op.create_foreign_key('chapters_replaces_id_fkey', 'chapters', 'chapters', ['replaces_id'], ['id'],
                          ondelete='SET NULL')
    op.execute("UPDATE chapters c SET replaces_id = r.chapter_id FROM experiment_ranges r "
               "WHERE c.experiment_item_id = r.item_id AND r.position = 0")
    op.drop_index(op.f('ix_experiment_ranges_chapter_id'), table_name='experiment_ranges')
    op.drop_table('experiment_ranges')
    op.drop_constraint('ck_items_insert_side', 'items', type_='check')
    op.drop_constraint('items_insert_at_chapter_id_fkey', 'items', type_='foreignkey')
    op.drop_column('items', 'insert_side')
    op.drop_column('items', 'insert_at_chapter_id')
    for table in ('facts', 'relationships'):
        op.drop_constraint(f'ck_{table}_until', table, type_='check')
        op.drop_constraint(f'ck_{table}_from', table, type_='check')
        for col in ('outside_time', 'until_approx', 'until_time', 'from_approx', 'from_time'):
            op.drop_column(table, col)
    op.drop_constraint('ck_chapters_outside_time', 'chapters', type_='check')
    op.drop_constraint('ck_chapters_told_as', 'chapters', type_='check')
    for col in ('told_as', 'outside_time', 'time_approx', 'time_label', 'time_end', 'time_at'):
        op.drop_column('chapters', col)
    op.drop_column('worlds', 'time_units')
    op.drop_column('worlds', 'time_unit')
