"""The world model: facts about entries, relationship types and relationships, and the cards the editor uses to
colour names and show them on hover (docs/WORLD-MODEL.md §2–§5)."""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import first_name_aliases
from ..models import Chapter, Entity, Fact, FactLabel, JournalEntry, Project, RelationType, Relationship, User, World
from ..vocabulary import HAS_ROLE_LABELS, STARTING_TYPES, SUGGESTED_FACTS, SUGGESTED_VALUES
from .deps import current_user
from .storytime import check_span
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

Standing = Literal["canon", "planned", "rumour"]
KINDS = ("character", "place", "faction", "culture", "species", "event", "object", "term", "other")


def seed_relation_types(db: Session, world_id: uuid.UUID) -> None:
    """A new world gets the starting vocabulary."""
    for i, (a, b, label, reverse) in enumerate(STARTING_TYPES):
        db.add(RelationType(world_id=world_id, a_kind=a, b_kind=b, label=label, reverse_label=reverse, position=i,
                            has_role=has_role_label(label)))


def has_role_label(label: str) -> bool:
    """Types that start with "has a role" on: member of, leads, serves, works at (any capitals)."""
    return " ".join(label.split()).lower() in HAS_ROLE_LABELS


def clean_role(role: str | None) -> str | None:
    return " ".join((role or "").split())[:100] or None


def _fits(kind: str, side: str) -> bool:
    return side == "*" or side == kind


# shapes --------------------------------------------------------------------------------------------------------


