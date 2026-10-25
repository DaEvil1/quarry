"""Decisions with follow-ups (docs/SPEC.md §16): the planned facts and relationships and the tasks that carry a
decision out, the state worked out from them, and the gap a written chapter shows while a planned change tied to it
is still to do.

A follow-up is only the link (`decision_followups`). Its state is read from its row each time:

- to do: a fact or relationship planned or rumour, a task open or deferred;
- done: a fact or relationship canon, a task accepted or harvested;
- dropped: by Drop, by deleting its row (dated), by losing the row to a cascade (undated), or a task rejected.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..clock import time_text
from ..db import get_db
from ..mentions import refresh_source
from ..models import (
    Chapter,
    Decision,
    DecisionFollowup,
    DecisionLink,
    Entity,
    Fact,
    Item,
    ItemLink,
    Mention,
    Project,
    RelationType,
    Relationship,
    Resolution,
    User,
    World,
)
from .deps import current_user
from .manuscript import words
from .storytime import world_clock
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

TABLES = ("fact", "relationship", "item")
TODO_STANDINGS = ("planned", "rumour")
OPEN_TASKS = ("open", "deferred")
DONE_TASKS = ("accepted", "harvested")
# "Not yet" on a gap line is a resolution of this rule, keyed "<follow-up id>:<chapter id>" (docs/SPEC.md §16.4)
GAP_RULE = "followup_gap"
# at most this many chapters a decision names are offered (§16.1)
NAMED_CHAPTERS = 3
NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
                "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty")
CHAPTER_RE = re.compile(r"\b(?:chapter|ch\.?)\s+(\d{1,3}|" + "|".join(NUMBER_WORDS) + r")\b", re.I)


# the state ------------------------------------------------------------------------------------------------------


def state_of(fu: DecisionFollowup, standing: str | None = None, status: str | None = None) -> str:
    """todo, done or dropped: worked out from the row (its standing or status), never stored."""
    if fu.dropped_on is not None or not (fu.fact_id or fu.relationship_id or fu.item_id):
        return "dropped"
    if fu.item_id:
        if status in OPEN_TASKS:
            return "todo"
        return "done" if status in DONE_TASKS else "dropped"
    return "todo" if standing in TODO_STANDINGS else "done"


def _rows_of(db: Session, fus: list[DecisionFollowup]) -> tuple[dict, dict, dict]:
    facts = {f.id: f for f in db.scalars(select(Fact).where(Fact.id.in_([x.fact_id for x in fus if x.fact_id])))}
    rels = {r.id: r for r in db.scalars(select(Relationship).where(
        Relationship.id.in_([x.relationship_id for x in fus if x.relationship_id])))}
    items = {i.id: i for i in db.scalars(select(Item).where(Item.id.in_([x.item_id for x in fus if x.item_id])))}
    return facts, rels, items


def _state(fu: DecisionFollowup, facts: dict, rels: dict, items: dict) -> str:
    row = facts.get(fu.fact_id) or rels.get(fu.relationship_id)
    item = items.get(fu.item_id)
    return state_of(fu, row.standing if row else None, item.status if item else None)


def counts_for(db: Session, decision_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    """Per decision: how many follow-ups are to do, done and dropped. A decision with none has no entry."""
    out: dict[uuid.UUID, dict[str, int]] = {}
    if not decision_ids:
        return out
    fus = list(db.scalars(select(DecisionFollowup).where(DecisionFollowup.decision_id.in_(decision_ids))))
    rows = _rows_of(db, fus)
    for fu in fus:
        c = out.setdefault(fu.decision_id, {"todo": 0, "done": 0, "dropped": 0})
        c[_state(fu, *rows)] += 1
    return out


def open_decisions(db: Session, world: World) -> dict[uuid.UUID, dict[str, int]]:
    """The decisions of a world with something still to do, and their counts."""
    ids = list(db.scalars(select(DecisionFollowup.decision_id).join(Decision, Decision.id == DecisionFollowup.decision_id)
                          .where(Decision.world_id == world.id, DecisionFollowup.dropped_on.is_(None)).distinct()))
    return {k: v for k, v in counts_for(db, ids).items() if v["todo"]}


def follows_of(db: Session, table: str, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    """The decisions each row follows (docs/SPEC.md §16.1): its date and text, oldest first."""
    out: dict[uuid.UUID, list[dict]] = defaultdict(list)
    if not ids:
        return out
    col = {"fact": DecisionFollowup.fact_id, "relationship": DecisionFollowup.relationship_id,
           "item": DecisionFollowup.item_id}[table]
    for fu, d in db.execute(select(DecisionFollowup, Decision).join(Decision, Decision.id == DecisionFollowup.decision_id)
                            .where(col.in_(ids)).order_by(Decision.decided_on, Decision.created_at)).all():
        out[getattr(fu, f"{table}_id")].append({"id": str(d.id), "decided_on": d.decided_on.isoformat(),
                                               "text": d.text, "followup_id": str(fu.id)})
    return out


# the row in words -----------------------------------------------------------------------------------------------


class Words:
    """Chapters and times in words, for one world: "chapter 9", "chapter 9, The Drowned Bell", "year 412"."""

    def __init__(self, db: Session, world: World) -> None:
        self.world = world
        projects = {p.id: p for p in world.projects}
        self.chapters = {c.id: c for c in db.scalars(select(Chapter).where(Chapter.project_id.in_(list(projects))))} \
            if projects else {}

    def chapter(self, chapter_id: uuid.UUID | None, long: bool = False, this: uuid.UUID | None = None) -> str:
        if chapter_id is not None and chapter_id == this:
            return "this chapter"
        c = self.chapters.get(chapter_id) if chapter_id else None
        if c is None:
            return "a chapter no longer in the book"
        if c.state != "current":
            return c.title
        return f"chapter {c.position + 1}, {c.title}" if long else f"chapter {c.position + 1}"

    def time(self, t: float | None, approx: bool) -> str:
        return time_text(self.world.time_unit, self.world.time_units, float(t), None, None, approx) if t is not None else ""

    def span(self, x: Fact | Relationship, long: bool = False, this: uuid.UUID | None = None) -> str:
        if x.outside_time:
            return "outside time"
        a = self.chapter(x.from_chapter_id, long, this) if x.from_chapter_id else self.time(x.from_time, x.from_approx)
        b = self.chapter(x.until_chapter_id, long, this) if x.until_chapter_id else self.time(x.until_time, x.until_approx)
        if a and b:
            return f"{a} – {b}"
        return f"from {a}" if a else f"until {b}" if b else ""


def fact_words(w: Words, f: Fact, name: str, long: bool = False, this: uuid.UUID | None = None, sep: str = " · ") -> str:
    what = f"{name} · {f.label}: {f.value}" if f.value else f"{name} · {f.label}"
    span = w.span(f, long, this)
    return f"{what}{sep}{span}" if span else what


def relationship_words(w: Words, r: Relationship, t: RelationType | None, a: str, b: str, long: bool = False,
                       this: uuid.UUID | None = None, sep: str = " · ") -> str:
    what = f"{a} {t.label if t else 'related to'} {b}" + (f" · {r.role}" if r.role else "")
    span = w.span(r, long, this)
    return f"{what}{sep}{span}" if span else what


def task_words(i: Item) -> str:
    return f"task: {(i.title or i.body.split(chr(10), 1)[0]).strip()}"


def what_of(db: Session, world: World, table: str, row) -> str:  # type: ignore[no-untyped-def]
    """The words kept on a follow-up, for when its row is gone (docs/SPEC.md §16.6)."""
    w = Words(db, world)
    if table == "fact":
        e = db.get(Entity, row.entity_id)
        return fact_words(w, row, e.name if e else "?")
    if table == "relationship":
        a, b = db.get(Entity, row.a_id), db.get(Entity, row.b_id)
        return relationship_words(w, row, db.get(RelationType, row.type_id), a.name if a else "?", b.name if b else "?")
    return task_words(row)


def refresh_what(db: Session, world: World, table: str, row) -> None:  # type: ignore[no-untyped-def]
    """A row saved through its endpoint: its follow-ups' words are written again, so they read right if it goes."""
    col = getattr(DecisionFollowup, f"{table}_id")
    fus = list(db.scalars(select(DecisionFollowup).where(col == row.id)))
    if fus:
        what = what_of(db, world, table, row)
        for fu in fus:
            fu.what = what


