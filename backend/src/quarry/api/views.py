"""Views over the world model (docs/WORLD-MODEL.md §6): everything the relationship graph and the place tree need in
one read, including co-occurrence (two entries named in the same paragraph), computed from the stored mentions when
asked for, never stored as fact."""

from __future__ import annotations

import bisect
import itertools
import uuid
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Entity, Mention, Presence, RelationType, Relationship, User
from .deps import current_user
from .storytime import _paragraph_bounds, story_order
from .world import time_bounds
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")


def _sid(x: uuid.UUID | None) -> str | None:
    return str(x) if x else None


@router.get("/graph")
def graph(slug: str, co: bool = Query(default=False), user: User = Depends(current_user),
          db: Session = Depends(get_db)) -> dict:
    """Entries, relationships (with their spans, so the browser can show any point in the story), "is at" presence,
    and with `co`, co-occurrence per chapter: for each pair of entries, in how many paragraphs of each chapter both
    are named."""
    world, _ = member_world(db, user, slug)
    entities = list(db.scalars(select(Entity).where(Entity.world_id == world.id).order_by(Entity.name)))
    types = {t.id: t for t in db.scalars(select(RelationType).where(RelationType.world_id == world.id))}
    projects = {p.id: p.slug for p in world.projects}
    edges = [{"id": str(r.id), "a": str(r.a_id), "b": str(r.b_id), "type_id": str(r.type_id),
              "label": types[r.type_id].label, "reverse_label": types[r.type_id].reverse_label,
              "standing": r.standing, "from_chapter_id": _sid(r.from_chapter_id),
              "until_chapter_id": _sid(r.until_chapter_id), **time_bounds(r), "role": r.role}
             for r in db.scalars(select(Relationship).where(Relationship.world_id == world.id))]
    presence = [{"entity_id": str(p.entity_id), "place_id": str(p.place_id), "chapter_id": str(p.chapter_id)}
                for p in db.scalars(select(Presence).where(Presence.world_id == world.id))]
    out = {
        # with each entry's level (a project's slug, for the project filter) and a character's gender (for the family
        # tree's words)
        "nodes": [{"id": str(e.id), "name": e.name, "kind": e.kind, "summary": e.summary,
                   "project": projects.get(e.project_id) if e.project_id else None, "gender": e.gender}
                  for e in entities],
        "edges": edges,
        "types": [{"id": str(t.id), "a_kind": t.a_kind, "b_kind": t.b_kind, "label": t.label,
                   "reverse_label": t.reverse_label} for t in sorted(types.values(), key=lambda t: t.position)],
        "presence": presence,
        "cooccurrence": [],
    }
    if co:
        out["cooccurrence"] = cooccurrence(db, world)
    return out


def cooccurrence(db: Session, world) -> list[dict]:  # type: ignore[no-untyped-def]
    chapters = [c for c, _ in story_order(db, world)]
    if not chapters:
        return []
    by_chapter: dict[uuid.UUID, list[tuple[int, uuid.UUID]]] = defaultdict(list)
    for source_id, start, entity_id in db.execute(
            select(Mention.source_id, Mention.start, Mention.entity_id)
            .where(Mention.source_table == "chapter", Mention.source_id.in_([c.id for c in chapters]),
                   Mention.kind != "near_miss")):
        by_chapter[source_id].append((start, entity_id))
    pairs: dict[tuple[uuid.UUID, uuid.UUID], Counter] = defaultdict(Counter)
    for ch in chapters:
        starts = _paragraph_bounds(ch.body)
        paragraphs: dict[int, set[uuid.UUID]] = defaultdict(set)
        for start, eid in by_chapter.get(ch.id, []):
            paragraphs[bisect.bisect_right(starts, start) - 1].add(eid)
        for names in paragraphs.values():
            for a, b in itertools.combinations(sorted(names, key=str), 2):
                pairs[(a, b)][str(ch.id)] += 1
    return [{"a": str(a), "b": str(b), "by_chapter": dict(c)} for (a, b), c in pairs.items()]
