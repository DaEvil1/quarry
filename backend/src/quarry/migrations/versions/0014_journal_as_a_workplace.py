"""The Journal as a workplace (SPEC §14.1–§14.3): journal entries get revisions like chapters; facts and
relationships can say where they were planned (a journal entry and its passage); an event's passage can be a note in
the Journal; an item can be linked to the journal entry it came from, and to the passage of a chapter or journal entry.

Nothing changes for existing data: no revisions are made (an entry gets its first one the first time it is saved
after the upgrade), every fact, relationship and telling keeps its standing and has no planned-in, and existing item
links have no passage.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-27 09:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_revisions_doc', 'revisions', type_='check')
    op.create_check_constraint('ck_revisions_doc', 'revisions', "doc_table IN ('chapter', 'journal')")
    for table in ('facts', 'relationships'):
        op.add_column(table, sa.Column('planned_in_journal_id', sa.UUID(), nullable=True))
        op.add_column(table, sa.Column('planned_evidence', sa.Text(), nullable=True))
        op.create_foreign_key(f'{table}_planned_in_journal_id_fkey', table, 'journal', ['planned_in_journal_id'],
                              ['id'], ondelete='SET NULL')
        op.create_index(op.f(f'ix_{table}_planned_in_journal_id'), table, ['planned_in_journal_id'], unique=False)
    op.add_column('tellings', sa.Column('journal_id', sa.UUID(), nullable=True))
    op.create_foreign_key('tellings_journal_id_fkey', 'tellings', 'journal', ['journal_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_tellings_journal_id'), 'tellings', ['journal_id'], unique=False)
    op.create_check_constraint('ck_tellings_source', 'tellings', 'chapter_id IS NULL OR journal_id IS NULL')
    op.drop_constraint('ck_item_links_target', 'item_links', type_='check')
    op.create_check_constraint('ck_item_links_target', 'item_links',
                               "target_table IN ('entity', 'chapter', 'journal')")
    op.add_column('item_links', sa.Column('passage', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('item_links', 'passage')
    op.execute("DELETE FROM item_links WHERE target_table = 'journal'")
    op.drop_constraint('ck_item_links_target', 'item_links', type_='check')
    op.create_check_constraint('ck_item_links_target', 'item_links', "target_table IN ('entity', 'chapter')")
    op.drop_constraint('ck_tellings_source', 'tellings', type_='check')
    op.drop_index(op.f('ix_tellings_journal_id'), table_name='tellings')
    op.drop_constraint('tellings_journal_id_fkey', 'tellings', type_='foreignkey')
    op.drop_column('tellings', 'journal_id')
    for table in ('relationships', 'facts'):
        op.drop_index(op.f(f'ix_{table}_planned_in_journal_id'), table_name=table)
        op.drop_constraint(f'{table}_planned_in_journal_id_fkey', table, type_='foreignkey')
        op.drop_column(table, 'planned_evidence')
        op.drop_column(table, 'planned_in_journal_id')
    op.execute("DELETE FROM revisions WHERE doc_table = 'journal'")
    op.drop_constraint('ck_revisions_doc', 'revisions', type_='check')
    op.create_check_constraint('ck_revisions_doc', 'revisions', "doc_table IN ('chapter')")
