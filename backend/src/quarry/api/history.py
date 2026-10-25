"""History and the Timeline (docs/SPEC.md §13.2): when an event happens, eras and their colours, tellings, recording an
event from a passage of prose ("Record as event"), and what the Timeline reads that the cards and the graph don't
carry (`GET /chronology`: "is at" and tellings). Everything else on the Timeline is worked out in the browser."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import Clock
from ..db import get_db
from ..mentions import refresh_world
from ..models import (
    ERA_COLOURS,
    Chapter,
    Entity,
    Fact,
    Presence,
    RelationType,
    Relationship,
    Telling,
    User,
    World,
)
from .deps import current_user
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")


def _norm(text: str | None) -> str:
    return " ".join((text or "").split()).lower()


def is_era(db: Session, e: Entity) -> bool:
    """An era is an event whose type (any of its type facts, any standing) is "era", whatever the capitals."""
    if e.kind != "event":
        return False
    return any(_norm(f.label) == "type" and _norm(f.value) == "era"
               for f in db.scalars(select(Fact).where(Fact.entity_id == e.id)))


def assign_era_colour(db: Session, world: World, e: Entity) -> None:
    """A new era takes the next colour of the palette not yet used in the world (after the last one, round again)."""
    if e.era_colour or not is_era(db, e):
        return
    used = [c for c in db.scalars(select(Entity.era_colour).where(Entity.world_id == world.id,
                                                                 Entity.era_colour.is_not(None)))]
    free = [c for c in ERA_COLOURS if c not in used]
    e.era_colour = free[0] if free else ERA_COLOURS[len(used) % len(ERA_COLOURS)]


def event_when(e: Entity) -> dict | None:
    """An event's "when" as the API and the cards show it (only when something is set)."""
    if e.time_chapter_id is None and e.time_at is None and not e.outside_time:
        return None
    return {"chapter": str(e.time_chapter_id) if e.time_chapter_id else None,
            "at": float(e.time_at) if e.time_at is not None else None,
            "end": float(e.time_end) if e.time_end is not None else None, "label": e.time_label,
            "approx": bool(e.time_approx), "outside": bool(e.outside_time)}


def event_time(e: Entity, clock: Clock) -> tuple[float | None, bool]:
    """Where an event sits in time: its own time, or the set time of the chapter it happens in (None when neither, or
    outside time)."""
    if e.outside_time:
        return None, False
    if e.time_at is not None:
        return float(e.time_at), bool(e.time_approx)
    x = clock.get(e.time_chapter_id)
    if x is not None and x.comparable and x.set_time is not None:
        return x.set_time, x.set_approx
    return None, False


def passage_spans(db: Session, world: World, chapters: dict[uuid.UUID, Chapter]) -> tuple[
        dict[uuid.UUID, list[tuple[int, int]]], set[uuid.UUID]]:
    """Where each telling's passage is in its chapter (found by its text), and the tellings whose passage can't be
    found any more (the passage changed)."""
    spans: dict[uuid.UUID, list[tuple[int, int]]] = {}
    changed: set[uuid.UUID] = set()
    for t in db.scalars(select(Telling).where(Telling.world_id == world.id)):
        ch = chapters.get(t.chapter_id) if t.chapter_id else None
        if ch is None:
            continue
        at = ch.body.find(t.passage)
        if at < 0:
            changed.add(t.id)
        else:
            spans.setdefault(ch.id, []).append((at, at + len(t.passage)))
    return spans, changed


def tellings_of(db: Session, world: World, event_id: uuid.UUID) -> list[dict]:
    """An event's tellings, for its page (Told in): each passage with its chapter, and whether it can still be found."""
    out = []
    for t in db.scalars(select(Telling).where(Telling.event_id == event_id).order_by(Telling.created_at)):
        ch = db.get(Chapter, t.chapter_id) if t.chapter_id else None
        out.append({"id": str(t.id), "passage": t.passage,
                    "chapter": {"id": str(ch.id), "title": ch.title, "state": ch.state} if ch else None,
                    "at": ch.body.find(t.passage) if ch else -1,
                    "changed": ch is not None and t.passage not in ch.body})
    return out


