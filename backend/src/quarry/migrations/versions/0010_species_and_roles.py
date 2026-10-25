"""Species, roles and more starting vocabulary (SPEC §13.3–§13.5): the ninth kind, a role on relationships of types
that have one, the per-role "one at a time" switch, and the new starting types for every existing world.

Each new type goes at the end of its pair (after the world's last type joining the same two kinds, else at the end of
the list), unless the world has a type for that pair reading the same already (either way round, any capitals), as
"witnessed" did in 0009. "Has a role" is switched on for every type labelled member of, leads, serves or works at.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-25 12:00:00
"""
import uuid

from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

OLD_KINDS = "kind IN ('character', 'place', 'faction', 'culture', 'event', 'object', 'term', 'other')"
NEW_KINDS = "kind IN ('character', 'place', 'faction', 'culture', 'species', 'event', 'object', 'term', 'other')"

# (a_kind, b_kind, label, reverse), in the order they are added
NEW_TYPES = [
    ("character", "character", "possesses", "possessed by"),
    ("character", "character", "ancestor of", "descendant of"),
    ("character", "species", "is a", "includes"),
    ("character", "species", "appears as", "the guise of"),
    ("place", "place", "north of", "south of"),
    ("place", "place", "east of", "west of"),
    ("species", "species", "descended from", "ancestor of"),
    ("species", "species", "related to", None),
    ("species", "species", "preys on", "prey of"),
    ("species", "place", "native to", "home of"),
    ("culture", "species", "culture of", "has culture"),
    ("faction", "species", "made up of", "makes up"),
]
HAS_ROLE = ("member of", "leads", "serves", "works at")


def _fits(kind: str, side: str) -> bool:
    return side == "*" or side == kind


def _words(label, reverse) -> set:  # type: ignore[no-untyped-def]
    return {" ".join(x.split()).lower() for x in (label, reverse or "") if x and x.strip()}


def _reads_same(a, b) -> bool:  # type: ignore[no-untyped-def]
    same_way = _fits(a[0], b[0]) and _fits(a[1], b[1]) or _fits(b[0], a[0]) and _fits(b[1], a[1])
    other_way = _fits(a[0], b[1]) and _fits(a[1], b[0]) or _fits(b[1], a[0]) and _fits(b[0], a[1])
    return (same_way or other_way) and bool(_words(a[2], a[3]) & _words(b[2], b[3]))


def upgrade() -> None:
    op.drop_constraint('ck_entities_kind', 'entities', type_='check')
    op.create_check_constraint('ck_entities_kind', 'entities', NEW_KINDS)
    op.add_column('relation_types', sa.Column('has_role', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('relationships', sa.Column('role', sa.String(length=100), nullable=True))
    op.create_table('roles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(length=100), nullable=False),
    sa.Column('one_at_a_time', sa.Boolean(), server_default='false', nullable=False),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_roles_world_id'), 'roles', ['world_id'], unique=False)
    op.create_index('uq_roles_world_role', 'roles', ['world_id', sa.text('lower(role)')], unique=True)

    bind = op.get_bind()
    bind.execute(sa.text("UPDATE relation_types SET has_role = true WHERE lower(trim(label)) IN :labels")
                 .bindparams(sa.bindparam("labels", expanding=True)), {"labels": list(HAS_ROLE)})
    types: dict = {}
    for wid, a, b, label, reverse, position in bind.execute(sa.text(
            "SELECT world_id, a_kind, b_kind, label, reverse_label, position FROM relation_types")).all():
        types.setdefault(wid, []).append([a, b, label, reverse, position])
    for (wid,) in bind.execute(sa.text("SELECT id FROM worlds")).all():
        rows = types.get(wid, [])
        for t in NEW_TYPES:
            if any(_reads_same((a, b, label, reverse), t) for a, b, label, reverse, _ in rows):
                continue
            pair = [p for a, b, _, _, p in rows if (a, b) == (t[0], t[1])]
            if pair:
                position = max(pair) + 1
                bind.execute(sa.text("UPDATE relation_types SET position = position + 1 "
                                     "WHERE world_id = :w AND position >= :p"), {"w": wid, "p": position})
                for r in rows:
                    if r[4] >= position:
                        r[4] += 1
            else:
                position = max((r[4] for r in rows), default=-1) + 1
            bind.execute(sa.text(
                "INSERT INTO relation_types (id, world_id, a_kind, b_kind, label, reverse_label, position, has_role) "
                "VALUES (:id, :w, :a, :b, :l, :r, :p, false)"),
                {"id": uuid.uuid4(), "w": wid, "a": t[0], "b": t[1], "l": t[2], "r": t[3], "p": position})
            rows.append([*t, position])


def downgrade() -> None:
    # the new types go where nothing uses them; species entries become "other"
    for a, b, label, _ in NEW_TYPES:
        op.execute(sa.text("DELETE FROM relation_types t WHERE a_kind = :a AND b_kind = :b AND label = :l "
                           "AND NOT EXISTS (SELECT 1 FROM relationships r WHERE r.type_id = t.id)")
                   .bindparams(a=a, b=b, l=label))
    op.execute("UPDATE entities SET kind = 'other' WHERE kind = 'species'")
    op.drop_index('uq_roles_world_role', table_name='roles')
    op.drop_index(op.f('ix_roles_world_id'), table_name='roles')
    op.drop_table('roles')
    op.drop_column('relationships', 'role')
    op.drop_column('relation_types', 'has_role')
    op.drop_constraint('ck_entities_kind', 'entities', type_='check')
    op.create_check_constraint('ck_entities_kind', 'entities', OLD_KINDS)