def drop_for_deleted(db: Session, world: World, table: str, row) -> None:  # type: ignore[no-untyped-def]
    """A row deleted through the API: its follow-ups are dropped today, keeping its words (§16.6)."""
    col = getattr(DecisionFollowup, f"{table}_id")
    fus = list(db.scalars(select(DecisionFollowup).where(col == row.id)))
    if fus:
        what = what_of(db, world, table, row)
        for fu in fus:
            fu.what = what
            if fu.dropped_on is None:
                fu.dropped_on = date.today()
            setattr(fu, f"{table}_id", None)
        db.flush()


# the chapters a decision names ----------------------------------------------------------------------------------


def named_chapters(db: Session, world: World, d: Decision) -> list[dict]:
    """The current chapters the decision's text names (docs/SPEC.md §16.1), at most three, in the order they appear in
    it: "chapter 9", "ch 9", "ch. 9" or "chapter nine" by position in its project (once per project with that many
    chapters, for a decision with no project), and a chapter's full title as a whole phrase, any capitals (a one-word
    title shorter than five letters is not matched)."""
    projects = [p for p in world.projects if d.project_id is None or p.id == d.project_id]
    if not projects:
        return []
    by_project: dict[uuid.UUID, list[Chapter]] = {p.id: [] for p in projects}
    for c in db.scalars(select(Chapter).where(Chapter.project_id.in_(list(by_project)), Chapter.state == "current")
                        .order_by(Chapter.position, Chapter.created_at)):
        by_project[c.project_id].append(c)
    names = {p.id: p.name for p in projects}
    found: list[tuple[int, int, Chapter]] = []
    for m in CHAPTER_RE.finditer(d.text):
        n = m.group(1).lower()
        num = int(n) if n.isdigit() else NUMBER_WORDS.index(n) + 1
        for i, p in enumerate(projects):
            chs = by_project[p.id]
            if 1 <= num <= len(chs):
                found.append((m.start(), i, chs[num - 1]))
    low = d.text.lower()
    for i, p in enumerate(projects):
        for c in by_project[p.id]:
            title = " ".join(c.title.split()).lower()
            if not title or (" " not in title and len(title) < 5):
                continue
            m = re.search(r"(?<!\w)" + re.escape(title).replace(r"\ ", r"\s+") + r"(?!\w)", low)
            if m:
                found.append((m.start(), i, c))
    found.sort(key=lambda x: (x[0], x[1]))
    out: list[dict] = []
    seen: set[uuid.UUID] = set()
    for _, i, c in found:
        if c.id in seen:
            continue
        seen.add(c.id)
        label = f"chapter {c.position + 1}, {c.title}"
        out.append({"id": str(c.id), "title": c.title, "n": c.position + 1, "project": projects[i].slug,
                    "project_name": names[c.project_id],
                    "label": label if d.project_id is not None or len(world.projects) < 2 else f"{label} ({names[c.project_id]})"})
        if len(out) == NAMED_CHAPTERS:
            break
    return out


