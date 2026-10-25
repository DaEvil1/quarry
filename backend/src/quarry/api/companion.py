"""The writing companion's server side (docs/WORLD-MODEL.md §7): the Checks (rules over recorded data, never guesses
from prose), how findings were resolved, the note left for next time in a chapter, and the items tied to a chapter.
The findings about the text itself (proofreading, unrecorded connections, unknown names) are worked out in the
browser, live; this module only stores how they were resolved."""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Chapter,
    Entity,
    Fact,
    Item,
    ItemLink,
    Mention,
    Project,
    RelationType,
    Relationship,
    Resolution,
    SessionNote,
    User,
    World,
)
from .deps import current_user
from .storytime import story_order
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

DEAD_RE = re.compile(r"\b(dead|deceased|died|killed|slain|murdered)\b", re.I)
# facts whose "from" chapter is when someone comes into the story: being named before it is a finding
START_LABELS = ("born", "introduced", "arrives", "first appears")
INSIDE_RE = re.compile(r"^(inside|in|part of|within)$", re.I)
# character–character types read as parenthood, the way the place tree reads "inside" (docs/SPEC.md §12.2): A is
# B's parent when the label ends in "parent of" / "father of" / "mother of" or the reverse in "child of" / "son of" /
# "daughter of"; the mirror image (a label "son of", a reverse "father of") makes B the parent
PARENT_RE = re.compile(r"(^|\s)(parent|father|mother) of$", re.I)
CHILD_RE = re.compile(r"(^|\s)(child|son|daughter) of$", re.I)
# a lineage across generations not recorded (docs/SPEC.md §13.5): "ancestor of" / "descendant of", or the mirror
ANCESTOR_RE = re.compile(r"(^|\s)ancestor of$", re.I)
DESCENDANT_RE = re.compile(r"(^|\s)descendant of$", re.I)


def parent_direction(label: str, reverse: str | None) -> int:
    """1 when a type reads "A parent of B", -1 when it reads "B parent of A", 0 when it isn't parenthood."""
    label, reverse = label.strip(), (reverse or "").strip()
    if PARENT_RE.search(label) or CHILD_RE.search(reverse):
        return 1
    if CHILD_RE.search(label) or PARENT_RE.search(reverse):
        return -1
    return 0


def ancestor_direction(label: str, reverse: str | None) -> int:
    """1 when a type reads "A ancestor of B", -1 when it reads "B ancestor of A", 0 otherwise."""
    label, reverse = label.strip(), (reverse or "").strip()
    if ANCESTOR_RE.search(label) or DESCENDANT_RE.search(reverse):
        return 1
    if DESCENDANT_RE.search(label) or ANCESTOR_RE.search(reverse):
        return -1
    return 0


def plural(role: str) -> str:
    """"two Captains": a role's plural, simply."""
    return role if role.lower().endswith("s") else role + "s"


def _ref(e: Entity) -> dict:
    return {"id": str(e.id), "name": e.name, "kind": e.kind}


def _q(title: str) -> str:
    return f"“{title}”"


