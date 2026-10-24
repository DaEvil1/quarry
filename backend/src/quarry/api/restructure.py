"""Restructuring (docs/SPEC.md §13.6): experiments that replace a range of chapters with several drafts (or only add
some at a place), and the review of everything tied to chapters before they leave the book, with Undo, Reinstate and
the Archivist's evidence in Salvage.

A review lists, for the chapters leaving: facts and relationships bounded by them or established in them, "is at"
records in them, items linked to them and the note for next time left in them. Each row is kept (a bound becomes the
chapter's set time, or goes when it has none), moved to another chapter, marked as planned, or dropped. It is applied
in one transaction with the retirement, and stored (retire_reviews) as it was before, for Undo and Reinstate.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Numeric, any_, delete, select
from sqlalchemy.orm import Session

from ..clock import TIMED, Clock, time_text
from ..db import get_db
from ..mentions import refresh_source
from ..models import (
    Chapter,
    Decision,
    Entity,
    ExperimentRange,
    Fact,
    Item,
    ItemLink,
    Presence,
    Project,
    RelationType,
    Relationship,
    Resolution,
    RetireReview,
    SessionNote,
    User,
    World,
)
from .deps import current_user
from .manuscript import _chapter, _next_position, _renumber, _retire, chapter_detail, chapter_out, snapshot, words
from .storytime import story_order, world_clock
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

Action = Literal["keep", "move", "planned", "drop"]


# ---- experiments: ranges and drafts ------------------------------------------------------------------------------


def range_of(db: Session, item_id: uuid.UUID) -> list[Chapter]:
    """The chapters an experiment would replace, in order (whatever state they are in now)."""
    return list(db.scalars(select(Chapter).join(ExperimentRange, ExperimentRange.chapter_id == Chapter.id)
                           .where(ExperimentRange.item_id == item_id).order_by(ExperimentRange.position)))


def drafts_of(db: Session, item_id: uuid.UUID, states: tuple[str, ...] = ("experiment",)) -> list[Chapter]:
    return list(db.scalars(select(Chapter).where(Chapter.experiment_item_id == item_id, Chapter.state.in_(states))
                           .order_by(Chapter.position, Chapter.created_at)))


def experiment_info(db: Session, world: World, item: Item) -> dict:
    """An experiment as the manuscript list and the editor show it: its range (or where it adds), its drafts, the
    words on each side, and which of its chapters other experiments have replaced since."""
    rng = range_of(db, item.id)
    drafts = drafts_of(db, item.id)
    lost = [c for c in rng if c.state != "current"]
    replaced_by: str | None = None
    if lost:
        other = db.scalar(select(Item).join(ExperimentRange, ExperimentRange.item_id == Item.id)
                          .where(ExperimentRange.chapter_id == lost[0].id, Item.id != item.id,
                                 Item.status == "accepted"))
        replaced_by = (other.title or other.body.split("\n", 1)[0]) if other else None
    anchor = db.get(Chapter, item.insert_at_chapter_id) if item.insert_at_chapter_id else None
    return {"id": str(item.id), "title": item.title or item.body.split("\n", 1)[0][:300], "status": item.status,
            "range": [{"id": str(c.id), "title": c.title, "state": c.state, "words": words(c.body)} for c in rng],
            "range_words": sum(words(c.body) for c in rng if c.state == "current"),
            "insert": {"chapter_id": str(anchor.id), "title": anchor.title, "side": item.insert_side}
            if anchor is not None and item.insert_side else None,
            "drafts": [chapter_out(db, world, c).model_dump(mode="json") for c in drafts],
            "words": sum(words(c.body) for c in drafts),
            "lost": [c.title for c in lost], "replaced_by": replaced_by}


def experiments_in(db: Session, world: World, project_id: uuid.UUID) -> list[dict]:
    """The open experiments of a project, oldest first."""
    items = db.scalars(select(Item).where(Item.world_id == world.id, Item.project_id == project_id,
                                          Item.kind == "experiment", Item.status == "open").order_by(Item.created_at))
    out = []
    for it in items:
        info = experiment_info(db, world, it)
        if info["drafts"] or info["range"] or info["insert"]:
            out.append(info)
    return out


def _item(db: Session, world: World, item_id: uuid.UUID) -> Item:
    it = db.get(Item, item_id)
    if it is None or it.world_id != world.id or it.kind != "experiment":
        raise HTTPException(404, "No such experiment.")
    return it


def _run(db: Session, world: World, ids: list[uuid.UUID]) -> tuple[Project, list[Chapter]]:
    """A range: a run of current chapters in one project, in book order."""
    chapters = [_chapter(db, world, i) for i in ids]
    if not chapters:
        raise HTTPException(422, "Pick the chapters it would replace.")
    if any(c.state != "current" for c in chapters) or len({c.project_id for c in chapters}) != 1:
        raise HTTPException(422, "The range is a run of chapters in the book, in one project.")
    project = db.get(Project, chapters[0].project_id)
    assert project is not None
    current = list(db.scalars(select(Chapter).where(Chapter.project_id == project.id, Chapter.state == "current")
                              .order_by(Chapter.position, Chapter.created_at)))
    idx = sorted(current.index(c) for c in chapters)
    if idx != list(range(idx[0], idx[0] + len(idx))):
        raise HTTPException(422, "The range is a run of chapters next to each other.")
    return project, [current[i] for i in idx]


def _copy_into(db: Session, world: World, user: User, item: Item, source: Chapter | None, title: str,
               position: int, project_id: uuid.UUID) -> Chapter:
    """A new draft of an experiment: empty, or a copy of a chapter (its text, summary, status, point of view, time and
    mark), which starts with a `start` revision (a copy is not a day's writing)."""
    ch = Chapter(project_id=project_id, title=title, body=source.body if source else "", state="experiment",
                 position=position, experiment_item_id=item.id, created_by=user.id, updated_by=user.id,
                 pov_entity_id=source.pov_entity_id if source else None, summary=source.summary if source else "",
                 status_id=source.status_id if source and source.project_id == project_id else None,
                 time_at=source.time_at if source else None, time_end=source.time_end if source else None,
                 time_label=source.time_label if source else None,
                 time_approx=source.time_approx if source else False,
                 outside_time=source.outside_time if source else False, told_as=source.told_as if source else None)
    db.add(ch)
    db.flush()
    if ch.body.strip():
        snapshot(db, ch, "start", user)
    refresh_source(db, world.id, "chapter", ch.id, ch.body)
    return ch


def new_experiment(db: Session, world: World, user: User, project: Project, title: str, start: str,
                   rng: list[Chapter], insert: tuple[Chapter, str] | None) -> tuple[Item, list[Chapter]]:
    """Start an experiment: from scratch (one empty draft) or from copies (a draft copied from each chapter in the
    range). One that only adds starts with one empty draft."""
    what = (f"Rewrite of {', '.join(f'“{c.title}”' for c in rng)}" if rng else
            f"New chapters {insert[1]} “{insert[0].title}”" if insert else "New chapters")
    item = Item(world_id=world.id, project_id=project.id, kind="experiment", title=title[:300],
                body=f"{what} ({'from scratch' if start == 'scratch' or not rng else 'from copies'})", source="desk",
                insert_at_chapter_id=insert[0].id if insert else None, insert_side=insert[1] if insert else None,
                created_by=user.id, updated_by=user.id)
    db.add(item)
    db.flush()
    for i, c in enumerate(rng):
        db.add(ExperimentRange(item_id=item.id, chapter_id=c.id, position=i))
    drafts: list[Chapter] = []
    if start == "copy" and rng:
        # each draft keeps its chapter's title; a single chapter's draft takes the experiment's, as it always has
        for i, c in enumerate(rng):
            drafts.append(_copy_into(db, world, user, item, c, title if len(rng) == 1 else c.title, i, project.id))
    else:
        drafts.append(_copy_into(db, world, user, item, None, title, 0, project.id))
    refresh_source(db, world.id, "item", item.id, item.body)
    return item, drafts


class InsertAt(BaseModel):
    chapter_id: uuid.UUID
    side: Literal["before", "after"]


class StartIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    start: Literal["scratch", "copy"] = "copy"
    # the chapters it would replace (a run in one project), or none and a place to add at
    range: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    insert: InsertAt | None = None


@router.post("/projects/{project_slug}/experiments", status_code=201)
def start_experiment(slug: str, project_slug: str, body: StartIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    project = next((p for p in world.projects if p.slug == project_slug), None)
    if project is None:
        raise HTTPException(404, "No such project.")
    title = " ".join(body.title.split())
    insert = None
    rng: list[Chapter] = []
    if body.range:
        p, rng = _run(db, world, body.range)
        if p.id != project.id:
            raise HTTPException(422, "The range is in another project.")
    elif body.insert is not None:
        anchor = _chapter(db, world, body.insert.chapter_id)
        if anchor.state != "current" or anchor.project_id != project.id:
            raise HTTPException(422, "Add next to a chapter in this book.")
        insert = (anchor, body.insert.side)
    else:
        raise HTTPException(422, "Pick the chapters it would replace, or a place to add chapters.")
    item, drafts = new_experiment(db, world, user, project, title, body.start, rng, insert)
    db.commit()
    return {**experiment_info(db, world, item), "first": str(drafts[0].id)}


@router.get("/experiments/{item_id}")
def get_experiment(slug: str, item_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    return experiment_info(db, world, _item(db, world, item_id))


class DraftIn(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    # copy a chapter in: any chapter of the world, current or retired (from Salvage too)
    copy_from: uuid.UUID | None = None


@router.post("/experiments/{item_id}/drafts", status_code=201)
def add_draft(slug: str, item_id: uuid.UUID, body: DraftIn, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
    if item.status != "open":
        raise HTTPException(409, "This experiment is closed.")
    source = _chapter(db, world, body.copy_from) if body.copy_from else None
    drafts = drafts_of(db, item.id)
    title = " ".join((body.title or (source.title if source else "New draft")).split()) or "New draft"
    project_id = item.project_id or (drafts[0].project_id if drafts else None)
    if project_id is None:
        raise HTTPException(422, "This experiment has no project.")
    ch = _copy_into(db, world, user, item, source, title, len(drafts), project_id)
    db.commit()
    return chapter_detail(db, world, ch)


class IdsIn(BaseModel):
    ids: list[uuid.UUID] = Field(max_length=500)


@router.put("/experiments/{item_id}/drafts")
def order_drafts(slug: str, item_id: uuid.UUID, body: IdsIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
    drafts = {c.id: c for c in drafts_of(db, item.id)}
    if set(body.ids) != set(drafts) or len(body.ids) != len(drafts):
        raise HTTPException(422, "Send every draft exactly once.")
    for i, cid in enumerate(body.ids):
        drafts[cid].position = i
    db.commit()
    return experiment_info(db, world, item)


class RangeIn(BaseModel):
    range: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    insert: InsertAt | None = None


@router.put("/experiments/{item_id}/range")
def set_range(slug: str, item_id: uuid.UUID, body: RangeIn, user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> dict:
    """Give an experiment a new range (after another one replaced some of its chapters), or a place to add at."""
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
    db.execute(delete(ExperimentRange).where(ExperimentRange.item_id == item.id))
    item.insert_at_chapter_id = item.insert_side = None
    if body.range:
        _, rng = _run(db, world, body.range)
        for i, c in enumerate(rng):
            db.add(ExperimentRange(item_id=item.id, chapter_id=c.id, position=i))
    elif body.insert is not None:
        anchor = _chapter(db, world, body.insert.chapter_id)
        if anchor.state != "current":
            raise HTTPException(422, "Add next to a chapter in the book.")
        item.insert_at_chapter_id, item.insert_side = anchor.id, body.insert.side
    db.commit()
    return experiment_info(db, world, item)


def draft_points(db: Session, world: World, clock: Clock) -> list[dict]:
    """Where each open experiment's drafts are read on the clock (docs/SPEC.md §13.6.1): as if they stood where their
    range stands. A draft with a time of its own sits at it; one without carries on from the chapter before the range
    (or, with none, the range's first chapter). Places are between whole chapters' places."""
    order = [c for c, _ in story_order(db, world)]
    book = {c.id: i for i, c in enumerate(order)}

    def by_time(t: float) -> float:
        return sum(1 for x in clock.happened if (0 if x.early else 1, x.set_time if x.set_time is not None else 0)
                   <= (TIMED, t) and (x.early or x.set_time is not None)) - 0.5

    out = []
    items = db.scalars(select(Item).where(Item.world_id == world.id, Item.kind == "experiment", Item.status == "open"))
    for item in items:
        rng = [c for c in range_of(db, item.id) if c.state == "current"]
        anchor = rng[0] if rng else (db.get(Chapter, item.insert_at_chapter_id) if item.insert_at_chapter_id else None)
        if anchor is None or anchor.id not in book:
            continue
        after = not rng and item.insert_side == "after"
        x = clock.get(anchor.id)
        i = book[anchor.id]
        before = clock.get(anchor.id) if after else (clock.get(order[i - 1].id) if i > 0 else None)
        for d in drafts_of(db, item.id):
            if d.outside_time:
                out.append({"id": str(d.id), "item": str(item.id), "clock": None, "set_time": None,
                            "set_approx": False, "outside_time": True})
                continue
            if d.time_at is not None:
                t, ap = float(d.time_at), d.time_approx
            elif before is not None and before.set_time is not None:
                t, ap = before.set_time, before.set_approx
            else:
                t, ap = (x.set_time, x.set_approx) if x is not None else (None, False)
            if t is not None and not d.told_as:
                place = by_time(t)
            elif x is not None and x.place is not None:
                place = x.place + (0.5 if after else -0.5)
            else:
                place = None
            out.append({"id": str(d.id), "item": str(item.id), "clock": place, "set_time": t, "set_approx": ap,
                        "outside_time": False})
    return out


@router.get("/draft-clock")
def draft_clock(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    return draft_points(db, world, world_clock(db, world))


# ---- what is tied to chapters ------------------------------------------------------------------------------------


def _ranges(nums: list[int]) -> str:
    """[1, 2, 3, 5] → "1–3, 5"."""
    nums = sorted(set(nums))
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(f"{nums[i]}–{nums[j]}" if j > i else str(nums[i]))
        i = j + 1
    return ", ".join(out)


def ties(db: Session, world: World, chapter_ids: list[uuid.UUID], drafts: list[Chapter] | None = None) -> list[dict]:
    """Everything tied to these chapters, one row per tie, each with the choices that apply, the one it starts on and
    where "move" would point. `drafts`: an experiment being accepted, whose drafts are the likely places to move to."""
    ids = set(chapter_ids)
    if not ids:
        return []
    clock = world_clock(db, world)
    order = [c for c, _ in story_order(db, world)]
    staying = [c for c in order if c.id not in ids]
    chapters = {c.id: c for c in db.scalars(select(Chapter).where(Chapter.id.in_(ids)))}
    entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.world_id == world.id))}
    types = {t.id: t for t in db.scalars(select(RelationType).where(RelationType.world_id == world.id))}
    unit, units = world.time_unit, world.time_units
    rows: list[dict] = []

    def ref(e: Entity | None) -> dict | None:
        return {"id": str(e.id), "name": e.name, "kind": e.kind} if e else None

    def neighbour(cid: uuid.UUID, later: bool) -> Chapter | None:
        """The chapter after (or before) one that leaves, among those staying, in book order."""
        if cid in {c.id for c in order}:
            i = [c.id for c in order].index(cid)
            seq = order[i + 1:] if later else list(reversed(order[:i]))
            return next((c for c in seq if c.id not in ids), None)
        return staying[0] if later and staying else (staying[-1] if staying else None)

    def found(passage: str | None) -> Chapter | None:
        """Where a passage is now: a draft first (when accepting), else a chapter staying in the book."""
        text = (passage or "").strip()
        if not text:
            return None
        for c in [*(drafts or []), *staying]:
            if text in c.body:
                return c
        return None

    def kept(cid: uuid.UUID, side: str) -> tuple[str, str | None]:
        x = clock.get(cid)
        if x is None or x.set_time is None or x.early:
            return ("will hold from the start" if side == "from" else "will hold to the end"), None
        text = time_text(unit, units, x.set_time, None, None, x.set_approx)
        same = [y.book + 1 for y in clock.chapters if y.set_time == x.set_time and not y.early and not y.outside]
        warn = f"chapters {_ranges(same)} are all set in {text}" if len(same) > 1 else None
        return f"{side} {text}", warn

    def add(kind: str, obj_id: uuid.UUID, field: str, cid: uuid.UUID, text: str, who: list[Entity | None],
            choices: list[str], evidence: str | None = None, keep_text: str | None = None, warn: str | None = None,
            later: bool = True) -> None:
        if drafts:
            to = found(evidence) or (drafts[0] if later else drafts[-1])
        else:
            to = found(evidence) if evidence else None
            to = to or neighbour(cid, later)
        rows.append({"key": f"{kind}:{obj_id}:{field}:{cid}", "kind": kind, "id": str(obj_id), "field": field,
                     "chapter": {"id": str(cid), "title": chapters[cid].title}, "text": text, "evidence": evidence,
                     "entities": [r for r in (ref(e) for e in who) if r], "choices": choices,
                     "default": "move" if warn and to is not None else "keep", "keep_text": keep_text, "warn": warn,
                     "move_to": {"id": str(to.id), "title": to.title} if to is not None else None})

    span_choices = ["keep", "move", "planned", "drop"]
    for f in db.scalars(select(Fact).where(Fact.world_id == world.id)):
        e = entities.get(f.entity_id)
        text = f"{e.name if e else '?'}: “{f.label}{': ' + f.value if f.value else ''}”"
        for side in ("from", "until"):
            cid = getattr(f, f"{side}_chapter_id")
            if cid in ids:
                kt, warn = kept(cid, side)
                add("fact", f.id, side, cid, text, [e], span_choices, keep_text=kt, warn=warn, later=side == "from")
        if f.established_in_chapter_id in ids:
            add("fact", f.id, "established", f.established_in_chapter_id, text, [e], span_choices,
                evidence=f.evidence)
    for r in db.scalars(select(Relationship).where(Relationship.world_id == world.id)):
        a, b = entities.get(r.a_id), entities.get(r.b_id)
        t = types.get(r.type_id)
        text = f"“{a.name if a else '?'} {t.label if t else '?'} {b.name if b else '?'}”"
        for side in ("from", "until"):
            cid = getattr(r, f"{side}_chapter_id")
            if cid in ids:
                kt, warn = kept(cid, side)
                add("relationship", r.id, side, cid, text, [a, b], span_choices, keep_text=kt, warn=warn,
                    later=side == "from")
        if r.established_in_chapter_id in ids:
            add("relationship", r.id, "established", r.established_in_chapter_id, text, [a, b], span_choices,
                evidence=r.evidence)
    for p in db.scalars(select(Presence).where(Presence.chapter_id.in_(ids))):
        e, place = entities.get(p.entity_id), entities.get(p.place_id)
        add("presence", p.id, "is_at", p.chapter_id, f"{e.name if e else '?'} is at {place.name if place else '?'}",
            [e, place], ["keep", "move", "drop"])
    for link in db.scalars(select(ItemLink).where(ItemLink.target_table == "chapter", ItemLink.target_id.in_(ids))):
        it = db.get(Item, link.item_id)
        if it is None or it.world_id != world.id:
            continue
        add("link", it.id, "item", link.target_id, f"Item: {it.title or it.body.split(chr(10), 1)[0][:120]}", [],
            ["keep", "move", "drop"])
    for n in db.scalars(select(SessionNote).where(SessionNote.chapter_id.in_(ids))):
        if n.note.strip():
            add("note", n.user_id, "note", n.chapter_id, f"The note for next time: {n.note[:200]}", [],
                ["keep", "move", "drop"])
    rows.sort(key=lambda r: (r["chapter"]["title"], ["fact", "relationship", "presence", "link", "note"].index(r["kind"]),
                             r["text"]))
    return rows


@router.get("/chapters/ties")
def get_ties(slug: str, ids: str = Query(..., max_length=20000), experiment: uuid.UUID | None = Query(default=None),
             user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """What is tied to these chapters, for the review before they leave the book. With `experiment`, the chapters are
    those leaving when it is accepted, and its drafts are where things move to."""
    world, _ = member_world(db, user, slug)
    chapter_ids = []
    for x in ids.split(","):
        if x.strip():
            try:
                chapter_ids.append(_chapter(db, world, uuid.UUID(x.strip())).id)
            except ValueError:
                raise HTTPException(422, "Not a chapter id.") from None
    drafts = drafts_of(db, _item(db, world, experiment).id) if experiment else None
    return {"rows": ties(db, world, chapter_ids, drafts)}


# ---- applying a review, and undoing it ----------------------------------------------------------------------------


def _json(v: Any) -> Any:
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def _row(obj: Any) -> dict:
    return {c.key: _json(getattr(obj, c.key)) for c in obj.__table__.columns}


def _load(model: Any, data: dict) -> Any:
    """A row as it was, from `_row`."""
    values = {}
    for c in model.__table__.columns:
        v = data.get(c.key)
        if v is not None:
            if isinstance(c.type, DateTime):
                v = datetime.fromisoformat(v)
            elif isinstance(c.type, Numeric):
                v = float(v)
            elif isinstance(c.type, Boolean):
                v = bool(v)
            elif c.key.endswith("_id") or c.key in ("id", "created_by", "updated_by"):
                v = uuid.UUID(v)
        values[c.key] = v
    return model(**values)


MODELS = {"fact": Fact, "relationship": Relationship}
BOUND_FIELDS = ("from_chapter_id", "from_time", "from_approx", "until_chapter_id", "until_time", "until_approx")


class Choice(BaseModel):
    key: str = Field(max_length=300)
    action: Action
    # for "move": the chapter to point at instead
    to: uuid.UUID | None = None


def apply_review(db: Session, world: World, user: User, chapter_ids: list[uuid.UUID], choices: list[Choice],
                 drafts: list[Chapter] | None = None) -> list[dict]:
    """Apply a review's choices (a row not chosen gets its default) before the chapters leave. Returns the changes,
    each with what it was before, for Undo and Reinstate. Flushed, not committed."""
    rows = ties(db, world, chapter_ids, drafts)
    chosen = {c.key: c for c in choices}
    clock = world_clock(db, world)
    changes: list[dict] = []
    touched: dict[tuple[str, str], Any] = {}
    drops: list[tuple[dict, Choice]] = []

    def target(c: Choice, row: dict) -> uuid.UUID:
        to = c.to or (uuid.UUID(row["move_to"]["id"]) if row["move_to"] else None)
        if to is None:
            raise HTTPException(422, f"Pick a chapter to move {row['text']} to.")
        ch = _chapter(db, world, to)
        if ch.id in set(chapter_ids):
            raise HTTPException(422, "Move it to a chapter that stays.")
        return ch.id

    for row in rows:
        c = chosen.get(row["key"]) or Choice(key=row["key"], action=row["default"],
                                             to=uuid.UUID(row["move_to"]["id"]) if row["move_to"] else None)
        if c.action not in row["choices"]:
            raise HTTPException(422, f"“{c.action}” doesn't apply to {row['text']}.")
        cid = uuid.UUID(row["chapter"]["id"])
        base = {"key": row["key"], "action": c.action, "kind": row["kind"], "id": row["id"], "field": row["field"],
                "chapter_id": str(cid)}
        if c.action == "drop":
            drops.append((row, c))
            continue
        kind, field = row["kind"], row["field"]
        if kind in MODELS:
            obj = db.get(MODELS[kind], uuid.UUID(row["id"]))
            if obj is None:
                continue
            touched[(kind, row["id"])] = obj
            before = {k: _json(getattr(obj, k)) for k in (*BOUND_FIELDS, "established_in_chapter_id", "standing")}
            if field in ("from", "until"):
                if c.action == "move":
                    setattr(obj, f"{field}_chapter_id", target(c, row))
                else:
                    x = clock.get(cid)
                    setattr(obj, f"{field}_chapter_id", None)
                    if x is not None and x.set_time is not None and not x.early:
                        setattr(obj, f"{field}_time", x.set_time)
                        setattr(obj, f"{field}_approx", x.set_approx)
            elif field == "established" and c.action == "move":
                obj.established_in_chapter_id = target(c, row)
            if c.action == "planned":
                obj.standing = "planned"
            obj.version += 1
            obj.updated_by = user.id
            changes.append({**base, "before": before})
        elif kind == "presence" and c.action == "move":
            p = db.get(Presence, uuid.UUID(row["id"]))
            if p is None:
                continue
            to = target(c, row)
            clash = db.scalar(select(Presence).where(Presence.entity_id == p.entity_id, Presence.chapter_id == to))
            changes.append({**base, "before": _row(p), "replaced": _row(clash) if clash else None,
                            "after": {"chapter_id": str(to)}})
            if clash is not None:
                db.delete(clash)
                db.flush()
            p.chapter_id = to
        elif kind == "link" and c.action == "move":
            to = target(c, row)
            link = db.get(ItemLink, (uuid.UUID(row["id"]), "chapter", cid))
            if link is None:
                continue
            db.delete(link)
            db.flush()
            if db.get(ItemLink, (uuid.UUID(row["id"]), "chapter", to)) is None:
                db.add(ItemLink(item_id=uuid.UUID(row["id"]), target_table="chapter", target_id=to))
            changes.append({**base, "after": {"chapter_id": str(to)}})
        elif kind == "note" and c.action == "move":
            n = db.get(SessionNote, (cid, uuid.UUID(row["id"])))
            if n is None:
                continue
            to = target(c, row)
            there = db.get(SessionNote, (to, n.user_id))
            changes.append({**base, "before": _row(n), "replaced": _row(there) if there else None,
                            "after": {"chapter_id": str(to)}})
            if there is not None:
                there.note = f"{there.note}\n{n.note}".strip()
            else:
                db.add(SessionNote(chapter_id=to, user_id=n.user_id, note=n.note, cursor=0))
            db.delete(n)
        else:
            # keep: nothing changes (evidence, "is at", the link and the note stay pointing at the chapter, in Salvage)
            changes.append({**base})
    db.flush()
    for row, c in drops:
        base = {"key": row["key"], "action": "drop", "kind": row["kind"], "id": row["id"], "field": row["field"],
                "chapter_id": row["chapter"]["id"]}
        kind = row["kind"]
        if kind in MODELS:
            obj = db.get(MODELS[kind], uuid.UUID(row["id"]))
            if obj is None:
                changes.append(base)
                continue
            changes.append({**base, "before": _row(obj)})
            touched.pop((kind, row["id"]), None)
            db.delete(obj)
        elif kind == "presence":
            p = db.get(Presence, uuid.UUID(row["id"]))
            if p is not None:
                changes.append({**base, "before": _row(p)})
                db.delete(p)
        elif kind == "link":
            link = db.get(ItemLink, (uuid.UUID(row["id"]), "chapter", uuid.UUID(row["chapter"]["id"])))
            if link is not None:
                changes.append({**base, "before": _row(link)})
                db.delete(link)
        elif kind == "note":
            n = db.get(SessionNote, (uuid.UUID(row["chapter"]["id"]), uuid.UUID(row["id"])))
            if n is not None:
                changes.append({**base, "before": _row(n)})
                db.delete(n)
        db.flush()
    # each changed fact or relationship: its version after the whole review, so Undo leaves one changed since
    for ch in changes:
        obj = touched.get((ch["kind"], ch["id"]))
        if obj is not None:
            ch["version"] = obj.version
    return changes


def undo_changes(db: Session, changes: list[dict], user: User, only_chapter: str | None = None) -> tuple[int, int]:
    """Put back each row a review changed that hasn't changed since (newest first). Returns (put back, skipped)."""
    done = skipped = 0
    # a fact or relationship changed by several rows goes back once, to how it was before the first of them
    first: dict[tuple[str, str], dict] = {}
    for ch in changes:
        if ch["kind"] in MODELS and ch["action"] != "drop" and "before" in ch:
            first.setdefault((ch["kind"], ch["id"]), ch)
    for ch in reversed(changes):
        if only_chapter and ch.get("chapter_id") != only_chapter:
            continue
        kind, action = ch["kind"], ch["action"]
        if action == "keep" and kind not in MODELS:
            continue
        if kind in MODELS:
            model = MODELS[kind]
            if action == "drop":
                if ch.get("before") and db.get(model, uuid.UUID(ch["id"])) is None:
                    db.add(_load(model, ch["before"]))
                    done += 1
                continue
            if first.get((kind, ch["id"])) is not ch:
                continue
            obj = db.get(model, uuid.UUID(ch["id"]))
            if obj is None or ("version" in ch and obj.version != ch["version"]):
                skipped += 1
                continue
            for k, v in (ch.get("before") or {}).items():
                col = model.__table__.columns[k]
                if v is not None and k.endswith("_id"):
                    v = uuid.UUID(v)
                elif v is not None and isinstance(col.type, Numeric):
                    v = float(v)
                setattr(obj, k, v)
            obj.version += 1
            obj.updated_by = user.id
            done += 1
        elif kind == "presence":
            if action == "drop":
                if db.get(Presence, uuid.UUID(ch["id"])) is None:
                    db.add(_load(Presence, ch["before"]))
                    done += 1
                continue
            p = db.get(Presence, uuid.UUID(ch["id"]))
            if p is None or str(p.chapter_id) != ch["after"]["chapter_id"]:
                skipped += 1
                continue
            p.chapter_id = uuid.UUID(ch["before"]["chapter_id"])
            db.flush()
            if ch.get("replaced") and db.get(Presence, uuid.UUID(ch["replaced"]["id"])) is None:
                db.add(_load(Presence, ch["replaced"]))
            done += 1
        elif kind == "link":
            old = (uuid.UUID(ch["id"]), "chapter", uuid.UUID(ch["chapter_id"]))
            if action == "move":
                moved = db.get(ItemLink, (uuid.UUID(ch["id"]), "chapter", uuid.UUID(ch["after"]["chapter_id"])))
                if moved is not None:
                    db.delete(moved)
                    db.flush()
            if db.get(ItemLink, old) is None:
                db.add(ItemLink(item_id=old[0], target_table="chapter", target_id=old[2]))
                done += 1
        elif kind == "note":
            if action == "move":
                to = (uuid.UUID(ch["after"]["chapter_id"]), uuid.UUID(ch["id"]))
                there = db.get(SessionNote, to)
                if there is not None:
                    if ch.get("replaced"):
                        there.note = ch["replaced"]["note"]
                    else:
                        db.delete(there)
                    db.flush()
            if db.get(SessionNote, (uuid.UUID(ch["chapter_id"]), uuid.UUID(ch["id"]))) is None:
                db.add(_load(SessionNote, ch["before"]))
                done += 1
    db.flush()
    return done, skipped


def summary_of(changes: list[dict], chapter_id: str | None = None) -> dict:
    """"14 kept, 3 moved, 1 dropped": what a review did, per action (for one chapter, or all)."""
    out = {"keep": 0, "move": 0, "planned": 0, "drop": 0}
    for ch in changes:
        if ch.get("kind") in ("chapter", "experiment") or (chapter_id and ch.get("chapter_id") != chapter_id):
            continue
        out[ch["action"]] = out.get(ch["action"], 0) + 1
    return out


def _leave(db: Session, user: User, chapters: list[Chapter], notes: dict[str, str]) -> list[dict]:
    """Retire chapters (each with its harvest note), keeping how they were for Undo."""
    out = []
    for ch in chapters:
        out.append({"kind": "chapter", "action": "retire", "id": str(ch.id), "chapter_id": str(ch.id),
                    "before": {"state": ch.state, "position": ch.position}})
        _retire(db, ch, user, notes.get(str(ch.id)))
    return out


class RetireManyIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    review: list[Choice] = Field(default_factory=list, max_length=100_000)
    # harvest notes, one per chapter (each optional)
    notes: dict[str, str] = Field(default_factory=dict)


def _review_out(review: RetireReview) -> dict:
    return {"id": str(review.id), "summary": summary_of(review.changes),
            "chapters": [str(c) for c in review.chapter_ids]}


@router.post("/chapters/retire")
def retire_many(slug: str, body: RetireManyIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Retire one or several chapters (in the book, or an experiment's drafts) after the review of what is tied to
    them, in one transaction. Answers with the review, for Undo."""
    world, _ = member_world(db, user, slug)
    chapters = [_chapter(db, world, i) for i in dict.fromkeys(body.ids)]
    if any(c.state == "retired" for c in chapters):
        raise HTTPException(409, "That chapter is in Salvage already.")
    changes = apply_review(db, world, user, [c.id for c in chapters], body.review)
    changes += _leave(db, user, chapters, body.notes)
    db.flush()
    for pid in {c.project_id for c in chapters}:
        _renumber(db, pid)
    review = RetireReview(world_id=world.id, chapter_ids=[c.id for c in chapters], changes=changes,
                          created_by=user.id)
    db.add(review)
    db.commit()
    return _review_out(review)


def _review(db: Session, world: World, review_id: uuid.UUID) -> RetireReview:
    r = db.get(RetireReview, review_id)
    if r is None or r.world_id != world.id:
        raise HTTPException(404, "No such review.")
    return r


@router.post("/retire-reviews/{review_id}/undo")
def undo_review(slug: str, review_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """One step back: each row that hasn't changed since goes back as it was, and so do the chapters (and an
    experiment that was closed by it)."""
    world, _ = member_world(db, user, slug)
    r = _review(db, world, review_id)
    changes = [dict(c) for c in r.changes]
    # the chapters first: rows point back at them
    projects = set()
    for ch in reversed(changes):
        if ch["kind"] == "chapter":
            c = db.get(Chapter, uuid.UUID(ch["id"]))
            if c is None:
                continue
            snapshot(db, c, "state", user)
            c.state = ch["before"]["state"]
            c.position = ch["before"]["position"]
            c.retired_at = None if c.state != "retired" else c.retired_at
            c.version += 1
            c.updated_by = user.id
            projects.add(c.project_id)
        elif ch["kind"] == "experiment":
            it = db.get(Item, uuid.UUID(ch["id"]))
            if it is not None:
                it.status, it.closed_at, it.closed_note = ch["before"]["status"], None, None
                it.version += 1
            for d in db.scalars(select(Decision).where(Decision.id.in_([uuid.UUID(x) for x in ch.get("decisions", [])]))):
                db.delete(d)
    db.flush()
    for pid in projects:
        # put the book back in its order: chapters that came back at their old places, the rest after them
        current = list(db.scalars(select(Chapter).where(Chapter.project_id == pid, Chapter.state == "current")
                                  .order_by(Chapter.position, Chapter.created_at)))
        for i, c in enumerate(current):
            c.position = i
    done, skipped = undo_changes(db, [c for c in changes if c["kind"] not in ("chapter", "experiment")], user)
    db.delete(r)
    db.commit()
    return {"restored": done, "skipped": skipped}


class ReviewIn(BaseModel):
    review: list[Choice] = Field(default_factory=list, max_length=100_000)


@router.post("/chapters/{chapter_id}/review")
def review_retired(slug: str, chapter_id: uuid.UUID, body: ReviewIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> dict:
    """Review a chapter retired before phase 12 ("Still tied … Review…"): the same review, for a chapter already in
    Salvage."""
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    if ch.state != "retired":
        raise HTTPException(409, "Only a chapter in Salvage is reviewed this way.")
    changes = apply_review(db, world, user, [ch.id], body.review)
    review = RetireReview(world_id=world.id, chapter_ids=[ch.id], changes=changes, created_by=user.id)
    db.add(review)
    db.commit()
    return _review_out(review)


def reviews_of(db: Session, world: World, chapter_id: uuid.UUID) -> list[RetireReview]:
    return list(db.scalars(select(RetireReview).where(RetireReview.world_id == world.id,
                                                      chapter_id == any_(RetireReview.chapter_ids))
                           .order_by(RetireReview.created_at)))


def salvage_extra(db: Session, world: World, ch: Chapter) -> dict:
    """On a retired chapter's page in Salvage: what its review did, or what is still tied to it when it was retired
    before reviews existed."""
    reviews = reviews_of(db, world, ch.id)
    if reviews:
        total = {"keep": 0, "move": 0, "planned": 0, "drop": 0}
        for r in reviews:
            for k, v in summary_of(r.changes, str(ch.id)).items():
                total[k] += v
        return {"review": {"id": str(reviews[-1].id), **total}, "still_tied": None}
    rows = ties(db, world, [ch.id])
    if not rows:
        return {"review": None, "still_tied": None}
    count = {"facts": len({r["id"] for r in rows if r["kind"] == "fact"}),
             "relationships": len({r["id"] for r in rows if r["kind"] == "relationship"}),
             "is_at": sum(r["kind"] == "presence" for r in rows), "items": sum(r["kind"] == "link" for r in rows),
             "notes": sum(r["kind"] == "note" for r in rows)}
    return {"review": None, "still_tied": count}


@router.post("/chapters/{chapter_id}/reinstate-review")
def reinstate_rows(slug: str, chapter_id: uuid.UUID, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> dict:
    """Reinstate: put back, as they were, the rows the reviews of this chapter changed (each that hasn't changed
    since). Used when the chapter comes back into the book."""
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    done = skipped = 0
    for r in reversed(reviews_of(db, world, ch.id)):
        changes = [dict(c) for c in r.changes]
        d, s = undo_changes(db, [c for c in changes if c["kind"] not in ("chapter", "experiment")], user,
                            only_chapter=str(ch.id))
        done, skipped = done + d, skipped + s
        r.changes = [c for c in changes if c.get("chapter_id") != str(ch.id) or c["kind"] == "chapter"]
    db.commit()
    return {"restored": done, "skipped": skipped}


# ---- closing an experiment ---------------------------------------------------------------------------------------


class CloseIn(BaseModel):
    outcome: Literal["accepted", "rejected", "harvested"]
    # harvest notes, one per chapter leaving the book (each optional), or one note for them all
    notes: dict[str, str] = Field(default_factory=dict)
    note: str | None = Field(default=None, max_length=5000)
    decision: str | None = Field(default=None, max_length=1000)
    decided_on: date | None = None
    review: list[Choice] = Field(default_factory=list, max_length=100_000)


def close(db: Session, world: World, user: User, item: Item, body: CloseIn) -> tuple[RetireReview, list[str]]:
    """Accept: the drafts become current chapters in their order at the place of the range's first chapter still
    current (or where it adds), after the review of the range, which is retired. Harvest or reject: the drafts are
    retired, after the review of what was recorded in them. Returns the review and anything to say about it."""
    if item.status != "open":
        raise HTTPException(409, "This experiment is closed already.")
    drafts = drafts_of(db, item.id)
    rng = range_of(db, item.id)
    said: list[str] = []
    notes = dict(body.notes)
    if body.outcome == "accepted":
        leaving = [c for c in rng if c.state == "current"]
        gone = [c for c in rng if c.state != "current"]
        if gone:
            said.append(f"{len(gone)} of the chapters it would replace {'was' if len(gone) == 1 else 'were'} no "
                        f"longer in the book, and stayed where {'it is' if len(gone) == 1 else 'they are'}.")
        if body.note and leaving and not notes:
            notes = {str(leaving[0].id): body.note}
        changes = apply_review(db, world, user, [c.id for c in leaving], body.review, drafts)
        project_id = (leaving[0].project_id if leaving else drafts[0].project_id if drafts else item.project_id)
        current = list(db.scalars(select(Chapter).where(Chapter.project_id == project_id, Chapter.state == "current")
                                  .order_by(Chapter.position, Chapter.created_at)))
        if leaving:
            at = current.index(leaving[0])
        else:
            anchor = db.get(Chapter, item.insert_at_chapter_id) if item.insert_at_chapter_id else None
            if anchor is not None and anchor in current:
                at = current.index(anchor) + (1 if item.insert_side == "after" else 0)
            else:
                at = len(current)
        changes += _leave(db, user, leaving, notes)
        stay = [c for c in current if c not in leaving]
        before = sum(1 for c in current[:at] if c not in leaving)
        for d in drafts:
            changes.append({"kind": "chapter", "action": "accept", "id": str(d.id), "chapter_id": str(d.id),
                            "before": {"state": d.state, "position": d.position}})
            snapshot(db, d, "state", user)
            d.state = "current"
            d.version += 1
            d.updated_by = user.id
        book = stay[:before] + drafts + stay[before:]
        for i, c in enumerate(book):
            c.position = i
    else:
        if body.note and drafts and not notes:
            notes = {str(d.id): body.note for d in drafts}
        changes = apply_review(db, world, user, [d.id for d in drafts], body.review)
        changes += _leave(db, user, drafts, notes)
    changes.append({"kind": "experiment", "action": body.outcome, "id": str(item.id), "chapter_id": None,
                    "before": {"status": item.status}, "decisions": []})
    item.status = body.outcome
    item.closed_at = datetime.now(UTC)
    item.closed_note = (body.note or "").strip() or None
    item.version += 1
    item.updated_by = user.id
    text = " ".join((body.decision or "").split())
    if text:
        d = Decision(world_id=world.id, project_id=item.project_id, decided_on=body.decided_on or date.today(),
                     text=text, item_id=item.id, created_by=user.id, updated_by=user.id)
        db.add(d)
        db.flush()
        refresh_source(db, world.id, "decision", d.id, d.text)
        changes[-1]["decisions"] = [str(d.id)]
    db.flush()
    for pid in {c.project_id for c in [*rng, *drafts]}:
        _renumber(db, pid)
    ids = [uuid.UUID(c["id"]) for c in changes if c["kind"] == "chapter" and c["action"] == "retire"]
    review = RetireReview(world_id=world.id, chapter_ids=ids, changes=changes, created_by=user.id)
    db.add(review)
    db.flush()
    return review, said


@router.post("/experiments/{item_id}/close")
def close_experiment(slug: str, item_id: uuid.UUID, body: CloseIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
    review, said = close(db, world, user, item, body)
    db.commit()
    first = drafts_of(db, item.id, ("current",))
    return {**_review_out(review), "said": said, "first": str(first[0].id) if first else None}


# ---- evidence in Salvage (docs/SPEC.md §13.6.3) ---------------------------------------------------------------


def evidence_retired(db: Session, world: World) -> list[dict]:
    """The Archivist's findings: a fact's or relationship's evidence (its passage, established in a chapter) in a
    retired chapter. Each with the chapters where the passage is found now (current ones and drafts), first."""
    retired = {c.id: c for c, in db.execute(select(Chapter).join(Project, Project.id == Chapter.project_id)
                                            .where(Project.world_id == world.id, Chapter.state == "retired"))}
    if not retired:
        return []
    dismissed = {r.key for r in db.scalars(select(Resolution).where(Resolution.world_id == world.id,
                                                                    Resolution.rule == "evidence_retired",
                                                                    Resolution.outcome == "intentional"))}
    living = list(db.scalars(select(Chapter).join(Project, Project.id == Chapter.project_id)
                             .where(Project.world_id == world.id, Chapter.state != "retired")
                             .order_by(Project.position, Chapter.state, Chapter.position)))
    entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.world_id == world.id))}
    types = {t.id: t for t in db.scalars(select(RelationType).where(RelationType.world_id == world.id))}
    out = []

    def ref(e: Entity | None) -> dict | None:
        return {"id": str(e.id), "name": e.name, "kind": e.kind} if e else None

    def add(kind: str, obj: Fact | Relationship, who: list[Entity | None], what: str) -> None:
        ch = retired.get(obj.established_in_chapter_id) if obj.established_in_chapter_id else None
        key = f"{kind}:{obj.id}"
        if ch is None or not (obj.evidence or "").strip() or key in dismissed:
            return
        passage = obj.evidence.strip()
        found = [{"id": str(c.id), "title": c.title, "state": c.state} for c in living if passage in c.body]
        out.append({"rule": "evidence_retired", "key": key, "kind": kind, "id": str(obj.id),
                    "message": f"{what} rests on a passage in a retired chapter, “{ch.title}”.",
                    "chapter": {"id": str(ch.id), "title": ch.title}, "passage": passage,
                    "entities": [r for r in (ref(e) for e in who) if r], "found": found})

    for f in db.scalars(select(Fact).where(Fact.world_id == world.id, Fact.established_in_chapter_id.in_(retired))):
        e = entities.get(f.entity_id)
        add("fact", f, [e], f"{e.name if e else '?'}: “{f.label}{': ' + f.value if f.value else ''}”")
    for r in db.scalars(select(Relationship).where(Relationship.world_id == world.id,
                                                   Relationship.established_in_chapter_id.in_(retired))):
        a, b = entities.get(r.a_id), entities.get(r.b_id)
        t = types.get(r.type_id)
        add("relationship", r, [a, b], f"“{a.name if a else '?'} {t.label if t else '?'} {b.name if b else '?'}”")
    return out


@router.get("/evidence-retired")
def list_evidence_retired(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    return evidence_retired(db, world)


class ReanchorIn(BaseModel):
    kind: Literal["fact", "relationship"]
    id: uuid.UUID
    chapter_id: uuid.UUID


@router.post("/evidence/re-anchor")
def re_anchor(slug: str, body: ReanchorIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Re-anchor: the evidence points at another chapter (one where its passage is found, usually)."""
    world, _ = member_world(db, user, slug)
    obj = db.get(MODELS[body.kind], body.id)
    if obj is None or obj.world_id != world.id:
        raise HTTPException(404, "No such fact or relationship.")
    obj.established_in_chapter_id = _chapter(db, world, body.chapter_id).id
    obj.version += 1
    obj.updated_by = user.id
    db.commit()
    return {"id": str(obj.id), "established_in_chapter_id": str(obj.established_in_chapter_id)}