# the gap in a chapter -------------------------------------------------------------------------------------------


def _tied(x: Fact | Relationship, chapter_id: uuid.UUID, placed) -> bool:  # type: ignore[no-untyped-def]
    """Is a planned change tied to this chapter? By its from, until or established-in chapter, or by a time bound the
    chapter is set at (its set time, or the span from its own time to its end); never outside time (§16.4)."""
    if chapter_id in (x.from_chapter_id, x.until_chapter_id, x.established_in_chapter_id):
        return True
    if x.outside_time or placed is None or placed.set_time is None or placed.early or placed.outside:
        return False
    lo = placed.set_time
    hi = placed.end if placed.own is not None and placed.end is not None else lo
    return any(t is not None and lo <= float(t) <= hi for t in (x.from_time, x.until_time))


def written_chapter(db: Session, world: World, fus: list[DecisionFollowup], facts: dict, rels: dict) -> dict:
    """For each to-do planned change: the first current chapter with text it is tied to (`chapter 9 is written`)."""
    out: dict[uuid.UUID, dict] = {}
    todo = [(fu, facts.get(fu.fact_id) or rels.get(fu.relationship_id)) for fu in fus if fu.dropped_on is None]
    todo = [(fu, x) for fu, x in todo if x is not None and x.standing in TODO_STANDINGS]
    if not todo:
        return out
    projects = {p.id: p for p in world.projects}
    chapters = [c for c in db.scalars(select(Chapter).where(Chapter.project_id.in_(list(projects)),
                                                           Chapter.state == "current")
                                      .order_by(Chapter.position))] if projects else []
    order = {p.id: i for i, p in enumerate(world.projects)}
    chapters.sort(key=lambda c: (order[c.project_id], c.position))
    clock = world_clock(db, world)
    written = [c for c in chapters if words(c.body)]
    for fu, x in todo:
        for c in written:
            if _tied(x, c.id, clock.get(c.id)):
                out[fu.id] = {"id": str(c.id), "title": c.title, "n": c.position + 1}
                break
    return out


