"""The writing companion's server side (docs/WORLD-MODEL.md §7): the Checks (rules over recorded data, never guesses
from prose), how findings were resolved, the note left for next time in a chapter, and the items tied to a chapter.
The findings about the text itself (proofreading, unrecorded connections, unknown names) are worked out in the
browser, live; this module only stores how they were resolved."""

from __future__ import annotations

import math
import re
import uuid
from collections import Counter, defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..clock import INF, TIMED, Clock, time_text
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
# facts whose start is when someone comes into the story: being named before it is a finding. Born and arrives are
# about the world, so they are read on the clock; introduced and first appears are about the reader (book order)
CLOCK_START_LABELS = ("born", "arrives")
START_LABELS = ("introduced", "first appears")
# an "age" fact read as a number when its value starts with one (17, about 60); anything else is never compared
AGE_RE = re.compile(r"^\s*(about\s+|around\s+|roughly\s+|c\.\s*|~\s*)?(\d+(?:\.\d+)?)", re.I)
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
    """Every finding of the continuity rules, listed by chapter in book order. They compare on the clock (docs/SPEC.md
    §13.1.7): happened order, with time bounds; a tale or flashback with no time, a chapter outside time and anything
    outside time are skipped by every check that compares times. With no times and no marks the clock is book order."""
    from .labels import one_at_a_time_roles, several_labels

    several = several_labels(db, world)
    order = story_order(db, world)
    clock = Clock(order)
    unit, units = world.time_unit, world.time_units
    # book order, for listing findings and for "introduced" / "first appears" (about the reader)
    index = {c.id: i for i, (c, _) in enumerate(order)}
    chapter = {c.id: c for c, _ in order}
    entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.world_id == world.id))}
    # how often each entry is named in each chapter of the story (margin notes excluded when mentions were stored),
    # and how often outside the passages told as events: telling of the dead is history, not an appearance
    from .history import passage_spans

    told, _ = passage_spans(db, world, chapter)
    named: dict[uuid.UUID, Counter] = defaultdict(Counter)
    appears: dict[uuid.UUID, Counter] = defaultdict(Counter)
    if order:
        for m in db.scalars(select(Mention).where(Mention.source_table == "chapter", Mention.source_id.in_(list(index)),
                                                  Mention.kind != "near_miss")):
            named[m.entity_id][m.source_id] += 1
            if not any(a <= m.start < b for a, b in told.get(m.source_id, ())):
                appears[m.entity_id][m.source_id] += 1
    facts = [f for f in db.scalars(select(Fact).where(Fact.world_id == world.id, Fact.standing == "canon"))
             if not f.outside_time]
    out: list[dict] = []

    def add(rule: str, key: str, message: str, chapter_id: uuid.UUID | None, *who: Entity, **extra) -> None:  # type: ignore[no-untyped-def]
        ch = chapter.get(chapter_id) if chapter_id else None
        out.append({"rule": rule, "key": key, "message": message,
                    "chapter": {"id": str(ch.id), "title": ch.title} if ch else None,
                    "entities": [_ref(e) for e in who], "_at": index.get(chapter_id, -1) if chapter_id else -1, **extra})

    def when(chapter_id: uuid.UUID | None, t: float | None, approx: bool = False) -> str:
        """A bound in words: a chapter's title, or a time ("year 312")."""
        if t is not None:
            return time_text(unit, units, float(t), None, None, approx)
        c = chapter.get(chapter_id) if chapter_id else None
        return _q(c.title) if c else "a chapter no longer in the book"

    def placed(x) -> bool:  # type: ignore[no-untyped-def]
        """A fact's start can be placed: a time, or a chapter on the clock."""
        return x.from_time is not None or clock.pos(x.from_chapter_id) is not None

    def side_of_start(x, cid: uuid.UUID) -> int | None:  # type: ignore[no-untyped-def]
        """-1 when the chapter is before the fact's start on the clock, 1 when after it, 0 at it; None when it can't
        be compared (a tale with no time, outside time, no set time against a time)."""
        c = clock.get(cid)
        if c is None or not c.comparable:
            return None
        if x.from_time is not None:
            if c.set_time is None:
                return None
            return -1 if c.set_time < float(x.from_time) else 1
        a = clock.get(x.from_chapter_id)
        if a is None or a.place is None:
            return None
        return (c.place > a.place) - (c.place < a.place)

    for f in facts:
        e = entities.get(f.entity_id)
        if e is None or not placed(f):
            continue
        since = when(f.from_chapter_id, f.from_time, f.from_approx)
        # named after being recorded dead, on the clock
        if DEAD_RE.search(f.value) or DEAD_RE.search(f.label):
            for ch_id, n in appears[e.id].items():
                if side_of_start(f, ch_id) == 1:
                    add("dead_mentioned", f"{e.id}:{ch_id}",
                        f"{e.name} is named in {_q(chapter[ch_id].title)}{f' ({n}×)' if n > 1 else ''}, after being "
                        f"recorded {f.value or f.label} from {since}.", ch_id, e)
        label = f.label.strip().lower()
        # named before coming into the story: born and arrives are about the world (the clock); introduced and first
        # appears are about the reader (book order)
        if label in CLOCK_START_LABELS:
            for ch_id, n in named[e.id].items():
                if side_of_start(f, ch_id) == -1:
                    add("before_start", f"{e.id}:{ch_id}",
                        f"{e.name} is named in {_q(chapter[ch_id].title)}, before “{f.label}” from {since}.", ch_id, e)
        elif label in START_LABELS and f.from_chapter_id in index:
            start = index[f.from_chapter_id]
            for ch_id, n in named[e.id].items():
                if index[ch_id] < start:
                    add("before_start", f"{e.id}:{ch_id}",
                        f"{e.name} is named in {_q(chapter[ch_id].title)}, before “{f.label}” from {since}.", ch_id, e)

    # a point-of-view character who isn't in their own chapter
    for c, _ in order:
        pov = entities.get(c.pov_entity_id) if c.pov_entity_id else None
        if pov is not None and not named[pov.id].get(c.id):
            add("pov_absent", f"{c.id}", f"{_q(c.title)} is told from {pov.name}'s point of view, but never names "
                f"{pov.name}.", c.id, pov)

    # spans that run backwards on the clock (chapters were reordered, or given times, after they were set)
    def backwards(x, what: str, *who: Entity) -> None:  # type: ignore[no-untyped-def]
        if x.outside_time or not clock.backwards(x):
            return
        add("span_backwards", str(x.id), f"{what} runs from {when(x.from_chapter_id, x.from_time, x.from_approx)} "
            f"until {when(x.until_chapter_id, x.until_time, x.until_approx)}, which comes earlier in the story.",
            x.from_chapter_id or x.until_chapter_id, *who)

    for f in db.scalars(select(Fact).where(Fact.world_id == world.id)):
        if f.entity_id in entities:
            backwards(f, f"{entities[f.entity_id].name}: “{f.label}: {f.value}”", entities[f.entity_id])
    types = {t.id: t for t in db.scalars(select(RelationType).where(RelationType.world_id == world.id))}
    rels = list(db.scalars(select(Relationship).where(Relationship.world_id == world.id)))
    for r in rels:
        a, b = entities.get(r.a_id), entities.get(r.b_id)
        if a and b:
            backwards(r, f"“{a.name} {types[r.type_id].label} {b.name}”", a, b)

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
        seen_ids: set[uuid.UUID] = set()
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
                elif up not in seen_ids:
                    seen_ids.add(up)
                    stack.append((up, [*path, up]))

    # where two spans first hold together on the clock, among chapters it can compare (None when they never do)
    on_clock = [x for x in clock.happened if x.comparable]

    def comparable(p: tuple | None, q: tuple | None) -> bool:
        """Two starts or ends can be compared: chapters, or a time against a chapter with a set time (or a time)."""
        if p is None or q is None or p[0] == -INF or q[0] == -INF:
            return True
        if p[2] in (-1, INF) or q[2] in (-1, INF):
            return p[0] == TIMED and q[0] == TIMED
        return True

    def first_together(x, y) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
        for c in on_clock:
            if clock.holds(x, c.id) and clock.holds(y, c.id):
                return c.id
        return None

    def ordered(s1, s2):  # type: ignore[no-untyped-def]
        """(earlier, its start, later, its start), unbounded starts first."""
        low = (-INF, 0.0, 0)
        k1, k2 = clock.start(s1) or low, clock.start(s2) or low
        return (s1, k1, s2, k2) if k1 <= k2 else (s2, k2, s1, k1)

    # two values of the same fact at once: same start, or an explicit end that runs past the next one's start (a later
    # fact with an open-ended earlier one simply takes over: that's how "dead from chapter 9" works). Not for a label
    # that holds several values for the entry's kind: those values hold together.
    by_label: dict[tuple[uuid.UUID, str], list[Fact]] = defaultdict(list)
    for f in facts:
        by_label[(f.entity_id, " ".join(f.label.split()).lower())].append(f)
    for (eid, label_key), group in by_label.items():
        e = entities.get(eid)
        if e is not None and (e.kind, label_key) in several:
            continue
        for i, f1 in enumerate(group):
            for f2 in group[i + 1:]:
                if e is None or f1.value.strip().lower() == f2.value.strip().lower():
                    continue
                x, sx, y, sy = ordered(f1, f2)
                ex = clock.end(x)
                if not comparable(sx, sy) or not comparable(ex, sy):
                    continue
                if sx != sy and (ex is None or ex < sy):
                    continue
                at = first_together(x, y)
                if at is not None:
                    add("fact_conflict", ":".join(sorted([str(f1.id), str(f2.id)])),
                        f"{e.name}: “{f1.label}” is both “{f1.value}” and “{f2.value}” in {_q(chapter[at].title)}.", at,
                        e, label=f1.label, kind=e.kind)

    # two holders of a one-at-a-time role in the same group at once (docs/SPEC.md §13.4): canon relationships only,
    # on the clock; a handover (one ends at the chapter or time where the other starts) is not a clash
    single = one_at_a_time_roles(db, world)
    holders: dict[tuple[uuid.UUID, str], list[Relationship]] = defaultdict(list)
    for r in rels:
        if r.role and r.standing == "canon" and not r.outside_time and " ".join(r.role.split()).lower() in single:
            holders[(r.b_id, " ".join(r.role.split()).lower())].append(r)
    for (group_id, _), group in holders.items():
        g = entities.get(group_id)
        for i, r1 in enumerate(group):
            for r2 in group[i + 1:]:
                h1, h2 = entities.get(r1.a_id), entities.get(r2.a_id)
                if g is None or h1 is None or h2 is None or r1.a_id == r2.a_id or clock.backwards(r1) \
                        or clock.backwards(r2):
                    continue
                x, sx, y, sy = ordered(r1, r2)
                if not comparable(sx, sy):
                    continue
                handover = (x.until_chapter_id is not None and x.until_chapter_id == y.from_chapter_id) or (
                    x.until_time is not None and y.from_time is not None and float(x.until_time) == float(y.from_time))
                at = None if handover else first_together(x, y)
                if at is None:
                    continue
                hx, hy = entities[x.a_id], entities[y.a_id]

                def since(r: Relationship) -> str:
                    if r.from_chapter_id is None and r.from_time is None:
                        return "from the start"
                    return f"from {when(r.from_chapter_id, r.from_time, r.from_approx)}"
                add("role_clash", ":".join(sorted([str(r1.id), str(r2.id)])),
                    f"{g.name} has two {plural(x.role or '')} in {_q(chapter[at].title)}: {hx.name} ({since(x)}) and "
                    f"{hy.name} ({since(y)}).", at, g, hx, hy,
                    end={"id": str(x.id), "name": hx.name},
                    before={"id": str(y.id), "name": hy.name} if (y.from_chapter_id or y.from_time is not None) else None)

    # a computed age that disagrees with an "age" fact (docs/SPEC.md §13.2.4): canon facts, chapters on the clock; a
    # birth is a "born" fact or a canon birth event they are related to
    births = life_events(db, world, clock, entities, rels, "birth")
    for e in entities.values():
        if e.kind != "character":
            continue
        mine = [f for f in facts if f.entity_id == e.id]
        born = birth_of(clock, mine) or births.get(e.id)
        if born is None:
            continue
        b, b_approx, born_fact = born
        her = {"female": ("she", "her", "her"), "male": ("he", "him", "his")}.get(e.gender or "", ("they", "them", "their"))
        chapters_named = set(named[e.id])
        for a in mine:
            if " ".join(a.label.split()).lower() != "age":
                continue
            m = AGE_RE.match(a.value or "")
            if not m:
                continue
            stated, about = float(m.group(2)), bool(m.group(1)) or b_approx
            where = [c for c in on_clock if c.set_time is not None and (c.id in chapters_named or c.id == a.from_chapter_id)
                     and clock.holds(a, c.id)]
            for c in where:
                computed = math.floor(c.set_time - b)
                if computed < 0:
                    continue
                approx = about or c.set_approx
                tol = 1 + (0.1 * computed if approx else 0)
                if abs(computed - stated) > tol:
                    add("age_conflict", f"{a.id}:{born_fact.id}",
                        f"{e.name} is {m.group(0).strip()} in {_q(c.title)} by {her[2]} age, but born in "
                        f"{time_text(unit, units, b, None, None, b_approx)} makes {her[1]} "
                        f"{'about ' if approx else ''}{computed}.", c.id, e)
                    break

    out.sort(key=lambda x: (x["_at"], x["rule"], x["message"]))
    for x in out:
        del x["_at"]
    return out