def checks(db: Session, world: World) -> list[dict]:
    """Every finding of the continuity rules, in story order."""
    from .labels import several_labels

    several = several_labels(db, world)
    order = story_order(db, world)
    index = {c.id: i for i, (c, _) in enumerate(order)}
    chapter = {c.id: c for c, _ in order}
    entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.world_id == world.id))}
    # how often each entry is named in each chapter of the story (margin notes excluded when mentions were stored)
    named: dict[uuid.UUID, Counter] = defaultdict(Counter)
    if order:
        for m in db.scalars(select(Mention).where(Mention.source_table == "chapter", Mention.source_id.in_(list(index)),
                                                  Mention.kind != "near_miss")):
            named[m.entity_id][m.source_id] += 1
    facts = list(db.scalars(select(Fact).where(Fact.world_id == world.id, Fact.standing == "canon")))
    out: list[dict] = []

    def add(rule: str, key: str, message: str, chapter_id: uuid.UUID | None, *who: Entity, **extra) -> None:  # type: ignore[no-untyped-def]
        ch = chapter.get(chapter_id) if chapter_id else None
        out.append({"rule": rule, "key": key, "message": message,
                    "chapter": {"id": str(ch.id), "title": ch.title} if ch else None,
                    "entities": [_ref(e) for e in who], "_at": index.get(chapter_id, -1) if chapter_id else -1, **extra})

    for f in facts:
        e = entities.get(f.entity_id)
        start = index.get(f.from_chapter_id) if f.from_chapter_id else None
        if e is None or start is None:
            continue
        # named after being recorded dead
        if DEAD_RE.search(f.value) or DEAD_RE.search(f.label):
            for ch_id, n in named[e.id].items():
                if index[ch_id] > start:
                    add("dead_mentioned", f"{e.id}:{ch_id}",
                        f"{e.name} is named in {_q(chapter[ch_id].title)}{f' ({n}×)' if n > 1 else ''}, after being "
                        f"recorded {f.value or f.label} from {_q(chapter[f.from_chapter_id].title)}.", ch_id, e)
        # named before coming into the story
        if f.label.strip().lower() in START_LABELS:
            for ch_id, n in named[e.id].items():
                if index[ch_id] < start:
                    add("before_start", f"{e.id}:{ch_id}",
                        f"{e.name} is named in {_q(chapter[ch_id].title)}, before “{f.label}” from "
                        f"{_q(chapter[f.from_chapter_id].title)}.", ch_id, e)

    # a point-of-view character who isn't in their own chapter
    for c, _ in order:
        pov = entities.get(c.pov_entity_id) if c.pov_entity_id else None
        if pov is not None and not named[pov.id].get(c.id):
            add("pov_absent", f"{c.id}", f"{_q(c.title)} is told from {pov.name}'s point of view, but never names "
                f"{pov.name}.", c.id, pov)

    # spans that run backwards (chapters were reordered after they were set)
    def backwards(obj_id: uuid.UUID, what: str, from_id, until_id, *who: Entity) -> None:  # type: ignore[no-untyped-def]
        a, b = index.get(from_id), index.get(until_id)
        if a is not None and b is not None and a > b:
            add("span_backwards", str(obj_id), f"{what} runs from {_q(chapter[from_id].title)} until "
                f"{_q(chapter[until_id].title)}, which comes earlier in the story.", from_id, *who)

    for f in db.scalars(select(Fact).where(Fact.world_id == world.id)):
        if f.entity_id in entities:
            backwards(f.id, f"{entities[f.entity_id].name}: “{f.label}: {f.value}”", f.from_chapter_id,
                      f.until_chapter_id, entities[f.entity_id])
    types = {t.id: t for t in db.scalars(select(RelationType).where(RelationType.world_id == world.id))}
    rels = list(db.scalars(select(Relationship).where(Relationship.world_id == world.id)))
    for r in rels:
        a, b = entities.get(r.a_id), entities.get(r.b_id)
        if a and b:
            backwards(r.id, f"“{a.name} {types[r.type_id].label} {b.name}”", r.from_chapter_id, r.until_chapter_id,
                      a, b)

    # places inside each other in a circle
    parent: dict[uuid.UUID, uuid.UUID] = {}
    for r in rels:
        t = types[r.type_id]
        a, b = entities.get(r.a_id), entities.get(r.b_id)
        if a and b and a.kind == b.kind == "place" and r.standing == "canon" and (
                INSIDE_RE.match(t.label) or (t.reverse_label or "").lower() == "contains"):
            parent.setdefault(a.id, b.id)
    reported: set[frozenset] = set()
    for start in parent:
        seen = [start]
        up = parent.get(start)
        while up is not None and up not in seen:
            seen.append(up)
            up = parent.get(up)
        if up is not None:
            ring = seen[seen.index(up):]
            if frozenset(ring) not in reported:
                reported.add(frozenset(ring))
                names = " → ".join(entities[x].name for x in ring + [ring[0]])
                add("place_cycle", ":".join(sorted(str(x) for x in ring)), f"Places inside each other in a circle: "
                    f"{names}.", None, *(entities[x] for x in ring))

    # someone recorded as their own ancestor (parenthood, or "ancestor of", in a circle), like a place inside itself
    parents: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for r in rels:
        t = types[r.type_id]
        a, b = entities.get(r.a_id), entities.get(r.b_id)
        way = parent_direction(t.label, t.reverse_label) or ancestor_direction(t.label, t.reverse_label)
        if a and b and a.kind == b.kind == "character" and r.standing == "canon" and way:
            child, parent_id = (b.id, a.id) if way > 0 else (a.id, b.id)
            parents[child].add(parent_id)
    looped: set[frozenset] = set()
    for start in sorted(parents, key=lambda x: entities[x].name.lower()):
        # a path up through the parents that comes back to where it started
        stack: list[tuple[uuid.UUID, list[uuid.UUID]]] = [(start, [start])]
        seen: set[uuid.UUID] = set()
        while stack:
            node, path = stack.pop()
            for up in sorted(parents.get(node, ()), key=str):
                if up == start:
                    ring = frozenset(path)
                    if ring not in looped:
                        looped.add(ring)
                        names = " → ".join(entities[x].name for x in [start, *reversed(path[1:]), start])
                        add("own_ancestor", ":".join(sorted(str(x) for x in ring)),
                            f"{entities[start].name} is recorded as their own ancestor: {names}.", None,
                            *(entities[x] for x in path))
                elif up not in seen:
                    seen.add(up)
                    stack.append((up, [*path, up]))

    # two values of the same fact at once: same start, or an explicit end that runs past the next one's start
    # (a later fact with an open-ended earlier one simply takes over: that's how "dead from chapter 9" works). Not for
    # a label that holds several values for the entry's kind: those values hold together.
    by_label: dict[tuple[uuid.UUID, str], list[Fact]] = defaultdict(list)
    for f in facts:
        by_label[(f.entity_id, " ".join(f.label.split()).lower())].append(f)
    last = len(order) - 1
    for (eid, label_key), group in by_label.items():
        e = entities.get(eid)
        if e is not None and (e.kind, label_key) in several:
            continue
        for i, f1 in enumerate(group):
            for f2 in group[i + 1:]:
                if e is None or f1.value.strip().lower() == f2.value.strip().lower():
                    continue
                s1 = index.get(f1.from_chapter_id, 0) if f1.from_chapter_id else 0
                s2 = index.get(f2.from_chapter_id, 0) if f2.from_chapter_id else 0
                (x, sx), (y, sy) = sorted([(f1, s1), (f2, s2)], key=lambda p: p[1])
                x_end = index.get(x.until_chapter_id, last) if x.until_chapter_id else None
                clash = None
                if sx == sy:
                    clash = sx
                elif x_end is not None and x_end >= sy:
                    clash = sy
                if clash is not None and 0 <= clash <= last:
                    ch = order[clash][0]
                    add("fact_conflict", ":".join(sorted([str(f1.id), str(f2.id)])),
                        f"{e.name}: “{f1.label}” is both “{f1.value}” and “{f2.value}” in {_q(ch.title)}.", ch.id, e,
                        label=f1.label, kind=e.kind)

    # two holders of a one-at-a-time role in the same group at once (docs/SPEC.md §13.4): canon relationships only;
    # a handover (one ends at the chapter where the other starts) is not a clash
    from .labels import one_at_a_time_roles

    single = one_at_a_time_roles(db, world)
    holders: dict[tuple[uuid.UUID, str], list[Relationship]] = defaultdict(list)
    for r in rels:
        if r.role and r.standing == "canon" and " ".join(r.role.split()).lower() in single:
            holders[(r.b_id, " ".join(r.role.split()).lower())].append(r)

    def bounds(r: Relationship) -> tuple[int, int] | None:
        """Where a span runs in the story, both ends in; None for one that runs backwards."""
        s = index.get(r.from_chapter_id, 0) if r.from_chapter_id else 0
        e = index.get(r.until_chapter_id, last) if r.until_chapter_id else last
        return (s, e) if s <= e else None

    for (group_id, _), group in holders.items():
        g = entities.get(group_id)
        for i, r1 in enumerate(group):
            for r2 in group[i + 1:]:
                h1, h2 = entities.get(r1.a_id), entities.get(r2.a_id)
                b1, b2 = bounds(r1), bounds(r2)
                if g is None or h1 is None or h2 is None or r1.a_id == r2.a_id or b1 is None or b2 is None:
                    continue
                (x, bx), (y, by) = sorted([(r1, b1), (r2, b2)], key=lambda p: (p[1][0], p[1][1]))
                start, end = max(bx[0], by[0]), min(bx[1], by[1])
                # a handover: the earlier one ends at the chapter where the later one starts
                if start == end and x.until_chapter_id and x.until_chapter_id == y.from_chapter_id:
                    continue
                if start > end or not order:
                    continue
                ch = order[start][0]
                hx, hy = entities[x.a_id], entities[y.a_id]

                def since(r: Relationship) -> str:
                    return f"from {_q(chapter[r.from_chapter_id].title)}" if r.from_chapter_id in chapter \
                        else "from the start"
                add("role_clash", ":".join(sorted([str(r1.id), str(r2.id)])),
                    f"{g.name} has two {plural(x.role or '')} in {_q(ch.title)}: {hx.name} ({since(x)}) and "
                    f"{hy.name} ({since(y)}).", ch.id, g, hx, hy,
                    end={"id": str(x.id), "name": hx.name}, before={"id": str(y.id), "name": hy.name}
                    if y.from_chapter_id else None)

    out.sort(key=lambda x: (x["_at"], x["rule"], x["message"]))
    for x in out:
        del x["_at"]
    return out