def chapter_gaps(db: Session, world: World, ch: Chapter) -> list[dict]:
    """The gap lines of a chapter (docs/SPEC.md §16.4): each planned change that follows a decision, is still to do and
    is tied to this chapter, when the chapter is current and has text. Each says whether it was put off ("Not yet")."""
    if ch.state != "current" or not words(ch.body):
        return []
    clock = world_clock(db, world)
    placed = clock.get(ch.id)
    rows: list[tuple[DecisionFollowup, Decision, Fact | Relationship, str]] = []
    base = (select(DecisionFollowup, Decision).join(Decision, Decision.id == DecisionFollowup.decision_id)
            .where(Decision.world_id == world.id, DecisionFollowup.dropped_on.is_(None)))
    for fu, d, f in db.execute(base.add_columns(Fact).join(Fact, Fact.id == DecisionFollowup.fact_id)
                               .where(Fact.standing.in_(TODO_STANDINGS))).all():
        if _tied(f, ch.id, placed):
            rows.append((fu, d, f, "fact"))
    for fu, d, r in db.execute(base.add_columns(Relationship).join(Relationship, Relationship.id == DecisionFollowup.relationship_id)
                               .where(Relationship.standing.in_(TODO_STANDINGS))).all():
        if _tied(r, ch.id, placed):
            rows.append((fu, d, r, "relationship"))
    if not rows:
        return []
    later = {r.key: r for r in db.scalars(select(Resolution).where(Resolution.world_id == world.id,
                                                                    Resolution.rule == GAP_RULE))}
    w = Words(db, world)
    ids = {x for _, _, row, t in rows for x in ((row.entity_id,) if t == "fact" else (row.a_id, row.b_id))}
    names = {e.id: e for e in db.scalars(select(Entity).where(Entity.id.in_(ids)))}
    types = {t.id: t for t in db.scalars(select(RelationType).where(RelationType.world_id == world.id))}
    counts = counts_for(db, list({d.id for _, d, _, _ in rows}))
    out = []
    for fu, d, row, table in sorted(rows, key=lambda x: (x[1].decided_on, x[1].created_at, str(x[0].id))):
        key = f"{fu.id}:{ch.id}"
        res = later.get(key)
        if table == "fact":
            e = names.get(row.entity_id)
            what = fact_words(w, row, e.name if e else "?", this=ch.id, sep=", ")
            extra = {"entity_id": str(row.entity_id), "label": row.label}
        else:
            a, b = names.get(row.a_id), names.get(row.b_id)
            what = relationship_words(w, row, types.get(row.type_id), a.name if a else "?", b.name if b else "?",
                                      this=ch.id, sep=", ")
            extra = {"entity_id": str(row.a_id), "type_id": str(row.type_id), "a_id": str(row.a_id),
                     "b_id": str(row.b_id)}
        out.append({"followup_id": str(fu.id), "key": key, "table": table, "id": str(row.id), "what": what,
                    "standing": row.standing, "version": row.version,
                    "decision": {"id": str(d.id), "decided_on": d.decided_on.isoformat(), "text": d.text},
                    # the decision's other follow-ups still to do: none, and making this canon finishes it
                    "others_todo": counts.get(d.id, {}).get("todo", 1) - 1,
                    "not_yet": str(res.id) if res is not None and res.outcome == "later" else None, **extra})
    return out


# the list -------------------------------------------------------------------------------------------------------