def life_events(db: Session, world: World, clock: Clock, entities: dict, rels: list[Relationship],
                kind: str) -> dict[uuid.UUID, tuple[float, bool, Entity]]:
    """Per character, the time of a canon birth (or death) event they are related to: an event whose canon type is
    "birth" (or "death"), placed in time."""
    from .history import event_time

    typed = {f.entity_id for f in db.scalars(select(Fact).where(Fact.world_id == world.id, Fact.standing == "canon"))
             if " ".join(f.label.split()).lower() == "type" and " ".join(f.value.split()).lower() == kind}
    out: dict[uuid.UUID, tuple[float, bool, Entity]] = {}
    for r in rels:
        if r.standing != "canon":
            continue
        for ev_id, who_id in ((r.a_id, r.b_id), (r.b_id, r.a_id)):
            ev, who = entities.get(ev_id), entities.get(who_id)
            if ev is None or who is None or ev.id not in typed or who.kind != "character" or who.id in out:
                continue
            t, approx = event_time(ev, clock)
            if t is not None:
                out[who.id] = (t, approx, ev)
    return out


def birth_of(clock: Clock, facts: list[Fact]) -> tuple[float, bool, Fact] | None:
    """A character's birth time on the clock: the start of their canon "born" fact, a time or the set time of a chapter
    (docs/SPEC.md §13.2.4). None when it can't be placed."""
    for f in facts:
        if " ".join(f.label.split()).lower() != "born" or f.outside_time or f.standing != "canon":
            continue
        if f.from_time is not None:
            return float(f.from_time), bool(f.from_approx), f
        x = clock.get(f.from_chapter_id)
        if x is not None and x.comparable and x.set_time is not None:
            return x.set_time, x.set_approx, f
    return None


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
    """Open items tied to this chapter (thoughts stashed while writing it, and items made from its passages)."""
    world, _ = member_world(db, user, slug)
    _chapter(db, world, chapter_id)
    return linked_items(db, world, "chapter", chapter_id)


def linked_items(db: Session, world: World, table: str, target_id: uuid.UUID) -> list[dict]:
    """Open items linked to a chapter or journal entry, each with the passage it was made from (if any)."""
    rows = db.execute(select(Item, ItemLink.passage).join(ItemLink, ItemLink.item_id == Item.id)
                      .where(ItemLink.target_table == table, ItemLink.target_id == target_id,
                             Item.world_id == world.id, Item.status == "open")
                      .order_by(Item.created_at)).all()
    return [{"id": str(i.id), "kind": i.kind, "title": i.title, "body": i.body, "passage": passage}
            for i, passage in rows]
