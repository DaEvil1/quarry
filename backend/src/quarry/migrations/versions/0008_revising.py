"""Revising and salvaging (SPEC §11): chapter summaries and statuses, the cuts bin, the "start" revision reason, and
the words added and removed by every existing revision.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-24 19:00:00
"""
import json
import uuid

from alembic import op
import sqlalchemy as sa

from quarry.wordhistory import word_changes


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

STARTING = ("raw", "rewritten", "polished")


def upgrade() -> None:
    op.create_table('chapter_statuses',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chapter_statuses_project_id'), 'chapter_statuses', ['project_id'], unique=False)
    op.add_column('chapters', sa.Column('summary', sa.String(length=300), server_default='', nullable=False))
    op.add_column('chapters', sa.Column('status_id', sa.UUID(), nullable=True))
    op.create_foreign_key('chapters_status_id_fkey', 'chapters', 'chapter_statuses', ['status_id'], ['id'],
                          ondelete='SET NULL')
    op.create_table('cuts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('chapter_id', sa.UUID(), nullable=True),
    sa.Column('chapter_title', sa.String(length=300), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('before', sa.Text(), nullable=False),
    sa.Column('after', sa.Text(), nullable=False),
    sa.Column('cut_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('put_back_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('put_back_to', sa.UUID(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['put_back_to'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cuts_chapter_id'), 'cuts', ['chapter_id'], unique=False)
    op.create_index(op.f('ix_cuts_project_id'), 'cuts', ['project_id'], unique=False)
    op.create_index(op.f('ix_cuts_world_id'), 'cuts', ['world_id'], unique=False)
    op.drop_constraint('ck_revisions_reason', 'revisions', type_='check')
    op.create_check_constraint('ck_revisions_reason', 'revisions',
                               "reason IN ('autosnap', 'checkpoint', 'state', 'restore', 'conflict', 'start')")

    bind = op.get_bind()
    # every project starts with the same three statuses
    for (project_id,) in bind.execute(sa.text("SELECT id FROM projects")).all():
        for i, label in enumerate(STARTING):
            bind.execute(sa.text("INSERT INTO chapter_statuses (id, project_id, label, position) VALUES (:id, :p, :l, :i)"),
                         {"id": uuid.uuid4(), "p": project_id, "l": label, "i": i})

    # word history for the revisions there are: each chapter's first one is its start (no words), conflict copies
    # are side copies (no words, and not the chapter's line), the rest are compared with the one before
    rows = bind.execute(sa.text(
        "SELECT id, doc_id, reason, body FROM revisions WHERE doc_table = 'chapter' ORDER BY doc_id, created_at, id"
    )).all()
    previous: dict = {}
    for rid, doc_id, reason, body in rows:
        if reason == "conflict":
            added = removed = 0
        elif doc_id not in previous:
            added = removed = 0
            previous[doc_id] = body
        else:
            added, removed = word_changes(previous[doc_id], body)
            previous[doc_id] = body
        bind.execute(sa.text("UPDATE revisions SET meta = meta || CAST(:m AS jsonb) WHERE id = :id"),
                     {"m": json.dumps({"added": added, "removed": removed}), "id": rid})


def downgrade() -> None:
    op.execute("DELETE FROM revisions WHERE reason = 'start'")
    op.drop_constraint('ck_revisions_reason', 'revisions', type_='check')
    op.create_check_constraint('ck_revisions_reason', 'revisions',
                               "reason IN ('autosnap', 'checkpoint', 'state', 'restore', 'conflict')")
    op.drop_index(op.f('ix_cuts_world_id'), table_name='cuts')
    op.drop_index(op.f('ix_cuts_project_id'), table_name='cuts')
    op.drop_index(op.f('ix_cuts_chapter_id'), table_name='cuts')
    op.drop_table('cuts')
    op.drop_constraint('chapters_status_id_fkey', 'chapters', type_='foreignkey')
    op.drop_column('chapters', 'status_id')
    op.drop_column('chapters', 'summary')
    op.drop_index(op.f('ix_chapter_statuses_project_id'), table_name='chapter_statuses')
    op.drop_table('chapter_statuses')
