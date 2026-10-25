"""Labels and values (docs/SPEC.md §12.6): the world's fact labels per kind with their values, renaming and merging
labels and values across the world (with Undo), and the per-label switches: several values, expected, and whether the
"expect it?" prompt was shown. Labels and values aren't stored on their own; they are read from the facts."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Entity, Fact, FactLabel, RelationType, Relationship, Resolution, Role, User, World
from .deps import current_user
from .world import KINDS, norm
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

Kind = Literal["character", "place", "faction", "culture", "species", "event", "object", "term", "other"]
PLURAL = {"character": "characters", "place": "places", "faction": "factions", "culture": "cultures",
          "species": "species", "event": "events", "object": "objects", "term": "terms", "other": "other entries"}


def label_rows(db: Session, world: World) -> dict[tuple[str, str], FactLabel]:
    """The world's switch rows, by (kind, label as compared)."""
    return {(r.kind, norm(r.label)): r for r in db.scalars(select(FactLabel).where(FactLabel.world_id == world.id))}


def several_labels(db: Session, world: World) -> set[tuple[str, str]]:
    """(kind, label) pairs whose label holds several values at once."""
    return {k for k, r in label_rows(db, world).items() if r.several}


def _ref(e: Entity) -> dict:
    return {"id": str(e.id), "name": e.name, "kind": e.kind}


def role_rows(db: Session, world: World) -> dict[str, Role]:
    """The world's role switches, by role as compared."""
    return {norm(r.role): r for r in db.scalars(select(Role).where(Role.world_id == world.id))}


def one_at_a_time_roles(db: Session, world: World) -> set[str]:
    """Roles (as compared) that only one may hold in a group at a time."""
    return {k for k, r in role_rows(db, world).items() if r.one_at_a_time}


def roles_page(db: Session, world: World) -> list[dict]:
    """The world's roles (docs/SPEC.md §13.4): each with how many relationships carry it, the types and groups it is
    used in, and its switch; a role switched on that nothing uses any more is listed too."""
    rows = role_rows(db, world)
    spelling: dict[str, Counter] = defaultdict(Counter)
    groups: dict[str, set[uuid.UUID]] = defaultdict(set)
    types: dict[str, set[str]] = defaultdict(set)
    labels = {t.id: t.label for t in db.scalars(select(RelationType).where(RelationType.world_id == world.id))}
    for r in db.scalars(select(Relationship).where(Relationship.world_id == world.id, Relationship.role.is_not(None))
                        .order_by(Relationship.created_at)):
        key = norm(r.role or "")
        spelling[key][r.role] += 1
        groups[key].add(r.b_id)
        types[key].add(labels.get(r.type_id, ""))
    names = {e.id: e for e in db.scalars(select(Entity).where(Entity.id.in_({g for gs in groups.values() for g in gs})))}
    out = []
    for key in set(spelling) | set(rows):
        row = rows.get(key)
        out.append({"role": spelling[key].most_common(1)[0][0] if spelling.get(key) else (row.role if row else key),
                    "count": sum(spelling[key].values()), "one_at_a_time": bool(row and row.one_at_a_time),
                    "types": sorted(types.get(key, ())),
                    "groups": [_ref(names[g]) for g in sorted(groups.get(key, ()), key=lambda g: names[g].name.lower())
                               if g in names]})
    out.sort(key=lambda x: (-x["count"], x["role"].lower()))
    return out