STATE_ORDER = {"todo": 0, "done": 1, "dropped": 2}


def followup_list(db: Session, world: World, d: Decision) -> list[dict]:
    """A decision's follow-ups, to do first, then done, then dropped (docs/SPEC.md §16.2)."""
    fus = list(db.scalars(select(DecisionFollowup).where(DecisionFollowup.decision_id == d.id)
                          .order_by(DecisionFollowup.created_at, DecisionFollowup.id)))
    facts, rels, items = _rows_of(db, fus)
    w = Words(db, world)
    ids = {f.entity_id for f in facts.values()} | {x for r in rels.values() for x in (r.a_id, r.b_id)}
    names = {e.id: e for e in db.scalars(select(Entity).where(Entity.id.in_(ids)))} if ids else {}
    types = {t.id: t for t in db.scalars(select(RelationType).where(RelationType.world_id == world.id))}
    written = written_chapter(db, world, fus, facts, rels)
    out = []
    for fu in fus:
        st = _state(fu, facts, rels, items)
        f, r, i = facts.get(fu.fact_id), rels.get(fu.relationship_id), items.get(fu.item_id)
        x: dict = {"id": str(fu.id), "state": st, "what": fu.what, "dropped_on": fu.dropped_on.isoformat() if fu.dropped_on else None,
                   "kind": None, "text": fu.what, "standing": None, "status": None, "closed_at": None, "link": None,
                   "written": written.get(fu.id)}
        if f is not None:
            e = names.get(f.entity_id)
            x.update(kind="fact", text=fact_words(w, f, e.name if e else "?", long=True), standing=f.standing,
                     link={"entity": str(f.entity_id), "fact": str(f.id)})
        elif r is not None:
            a, b = names.get(r.a_id), names.get(r.b_id)
            x.update(kind="relationship", standing=r.standing, link={"entity": str(r.a_id), "relationship": str(r.id)},
                     text=relationship_words(w, r, types.get(r.type_id), a.name if a else "?", b.name if b else "?", long=True))
        elif i is not None:
            x.update(kind="task", text=task_words(i)[len("task: "):], status=i.status,
                     closed_at=i.closed_at.isoformat() if i.closed_at else None, link={"item": str(i.id)})
        out.append(x)
    out.sort(key=lambda x: STATE_ORDER[x["state"]])
    return out


# endpoints ------------------------------------------------------------------------------------------------------


def _decision(db: Session, world: World, decision_id: uuid.UUID) -> Decision:
    d = db.get(Decision, decision_id)
    if d is None or d.world_id != world.id:
        raise HTTPException(404, "No such decision.")
    return d


def _followup(db: Session, d: Decision, followup_id: uuid.UUID) -> DecisionFollowup:
    fu = db.get(DecisionFollowup, followup_id)
    if fu is None or fu.decision_id != d.id:
        raise HTTPException(404, "No such follow-up.")
    return fu


class TaskIn(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)
    entities: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    chapters: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class AttachIn(BaseModel):
    table: str
    id: uuid.UUID
    # Undo of a Detach: put back whatever state the row is in
    any: bool = False


class FollowupIn(BaseModel):
    fact: dict | None = None
    relationship: dict | None = None
    item: TaskIn | None = None
    attach: AttachIn | None = None


def _one(db: Session, world: World, d: Decision, fu: DecisionFollowup) -> dict:
    return next(x for x in followup_list(db, world, d) if x["id"] == str(fu.id))


def _link(db: Session, world: World, d: Decision, table: str, row, user: User) -> DecisionFollowup:  # type: ignore[no-untyped-def]
    col = getattr(DecisionFollowup, f"{table}_id")
    if db.scalar(select(DecisionFollowup.id).where(DecisionFollowup.decision_id == d.id, col == row.id)):
        raise HTTPException(409, "That already follows this decision.")
    fu = DecisionFollowup(decision_id=d.id, what=what_of(db, world, table, row), created_by=user.id,
                          **{f"{table}_id": row.id})
    db.add(fu)
    db.flush()
    return fu


