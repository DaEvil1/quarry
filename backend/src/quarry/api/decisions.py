"""The decisions log: dated one-line verdicts, kept apart from the reasoning that led to them."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import forget_source, refresh_source
from ..models import Decision, Item, User, World
from .deps import current_user
from .items import WORLD_ONLY, project_by_slug
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")


class DecisionOut(BaseModel):
    id: uuid.UUID
    decided_on: date
    text: str
    project: str | None
    item_id: uuid.UUID | None
    created_at: datetime


class DecisionIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    decided_on: date | None = None
    project: str | None = None
    item_id: uuid.UUID | None = None


class DecisionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=1000)
    decided_on: date | None = None
    project: str | None = None


def _out(d: Decision, world: World) -> DecisionOut:
    slugs = {p.id: p.slug for p in world.projects}
    return DecisionOut(id=d.id, decided_on=d.decided_on, text=d.text,
                       project=slugs.get(d.project_id) if d.project_id else None, item_id=d.item_id,
                       created_at=d.created_at)


def _text(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        raise HTTPException(422, "Write the decision first.")
    return text


def _decision(db: Session, world: World, decision_id: uuid.UUID) -> Decision:
    d = db.get(Decision, decision_id)
    if d is None or d.world_id != world.id:
        raise HTTPException(404, "No such decision.")
    return d


@router.get("/decisions")
def list_decisions(slug: str, project: str | None = None, limit: int = Query(500, ge=1, le=2000),
                   user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[DecisionOut]:
    world, _ = member_world(db, user, slug)
    q = select(Decision).where(Decision.world_id == world.id)
    if project == WORLD_ONLY:
        q = q.where(Decision.project_id.is_(None))
    elif project:
        p = project_by_slug(world, project)
        assert p is not None
        q = q.where(Decision.project_id == p.id)
    q = q.order_by(Decision.decided_on.desc(), Decision.created_at.desc()).limit(limit)
    return [_out(d, world) for d in db.scalars(q)]


@router.post("/decisions", status_code=201)
def create_decision(slug: str, body: DecisionIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)) -> DecisionOut:
    world, _ = member_world(db, user, slug)
    project = project_by_slug(world, body.project)
    if body.item_id is not None:
        item = db.get(Item, body.item_id)
        if item is None or item.world_id != world.id:
            raise HTTPException(422, "No such item in this world.")
    d = Decision(world_id=world.id, project_id=project.id if project else None,
                 decided_on=body.decided_on or date.today(), text=_text(body.text), item_id=body.item_id,
                 created_by=user.id, updated_by=user.id)
    db.add(d)
    db.flush()
    refresh_source(db, world.id, "decision", d.id, d.text)
    db.commit()
    return _out(d, world)


@router.patch("/decisions/{decision_id}")
def update_decision(slug: str, decision_id: uuid.UUID, body: DecisionUpdate, user: User = Depends(current_user),
                    db: Session = Depends(get_db)) -> DecisionOut:
    world, _ = member_world(db, user, slug)
    d = _decision(db, world, decision_id)
    if body.text is not None:
        d.text = _text(body.text)
    if body.decided_on is not None:
        d.decided_on = body.decided_on
    if "project" in body.model_fields_set:
        p = project_by_slug(world, body.project)
        d.project_id = p.id if p else None
    d.updated_by = user.id
    db.flush()
    refresh_source(db, world.id, "decision", d.id, d.text)
    db.commit()
    return _out(d, world)


@router.delete("/decisions/{decision_id}", status_code=204)
def delete_decision(slug: str, decision_id: uuid.UUID, user: User = Depends(current_user),
                    db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    d = _decision(db, world, decision_id)
    forget_source(db, "decision", d.id)
    db.delete(d)
    db.commit()
