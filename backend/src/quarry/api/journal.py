"""The journal: dated thinking on paper, for the whole world or one project."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import forget_source, refresh_source
from ..models import JournalEntry, User, World
from .deps import current_user
from .items import WORLD_ONLY, project_by_slug
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")


class EntryOut(BaseModel):
    id: uuid.UUID
    entry_date: date
    title: str | None
    body: str
    project: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class EntryIn(BaseModel):
    entry_date: date | None = None
    title: str | None = Field(default=None, max_length=300)
    body: str = Field(default="", max_length=500_000)
    project: str | None = None


class EntryUpdate(BaseModel):
    base_version: int
    entry_date: date | None = None
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=500_000)
    project: str | None = None


def _out(j: JournalEntry, world: World) -> EntryOut:
    slugs = {p.id: p.slug for p in world.projects}
    return EntryOut(id=j.id, entry_date=j.entry_date, title=j.title, body=j.body,
                    project=slugs.get(j.project_id) if j.project_id else None, version=j.version,
                    created_at=j.created_at, updated_at=j.updated_at)


def _entry(db: Session, world: World, entry_id: uuid.UUID) -> JournalEntry:
    j = db.get(JournalEntry, entry_id)
    if j is None or j.world_id != world.id:
        raise HTTPException(404, "No such journal entry.")
    return j


@router.get("/journal")
def list_journal(slug: str, project: str | None = None, limit: int = Query(200, ge=1, le=2000),
                 user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[EntryOut]:
    world, _ = member_world(db, user, slug)
    q = select(JournalEntry).where(JournalEntry.world_id == world.id)
    if project == WORLD_ONLY:
        q = q.where(JournalEntry.project_id.is_(None))
    elif project:
        p = project_by_slug(world, project)
        assert p is not None
        q = q.where(JournalEntry.project_id == p.id)
    q = q.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc()).limit(limit)
    return [_out(j, world) for j in db.scalars(q)]


@router.post("/journal", status_code=201)
def create_entry(slug: str, body: EntryIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> EntryOut:
    world, _ = member_world(db, user, slug)
    p = project_by_slug(world, body.project)
    j = JournalEntry(world_id=world.id, project_id=p.id if p else None, entry_date=body.entry_date or date.today(),
                     title=(body.title or "").strip() or None, body=body.body, created_by=user.id,
                     updated_by=user.id)
    db.add(j)
    db.flush()
    refresh_source(db, world.id, "journal", j.id, j.body)
    db.commit()
    return _out(j, world)


@router.get("/journal/{entry_id}")
def get_entry(slug: str, entry_id: uuid.UUID, user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> EntryOut:
    world, _ = member_world(db, user, slug)
    return _out(_entry(db, world, entry_id), world)


@router.patch("/journal/{entry_id}")
def update_entry(slug: str, entry_id: uuid.UUID, body: EntryUpdate, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    if j.version != body.base_version:
        return JSONResponse(status_code=409, content={
            "detail": "This entry changed on another device. Here is the newer version.",
            "entry": _out(j, world).model_dump(mode="json")})
    if body.entry_date is not None:
        j.entry_date = body.entry_date
    if "title" in body.model_fields_set:
        j.title = (body.title or "").strip() or None
    if body.body is not None:
        j.body = body.body
    if "project" in body.model_fields_set:
        p = project_by_slug(world, body.project)
        j.project_id = p.id if p else None
    j.version += 1
    j.updated_by = user.id
    db.flush()
    refresh_source(db, world.id, "journal", j.id, j.body)
    db.commit()
    return _out(j, world)


@router.delete("/journal/{entry_id}", status_code=204)
def delete_entry(slug: str, entry_id: uuid.UUID, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    forget_source(db, "journal", j.id)
    db.delete(j)
    db.commit()
