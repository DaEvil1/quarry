"""The world model: facts about entries, relationship types and relationships, and the cards the editor uses to
colour names and show them on hover (docs/WORLD-MODEL.md §2–§5)."""

from __future__ import annotations

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
from ..models import Chapter, Entity, Fact, FactLabel, Project, RelationType, Relationship, User, World
from ..vocabulary import STARTING_TYPES, SUGGESTED_FACTS
from .deps import current_user
from .storytime import check_span
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

Standing = Literal["canon", "planned", "rumour"]
KINDS = ("character", "place", "faction", "culture", "event", "object", "term", "other")


def seed_relation_types(db: Session, world_id: uuid.UUID) -> None:
    """A new world gets the starting vocabulary."""
    for i, (a, b, label, reverse) in enumerate(STARTING_TYPES):
        db.add(RelationType(world_id=world_id, a_kind=a, b_kind=b, label=label, reverse_label=reverse, position=i))


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
    version: int
    # after adding: the one-time "expect it on every …?" prompt, when this fact brought its label to three entries
    prompt: dict | None = None


class TypeIn(BaseModel):
    a_kind: str = Field(max_length=20)
    b_kind: str = Field(max_length=20)
    label: str = Field(min_length=1, max_length=100)
    reverse_label: str | None = Field(default=None, max_length=100)


class TypeUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    reverse_label: str | None = Field(default=None, max_length=100)


class TypeOut(BaseModel):
    id: uuid.UUID
    a_kind: str
    b_kind: str
    label: str
    reverse_label: str | None
    position: int
    used: int = 0


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


class RelationshipUpdate(BaseModel):
    base_version: int
    type_id: uuid.UUID | None = None
    standing: Standing | None = None
    evidence: str | None = Field(default=None, max_length=5000)
    note: str | None = Field(default=None, max_length=5000)
    established_in_chapter_id: uuid.UUID | None = None
    from_chapter_id: uuid.UUID | None = None
    until_chapter_id: uuid.UUID | None = None


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


def _sid(x: uuid.UUID | None) -> str | None:
    return str(x) if x else None


def _clean(text: str | None) -> str | None:
    return (text or "").strip() or None


def norm(text: str) -> str:
    """A label or value as it is compared: whatever the capitals, spaces trimmed (docs/SPEC.md §12.6)."""
    return " ".join(text.split()).lower()


# a label on at least this many entries of a kind is common for it: offered first, and as "Add:" on the others
COMMON_AT = 3


def fact_out(f: Fact) -> FactOut:
    return FactOut(id=f.id, entity_id=f.entity_id, label=f.label, value=f.value, position=f.position,
                   standing=f.standing, evidence=f.evidence, note=f.note,
                   established_in_chapter_id=f.established_in_chapter_id, from_chapter_id=f.from_chapter_id,
                   until_chapter_id=f.until_chapter_id, version=f.version)


def relationship_out(r: Relationship, t: RelationType, a: Entity, b: Entity) -> RelationshipOut:
    return RelationshipOut(id=r.id, type_id=t.id, a=Side(id=a.id, name=a.name, kind=a.kind),
                           b=Side(id=b.id, name=b.name, kind=b.kind), label=t.label, reverse_label=t.reverse_label,
                           standing=r.standing, evidence=r.evidence, note=r.note,
                           established_in_chapter_id=r.established_in_chapter_id, from_chapter_id=r.from_chapter_id,
                           until_chapter_id=r.until_chapter_id, version=r.version, created_at=r.created_at)


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
    top = db.scalar(select(func.max(Fact.position)).where(Fact.entity_id == e.id))
    label = " ".join(body.label.split())
    had_it = any(norm(x) == norm(label) for x in db.scalars(select(Fact.label).where(Fact.entity_id == e.id)))
    f = Fact(world_id=world.id, entity_id=e.id, label=label, value=body.value.strip(),
             position=0 if top is None else top + 1, standing=body.standing, evidence=_clean(body.evidence),
             note=_clean(body.note),
             established_in_chapter_id=_chapter_in_world(db, world, body.established_in_chapter_id),
             from_chapter_id=_chapter_in_world(db, world, body.from_chapter_id),
             until_chapter_id=_chapter_in_world(db, world, body.until_chapter_id),
             created_by=user.id, updated_by=user.id)
    check_span(db, world, f.from_chapter_id, f.until_chapter_id)
    db.add(f)
    db.flush()
    prompt = label_prompt(db, world, e, label, had_it)
    db.commit()
    out = fact_out(f)
    out.prompt = prompt
    return out


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
    for field in ("established_in_chapter_id", "from_chapter_id", "until_chapter_id"):
        if field in sent:
            setattr(f, field, _chapter_in_world(db, world, getattr(body, field)))
    check_span(db, world, f.from_chapter_id, f.until_chapter_id)
    f.version += 1
    f.updated_by = user.id
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
    return [TypeOut(id=t.id, a_kind=t.a_kind, b_kind=t.b_kind, label=t.label, reverse_label=t.reverse_label,
                    position=t.position, used=used.get(t.id, 0)) for t in rows]


