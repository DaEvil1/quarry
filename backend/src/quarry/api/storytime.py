"""Story time: the order of chapters across a world's projects, the clock that facts and relationships are dated by
(happened order, docs/SPEC.md §13.1), "is at" presence, and the Where-everyone-is grid (docs/WORLD-MODEL.md §4)."""

from __future__ import annotations

import uuid
import bisect
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import Clock, time_text
from ..db import get_db
from ..models import Chapter, Entity, Mention, Presence, Project, User, World
from .deps import current_user
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")


def story_order(db: Session, world: World) -> list[tuple[Chapter, Project]]:
    """The book's chapters in story order: projects in their order, then chapters in theirs. Experiments and retired
    chapters are not part of the story."""
    rows = db.execute(
        select(Chapter, Project).join(Project, Project.id == Chapter.project_id)
        .where(Project.world_id == world.id, Chapter.state == "current")
        .order_by(Project.position, Project.created_at, Chapter.position, Chapter.created_at)
    ).all()
    return [(c, p) for c, p in rows]


def story_index(db: Session, world: World) -> dict[uuid.UUID, int]:
    return {c.id: i for i, (c, _) in enumerate(story_order(db, world))}


def world_clock(db: Session, world: World) -> Clock:
    """The book's chapters placed in happened order."""
    return Clock(story_order(db, world))


def check_span(db: Session, world: World, span) -> None:  # type: ignore[no-untyped-def]
    """A span must run forwards on the clock: it starts no later than it ends (a chapter or a time on each side)."""
    has_from = span.from_chapter_id is not None or span.from_time is not None
    has_until = span.until_chapter_id is not None or span.until_time is not None
    if has_from and has_until and world_clock(db, world).backwards(span):
        raise HTTPException(422, "“From” must come before “until” in the story.")


def times(c: Chapter) -> dict:
    """A chapter's own time and mark, as the API shows them."""
    return {"time_at": float(c.time_at) if c.time_at is not None else None,
            "time_end": float(c.time_end) if c.time_end is not None else None,
            "time_label": c.time_label, "time_approx": c.time_approx, "outside_time": c.outside_time,
            "told_as": c.told_as}


