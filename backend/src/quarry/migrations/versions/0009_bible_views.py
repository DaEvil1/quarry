"""More views of the bible (SPEC §12): a gap length per project, a level (world or project) and a gender per entry,
the per-label switches of fact_labels, and the "witnessed" relationship type for every existing world.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-24 23:00:00
"""
import uuid

from alembic import op
import sqlalchemy as sa


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

WITNESSED = {"witnessed", "witnessed by"}


def _fits(kind: str, want: str) -> bool:
    return kind in ("*", want)


def upgrade() -> None:
    op.add_column('projects', sa.Column('gap_chapters', sa.Integer(), server_default='5', nullable=False))
    op.add_column('entities', sa.Column('project_id', sa.UUID(), nullable=True))
    op.add_column('entities', sa.Column('gender', sa.String(length=20), nullable=True))
    op.create_index(op.f('ix_entities_project_id'), 'entities', ['project_id'], unique=False)
    op.create_foreign_key('entities_project_id_fkey', 'entities', 'projects', ['project_id'], ['id'], ondelete='SET NULL')
    op.create_check_constraint('ck_entities_gender', 'entities', "gender IN ('female', 'male', 'nonbinary')")
    op.create_table('fact_labels',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('several', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('expected', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('asked', sa.Boolean(), server_default='false', nullable=False),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fact_labels_world_id'), 'fact_labels', ['world_id'], unique=False)
    op.create_index('uq_fact_labels_world_kind_label', 'fact_labels', ['world_id', 'kind', sa.text('lower(label)')],
                    unique=True)

    # "witnessed" / "witnessed by" (character → event), at the end of each world's character–event types, unless the
    # world has a character–event type reading "witnessed" already (either way round, any capitals)
    bind = op.get_bind()
    types: dict = {}
    for wid, tid, a, b, label, reverse, position in bind.execute(sa.text(
            "SELECT world_id, id, a_kind, b_kind, label, reverse_label, position FROM relation_types")).all():
        types.setdefault(wid, []).append((tid, a, b, label, reverse, position))
    for (wid,) in bind.execute(sa.text("SELECT id FROM worlds")).all():
        rows = types.get(wid, [])
        has = any(
            ((_fits(a, "character") and _fits(b, "event")) or (_fits(a, "event") and _fits(b, "character")))
            and ({(label or "").strip().lower(), (reverse or "").strip().lower()} & WITNESSED)
            for _, a, b, label, reverse, _ in rows)
        if has:
            continue
        ce = [p for _, a, b, _, _, p in rows if a == "character" and b == "event"]
        if ce:
            position = max(ce) + 1
            bind.execute(sa.text("UPDATE relation_types SET position = position + 1 WHERE world_id = :w AND position >= :p"),
                         {"w": wid, "p": position})
        else:
            position = max((p for *_, p in rows), default=-1) + 1
        bind.execute(sa.text(
            "INSERT INTO relation_types (id, world_id, a_kind, b_kind, label, reverse_label, position) "
            "VALUES (:id, :w, 'character', 'event', 'witnessed', 'witnessed by', :p)"),
            {"id": uuid.uuid4(), "w": wid, "p": position})


def downgrade() -> None:
    op.execute("DELETE FROM relation_types t WHERE a_kind = 'character' AND b_kind = 'event' AND label = 'witnessed' "
               "AND NOT EXISTS (SELECT 1 FROM relationships r WHERE r.type_id = t.id)")
    op.drop_index('uq_fact_labels_world_kind_label', table_name='fact_labels')
    op.drop_index(op.f('ix_fact_labels_world_id'), table_name='fact_labels')
    op.drop_table('fact_labels')
    op.drop_constraint('ck_entities_gender', 'entities', type_='check')
    op.drop_constraint('entities_project_id_fkey', 'entities', type_='foreignkey')
    op.drop_index(op.f('ix_entities_project_id'), table_name='entities')
    op.drop_column('entities', 'gender')
    op.drop_column('entities', 'project_id')
    op.drop_column('projects', 'gap_chapters')