@router.get("/chronology")
def chronology(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """What the Timeline reads besides the cards, the timeline and the graph: every "is at" record and every
    telling."""
    world, _ = member_world(db, user, slug)
    return {
        "presence": [{"entity_id": str(p.entity_id), "place_id": str(p.place_id), "chapter_id": str(p.chapter_id)}
                     for p in db.scalars(select(Presence).where(Presence.world_id == world.id))],
        "tellings": [{"id": str(t.id), "event_id": str(t.event_id),
                      "chapter_id": str(t.chapter_id) if t.chapter_id else None, "passage": t.passage}
                     for t in db.scalars(select(Telling).where(Telling.world_id == world.id)
                                         .order_by(Telling.created_at))],
    }


@router.delete("/tellings/{telling_id}", status_code=204)
def delete_telling(slug: str, telling_id: uuid.UUID, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    t = db.get(Telling, telling_id)
    if t is None or t.world_id != world.id:
        raise HTTPException(404, "No such telling.")
    db.delete(t)
    db.commit()


# recording an event from the prose (docs/SPEC.md §13.2.3) ---------------------------------------------------------


class WhenIn(BaseModel):
    time_at: float | None = None
    time_end: float | None = None
    time_label: str | None = Field(default=None, max_length=200)
    time_approx: bool = False
    outside_time: bool = False


class Taking(BaseModel):
    entity_id: uuid.UUID
    # taking part (characters, factions, species …), or where it happened (a place)
    role: Literal["involved", "place"] = "involved"


class RecordIn(BaseModel):
    # an existing event, or the name of a new one
    event_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=200)
    chapter_id: uuid.UUID
    passage: str = Field(min_length=1, max_length=20000)
    taking: list[Taking] = Field(default_factory=list, max_length=200)
    when: WhenIn | None = None
    # for an existing event with another time: keep its own, or use the one given
    time_choice: Literal["keep", "use"] = "keep"


def _type_by(types: list[RelationType], labels: set[str], reverses: set[str], a: str, b: str) -> RelationType | None:
    """A relationship type read by label (as the family tree finds parent types), joining these kinds."""
    for t in types:
        fits = t.a_kind in ("*", a) and t.b_kind in ("*", b)
        if fits and (_norm(t.label) in labels or _norm(t.reverse_label) in reverses):
            return t
    return None


@router.post("/events/record", status_code=201)
def record_event(slug: str, body: RecordIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Record as event, in one transaction: a new event (in the chapter's project's bible when the world has several)
    or an existing one; the passage kept as a telling; the ticked entries recorded with the world's "involved" and
    "happened at" types (by label; "linked to" when there are neither), established in this chapter with the passage
    as evidence; an empty time filled. Answers with what it added, for Undo."""
    world, _ = member_world(db, user, slug)
    ch = db.get(Chapter, body.chapter_id)
    if ch is None or ch.project_id not in {p.id for p in world.projects}:
        raise HTTPException(404, "No such chapter.")
    created = False
    if body.event_id is not None:
        e = db.get(Entity, body.event_id)
        if e is None or e.world_id != world.id or e.kind != "event":
            raise HTTPException(404, "No such event.")
    else:
        name = " ".join((body.name or "").split())
        if not name:
            raise HTTPException(422, "Give the event a name.")
        if db.scalar(select(Entity.id).where(Entity.world_id == world.id, Entity.name.ilike(name))) is not None:
            raise HTTPException(409, "The bible already has an entry with that name: pick it instead.")
        e = Entity(world_id=world.id, kind="event", name=name, aliases=[], body="", summary="",
                   project_id=ch.project_id if len(world.projects) > 1 else None, created_by=user.id,
                   updated_by=user.id)
        db.add(e)
        db.flush()
        created = True
    before = event_when(e)
    w = body.when
    given = w is not None and (w.time_at is not None or w.outside_time)
    if given and (before is None or (not created and body.time_choice == "use")):
        assert w is not None
        e.time_chapter_id = None
        e.outside_time = w.outside_time
        e.time_at = None if w.outside_time else w.time_at
        e.time_end = None if w.outside_time else w.time_end
        e.time_label = None if w.outside_time else (" ".join((w.time_label or "").split()) or None)
        e.time_approx = False if w.outside_time else w.time_approx
        e.version += 1
    telling = Telling(world_id=world.id, event_id=e.id, chapter_id=ch.id, passage=body.passage.strip(),
                      created_by=user.id)
    db.add(telling)
    types = list(db.scalars(select(RelationType).where(RelationType.world_id == world.id)
                            .order_by(RelationType.position)))
    related = {r.b_id if r.a_id == e.id else r.a_id for r in db.scalars(
        select(Relationship).where(Relationship.world_id == world.id,
                                   (Relationship.a_id == e.id) | (Relationship.b_id == e.id)))}
    added: list[str] = []
    for x in body.taking:
        other = db.get(Entity, x.entity_id)
        if other is None or other.world_id != world.id or other.id == e.id or other.id in related:
            continue
        if x.role == "place" and other.kind == "place":
            t = _type_by(types, {"happened at"}, {"scene of"}, "event", "place")
        else:
            t = _type_by(types, {"involved"}, {"took part in"}, "event", other.kind)
        t = t or _type_by(types, {"linked to"}, {"linked to"}, "event", other.kind)
        if t is None:
            continue
        # the event on the type's A side, read either way
        a, b = (e, other) if t.a_kind in ("*", "event") and t.b_kind in ("*", other.kind) else (other, e)
        r = Relationship(world_id=world.id, type_id=t.id, a_id=a.id, b_id=b.id, standing="canon",
                         established_in_chapter_id=ch.id, evidence=body.passage.strip()[:5000],
                         from_approx=False, until_approx=False, outside_time=False, created_by=user.id,
                         updated_by=user.id)
        db.add(r)
        db.flush()
        related.add(other.id)
        added.append(str(r.id))
    db.flush()
    if created:
        refresh_world(db, world.id)
    db.commit()
    now = event_when(e)
    return {"event": {"id": str(e.id), "name": e.name, "kind": "event"}, "event_id": str(e.id), "created": created,
            "telling_id": str(telling.id), "relationships": added, "when_before": before, "when": now,
            # another time was given for an event that has one, and it was kept: the page asks Keep … · Use …
            "time_differs": bool(given and before is not None and not created and body.time_choice == "keep" and w and (
                bool(before.get("outside")) != w.outside_time or before.get("at") != w.time_at
                or before.get("chapter") is not None))}


class UndoRecordIn(BaseModel):
    event_id: uuid.UUID
    created: bool
    telling_id: uuid.UUID
    relationships: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    when_before: dict | None = None


@router.post("/events/record/undo")
def undo_record(slug: str, body: UndoRecordIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Undo a Record as event: remove what that save added (the telling, the participants it recorded, the event it
    made) and put the event's time back."""
    world, _ = member_world(db, user, slug)
    for rid in body.relationships:
        r = db.get(Relationship, rid)
        if r is not None and r.world_id == world.id:
            db.delete(r)
    t = db.get(Telling, body.telling_id)
    if t is not None and t.world_id == world.id:
        db.delete(t)
    e = db.get(Entity, body.event_id)
    if e is not None and e.world_id == world.id:
        if body.created:
            db.delete(e)
        else:
            w = body.when_before or {}
            e.time_chapter_id = uuid.UUID(w["chapter"]) if w.get("chapter") else None
            e.time_at, e.time_end, e.time_label = w.get("at"), w.get("end"), w.get("label")
            e.time_approx, e.outside_time = bool(w.get("approx")), bool(w.get("outside"))
            e.version += 1
    db.flush()
    if body.created:
        refresh_world(db, world.id)
    db.commit()
    return {"undone": True}


def project_ids(world: World) -> set[uuid.UUID]:
    return {p.id for p in world.projects}


def chapter_in_world(db: Session, world: World, chapter_id: uuid.UUID | None) -> uuid.UUID | None:
    if chapter_id is None:
        return None
    ch = db.get(Chapter, chapter_id)
    if ch is None or ch.project_id not in project_ids(world):
        raise HTTPException(422, "No such chapter in this world.")
    return ch.id