@router.post("/relation-types", status_code=201)
def add_type(slug: str, body: TypeIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> TypeOut:
    world, _ = member_world(db, user, slug)
    for side in (body.a_kind, body.b_kind):
        if side != "*" and side not in KINDS:
            raise HTTPException(422, "Unknown kind.")
    top = db.scalar(select(func.max(RelationType.position)).where(RelationType.world_id == world.id))
    t = RelationType(world_id=world.id, a_kind=body.a_kind, b_kind=body.b_kind, label=" ".join(body.label.split()),
                     reverse_label=_clean(body.reverse_label), position=0 if top is None else top + 1)
    db.add(t)
    db.commit()
    return TypeOut(id=t.id, a_kind=t.a_kind, b_kind=t.b_kind, label=t.label, reverse_label=t.reverse_label,
                   position=t.position)


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
    db.commit()
    return TypeOut(id=t.id, a_kind=t.a_kind, b_kind=t.b_kind, label=t.label, reverse_label=t.reverse_label,
                   position=t.position)


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
    if not (_fits(a.kind, t.a_kind) and _fits(b.kind, t.b_kind)):
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
    r = Relationship(world_id=world.id, type_id=t.id, a_id=a.id, b_id=b.id, standing=body.standing,
                     evidence=_clean(body.evidence), note=_clean(body.note),
                     established_in_chapter_id=_chapter_in_world(db, world, body.established_in_chapter_id),
                     from_chapter_id=_chapter_in_world(db, world, body.from_chapter_id),
                     until_chapter_id=_chapter_in_world(db, world, body.until_chapter_id),
                     created_by=user.id, updated_by=user.id)
    check_span(db, world, r.from_chapter_id, r.until_chapter_id)
    db.add(r)
    db.commit()
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
    for field in ("established_in_chapter_id", "from_chapter_id", "until_chapter_id"):
        if field in sent:
            setattr(r, field, _chapter_in_world(db, world, getattr(body, field)))
    check_span(db, world, r.from_chapter_id, r.until_chapter_id)
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
    labels: dict[uuid.UUID, set[str]] = defaultdict(set)
    for f in db.scalars(select(Fact).where(Fact.world_id == world.id).order_by(Fact.entity_id, Fact.position)):
        labels[f.entity_id].add(norm(f.label))
        if f.standing == "canon":
            facts.setdefault(f.entity_id, []).append({"label": f.label, "value": f.value, "from": _sid(f.from_chapter_id),
                                                      "until": _sid(f.until_chapter_id)})
    relations: dict[uuid.UUID, list[dict]] = {}
    for r in relationships_of(db, world):
        span = {"from": _sid(r.from_chapter_id), "until": _sid(r.until_chapter_id)}
        relations.setdefault(r.a.id, []).append({"label": r.label, "other": r.b.model_dump(mode="json"),
                                                 "standing": r.standing, **span})
        relations.setdefault(r.b.id, []).append({"label": r.reverse_label or r.label,
                                                 "other": r.a.model_dump(mode="json"), "standing": r.standing, **span})
    return [{"id": str(e.id), "name": e.name, "kind": e.kind, "aliases": list(e.aliases),
             "first_name": firsts.get(e.id), "match_case": e.match_case, "exclusions": list(e.exclusions),
             "summary": e.summary, "facts": facts.get(e.id, []), "relations": relations.get(e.id, [])[:16],
             "labels": sorted(labels.get(e.id, ())), "project": projects.get(e.project_id) if e.project_id else None,
             "gender": e.gender}
            for e in entities]


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
    return {"facts": facts, "relationships": rels, "chapter_titles": chapter_titles}