@router.get("/checks")
def list_checks(slug: str, chapter: uuid.UUID | None = Query(default=None), user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> list[dict]:
    """The Checks, each with how it was resolved (if it was). Findings marked intentional are left out."""
    world, _ = member_world(db, user, slug)
    resolved = {(r.rule, r.key): r for r in db.scalars(select(Resolution).where(Resolution.world_id == world.id))}
    out = []
    for f in checks(db, world):
        if chapter is not None and (f["chapter"] or {}).get("id") != str(chapter):
            continue
        r = resolved.get((f["rule"], f["key"]))
        if r is not None and r.outcome == "intentional":
            continue
        out.append({**f, "later": r is not None and r.outcome == "later"})
    return out


# resolutions ----------------------------------------------------------------------------------------------------


class ResolutionIn(BaseModel):
    rule: str = Field(min_length=1, max_length=40)
    key: str = Field(min_length=1, max_length=300)
    outcome: Literal["intentional", "later", "not_connected"]
    note: str | None = Field(default=None, max_length=2000)


def _resolution_out(r: Resolution) -> dict:
    return {"id": str(r.id), "rule": r.rule, "key": r.key, "outcome": r.outcome, "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else None}


@router.get("/resolutions")
def list_resolutions(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    rows = db.scalars(select(Resolution).where(Resolution.world_id == world.id).order_by(Resolution.created_at))
    return [_resolution_out(r) for r in rows]


@router.put("/resolutions")
def resolve(slug: str, body: ResolutionIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    r = db.scalar(select(Resolution).where(Resolution.world_id == world.id, Resolution.rule == body.rule,
                                           Resolution.key == body.key))
    if r is None:
        r = Resolution(world_id=world.id, rule=body.rule, key=body.key, created_by=user.id)
        db.add(r)
    r.outcome = body.outcome
    r.note = (body.note or "").strip() or None
    db.commit()
    db.refresh(r)
    return _resolution_out(r)


@router.delete("/resolutions/{resolution_id}", status_code=204)
def unresolve(slug: str, resolution_id: uuid.UUID, user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    db.execute(delete(Resolution).where(Resolution.id == resolution_id, Resolution.world_id == world.id))
    db.commit()


# getting back into a chapter --------------------------------------------------------------------------------------


def _chapter(db: Session, world: World, chapter_id: uuid.UUID) -> Chapter:
    ch = db.get(Chapter, chapter_id)
    if ch is None or db.get(Project, ch.project_id).world_id != world.id:
        raise HTTPException(404, "No such chapter.")
    return ch


class SessionNoteIn(BaseModel):
    note: str = Field(default="", max_length=2000)
    cursor: int = Field(default=0, ge=0)


@router.get("/chapters/{chapter_id}/session-note")
def get_session_note(slug: str, chapter_id: uuid.UUID, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    _chapter(db, world, chapter_id)
    n = db.get(SessionNote, (chapter_id, user.id))
    return {"note": n.note if n else "", "cursor": n.cursor if n else 0,
            "updated_at": n.updated_at.isoformat() if n and n.updated_at else None}


@router.put("/chapters/{chapter_id}/session-note")
def put_session_note(slug: str, chapter_id: uuid.UUID, body: SessionNoteIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    _chapter(db, world, chapter_id)
    n = db.get(SessionNote, (chapter_id, user.id))
    if n is None:
        n = SessionNote(chapter_id=chapter_id, user_id=user.id)
        db.add(n)
    n.note = body.note.strip()
    n.cursor = body.cursor
    db.commit()
    db.refresh(n)
    return {"note": n.note, "cursor": n.cursor, "updated_at": n.updated_at.isoformat() if n.updated_at else None}


@router.get("/chapters/{chapter_id}/items")
def chapter_items(slug: str, chapter_id: uuid.UUID, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> list[dict]:
    """Open items tied to this chapter (thoughts stashed while writing it, among others)."""
    world, _ = member_world(db, user, slug)
    _chapter(db, world, chapter_id)
    rows = db.scalars(select(Item).join(ItemLink, ItemLink.item_id == Item.id)
                      .where(ItemLink.target_table == "chapter", ItemLink.target_id == chapter_id,
                             Item.world_id == world.id, Item.status == "open")
                      .order_by(Item.created_at))
    return [{"id": str(i.id), "kind": i.kind, "title": i.title, "body": i.body} for i in rows]
