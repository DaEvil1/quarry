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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Decision, Item, Project, User, World
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


class ItemIn(BaseModel):
    id: uuid.UUID | None = None
    kind: Kind = "spark"
    title: str | None = Field(default=None, max_length=300)
    body: str = Field(max_length=BODY_MAX)
    project: str | None = None
    source: str | None = Field(default=None, max_length=40)
    captured_at: datetime | None = None


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


def item_out(item: Item, world: World) -> ItemOut:
    slugs = {p.id: p.slug for p in world.projects}
    return ItemOut(id=item.id, kind=item.kind, title=item.title, body=item.body, status=item.status,
                   project=slugs.get(item.project_id) if item.project_id else None, source=item.source,
                   closed_note=item.closed_note, closed_at=item.closed_at, created_at=item.created_at,
                   updated_at=item.updated_at, version=item.version)


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
def list_items(slug: str, status: StatusFilter = "open", project: str | None = None, kind: Kind | None = None,
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
    return [item_out(i, world) for i in db.scalars(q.limit(limit))]


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
            return JSONResponse(status_code=200, content=item_out(existing, world).model_dump(mode="json"))
    project = project_by_slug(world, body.project)
    now = datetime.now(UTC)
    captured = body.captured_at
    if captured is not None and captured.tzinfo is None:
        captured = captured.replace(tzinfo=UTC)
    if captured is None or captured > now + CLOCK_SKEW:
        captured = now
    item = Item(id=body.id or uuid.uuid4(), world_id=world.id, project_id=project.id if project else None,
                kind=body.kind, title=(body.title or "").strip() or None, body=_clean_body(body.body),
                source=body.source, created_by=user.id, updated_by=user.id, created_at=captured)
    db.add(item)
    db.commit()
    return item_out(item, world)


@router.get("/items/{item_id}")
def get_item(slug: str, item_id: uuid.UUID, user: User = Depends(current_user),
             db: Session = Depends(get_db)) -> ItemOut:
    world, _ = member_world(db, user, slug)
    return item_out(_item(db, world, item_id), world)


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
    db.commit()
    return item_out(item, world)


@router.post("/items/{item_id}/close")
def close_item(slug: str, item_id: uuid.UUID, body: CloseIn, user: User = Depends(current_user),
               db: Session = Depends(get_db)) -> CloseOut:
    world, _ = member_world(db, user, slug)
    item = _item(db, world, item_id)
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
        decision_id = d.id
    db.commit()
    return CloseOut(item=item_out(item, world), decision_id=decision_id)


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
    return item_out(item, world)
