"""Items (sparks, questions, tasks): capture, list, edit, and close them in triage.

Captures may arrive late from an offline phone, so the client picks the id and the capture time; sending the same
capture twice saves it once. Edits carry the version they started from and are refused (409) when the item has
changed since, with the current copy in the answer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import refresh_source
from ..models import Chapter, Decision, Entity, Item, ItemLink, JournalEntry, Mention, Project, User, World
from .deps import current_user
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

Kind = Literal["spark", "question", "task"]
CloseStatus = Literal["accepted", "rejected", "harvested", "deferred"]
StatusFilter = Literal["open", "deferred", "closed", "all"]
CLOSED = ("accepted", "rejected", "harvested")
BODY_MAX = 20_000
# a capture's own time is trusted unless it claims to be from the future
CLOCK_SKEW = timedelta(minutes=5)
# "?project=-" means items that belong to the whole world rather than one project
WORLD_ONLY = "-"


class EntityRef(BaseModel):
    id: uuid.UUID
    name: str
    kind: str


class MentionOut(BaseModel):
    entity_id: uuid.UUID
    entity_name: str
    entity_kind: str = "other"
    start: int
    end: int
    matched_text: str
    kind: str


class ItemOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str | None
    body: str
    status: str
    project: str | None
    source: str | None
    closed_note: str | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int
    # bible entries the item is tagged with
    entities: list[EntityRef] = []
    # names (and near misses of names) found in the body
    mentions: list[MentionOut] = []
    # the chapter or journal entry it was made from, with the passage (docs/SPEC.md §14.3.1)
    origin: dict | None = None
    # the decisions it follows, as a task (docs/SPEC.md §16.1): id, decided_on, text
    follows: list[dict] = []


class ItemIn(BaseModel):
    id: uuid.UUID | None = None
    kind: Kind = "spark"
    title: str | None = Field(default=None, max_length=300)
    body: str = Field(max_length=BODY_MAX)
    project: str | None = None
    source: str | None = Field(default=None, max_length=40)
    captured_at: datetime | None = None
    # bible entries to tag it with (unknown ones are skipped: the phone's list may be older)
    entities: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    # the chapter it was thought of in (a thought stashed while writing), or the journal entry; with the passage it
    # was made from, when made from a selection (docs/SPEC.md §14.3.1)
    chapter_id: uuid.UUID | None = None
    journal_id: uuid.UUID | None = None
    passage: str | None = Field(default=None, max_length=BODY_MAX)
    # made from a plan's passage: the chapters ticked, so it shows in their Loose ends (docs/SPEC.md §18.4)
    chapter_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    # "Park it": kept as deferred instead of waiting in the inbox
    status: Literal["open", "deferred"] = "open"


class LinkIn(BaseModel):
    entity_id: uuid.UUID


class ItemUpdate(BaseModel):
    base_version: int
    kind: Kind | None = None
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=BODY_MAX)
    # present and null: move to the whole world; absent: leave as it is
    project: str | None = None


class CloseIn(BaseModel):
    status: CloseStatus
    note: str | None = Field(default=None, max_length=2000)
    # a one-line verdict for the decisions log
    decision: str | None = Field(default=None, max_length=1000)
    # the person's own date for the decision (their time zone, not the server's)
    decided_on: date | None = None


class CloseOut(BaseModel):
    item: ItemOut
    decision_id: uuid.UUID | None


def project_by_slug(world: World, slug: str | None) -> Project | None:
    if slug is None or slug == "":
        return None
    for p in world.projects:
        if p.slug == slug:
            return p
    raise HTTPException(422, "No such project in this world.")


def item_out(item: Item, world: World, entities: list[EntityRef] | None = None,
             mentions: list[MentionOut] | None = None, origin: dict | None = None,
             follows: list[dict] | None = None) -> ItemOut:
    slugs = {p.id: p.slug for p in world.projects}
    return ItemOut(id=item.id, kind=item.kind, title=item.title, body=item.body, status=item.status,
                   project=slugs.get(item.project_id) if item.project_id else None, source=item.source,
                   closed_note=item.closed_note, closed_at=item.closed_at, created_at=item.created_at,
                   updated_at=item.updated_at, version=item.version, entities=entities or [],
                   mentions=mentions or [], origin=origin, follows=follows or [])


def items_out(db: Session, world: World, items: list[Item]) -> list[ItemOut]:
    """Items with their tags and mentions, in two queries for the whole list."""
    ids = [i.id for i in items]
    tags: dict[uuid.UUID, list[EntityRef]] = {i: [] for i in ids}
    found: dict[uuid.UUID, list[MentionOut]] = {i: [] for i in ids}
    if ids:
        for item_id, e in db.execute(
            select(ItemLink.item_id, Entity).join(Entity, Entity.id == ItemLink.target_id)
            .where(ItemLink.item_id.in_(ids), ItemLink.target_table == "entity").order_by(Entity.name)
        ).all():
            tags[item_id].append(EntityRef(id=e.id, name=e.name, kind=e.kind))
        for m, name, ekind in db.execute(
            select(Mention, Entity.name, Entity.kind).join(Entity, Entity.id == Mention.entity_id)
            .where(Mention.source_table == "item", Mention.source_id.in_(ids)).order_by(Mention.start, Entity.name)
        ).all():
            found[m.source_id].append(MentionOut(entity_id=m.entity_id, entity_name=name, entity_kind=ekind,
                                                 start=m.start, end=m.end, matched_text=m.matched_text,
                                                 kind=m.kind))
    origins = item_origins(db, ids)
    from .followups import follows_of

    follows = follows_of(db, "item", ids)
    return [item_out(i, world, tags[i.id], found[i.id], origins.get(i.id), follows.get(i.id)) for i in items]


def item_origins(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """Where each item came from: the chapter (its title) or journal entry (its date and title) it is linked to, with
    the passage it was made from. A journal entry wins over a chapter; nothing for items without either."""
    out: dict[uuid.UUID, dict] = {}
    if not ids:
        return out
    for link, ch in db.execute(
        select(ItemLink, Chapter).join(Chapter, Chapter.id == ItemLink.target_id)
        .where(ItemLink.item_id.in_(ids), ItemLink.target_table == "chapter")
    ).all():
        out[link.item_id] = {"table": "chapter", "id": str(ch.id), "title": ch.title, "date": None,
                             "passage": link.passage}
    for link, j in db.execute(
        select(ItemLink, JournalEntry).join(JournalEntry, JournalEntry.id == ItemLink.target_id)
        .where(ItemLink.item_id.in_(ids), ItemLink.target_table == "journal")
    ).all():
        out[link.item_id] = {"table": "journal", "id": str(j.id), "title": j.title,
                             "date": j.entry_date.isoformat(), "passage": link.passage}
    return out


def one_out(db: Session, world: World, item: Item) -> ItemOut:
    return items_out(db, world, [item])[0]


def _item(db: Session, world: World, item_id: uuid.UUID) -> Item:
    item = db.get(Item, item_id)
    if item is None or item.world_id != world.id:
        raise HTTPException(404, "No such item.")
    return item


def _clean_body(body: str) -> str:
    body = body.strip()
    if not body:
        raise HTTPException(422, "Write something first.")
    return body


def _changed_since(item: Item, world: World, base_version: int) -> JSONResponse | None:
    if item.version == base_version:
        return None
    return JSONResponse(status_code=409, content={
        "detail": "This item changed on another device. Here is the newer version.",
        "item": item_out(item, world).model_dump(mode="json"),
    })


@router.get("/items")
def list_items(slug: str, status: StatusFilter = "open", project: str | None = None,
               kind: Literal["spark", "question", "task", "experiment"] | None = None,
               order: Literal["newest", "oldest"] = "newest", limit: int = Query(200, ge=1, le=1000),
               user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[ItemOut]:
    world, _ = member_world(db, user, slug)
    q = select(Item).where(Item.world_id == world.id)
    if status == "closed":
        q = q.where(Item.status.in_(CLOSED))
    elif status != "all":
        q = q.where(Item.status == status)
    if project == WORLD_ONLY:
        q = q.where(Item.project_id.is_(None))
    elif project:
        p = project_by_slug(world, project)
        assert p is not None
        q = q.where(Item.project_id == p.id)
    if kind:
        q = q.where(Item.kind == kind)
    if status == "closed":
        q = q.order_by(Item.closed_at.desc(), Item.id)
    elif order == "oldest":
        q = q.order_by(Item.created_at, Item.id)
    else:
        q = q.order_by(Item.created_at.desc(), Item.id)
    return items_out(db, world, list(db.scalars(q.limit(limit))))


@router.get("/items/counts")
def item_counts(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    world, _ = member_world(db, user, slug)
    rows = db.execute(
        select(Item.status, Item.project_id, func.count())
        .where(Item.world_id == world.id, Item.status.in_(("open", "deferred")))
        .group_by(Item.status, Item.project_id)
    ).all()
    slugs = {p.id: p.slug for p in world.projects}
    out: dict[str, Any] = {"open": 0, "deferred": 0, "open_by_project": {}}
    for status, project_id, n in rows:
        out[status] += n
        if status == "open":
            key = slugs.get(project_id, WORLD_ONLY) if project_id else WORLD_ONLY
            out["open_by_project"][key] = out["open_by_project"].get(key, 0) + n
    return out


@router.post("/items", status_code=201)
def create_item(slug: str, body: ItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    world, _ = member_world(db, user, slug)
    if body.id is not None:
        existing = db.get(Item, body.id)
        if existing is not None:
            if existing.world_id != world.id or existing.created_by != user.id:
                raise HTTPException(409, "That id is already taken.")
            # the same capture sent again (an offline phone retrying): already saved
            return JSONResponse(status_code=200, content=one_out(db, world, existing).model_dump(mode="json"))
    project = project_by_slug(world, body.project)
    now = datetime.now(UTC)
    captured = body.captured_at
    if captured is not None and captured.tzinfo is None:
        captured = captured.replace(tzinfo=UTC)
    if captured is None or captured > now + CLOCK_SKEW:
        captured = now
    item = Item(id=body.id or uuid.uuid4(), world_id=world.id, project_id=project.id if project else None,
                kind=body.kind, title=(body.title or "").strip() or None, body=_clean_body(body.body),
                status=body.status, source=body.source, created_by=user.id, updated_by=user.id, created_at=captured)
    db.add(item)
    db.flush()
    if body.entities:
        known = set(db.scalars(select(Entity.id).where(Entity.world_id == world.id, Entity.id.in_(body.entities))))
        db.add_all(ItemLink(item_id=item.id, target_table="entity", target_id=e) for e in dict.fromkeys(body.entities)
                   if e in known)
    passage = (body.passage or "").strip() or None
    if body.chapter_id is not None:
        ch = db.get(Chapter, body.chapter_id)
        if ch is not None and db.get(Project, ch.project_id).world_id == world.id:
            db.add(ItemLink(item_id=item.id, target_table="chapter", target_id=ch.id, passage=passage))
    if body.journal_id is not None:
        j = db.get(JournalEntry, body.journal_id)
        if j is not None and j.world_id == world.id:
            db.add(ItemLink(item_id=item.id, target_table="journal", target_id=j.id, passage=passage))
    for cid in dict.fromkeys(body.chapter_ids):
        ch = db.get(Chapter, cid)
        if cid != body.chapter_id and ch is not None and db.get(Project, ch.project_id).world_id == world.id:
            db.add(ItemLink(item_id=item.id, target_table="chapter", target_id=ch.id))
    refresh_source(db, world.id, "item", item.id, item.body)
    db.commit()
    return one_out(db, world, item)


@router.get("/items/{item_id}")
def get_item(slug: str, item_id: uuid.UUID, user: User = Depends(current_user),
             db: Session = Depends(get_db)) -> ItemOut:
    world, _ = member_world(db, user, slug)
    return one_out(db, world, _item(db, world, item_id))


@router.patch("/items/{item_id}")
def update_item(slug: str, item_id: uuid.UUID, body: ItemUpdate, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
    if (conflict := _changed_since(item, world, body.base_version)) is not None:
        return conflict
    if body.kind is not None:
        item.kind = body.kind
    if "title" in body.model_fields_set:
        item.title = (body.title or "").strip() or None
    if body.body is not None:
        item.body = _clean_body(body.body)
    if "project" in body.model_fields_set:
        p = project_by_slug(world, body.project)
        item.project_id = p.id if p else None
    item.version += 1
    item.updated_by = user.id
    db.flush()
    if body.body is not None:
        refresh_source(db, world.id, "item", item.id, item.body)
    from .followups import refresh_what

    refresh_what(db, world, "item", item)
    db.commit()
    return one_out(db, world, item)


@router.post("/items/{item_id}/links", status_code=201)
def link_item(slug: str, item_id: uuid.UUID, body: LinkIn, user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> ItemOut:
    """Tag an item with a bible entry."""
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
    e = db.get(Entity, body.entity_id)
    if e is None or e.world_id != world.id:
        raise HTTPException(422, "No such entry in this world's bible.")
    if db.get(ItemLink, (item.id, "entity", e.id)) is None:
        db.add(ItemLink(item_id=item.id, target_table="entity", target_id=e.id))
        db.commit()
    return one_out(db, world, item)


@router.delete("/items/{item_id}/links/{entity_id}")
def unlink_item(slug: str, item_id: uuid.UUID, entity_id: uuid.UUID, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> ItemOut:
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
    db.execute(delete(ItemLink).where(ItemLink.item_id == item.id, ItemLink.target_table == "entity",
                                      ItemLink.target_id == entity_id))
    db.commit()
    return one_out(db, world, item)


@router.post("/items/{item_id}/close")
def close_item(slug: str, item_id: uuid.UUID, body: CloseIn, user: User = Depends(current_user),
               db: Session = Depends(get_db)) -> CloseOut:
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
    if item.kind == "experiment":
        raise HTTPException(409, "Close an experiment from its chapter in the manuscript.")
    if item.status in CLOSED:
        raise HTTPException(409, f"This item is already {item.status}.")
    if item.status == body.status:
        raise HTTPException(409, f"This item is already {item.status}.")
    item.status = body.status
    item.closed_at = datetime.now(UTC)
    item.closed_note = (body.note or "").strip() or None
    item.version += 1
    item.updated_by = user.id
    decision_id = None
    text = " ".join((body.decision or "").split())
    if text:
        d = Decision(world_id=world.id, project_id=item.project_id, decided_on=body.decided_on or date.today(),
                     text=text, item_id=item.id, created_by=user.id, updated_by=user.id)
        db.add(d)
        db.flush()
        refresh_source(db, world.id, "decision", d.id, d.text)
        decision_id = d.id
    db.commit()
    return CloseOut(item=one_out(db, world, item), decision_id=decision_id)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(slug: str, item_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    """Undo an item just made (a spark or question from a passage): only an open or parked one, never an experiment,
    and never one a decision came from."""
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
    if item.kind == "experiment" or item.status not in ("open", "deferred") or db.scalar(
            select(func.count()).select_from(Decision).where(Decision.item_id == item.id)):
        raise HTTPException(409, "Only an open item can be removed; close it instead.")
    db.execute(delete(Mention).where(Mention.source_table == "item", Mention.source_id == item.id))
    from .followups import drop_for_deleted

    drop_for_deleted(db, world, "item", item)
    db.delete(item)
    db.commit()


@router.post("/items/{item_id}/reopen")
def reopen_item(slug: str, item_id: uuid.UUID, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> ItemOut:
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
    if item.status != "open":
        item.status = "open"
        item.closed_at = None
        item.closed_note = None
        item.version += 1
        item.updated_by = user.id
        db.commit()
    return one_out(db, world, item)