@router.get("/labels")
def list_labels(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Per kind: how many entries it has, and its labels by how many entries have them, each with its values (with
    counts and the entries that have each), its switches, and for an expected label the entries without it."""
    world, _ = member_world(db, user, slug)
    entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.world_id == world.id)
                                            .order_by(func.lower(Entity.name)))}
    rows = label_rows(db, world)
    resolved = {r.key for r in db.scalars(select(Resolution).where(Resolution.world_id == world.id,
                                                                   Resolution.rule == "missing_label",
                                                                   Resolution.outcome == "intentional"))}
    spelling: dict[tuple[str, str], Counter] = defaultdict(Counter)
    has: dict[tuple[str, str], set[uuid.UUID]] = defaultdict(set)
    value_spelling: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    value_has: dict[tuple[str, str, str], set[uuid.UUID]] = defaultdict(set)
    for f in db.scalars(select(Fact).where(Fact.world_id == world.id).order_by(Fact.created_at)):
        e = entities.get(f.entity_id)
        if e is None:
            continue
        key = (e.kind, norm(f.label))
        spelling[key][f.label] += 1
        has[key].add(e.id)
        if f.value.strip():
            vkey = (*key, norm(f.value))
            value_spelling[vkey][f.value.strip()] += 1
            value_has[vkey].add(e.id)
    total = Counter(e.kind for e in entities.values())
    out = []
    for kind in KINDS:
        keys = {k for k in has if k[0] == kind} | {k for k in rows if k[0] == kind}
        if not keys and not total.get(kind):
            continue
        labels = []
        for key in keys:
            row = rows.get(key)
            name = spelling[key].most_common(1)[0][0] if spelling.get(key) else (row.label if row else key[1])
            values = [{"value": value_spelling[vk].most_common(1)[0][0], "count": len(ids),
                       "entries": [_ref(entities[i]) for i in sorted(ids, key=lambda i: entities[i].name.lower())]}
                      for vk, ids in value_has.items() if vk[:2] == key]
            values.sort(key=lambda v: (-v["count"], v["value"].lower()))
            item = {"label": name, "count": len(has.get(key, ())), "values": values,
                    "several": bool(row and row.several), "expected": bool(row and row.expected),
                    "asked": bool(row and row.asked), "without": []}
            if item["expected"]:
                item["without"] = [{**_ref(e), "resolved": f"{e.id}:{key[1]}" in resolved}
                                   for e in entities.values() if e.kind == kind and e.id not in has.get(key, ())]
            labels.append(item)
        labels.sort(key=lambda x: (-x["count"], x["label"].lower()))
        out.append({"kind": kind, "total": total.get(kind, 0), "labels": labels})
    return {"kinds": out, "roles": roles_page(db, world)}


# renaming and merging --------------------------------------------------------------------------------------------


class RenameIn(BaseModel):
    kind: Kind
    old: str = Field(min_length=1, max_length=100)
    new: str = Field(min_length=1, max_length=100)
    # extend a label's rename to every other kind that uses it
    everywhere: bool = False


class ValueRenameIn(BaseModel):
    kind: Kind
    label: str = Field(min_length=1, max_length=100)
    old: str = Field(min_length=1, max_length=5000)
    new: str = Field(min_length=1, max_length=5000)


class Change(BaseModel):
    id: uuid.UUID
    field: Literal["label", "value"]
    before: str
    after: str
    # the fact's version after the change: Undo leaves a fact that changed since
    version: int


class RowMove(BaseModel):
    kind: str
    before: str
    after: str
    merged: bool


class UndoIn(BaseModel):
    changes: list[Change] = Field(max_length=100_000)
    rows: list[RowMove] = Field(default_factory=list)


def _facts_of(db: Session, world: World, kinds: set[str], label: str) -> list[Fact]:
    key = norm(label)
    rows = db.execute(select(Fact, Entity.kind).join(Entity, Entity.id == Fact.entity_id)
                      .where(Fact.world_id == world.id, Entity.kind.in_(kinds)).order_by(Fact.created_at)).all()
    return [f for f, _ in rows if norm(f.label) == key]


def _summary(changes: list[dict], facts: list[Fact], kinds: set[str]) -> str:
    """"Changed 5 facts on 5 events": what a rename did, for its Undo line."""
    n, entries = len(changes), len({f.entity_id for f in facts})
    if len(kinds) == 1:
        kind = next(iter(kinds))
        what = PLURAL[kind] if entries != 1 else ("other entry" if kind == "other" else kind)
    else:
        what = "entries" if entries != 1 else "entry"
    return f"Changed {n} fact{'' if n == 1 else 's'} on {entries} {what}."


@router.post("/labels/rename")
def rename_label(slug: str, body: RenameIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Rename a label on every fact of a kind (or of every kind using it). Renaming it to a label the kind already
    uses merges the two; an entry that had both keeps both facts. The label's switches go with it."""
    world, _ = member_world(db, user, slug)
    new = " ".join(body.new.split())
    if not new:
        raise HTTPException(422, "Give the label a name.")
    if body.everywhere:
        kinds = {k for k, in db.execute(select(Entity.kind).join(Fact, Fact.entity_id == Entity.id)
                                        .where(Fact.world_id == world.id).distinct())}
        kinds = {k for k in kinds if _facts_of(db, world, {k}, body.old)} | {body.kind}
    else:
        kinds = {body.kind}
    facts = _facts_of(db, world, kinds, body.old)
    changes = []
    for f in facts:
        if f.label == new:
            continue
        changes.append({"id": str(f.id), "field": "label", "before": f.label, "after": new, "version": f.version + 1})
        f.label = new
        f.version += 1
        f.updated_by = user.id
    rows = label_rows(db, world)
    moves = []
    for kind in kinds:
        old_row = rows.get((kind, norm(body.old)))
        if old_row is None:
            continue
        new_row = rows.get((kind, norm(new))) if norm(new) != norm(body.old) else None
        if new_row is not None:
            new_row.several |= old_row.several
            new_row.expected |= old_row.expected
            new_row.asked |= old_row.asked
            db.delete(old_row)
            moves.append({"kind": kind, "before": old_row.label, "after": new, "merged": True})
        else:
            moves.append({"kind": kind, "before": old_row.label, "after": new, "merged": False})
            old_row.label = new
    db.commit()
    changed = {c["id"] for c in changes}
    return {"changes": changes, "rows": moves, "message": _summary(changes, [f for f in facts if str(f.id) in changed],
                                                                   kinds)}


@router.post("/labels/values/rename")
def rename_value(slug: str, body: ValueRenameIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    """Rename or merge a value within a label and kind: every fact with that value (whatever the capitals) gets the
    new spelling; the same value under other kinds is left alone."""
    world, _ = member_world(db, user, slug)
    new = body.new.strip()
    if not new:
        raise HTTPException(422, "Give the value.")
    key = norm(body.old)
    facts = [f for f in _facts_of(db, world, {body.kind}, body.label) if norm(f.value) == key]
    changes = []
    for f in facts:
        if f.value == new:
            continue
        changes.append({"id": str(f.id), "field": "value", "before": f.value, "after": new, "version": f.version + 1})
        f.value = new
        f.version += 1
        f.updated_by = user.id
    db.commit()
    changed = [f for f in facts if str(f.id) in {c["id"] for c in changes}]
    return {"changes": changes, "rows": [], "message": _summary(changes, changed, {body.kind})}


@router.post("/labels/undo")
def undo_rename(slug: str, body: UndoIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Put back the old label or value on each fact that hasn't changed since the rename (its version and its text
    are still the rename's), and move the label's switches back."""
    world, _ = member_world(db, user, slug)
    restored = skipped = 0
    facts = {f.id: f for f in db.scalars(select(Fact).where(Fact.world_id == world.id,
                                                            Fact.id.in_([c.id for c in body.changes])))}
    for c in body.changes:
        f = facts.get(c.id)
        if f is None or f.version != c.version or getattr(f, c.field) != c.after:
            skipped += 1
            continue
        setattr(f, c.field, c.before)
        f.version += 1
        f.updated_by = user.id
        restored += 1
    rows = label_rows(db, world)
    for m in body.rows:
        row = rows.get((m.kind, norm(m.after)))
        if m.merged or row is None or (m.kind, norm(m.before)) in rows:
            continue
        row.label = m.before
    db.commit()
    return {"restored": restored, "skipped": skipped}


# roles: renaming and merging across the world, with Undo, and the "one at a time" switch -------------------------


class RoleRenameIn(BaseModel):
    old: str = Field(min_length=1, max_length=100)
    new: str = Field(min_length=1, max_length=100)


class RoleChange(BaseModel):
    id: uuid.UUID
    before: str
    after: str
    version: int


class RoleUndoIn(BaseModel):
    changes: list[RoleChange] = Field(max_length=100_000)
    # the switch row's spelling before the rename, when it was renamed rather than merged
    row_before: str | None = None
    row_after: str | None = None


@router.post("/labels/roles/rename")
def rename_role(slug: str, body: RoleRenameIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Rename a role on every relationship that has it (whatever the capitals); renaming it to a role in use merges
    the two. Its switch goes with it."""
    world, _ = member_world(db, user, slug)
    new = " ".join(body.new.split())
    if not new:
        raise HTTPException(422, "Give the role.")
    key = norm(body.old)
    changes = []
    rels = [r for r in db.scalars(select(Relationship).where(Relationship.world_id == world.id,
                                                             Relationship.role.is_not(None)))
            if norm(r.role or "") == key]
    for r in rels:
        if r.role == new:
            continue
        changes.append({"id": str(r.id), "before": r.role, "after": new, "version": r.version + 1})
        r.role = new
        r.version += 1
        r.updated_by = user.id
    rows = role_rows(db, world)
    old_row, new_row = rows.get(key), rows.get(norm(new)) if norm(new) != key else None
    row_before = row_after = None
    if old_row is not None:
        if new_row is not None:
            new_row.one_at_a_time |= old_row.one_at_a_time
            db.delete(old_row)
        else:
            row_before, row_after = old_row.role, new
            old_row.role = new
    db.commit()
    n = len(changes)
    return {"changes": changes, "row_before": row_before, "row_after": row_after,
            "message": f"Changed {n} relationship{'' if n == 1 else 's'}."}


@router.post("/labels/roles/undo")
def undo_role_rename(slug: str, body: RoleUndoIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> dict:
    """Put back the old role on each relationship that hasn't changed since the rename."""
    world, _ = member_world(db, user, slug)
    restored = skipped = 0
    rels = {r.id: r for r in db.scalars(select(Relationship).where(Relationship.world_id == world.id,
                                                                   Relationship.id.in_([c.id for c in body.changes])))}
    for c in body.changes:
        r = rels.get(c.id)
        if r is None or r.version != c.version or r.role != c.after:
            skipped += 1
            continue
        r.role = c.before
        r.version += 1
        r.updated_by = user.id
        restored += 1
    if body.row_before and body.row_after:
        rows = role_rows(db, world)
        row = rows.get(norm(body.row_after))
        if row is not None and norm(body.row_before) not in rows:
            row.role = body.row_before
    db.commit()
    return {"restored": restored, "skipped": skipped}


class RoleSwitchIn(BaseModel):
    one_at_a_time: bool


@router.put("/labels/roles/{role}")
def set_role_switch(slug: str, role: str, body: RoleSwitchIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)) -> dict:
    """Set whether only one may hold a role in a group at a time (across the world, whatever the capitals)."""
    world, _ = member_world(db, user, slug)
    role = " ".join(role.split())
    if not role or len(role) > 100:
        raise HTTPException(422, "Give the role.")
    row = db.scalar(select(Role).where(Role.world_id == world.id, func.lower(Role.role) == norm(role)))
    if row is None:
        row = Role(world_id=world.id, role=role, one_at_a_time=False)
        db.add(row)
    row.one_at_a_time = body.one_at_a_time
    db.commit()
    return {"role": row.role, "one_at_a_time": row.one_at_a_time}


# the switches -----------------------------------------------------------------------------------------------------


class SwitchesIn(BaseModel):
    several: bool | None = None
    expected: bool | None = None
    asked: bool | None = None


@router.put("/labels/{kind}/{label}")
def set_switches(slug: str, kind: Kind, label: str, body: SwitchesIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    """Set a label's switches for a kind: several values, expected on every entry, the prompt shown."""
    world, _ = member_world(db, user, slug)
    label = " ".join(label.split())
    if not label or len(label) > 100:
        raise HTTPException(422, "Give the label.")
    row = db.scalar(select(FactLabel).where(FactLabel.world_id == world.id, FactLabel.kind == kind,
                                            func.lower(FactLabel.label) == norm(label)))
    if row is None:
        row = FactLabel(world_id=world.id, kind=kind, label=label, several=False, expected=False, asked=False)
        db.add(row)
    for field in ("several", "expected", "asked"):
        value = getattr(body, field)
        if value is not None:
            setattr(row, field, value)
    if body.expected:
        row.asked = True
    db.commit()
    return {"kind": row.kind, "label": row.label, "several": row.several, "expected": row.expected,
            "asked": row.asked}