class FactIn(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    value: str = Field(default="", max_length=5000)
    standing: Standing = "canon"
    evidence: str | None = Field(default=None, max_length=5000)
    note: str | None = Field(default=None, max_length=5000)
    established_in_chapter_id: uuid.UUID | None = None
    from_chapter_id: uuid.UUID | None = None
    until_chapter_id: uuid.UUID | None = None
    # a bound can be an in-world time instead (docs/SPEC.md §13.1.5); outside time has no bounds (§13.1.8)
    from_time: float | None = None
    from_approx: bool | None = None
    until_time: float | None = None
    until_approx: bool | None = None
    outside_time: bool | None = None
    # where it was planned (docs/SPEC.md §14.1.2): a journal entry and its passage
    planned_in_journal_id: uuid.UUID | None = None
    planned_evidence: str | None = Field(default=None, max_length=5000)
    # "Make it canon here": the planned row this records in the book, instead of adding a second one
    make_canon: uuid.UUID | None = None


class FactUpdate(BaseModel):
    base_version: int
    label: str | None = Field(default=None, min_length=1, max_length=100)
    value: str | None = Field(default=None, max_length=5000)
    standing: Standing | None = None
    evidence: str | None = Field(default=None, max_length=5000)
    note: str | None = Field(default=None, max_length=5000)
    established_in_chapter_id: uuid.UUID | None = None
    from_chapter_id: uuid.UUID | None = None
    until_chapter_id: uuid.UUID | None = None
    # a bound can be an in-world time instead (docs/SPEC.md §13.1.5); outside time has no bounds (§13.1.8)
    from_time: float | None = None
    from_approx: bool | None = None
    until_time: float | None = None
    until_approx: bool | None = None
    outside_time: bool | None = None
    # where it was planned (docs/SPEC.md §14.1.2): a journal entry and its passage
    planned_in_journal_id: uuid.UUID | None = None
    planned_evidence: str | None = Field(default=None, max_length=5000)


class FactOut(BaseModel):
    id: uuid.UUID
    entity_id: uuid.UUID
    label: str
    value: str
    position: int
    standing: str
    evidence: str | None
    note: str | None
    established_in_chapter_id: uuid.UUID | None
    from_chapter_id: uuid.UUID | None
    until_chapter_id: uuid.UUID | None
    from_time: float | None = None
    from_approx: bool = False
    until_time: float | None = None
    until_approx: bool = False
    outside_time: bool = False
    planned_in_journal_id: uuid.UUID | None = None
    planned_evidence: str | None = None
    version: int
    # after adding: the one-time "expect it on every …?" prompt, when this fact brought its label to three entries
    prompt: dict | None = None


class TypeIn(BaseModel):
    a_kind: str = Field(max_length=20)
    b_kind: str = Field(max_length=20)
    label: str = Field(min_length=1, max_length=100)
    reverse_label: str | None = Field(default=None, max_length=100)
    has_role: bool = False


class TypeUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    reverse_label: str | None = Field(default=None, max_length=100)
    has_role: bool | None = None


class TypeOut(BaseModel):
    id: uuid.UUID
    a_kind: str
    b_kind: str
    label: str
    reverse_label: str | None
    position: int
    has_role: bool = False
    used: int = 0


def type_out(t: RelationType, used: int = 0) -> TypeOut:
    return TypeOut(id=t.id, a_kind=t.a_kind, b_kind=t.b_kind, label=t.label, reverse_label=t.reverse_label,
                   position=t.position, has_role=t.has_role, used=used)


class RelationshipIn(BaseModel):
    type_id: uuid.UUID
    a_id: uuid.UUID
    b_id: uuid.UUID
    standing: Standing = "canon"
    evidence: str | None = Field(default=None, max_length=5000)
    note: str | None = Field(default=None, max_length=5000)
    established_in_chapter_id: uuid.UUID | None = None
    from_chapter_id: uuid.UUID | None = None
    until_chapter_id: uuid.UUID | None = None
    # a bound can be an in-world time instead (docs/SPEC.md §13.1.5); outside time has no bounds (§13.1.8)
    from_time: float | None = None
    from_approx: bool | None = None
    until_time: float | None = None
    until_approx: bool | None = None
    outside_time: bool | None = None
    role: str | None = Field(default=None, max_length=100)
    # where it was planned (docs/SPEC.md §14.1.2): a journal entry and its passage
    planned_in_journal_id: uuid.UUID | None = None
    planned_evidence: str | None = Field(default=None, max_length=5000)
    # "Make it canon here": the planned row this records in the book, instead of adding a second one
    make_canon: uuid.UUID | None = None


class RelationshipUpdate(BaseModel):
    base_version: int
    type_id: uuid.UUID | None = None
    standing: Standing | None = None
    role: str | None = Field(default=None, max_length=100)
    evidence: str | None = Field(default=None, max_length=5000)
    note: str | None = Field(default=None, max_length=5000)
    established_in_chapter_id: uuid.UUID | None = None
    from_chapter_id: uuid.UUID | None = None
    until_chapter_id: uuid.UUID | None = None
    # a bound can be an in-world time instead (docs/SPEC.md §13.1.5); outside time has no bounds (§13.1.8)
    from_time: float | None = None
    from_approx: bool | None = None
    until_time: float | None = None
    until_approx: bool | None = None
    outside_time: bool | None = None
    # where it was planned (docs/SPEC.md §14.1.2): a journal entry and its passage
    planned_in_journal_id: uuid.UUID | None = None
    planned_evidence: str | None = Field(default=None, max_length=5000)


class Side(BaseModel):
    id: uuid.UUID
    name: str
    kind: str


class RelationshipOut(BaseModel):
    id: uuid.UUID
    type_id: uuid.UUID
    a: Side
    b: Side
    label: str
    reverse_label: str | None
    standing: str
    evidence: str | None
    note: str | None
    established_in_chapter_id: uuid.UUID | None
    from_chapter_id: uuid.UUID | None
    until_chapter_id: uuid.UUID | None
    from_time: float | None = None
    from_approx: bool = False
    until_time: float | None = None
    until_approx: bool = False
    outside_time: bool = False
    # the A side's role in the B side's group, and whether the type offers one
    role: str | None = None
    has_role: bool = False
    planned_in_journal_id: uuid.UUID | None = None
    planned_evidence: str | None = None
    version: int
    created_at: datetime


# helpers -------------------------------------------------------------------------------------------------------


def _entity(db: Session, world: World, entity_id: uuid.UUID) -> Entity:
    e = db.get(Entity, entity_id)
    if e is None or e.world_id != world.id:
        raise HTTPException(404, "No such entry in the bible.")
    return e


def _chapter_in_world(db: Session, world: World, chapter_id: uuid.UUID | None) -> uuid.UUID | None:
    if chapter_id is None:
        return None
    ch = db.get(Chapter, chapter_id)
    if ch is None or ch.project_id not in {p.id for p in world.projects}:
        raise HTTPException(422, "No such chapter in this world.")
    return ch.id


def _journal_in_world(db: Session, world: World, entry_id: uuid.UUID | None) -> uuid.UUID | None:
    if entry_id is None:
        return None
    j = db.get(JournalEntry, entry_id)
    if j is None or j.world_id != world.id:
        raise HTTPException(422, "No such journal entry in this world.")
    return j.id


def set_planned_in(db: Session, world: World, x: Fact | Relationship, body: BaseModel, sent: set[str]) -> None:
    """Where it was planned: a journal entry and its passage (docs/SPEC.md §14.1.2)."""
    if "planned_in_journal_id" in sent:
        x.planned_in_journal_id = _journal_in_world(db, world, body.planned_in_journal_id)  # type: ignore[attr-defined]
    if "planned_evidence" in sent:
        x.planned_evidence = _clean(body.planned_evidence)  # type: ignore[attr-defined]


def _sid(x: uuid.UUID | None) -> str | None:
    return str(x) if x else None


def _clean(text: str | None) -> str | None:
    return (text or "").strip() or None


def norm(text: str) -> str:
    """A label or value as it is compared: whatever the capitals, spaces trimmed (docs/SPEC.md §12.6)."""
    return " ".join(text.split()).lower()


# a label on at least this many entries of a kind is common for it: offered first, and as "Add:" on the others
COMMON_AT = 3


def _f(x) -> float | None:  # type: ignore[no-untyped-def]
    return None if x is None else float(x)


def time_bounds(x: Fact | Relationship) -> dict:
    """A fact's or relationship's time bounds and outside time, as the API shows them."""
    return {"from_time": _f(x.from_time), "from_approx": bool(x.from_approx), "until_time": _f(x.until_time),
            "until_approx": bool(x.until_approx), "outside_time": bool(x.outside_time)}


def set_bounds(db: Session, world: World, x: Fact | Relationship, body: BaseModel, sent: set[str]) -> None:
    """Apply the bounds sent: each side is a chapter or a time (the one sent last wins); outside time has none."""
    for side in ("from", "until"):
        ch, t, ap = f"{side}_chapter_id", f"{side}_time", f"{side}_approx"
        if ch in sent:
            setattr(x, ch, _chapter_in_world(db, world, getattr(body, ch)))
            if getattr(x, ch) is not None and t not in sent:
                setattr(x, t, None)
        if t in sent:
            setattr(x, t, getattr(body, t))
            if getattr(body, t) is not None and ch not in sent:
                setattr(x, ch, None)
        if ap in sent and getattr(body, ap) is not None:
            setattr(x, ap, getattr(body, ap))
        if getattr(x, ch) is not None and getattr(x, t) is not None:
            raise HTTPException(422, "A bound is a chapter or a time, not both.")
        if getattr(x, t) is None:
            setattr(x, ap, False)
    if "outside_time" in sent and body.outside_time is not None:  # type: ignore[attr-defined]
        x.outside_time = body.outside_time  # type: ignore[attr-defined]
    if x.outside_time:
        x.from_chapter_id = x.until_chapter_id = None
        x.from_time = x.until_time = None
        x.from_approx = x.until_approx = False


def fact_out(f: Fact) -> FactOut:
    return FactOut(id=f.id, entity_id=f.entity_id, label=f.label, value=f.value, position=f.position,
                   standing=f.standing, evidence=f.evidence, note=f.note,
                   established_in_chapter_id=f.established_in_chapter_id, from_chapter_id=f.from_chapter_id,
                   until_chapter_id=f.until_chapter_id, **time_bounds(f), planned_in_journal_id=f.planned_in_journal_id,
                   planned_evidence=f.planned_evidence, version=f.version)


def relationship_out(r: Relationship, t: RelationType, a: Entity, b: Entity) -> RelationshipOut:
    return RelationshipOut(id=r.id, type_id=t.id, a=Side(id=a.id, name=a.name, kind=a.kind),
                           b=Side(id=b.id, name=b.name, kind=b.kind), label=t.label, reverse_label=t.reverse_label,
                           standing=r.standing, evidence=r.evidence, note=r.note,
                           established_in_chapter_id=r.established_in_chapter_id, from_chapter_id=r.from_chapter_id,
                           until_chapter_id=r.until_chapter_id, **time_bounds(r), role=r.role, has_role=t.has_role,
                           planned_in_journal_id=r.planned_in_journal_id, planned_evidence=r.planned_evidence,
                           version=r.version, created_at=r.created_at)


def relationships_of(db: Session, world: World, entity_id: uuid.UUID | None = None) -> list[RelationshipOut]:
    """Every relationship of the world, or of one entry (either side)."""
    q = select(Relationship).where(Relationship.world_id == world.id)
    if entity_id is not None:
        q = q.where(or_(Relationship.a_id == entity_id, Relationship.b_id == entity_id))
    rows = list(db.scalars(q.order_by(Relationship.created_at)))
    if not rows:
        return []
    types = {t.id: t for t in db.scalars(select(RelationType).where(RelationType.world_id == world.id))}
    ids = {r.a_id for r in rows} | {r.b_id for r in rows}
    entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.id.in_(ids)))}
    return [relationship_out(r, types[r.type_id], entities[r.a_id], entities[r.b_id]) for r in rows]