@router.get("/timeline")
def timeline(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """The chapters in story order, each with its point-of-view entry and its project's gap length (for the mentions
    strip, docs/SPEC.md §12.1), its time and mark, its set time and its place on the clock (docs/SPEC.md §13.1):
    `clock` is its place in happened order, null outside time; `early` a tale or flashback set before the story."""
    world, _ = member_world(db, user, slug)
    order = story_order(db, world)
    clock = Clock(order)
    from ..models import ChapterStatus

    ids = [p.id for p in world.projects]
    status = {s.id: s.label for s in db.scalars(select(ChapterStatus).where(ChapterStatus.project_id.in_(ids)))} if ids else {}
    out = []
    for i, (c, p) in enumerate(order):
        x = clock.by_id[c.id]
        out.append({"id": str(c.id), "title": c.title, "project": p.slug, "project_name": p.name, "index": i,
                    "pov": str(c.pov_entity_id) if c.pov_entity_id else None, "gap_chapters": p.gap_chapters,
                    **times(c), "set_time": x.set_time, "set_approx": x.set_approx, "early": x.early,
                    "clock": x.place, "summary": c.summary, "status": status.get(c.status_id) if c.status_id else None})
    return out


# presence -------------------------------------------------------------------------------------------------------


class PresenceIn(BaseModel):
    place_id: uuid.UUID
    note: str | None = Field(default=None, max_length=2000)


def _ref(e: Entity) -> dict:
    return {"id": str(e.id), "name": e.name, "kind": e.kind}


def _world_entity(db: Session, world: World, entity_id: uuid.UUID) -> Entity:
    e = db.get(Entity, entity_id)
    if e is None or e.world_id != world.id:
        raise HTTPException(404, "No such entry.")
    return e


def _world_chapter(db: Session, world: World, chapter_id: uuid.UUID) -> Chapter:
    ch = db.get(Chapter, chapter_id)
    if ch is None or db.get(Project, ch.project_id).world_id != world.id:
        raise HTTPException(404, "No such chapter.")
    return ch


@router.get("/chapters/{chapter_id}/presence")
def chapter_presence(slug: str, chapter_id: uuid.UUID, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    _world_chapter(db, world, chapter_id)
    rows = db.scalars(select(Presence).where(Presence.chapter_id == chapter_id))
    return [{"entity_id": str(p.entity_id), "place": _ref(db.get(Entity, p.place_id)), "note": p.note} for p in rows]


@router.put("/chapters/{chapter_id}/presence/{entity_id}")
def set_presence(slug: str, chapter_id: uuid.UUID, entity_id: uuid.UUID, body: PresenceIn,
                 user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Record that an entry is at a place in this chapter (replacing where it was recorded before)."""
    world, _ = member_world(db, user, slug)
    _world_chapter(db, world, chapter_id)
    e = _world_entity(db, world, entity_id)
    place = _world_entity(db, world, body.place_id)
    if place.kind != "place":
        raise HTTPException(422, "Only a place can be where someone is.")
    if place.id == e.id:
        raise HTTPException(422, "A place can't be inside itself here.")
    p = db.scalar(select(Presence).where(Presence.entity_id == e.id, Presence.chapter_id == chapter_id))
    if p is None:
        p = Presence(world_id=world.id, entity_id=e.id, chapter_id=chapter_id, place_id=place.id, created_by=user.id)
        db.add(p)
    p.place_id = place.id
    p.note = (body.note or "").strip() or None
    db.commit()
    return {"entity_id": str(e.id), "place": _ref(place), "note": p.note}


@router.delete("/chapters/{chapter_id}/presence/{entity_id}", status_code=204)
def clear_presence(slug: str, chapter_id: uuid.UUID, entity_id: uuid.UUID, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    _world_chapter(db, world, chapter_id)
    p = db.scalar(select(Presence).where(Presence.entity_id == entity_id, Presence.chapter_id == chapter_id,
                                         Presence.world_id == world.id))
    if p is not None:
        db.delete(p)
        db.commit()


# where everyone is ----------------------------------------------------------------------------------------------


def _paragraph_bounds(text: str) -> list[int]:
    """Where each paragraph starts (a paragraph is a line of the chapter)."""
    starts = [0]
    i = text.find("\n")
    while i >= 0:
        starts.append(i + 1)
        i = text.find("\n", i + 1)
    return starts


def derived_places(body: str, mentions: list[tuple[int, uuid.UUID, str]]) -> dict[uuid.UUID, uuid.UUID]:
    """For each character in a chapter, the place most often named in the same paragraph as them, if any.
    `mentions` are (start, entity id, entity kind)."""
    starts = _paragraph_bounds(body)
    paragraphs: dict[int, tuple[set[uuid.UUID], list[uuid.UUID]]] = defaultdict(lambda: (set(), []))
    for start, eid, kind in mentions:
        para = bisect.bisect_right(starts, start) - 1
        chars, places = paragraphs[para]
        if kind == "character":
            chars.add(eid)
        elif kind == "place":
            places.append(eid)
    counts: dict[uuid.UUID, Counter] = defaultdict(Counter)
    for chars, places in paragraphs.values():
        for c in chars:
            counts[c].update(places)
    return {c: cnt.most_common(1)[0][0] for c, cnt in counts.items() if cnt}


KIND_NAMES = ("character", "place", "faction", "culture", "species", "event", "object", "term", "other")


def _ids(text: str | None) -> list[str]:
    return [x.strip() for x in (text or "").split(",") if x.strip()]


@router.get("/where")
def where_everyone_is(slug: str, project: str | None = Query(default=None), kinds: str | None = Query(default=None),
                      entities: str | None = Query(default=None), user: User = Depends(current_user),
                      db: Session = Depends(get_db)) -> dict:
    """Entries down, chapters across (docs/SPEC.md §12.3). Rows: every entry of the chosen `kinds` (characters when
    none are given) named in the chapters shown, plus the `entities` picked by hand, in order of first appearance;
    limited to a project, the kind rows leave out other projects' entries. Each cell: how often the chapter names the
    entry; for a character the place recorded with "is at", else the place derived from the text (named in the same
    paragraph); for a place, who is recorded "is at" there."""
    world, _ = member_world(db, user, slug)
    order = [(c, p) for c, p in story_order(db, world) if project is None or p.slug == project]
    chosen_project = next((p.id for p in world.projects if p.slug == project), None) if project else None
    wanted = [k for k in _ids(kinds) if k in KIND_NAMES] if kinds is not None else ["character"]
    picked: list[uuid.UUID] = []
    for x in _ids(entities):
        try:
            picked.append(uuid.UUID(x))
        except ValueError:
            raise HTTPException(422, "Not an entry id.") from None
    chapter_ids = [c.id for c, _ in order]
    all_entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.world_id == world.id))}
    mentions: dict[uuid.UUID, list[tuple[int, uuid.UUID, str]]] = defaultdict(list)
    if chapter_ids:
        for m in db.scalars(select(Mention).where(Mention.source_table == "chapter", Mention.source_id.in_(chapter_ids),
                                                  Mention.kind != "near_miss").order_by(Mention.start)):
            e = all_entities.get(m.entity_id)
            if e is not None:
                mentions[m.source_id].append((m.start, e.id, e.kind))
    recorded: dict[tuple[uuid.UUID, uuid.UUID], Presence] = {}
    if chapter_ids:
        for p in db.scalars(select(Presence).where(Presence.chapter_id.in_(chapter_ids))):
            recorded[(p.entity_id, p.chapter_id)] = p

    def as_row(e: Entity) -> bool:
        """A kind row: of a chosen kind, and (limited to a project) in the world's bible or that project's."""
        return e.kind in wanted and (chosen_project is None or e.project_id in (None, chosen_project))

    first_seen: dict[uuid.UUID, tuple[int, int]] = {}
    cells: dict[uuid.UUID, dict[str, dict]] = defaultdict(dict)
    events: dict[str, list[dict]] = {}
    for i, (ch, _) in enumerate(order):
        found = mentions.get(ch.id, [])
        derived = derived_places(ch.body, found)
        counts = Counter(eid for _, eid, _ in found)
        here = {eid for (eid, cid) in recorded if cid == ch.id}
        people: dict[uuid.UUID, list[dict]] = defaultdict(list)
        for eid in sorted(here, key=lambda x: all_entities[x].name.lower()):
            people[recorded[(eid, ch.id)].place_id].append(_ref(all_entities[eid]))
        first_at: dict[uuid.UUID, int] = {}
        for start, eid, _ in found:
            first_at.setdefault(eid, start)
        for eid in set(counts) | here | set(people):
            e = all_entities[eid]
            if not (as_row(e) or eid in picked):
                continue
            first_seen.setdefault(eid, (i, first_at.get(eid, len(ch.body))))
            rec = recorded.get((eid, ch.id))
            der = derived.get(eid) if e.kind == "character" else None
            cells[eid][str(ch.id)] = {
                "count": counts.get(eid, 0),
                "recorded": _ref(all_entities[rec.place_id]) if rec else None,
                "note": rec.note if rec else None,
                "derived": _ref(all_entities[der]) if der and not rec else None,
                "present": eid in counts,
                "people": people.get(eid, []) if e.kind == "place" else [],
            }
        evs = []
        for _, eid, kind in found:
            if kind == "event" and all(x["id"] != str(eid) for x in evs):
                evs.append(_ref(all_entities[eid]))
        if evs:
            events[str(ch.id)] = evs
    never = len(order)
    shown = set(first_seen) | {x for x in picked if x in all_entities}
    rows = [{"entity": _ref(all_entities[eid]), "added": eid in picked, "cells": cells.get(eid, {})}
            for eid in sorted(shown, key=lambda x: (*first_seen.get(x, (never, 0)), all_entities[x].name.lower()))]
    pov = {c.id: all_entities.get(c.pov_entity_id) if c.pov_entity_id else None for c, _ in order}
    # each chapter's head shows its set time and mark; the grid can be read in happened order (docs/SPEC.md §13.1.4)
    clock = world_clock(db, world)
    head = {}
    for c, _ in order:
        x = clock.by_id[c.id]
        head[c.id] = {**times(c), "set_time": x.set_time, "set_approx": x.set_approx, "early": x.early,
                      "clock": x.place,
                      "set_text": time_text(world.time_unit, world.time_units, x.set_time, None, None, x.set_approx,
                                            c.outside_time)}
    return {
        "chapters": [{"id": str(c.id), "title": c.title, "project": p.slug, "project_name": p.name,
                      "pov": _ref(pov[c.id]) if pov[c.id] else None, **head[c.id]} for c, p in order],
        "rows": rows,
        "events": events,
    }