def _new_task(db: Session, world: World, d: Decision, body: TaskIn, user: User) -> Item:
    """A task linked to the ticked entries and chapters (no passage), in the decision's project (§16.1)."""
    text = body.body.strip()
    if not text:
        raise HTTPException(422, "A task needs words.")
    item = Item(world_id=world.id, project_id=d.project_id, kind="task", body=text, status="open", source="desk",
                created_by=user.id, updated_by=user.id)
    db.add(item)
    db.flush()
    known = set(db.scalars(select(Entity.id).where(Entity.world_id == world.id, Entity.id.in_(body.entities)))) \
        if body.entities else set()
    db.add_all(ItemLink(item_id=item.id, target_table="entity", target_id=e) for e in dict.fromkeys(body.entities)
               if e in known)
    projects = [p.id for p in world.projects]
    chapters = set(db.scalars(select(Chapter.id).where(Chapter.id.in_(body.chapters), Chapter.project_id.in_(projects)))) \
        if body.chapters and projects else set()
    db.add_all(ItemLink(item_id=item.id, target_table="chapter", target_id=c) for c in dict.fromkeys(body.chapters)
               if c in chapters)
    refresh_source(db, world.id, "item", item.id, item.body)
    return item


@router.get("/decisions/{decision_id}/followups")
def list_followups(slug: str, decision_id: uuid.UUID, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    return followup_list(db, world, _decision(db, world, decision_id))


@router.post("/decisions/{decision_id}/followups", status_code=201)
def add_followup(slug: str, decision_id: uuid.UUID, body: FollowupIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    """Make a row and link it in one transaction (`fact`, `relationship` as their own endpoints take them, the fact
    with its `entity_id`; `item`: a task), or link one that exists (`attach`)."""
    world, _ = member_world(db, user, slug)
    d = _decision(db, world, decision_id)
    given = [k for k in ("fact", "relationship", "item", "attach") if getattr(body, k) is not None]
    if len(given) != 1:
        raise HTTPException(422, "Send one of fact, relationship, item or attach.")
    made = None
    if body.fact is not None:
        from .world import FactIn, _entity, new_fact

        data = dict(body.fact)
        entity_id = data.pop("entity_id", None)
        if entity_id is None:
            raise HTTPException(422, "Choose the entry the fact is about.")
        fact_in = FactIn(**data)
        if fact_in.make_canon is not None:
            raise HTTPException(422, "A follow-up is a new fact.")
        row, _prompt = new_fact(db, world, _entity(db, world, uuid.UUID(str(entity_id))), fact_in, user)
        fu = _link(db, world, d, "fact", row, user)
        made = {"table": "fact", "id": str(row.id)}
    elif body.relationship is not None:
        from .world import RelationshipIn, new_relationship

        rel_in = RelationshipIn(**body.relationship)
        if rel_in.make_canon is not None:
            raise HTTPException(422, "A follow-up is a new relationship.")
        row = new_relationship(db, world, rel_in, user)
        fu = _link(db, world, d, "relationship", row, user)
        made = {"table": "relationship", "id": str(row.id)}
    elif body.item is not None:
        row = _new_task(db, world, d, body.item, user)
        fu = _link(db, world, d, "item", row, user)
        made = {"table": "item", "id": str(row.id)}
    else:
        a = body.attach
        assert a is not None
        model = {"fact": Fact, "relationship": Relationship, "item": Item}.get(a.table)
        row = db.get(model, a.id) if model is not None else None
        if row is None or row.world_id != world.id:
            raise HTTPException(404, "No such row in this world.")
        if not a.any:
            if a.table == "item" and (row.kind != "task" or row.status not in OPEN_TASKS):
                raise HTTPException(422, "Only an open or deferred task can follow a decision.")
            if a.table != "item" and row.standing not in TODO_STANDINGS:
                raise HTTPException(422, "Only a planned fact or relationship can follow a decision: this one is canon.")
        fu = _link(db, world, d, a.table, row, user)
    db.commit()
    return {"followup": _one(db, world, d, fu), "made": made, "counts": counts_for(db, [d.id]).get(d.id)}


@router.post("/decisions/{decision_id}/followups/{followup_id}/drop")
def drop_followup(slug: str, decision_id: uuid.UUID, followup_id: uuid.UUID, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> dict:
    """Drop: the change or task won't happen. The row is left as it is."""
    world, _ = member_world(db, user, slug)
    d = _decision(db, world, decision_id)
    fu = _followup(db, d, followup_id)
    if fu.dropped_on is None:
        fu.dropped_on = date.today()
    db.commit()
    return {"followup": _one(db, world, d, fu), "counts": counts_for(db, [d.id]).get(d.id)}


@router.post("/decisions/{decision_id}/followups/{followup_id}/undrop")
def undrop_followup(slug: str, decision_id: uuid.UUID, followup_id: uuid.UUID, user: User = Depends(current_user),
                    db: Session = Depends(get_db)) -> dict:
    """Undo a Drop (a follow-up whose row was deleted stays dropped)."""
    world, _ = member_world(db, user, slug)
    d = _decision(db, world, decision_id)
    fu = _followup(db, d, followup_id)
    if fu.fact_id or fu.relationship_id or fu.item_id:
        fu.dropped_on = None
    db.commit()
    return {"followup": _one(db, world, d, fu), "counts": counts_for(db, [d.id]).get(d.id)}


@router.delete("/decisions/{decision_id}/followups/{followup_id}")
def detach_followup(slug: str, decision_id: uuid.UUID, followup_id: uuid.UUID, user: User = Depends(current_user),
                    db: Session = Depends(get_db)) -> dict:
    """Detach: the follow-up goes altogether (one made or attached by mistake); the row stays. Returns what Undo needs."""
    world, _ = member_world(db, user, slug)
    d = _decision(db, world, decision_id)
    fu = _followup(db, d, followup_id)
    table = "fact" if fu.fact_id else "relationship" if fu.relationship_id else "item" if fu.item_id else None
    row_id = fu.fact_id or fu.relationship_id or fu.item_id
    db.delete(fu)
    db.commit()
    return {"attach": {"table": table, "id": str(row_id), "any": True} if table else None,
            "counts": counts_for(db, [d.id]).get(d.id)}


@router.get("/decisions/{decision_id}/chapters")
def decision_chapters(slug: str, decision_id: uuid.UUID, user: User = Depends(current_user),
                      db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    return named_chapters(db, world, _decision(db, world, decision_id))


@router.get("/decisions/{decision_id}/offers")
def offers(slug: str, decision_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """What the follow-up step offers, worked out once when it opens (docs/SPEC.md §16.3): the chapters the decision
    names, and its entries: those it is tagged with (and those the item it closed was tagged with), then those it
    names (its stored mentions)."""
    world, _ = member_world(db, user, slug)
    d = _decision(db, world, decision_id)
    tagged = list(db.scalars(select(DecisionLink.entity_id).where(DecisionLink.decision_id == d.id)))
    if d.item_id is not None:
        tagged += [x for x in db.scalars(select(ItemLink.target_id).where(ItemLink.item_id == d.item_id,
                                                                          ItemLink.target_table == "entity"))
                   if x not in tagged]
    named = [m.entity_id for m in db.scalars(select(Mention).where(Mention.source_table == "decision",
                                                                    Mention.source_id == d.id,
                                                                    Mention.kind.in_(("exact", "alias")))
                                            .order_by(Mention.start))]
    ids = list(dict.fromkeys([*tagged, *named]))
    entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.world_id == world.id, Entity.id.in_(ids)))}
    # tags keep no order: those the text names come first, in the order it names them, then the rest by name
    at = {x: i for i, x in reversed(list(enumerate(named)))}
    tagged_names = sorted((entities[x] for x in tagged if x in entities),
                          key=lambda e: (at.get(e.id, len(named)), e.name.lower()))
    return {"chapters": named_chapters(db, world, d),
            "entities": [{"id": str(e.id), "name": e.name, "kind": e.kind, "tagged": e.id in set(tagged)}
                         for e in [*tagged_names, *(entities[x] for x in ids if x in entities and x not in set(tagged))]]}


@router.get("/followup-candidates")
def candidates(slug: str, decision: uuid.UUID | None = Query(default=None), user: User = Depends(current_user),
               db: Session = Depends(get_db)) -> list[dict]:
    """What *Attach…* offers (docs/SPEC.md §16.1): planned and rumoured facts and relationships, those on the decision's
    tagged entries first, then open and deferred tasks, newest first. Rows already following the decision are left out."""
    world, _ = member_world(db, user, slug)
    tagged: set[uuid.UUID] = set()
    taken: set[uuid.UUID] = set()
    if decision is not None:
        d = _decision(db, world, decision)
        tagged = set(db.scalars(select(DecisionLink.entity_id).where(DecisionLink.decision_id == d.id)))
        for fu in db.scalars(select(DecisionFollowup).where(DecisionFollowup.decision_id == d.id)):
            taken |= {x for x in (fu.fact_id, fu.relationship_id, fu.item_id) if x}
    w = Words(db, world)
    entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.world_id == world.id))}
    types = {t.id: t for t in db.scalars(select(RelationType).where(RelationType.world_id == world.id))}
    rows: list[tuple[bool, str, dict]] = []
    for f in db.scalars(select(Fact).where(Fact.world_id == world.id, Fact.standing.in_(TODO_STANDINGS))):
        if f.id in taken:
            continue
        e = entities.get(f.entity_id)
        rows.append((f.entity_id not in tagged, e.name if e else "", {
            "table": "fact", "id": str(f.id), "text": f"{fact_words(w, f, e.name if e else '?')} · {f.standing}"}))
    for r in db.scalars(select(Relationship).where(Relationship.world_id == world.id,
                                                   Relationship.standing.in_(TODO_STANDINGS))):
        if r.id in taken:
            continue
        a, b = entities.get(r.a_id), entities.get(r.b_id)
        text = relationship_words(w, r, types.get(r.type_id), a.name if a else "?", b.name if b else "?")
        rows.append((not ({r.a_id, r.b_id} & tagged), a.name if a else "",
                     {"table": "relationship", "id": str(r.id), "text": f"{text} · {r.standing}"}))
    rows.sort(key=lambda x: (x[0], x[1].lower(), x[2]["text"].lower()))
    tasks = [{"table": "item", "id": str(i.id), "text": f"{task_words(i)[len('task: '):]} · task"
              + (" · deferred" if i.status == "deferred" else "")}
             for i in db.scalars(select(Item).where(Item.world_id == world.id, Item.kind == "task",
                                                    Item.status.in_(OPEN_TASKS)).order_by(Item.created_at.desc()))
             if i.id not in taken]
    return [x for _, _, x in rows] + tasks