# facts ---------------------------------------------------------------------------------------------------------


@router.get("/fact-suggestions")
def fact_suggestions(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """What is offered when adding a fact, per kind: the labels (common ones and the starting suggestions first, then
    labels used once or twice), which labels are common (on three or more entries), and for each label the values
    already used for it on that kind, most used first, with counts. Read per kind and whatever the capitals; each
    label and value in its most-used spelling."""
    world, _ = member_world(db, user, slug)
    rows = db.execute(select(Entity.kind, Fact.entity_id, Fact.label, Fact.value)
                      .join(Entity, Entity.id == Fact.entity_id).where(Fact.world_id == world.id)
                      .order_by(Fact.created_at)).all()
    spelling: dict[tuple[str, str], Counter] = defaultdict(Counter)
    entries: dict[tuple[str, str], set] = defaultdict(set)
    value_spelling: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    value_entries: dict[tuple[str, str, str], set] = defaultdict(set)
    for kind, eid, label, value in rows:
        key = (kind, norm(label))
        spelling[key][label] += 1
        entries[key].add(eid)
        if value.strip():
            vkey = (kind, norm(label), norm(value))
            value_spelling[vkey][value.strip()] += 1
            value_entries[vkey].add(eid)
    out: dict[str, dict] = {}
    for kind in KINDS:
        used = sorted(((lab, len(ids)) for (k, lab), ids in entries.items() if k == kind), key=lambda x: (-x[1], x[0]))
        common = [lab for lab, n in used if n >= COMMON_AT]
        shown = {lab: spelling[(kind, lab)].most_common(1)[0][0] for lab, _ in used}
        labels = [shown[lab] for lab in common]
        for sug in SUGGESTED_FACTS.get(kind, []):
            if norm(sug) not in common:
                labels.append(shown.get(norm(sug), sug))
        taken = {norm(x) for x in labels}
        labels += [shown[lab] for lab, _ in used if lab not in taken]
        values: dict[str, list[dict]] = defaultdict(list)
        for (k, lab, val), ids in value_entries.items():
            if k == kind:
                values[lab].append({"value": value_spelling[(k, lab, val)].most_common(1)[0][0], "count": len(ids)})
        for lab in values:
            values[lab].sort(key=lambda v: (-v["count"], v["value"].lower()))
        # then the starting values from the code, without counts (docs/SPEC.md §13.5)
        for (k, lab), starting in SUGGESTED_VALUES.items():
            if k != kind:
                continue
            have = {norm(v["value"]) for v in values.get(lab, [])}
            values[lab] = values.get(lab, []) + [{"value": v, "count": 0} for v in starting if norm(v) not in have]
        out[kind] = {"labels": labels, "common": [shown[lab] for lab in common], "values": dict(values)}
    return out


def label_prompt(db: Session, world: World, e: Entity, label: str, had_it: bool) -> dict | None:
    """The one-time question when a new fact brings its label to three (or more) entries of the kind: asked once per
    label and kind, and marked asked in the same save, so a prompt ignored or shown on another device isn't shown
    again (docs/SPEC.md §12.6.5)."""
    if had_it:
        return None
    key = norm(label)
    count = len({eid for eid, lab in db.execute(
        select(Fact.entity_id, Fact.label).join(Entity, Entity.id == Fact.entity_id)
        .where(Fact.world_id == world.id, Entity.kind == e.kind)).all() if norm(lab) == key})
    if count < COMMON_AT:
        return None
    row = db.scalar(select(FactLabel).where(FactLabel.world_id == world.id, FactLabel.kind == e.kind,
                                            func.lower(FactLabel.label) == key))
    if row is not None and (row.asked or row.expected):
        return None
    if row is None:
        row = FactLabel(world_id=world.id, kind=e.kind, label=label)
        db.add(row)
    row.asked = True
    return {"kind": e.kind, "label": label, "count": count}


@router.post("/entities/{entity_id}/facts", status_code=201)
def add_fact(slug: str, entity_id: uuid.UUID, body: FactIn, user: User = Depends(current_user),
             db: Session = Depends(get_db)) -> FactOut:
    world, _ = member_world(db, user, slug)
    e = _entity(db, world, entity_id)
    if body.make_canon is not None:
        return _make_fact_canon(db, world, e, body, user)
    top = db.scalar(select(func.max(Fact.position)).where(Fact.entity_id == e.id))
    label = " ".join(body.label.split())
    had_it = any(norm(x) == norm(label) for x in db.scalars(select(Fact.label).where(Fact.entity_id == e.id)))
    f = Fact(world_id=world.id, entity_id=e.id, label=label, value=body.value.strip(),
             position=0 if top is None else top + 1, standing=body.standing, evidence=_clean(body.evidence),
             note=_clean(body.note),
             established_in_chapter_id=_chapter_in_world(db, world, body.established_in_chapter_id),
             from_approx=False, until_approx=False, outside_time=False, created_by=user.id, updated_by=user.id)
    set_bounds(db, world, f, body, body.model_fields_set)
    set_planned_in(db, world, f, body, body.model_fields_set)
    check_span(db, world, f)
    db.add(f)
    db.flush()
    prompt = label_prompt(db, world, e, label, had_it)
    from .history import assign_era_colour

    assign_era_colour(db, world, e)
    db.commit()
    out = fact_out(f)
    out.prompt = prompt
    return out


def _make_fact_canon(db: Session, world: World, e: Entity, body: FactIn, user: User) -> FactOut:
    """Make it canon here (docs/SPEC.md §14.1.2): the planned fact becomes canon, established in this chapter with the
    passage as its evidence and the span the form chose; where it was planned stays."""
    f = _fact(db, world, body.make_canon)  # type: ignore[arg-type]
    if f.entity_id != e.id:
        raise HTTPException(422, "That fact belongs to another entry.")
    sent = body.model_fields_set - {"make_canon", "planned_in_journal_id", "planned_evidence", "label"}
    if body.value.strip():
        f.value = body.value.strip()
    f.standing = "canon"
    if "established_in_chapter_id" in sent:
        f.established_in_chapter_id = _chapter_in_world(db, world, body.established_in_chapter_id)
    if "evidence" in sent:
        f.evidence = _clean(body.evidence)
    if "note" in sent and _clean(body.note):
        f.note = _clean(body.note)
    set_bounds(db, world, f, body, sent)
    check_span(db, world, f)
    f.version += 1
    f.updated_by = user.id
    db.commit()
    return fact_out(f)


def _fact(db: Session, world: World, fact_id: uuid.UUID) -> Fact:
    f = db.get(Fact, fact_id)
    if f is None or f.world_id != world.id:
        raise HTTPException(404, "No such fact.")
    return f


@router.patch("/facts/{fact_id}")
def update_fact(slug: str, fact_id: uuid.UUID, body: FactUpdate, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    world, _ = member_world(db, user, slug)
    f = _fact(db, world, fact_id)
    if f.version != body.base_version:
        return JSONResponse(status_code=409, content={"detail": "This fact changed elsewhere. Here is the newer version.",
                                                      "fact": fact_out(f).model_dump(mode="json")})
    sent = body.model_fields_set
    if body.label is not None:
        f.label = " ".join(body.label.split())
    if body.value is not None:
        f.value = body.value.strip()
    if body.standing is not None:
        f.standing = body.standing
    for field in ("evidence", "note"):
        if field in sent:
            setattr(f, field, _clean(getattr(body, field)))
    if "established_in_chapter_id" in sent:
        f.established_in_chapter_id = _chapter_in_world(db, world, body.established_in_chapter_id)
    set_bounds(db, world, f, body, sent)
    set_planned_in(db, world, f, body, sent)
    check_span(db, world, f)
    f.version += 1
    f.updated_by = user.id
    db.flush()
    from .history import assign_era_colour

    e = db.get(Entity, f.entity_id)
    if e is not None:
        assign_era_colour(db, world, e)
    db.commit()
    return fact_out(f)


@router.delete("/facts/{fact_id}", status_code=204)
def delete_fact(slug: str, fact_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    db.delete(_fact(db, world, fact_id))
    db.commit()


class OrderIn(BaseModel):
    ids: list[uuid.UUID]


@router.put("/entities/{entity_id}/fact-order")
def order_facts(slug: str, entity_id: uuid.UUID, body: OrderIn, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> list[FactOut]:
    world, _ = member_world(db, user, slug)
    e = _entity(db, world, entity_id)
    facts = {f.id: f for f in db.scalars(select(Fact).where(Fact.entity_id == e.id))}
    if set(body.ids) != set(facts) or len(body.ids) != len(facts):
        raise HTTPException(422, "Send every fact of the entry exactly once.")
    for i, fid in enumerate(body.ids):
        facts[fid].position = i
    db.commit()
    return [fact_out(facts[fid]) for fid in body.ids]


# relationship types ---------------------------------------------------------------------------------------------


@router.get("/relation-types")
def list_types(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[TypeOut]:
    world, _ = member_world(db, user, slug)
    used = dict(db.execute(select(Relationship.type_id, func.count()).where(Relationship.world_id == world.id)
                           .group_by(Relationship.type_id)).all())
    rows = db.scalars(select(RelationType).where(RelationType.world_id == world.id).order_by(RelationType.position))
    return [type_out(t, used.get(t.id, 0)) for t in rows]


@router.post("/relation-types", status_code=201)
def add_type(slug: str, body: TypeIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> TypeOut:
    world, _ = member_world(db, user, slug)
    for side in (body.a_kind, body.b_kind):
        if side != "*" and side not in KINDS:
            raise HTTPException(422, "Unknown kind.")
    top = db.scalar(select(func.max(RelationType.position)).where(RelationType.world_id == world.id))
    t = RelationType(world_id=world.id, a_kind=body.a_kind, b_kind=body.b_kind, label=" ".join(body.label.split()),
                     reverse_label=_clean(body.reverse_label), position=0 if top is None else top + 1,
                     has_role=body.has_role)
    db.add(t)
    db.commit()
    return type_out(t)


def _type(db: Session, world: World, type_id: uuid.UUID) -> RelationType:
    t = db.get(RelationType, type_id)
    if t is None or t.world_id != world.id:
        raise HTTPException(404, "No such relationship type.")
    return t


@router.patch("/relation-types/{type_id}")
def update_type(slug: str, type_id: uuid.UUID, body: TypeUpdate, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> TypeOut:
    world, _ = member_world(db, user, slug)
    t = _type(db, world, type_id)
    if body.label is not None:
        t.label = " ".join(body.label.split())
    if "reverse_label" in body.model_fields_set:
        t.reverse_label = _clean(body.reverse_label)
    if body.has_role is not None:
        t.has_role = body.has_role
    db.commit()
    return type_out(t)


@router.delete("/relation-types/{type_id}", status_code=204)
def delete_type(slug: str, type_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    t = _type(db, world, type_id)
    if db.scalar(select(func.count()).select_from(Relationship).where(Relationship.type_id == t.id)):
        raise HTTPException(409, "Some relationships use this type. Change or remove them first.")
    db.delete(t)
    db.commit()


# relationships -------------------------------------------------------------------------------------------------


def _check_pair(t: RelationType, a: Entity, b: Entity) -> None:
    """The type joins these two: any of each one's kinds fits its side (docs/SPEC.md §14.8)."""
    if not (any(_fits(k, t.a_kind) for k in [a.kind, *(a.also_kinds or [])])
            and any(_fits(k, t.b_kind) for k in [b.kind, *(b.also_kinds or [])])):
        raise HTTPException(422, f"“{t.label}” joins a {t.a_kind} to a {t.b_kind}.")
    if a.id == b.id:
        raise HTTPException(422, "An entry can't be related to itself.")


@router.get("/relationships")
def list_relationships(slug: str, user: User = Depends(current_user),
                       db: Session = Depends(get_db)) -> list[RelationshipOut]:
    world, _ = member_world(db, user, slug)
    return relationships_of(db, world)


@router.post("/relationships", status_code=201)
def add_relationship(slug: str, body: RelationshipIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> RelationshipOut:
    world, _ = member_world(db, user, slug)
    t = _type(db, world, body.type_id)
    a, b = _entity(db, world, body.a_id), _entity(db, world, body.b_id)
    _check_pair(t, a, b)
    if body.make_canon is not None:
        return _make_relationship_canon(db, world, body, user)
    r = Relationship(world_id=world.id, type_id=t.id, a_id=a.id, b_id=b.id, standing=body.standing,
                     evidence=_clean(body.evidence), note=_clean(body.note),
                     established_in_chapter_id=_chapter_in_world(db, world, body.established_in_chapter_id),
                     from_approx=False, until_approx=False, outside_time=False,
                     role=clean_role(body.role) if t.has_role else None, created_by=user.id, updated_by=user.id)
    set_bounds(db, world, r, body, body.model_fields_set)
    set_planned_in(db, world, r, body, body.model_fields_set)
    check_span(db, world, r)
    db.add(r)
    db.commit()
    return relationship_out(r, t, a, b)


def _make_relationship_canon(db: Session, world: World, body: RelationshipIn, user: User) -> RelationshipOut:
    """Make it canon here, for a relationship planned before (the same two entries, either way round)."""
    r = _relationship(db, world, body.make_canon)  # type: ignore[arg-type]
    if {r.a_id, r.b_id} != {body.a_id, body.b_id}:
        raise HTTPException(422, "That relationship joins other entries.")
    sent = body.model_fields_set - {"make_canon", "planned_in_journal_id", "planned_evidence", "type_id", "a_id",
                                    "b_id", "standing"}
    r.standing = "canon"
    if "established_in_chapter_id" in sent:
        r.established_in_chapter_id = _chapter_in_world(db, world, body.established_in_chapter_id)
    if "evidence" in sent:
        r.evidence = _clean(body.evidence)
    set_bounds(db, world, r, body, sent)
    if "role" in sent and body.role:
        r.role = clean_role(body.role)
    check_span(db, world, r)
    r.version += 1
    r.updated_by = user.id
    db.commit()
    t = db.get(RelationType, r.type_id)
    a, b = db.get(Entity, r.a_id), db.get(Entity, r.b_id)
    assert t is not None and a is not None and b is not None
    return relationship_out(r, t, a, b)


def _relationship(db: Session, world: World, rel_id: uuid.UUID) -> Relationship:
    r = db.get(Relationship, rel_id)
    if r is None or r.world_id != world.id:
        raise HTTPException(404, "No such relationship.")
    return r


@router.patch("/relationships/{rel_id}")
def update_relationship(slug: str, rel_id: uuid.UUID, body: RelationshipUpdate, user: User = Depends(current_user),
                        db: Session = Depends(get_db)):
    world, _ = member_world(db, user, slug)
    r = _relationship(db, world, rel_id)
    a, b = db.get(Entity, r.a_id), db.get(Entity, r.b_id)
    assert a is not None and b is not None
    if r.version != body.base_version:
        t = db.get(RelationType, r.type_id)
        assert t is not None
        return JSONResponse(status_code=409, content={
            "detail": "This relationship changed elsewhere. Here is the newer version.",
            "relationship": relationship_out(r, t, a, b).model_dump(mode="json")})
    sent = body.model_fields_set
    if body.type_id is not None:
        t = _type(db, world, body.type_id)
        _check_pair(t, a, b)
        r.type_id = t.id
    if body.standing is not None:
        r.standing = body.standing
    for field in ("evidence", "note"):
        if field in sent:
            setattr(r, field, _clean(getattr(body, field)))
    if "established_in_chapter_id" in sent:
        r.established_in_chapter_id = _chapter_in_world(db, world, body.established_in_chapter_id)
    set_bounds(db, world, r, body, sent)
    set_planned_in(db, world, r, body, sent)
    if "role" in sent:
        r.role = clean_role(body.role)
    check_span(db, world, r)
    r.version += 1
    r.updated_by = user.id
    db.commit()
    t = db.get(RelationType, r.type_id)
    assert t is not None
    return relationship_out(r, t, a, b)


@router.delete("/relationships/{rel_id}", status_code=204)
def delete_relationship(slug: str, rel_id: uuid.UUID, user: User = Depends(current_user),
                        db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    db.delete(_relationship(db, world, rel_id))
    db.commit()


# cards: what the editor needs to colour names and show them on hover --------------------------------------------


@router.get("/cards")
def cards(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Every entry, small: names and matching rules (so the browser matches exactly as the server does) and what a
    hover card shows: the one-liner, the first facts and the closest relationships."""
    world, _ = member_world(db, user, slug)
    entities = list(db.scalars(select(Entity).where(Entity.world_id == world.id).order_by(func.lower(Entity.name))))
    firsts = first_name_aliases(entities)
    projects = {p.id: p.slug for p in world.projects}
    # every canon fact (the bible's tables filter and group by them), and the labels of all of them, whatever their
    # standing (the labels an entry has, for "Add:" and expected labels)
    facts: dict[uuid.UUID, list[dict]] = {}
    # planned facts, apart: cards in the Journal show them, marked (docs/SPEC.md §14.1.1); a chapter's don't
    planned: dict[uuid.UUID, list[dict]] = {}
    labels: dict[uuid.UUID, set[str]] = defaultdict(set)
    for f in db.scalars(select(Fact).where(Fact.world_id == world.id).order_by(Fact.entity_id, Fact.position)):
        labels[f.entity_id].add(norm(f.label))
        if f.standing in ("canon", "planned"):
            (facts if f.standing == "canon" else planned).setdefault(f.entity_id, []).append(
                {"label": f.label, "value": f.value, "from": _sid(f.from_chapter_id),
                 "until": _sid(f.until_chapter_id), **card_times(f)})
    relations: dict[uuid.UUID, list[dict]] = {}
    for r in relationships_of(db, world):
        span = {"from": _sid(r.from_chapter_id), "until": _sid(r.until_chapter_id), **card_times(r)}
        role = {"role": r.role} if r.role else {}
        relations.setdefault(r.a.id, []).append({"label": r.label, "other": r.b.model_dump(mode="json"),
                                                 "standing": r.standing, **span, **role})
        relations.setdefault(r.b.id, []).append({"label": r.reverse_label or r.label,
                                                 "other": r.a.model_dump(mode="json"), "standing": r.standing, **span,
                                                 **role})
    from .history import event_when

    out = []
    for e in entities:
        card = {"id": str(e.id), "name": e.name, "kind": e.kind, "aliases": list(e.aliases),
                "first_name": firsts.get(e.id), "match_case": e.match_case, "exclusions": list(e.exclusions),
                "summary": e.summary, "facts": facts.get(e.id, []), "relations": card_relations(e, relations.get(e.id, [])),
                "also_kinds": list(e.also_kinds or []),
                "labels": sorted(labels.get(e.id, ())), "project": projects.get(e.project_id) if e.project_id else None,
                "gender": e.gender}
        # an event's "when" and an era's colour, so a time's era is found on the device (docs/SPEC.md §13.2.1)
        if planned.get(e.id):
            card["planned"] = planned[e.id]
        if e.kind == "event":
            when = event_when(e)
            if when:
                card["when"] = when
            if e.era_colour:
                card["era_colour"] = e.era_colour
        out.append(card)
    return out


def card_times(x) -> dict:  # type: ignore[no-untyped-def]
    """Time bounds and outside time on a card, only when set (most facts have neither, and the cards stay small)."""
    out: dict = {}
    if x.from_time is not None:
        out["from_time"] = float(x.from_time)
        if x.from_approx:
            out["from_approx"] = True
    if x.until_time is not None:
        out["until_time"] = float(x.until_time)
        if x.until_approx:
            out["until_approx"] = True
    if x.outside_time:
        out["outside_time"] = True
    return out


# a character's species and outward form, and who possesses them, read by label from the character's side
# (docs/SPEC.md §13.3, §13.5), the way the family tree reads parent types
SPECIES_RE = re.compile(r"^(is an?|appears as( an?)?)$", re.I)
POSSESSED_RE = re.compile(r"^possessed by$", re.I)


def card_relations(e: Entity, rels: list[dict]) -> list[dict]:
    """A card's relationships: the first sixteen, plus every one the card reads by label (a character's species and
    outward form, and who possesses them), so the word beside the name follows "as of" offline too."""
    out = rels[:16]
    if e.kind == "character":
        # and every event: a birth or a death event is how an age is worked out (docs/SPEC.md §13.2.4)
        out += [r for r in rels[16:] if (r["other"]["kind"] == "species" and SPECIES_RE.match(r["label"].strip()))
                or POSSESSED_RE.match(r["label"].strip()) or r["other"]["kind"] == "event"]
    return out


# roles in groups (docs/SPEC.md §13.4) -----------------------------------------------------------------------------


@router.get("/role-suggestions")
def role_suggestions(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """The roles used on each relationship type across the world, most used first, with counts and the groups (B
    sides) they are used in, so a group's own roles can be offered first. Each in its most-used spelling."""
    world, _ = member_world(db, user, slug)
    spelling: dict[tuple[uuid.UUID, str], Counter] = defaultdict(Counter)
    groups: dict[tuple[uuid.UUID, str], set] = defaultdict(set)
    for type_id, group, role in db.execute(select(Relationship.type_id, Relationship.b_id, Relationship.role)
                                           .where(Relationship.world_id == world.id, Relationship.role.is_not(None))
                                           .order_by(Relationship.created_at)).all():
        key = (type_id, norm(role))
        spelling[key][role] += 1
        groups[key].add(str(group))
    out: dict[str, list[dict]] = defaultdict(list)
    for (type_id, _), counts in spelling.items():
        out[str(type_id)].append({"role": counts.most_common(1)[0][0], "count": sum(counts.values()),
                                  "groups": sorted(groups[(type_id, norm(counts.most_common(1)[0][0]))])})
    for lst in out.values():
        lst.sort(key=lambda r: (-r["count"], r["role"].lower()))
    return dict(out)


class ChangeRoleIn(BaseModel):
    base_version: int
    role: str | None = Field(default=None, max_length=100)
    # where the new role starts: a chapter (the old one ends at the chapter before it on the clock), or a time (the
    # two meet there: a handover)
    from_chapter_id: uuid.UUID | None = None
    from_time: float | None = None
    from_approx: bool = False


@router.post("/relationships/{rel_id}/change-role", status_code=201)
def change_role(slug: str, rel_id: uuid.UUID, body: ChangeRoleIn, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    """A promotion is a new span: the relationship ends just before the chosen chapter (or time), and a copy with the
    new role starts there. With no chapter before it on the clock, the two meet at the chosen chapter (a handover)."""
    world, _ = member_world(db, user, slug)
    r = _relationship(db, world, rel_id)
    a, b = db.get(Entity, r.a_id), db.get(Entity, r.b_id)
    t = db.get(RelationType, r.type_id)
    assert a is not None and b is not None and t is not None
    if r.version != body.base_version:
        return JSONResponse(status_code=409, content={
            "detail": "This relationship changed elsewhere. Here is the newer version.",
            "relationship": relationship_out(r, t, a, b).model_dump(mode="json")})
    copy = Relationship(world_id=world.id, type_id=r.type_id, a_id=r.a_id, b_id=r.b_id, standing=r.standing,
                        note=r.note, until_chapter_id=r.until_chapter_id, until_time=r.until_time,
                        until_approx=r.until_approx, outside_time=False, from_approx=False,
                        role=clean_role(body.role), created_by=user.id, updated_by=user.id)
    if body.from_time is not None:
        copy.from_time, copy.from_approx = body.from_time, body.from_approx
        r.until_chapter_id, r.until_time, r.until_approx = None, body.from_time, body.from_approx
    else:
        if body.from_chapter_id is None:
            raise HTTPException(422, "Pick where the new role starts: a chapter or a time.")
        start = _chapter_in_world(db, world, body.from_chapter_id)
        from .storytime import world_clock

        clock = world_clock(db, world)
        x = clock.get(start)
        if x is None or x.place is None:
            raise HTTPException(422, "Pick a chapter in the book, on the clock.")
        copy.from_chapter_id = start
        r.until_chapter_id = clock.happened[x.place - 1].id if x.place > 0 else start
        r.until_time, r.until_approx = None, False
    r.outside_time = False
    check_span(db, world, r)
    check_span(db, world, copy)
    r.version += 1
    r.updated_by = user.id
    db.add(copy)
    db.commit()
    return {"ended": relationship_out(r, t, a, b), "started": relationship_out(copy, t, a, b)}


@router.post("/relationships/{rel_id}/end-before/{other_id}")
def end_before(slug: str, rel_id: uuid.UUID, other_id: uuid.UUID, user: User = Depends(current_user),
               db: Session = Depends(get_db)) -> RelationshipOut:
    """Resolve two holders of a one-at-a-time role: the earlier one ends where the other starts (a handover)."""
    world, _ = member_world(db, user, slug)
    r, other = _relationship(db, world, rel_id), _relationship(db, world, other_id)
    if other.from_chapter_id is None and other.from_time is None:
        raise HTTPException(422, "The other one holds from the start: there is nothing to end before.")
    r.until_chapter_id, r.until_time, r.until_approx = other.from_chapter_id, other.from_time, other.from_approx
    check_span(db, world, r)
    r.version += 1
    r.updated_by = user.id
    db.commit()
    a, b, t = db.get(Entity, r.a_id), db.get(Entity, r.b_id), db.get(RelationType, r.type_id)
    assert a is not None and b is not None and t is not None
    return relationship_out(r, t, a, b)


# used by bible.py for an entry's page
def entity_world_detail(db: Session, world: World, e: Entity) -> dict:
    facts = [fact_out(f).model_dump(mode="json") for f in
             db.scalars(select(Fact).where(Fact.entity_id == e.id).order_by(Fact.position, Fact.created_at))]
    rels = []
    for r in relationships_of(db, world, e.id):
        mine = r.a.id == e.id
        rels.append({**r.model_dump(mode="json"), "reads": r.label if mine else (r.reverse_label or r.label),
                     "other": (r.b if mine else r.a).model_dump(mode="json"), "side": "a" if mine else "b"})
    chapter_titles = {}
    ids = {x for f in facts for x in (f["established_in_chapter_id"],) if x} | {
        x for r in rels for x in (r["established_in_chapter_id"],) if x}
    if ids:
        for ch in db.scalars(select(Chapter).join(Project, Project.id == Chapter.project_id)
                             .where(Chapter.id.in_(ids))):
            chapter_titles[str(ch.id)] = ch.title
    # where things were planned: each journal entry's date and title (docs/SPEC.md §14.1.2)
    journal_entries = {}
    jids = {x["planned_in_journal_id"] for x in [*facts, *rels] if x.get("planned_in_journal_id")}
    if jids:
        for j in db.scalars(select(JournalEntry).where(JournalEntry.id.in_(jids))):
            journal_entries[str(j.id)] = {"id": str(j.id), "date": j.entry_date.isoformat(), "title": j.title,
                                          "body": j.body}
    return {"facts": facts, "relationships": rels, "chapter_titles": chapter_titles,
            "journal_entries": journal_entries}