@router.get("/chapters/{chapter_id}/gaps")
def gaps(slug: str, chapter_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """The chapter's gap lines for Loose ends, fetched beside its items (docs/SPEC.md §16.4)."""
    world, _ = member_world(db, user, slug)
    ch = db.get(Chapter, chapter_id)
    if ch is None or db.get(Project, ch.project_id).world_id != world.id:
        raise HTTPException(404, "No such chapter.")
    return chapter_gaps(db, world, ch)


def delete_made(db: Session, world: World, d: Decision, followup_ids: list[uuid.UUID]) -> None:
    """Undoing a close: the rows made in its follow-up step go with the decision; attached ones stay (§16.1)."""
    for fu in db.scalars(select(DecisionFollowup).where(DecisionFollowup.decision_id == d.id,
                                                        DecisionFollowup.id.in_(followup_ids))):
        row = db.get(Fact, fu.fact_id) if fu.fact_id else db.get(Relationship, fu.relationship_id) \
            if fu.relationship_id else None
        if row is not None:
            db.delete(row)
        elif fu.item_id:
            item = db.get(Item, fu.item_id)
            if item is not None:
                db.query(Mention).filter(Mention.source_table == "item", Mention.source_id == item.id).delete()
                db.delete(item)
    db.flush()


def entity_follows(db: Session, entity_id: uuid.UUID) -> dict[str, int]:
    """How many of an entry's facts and relationships follow decisions (its delete warning says so, §16.6)."""
    facts = set(db.scalars(select(DecisionFollowup.fact_id).join(Fact, Fact.id == DecisionFollowup.fact_id)
                           .where(Fact.entity_id == entity_id)))
    rels = set(db.scalars(select(DecisionFollowup.relationship_id)
                          .join(Relationship, Relationship.id == DecisionFollowup.relationship_id)
                          .where(or_(Relationship.a_id == entity_id, Relationship.b_id == entity_id))))
    return {"facts": len(facts), "relationships": len(rels)}
