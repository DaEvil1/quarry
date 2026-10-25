"""The chart (docs/SPEC.md §13.7): a schematic map of the world's places, drawn in the browser from the cards and the
graph. What it stores is only where places were dragged to (pins, each relative to its container) and its settings
(shapes for the world's own place types). `GET /chart` returns both; a pin is set with `PUT /chart/pins/<place>`, and
`DELETE /chart/pins` unpins everything, or everything inside one container, answering with what it removed so that
`POST /chart/pins` can put it back (Undo)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ChartPin, Entity, User, World
from .deps import current_user
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

SHAPES = ("world", "hexagon", "circle", "rounded", "square", "water", "ribbon", "island", "triangle", "scalloped",
          "dotted", "plane")


class PinIn(BaseModel):
    container_id: uuid.UUID | None = None
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class PinOut(BaseModel):
    place_id: uuid.UUID
    container_id: uuid.UUID | None
    x: float
    y: float


class PinsIn(BaseModel):
    pins: list[PinOut] = Field(max_length=5000)


class SettingsIn(BaseModel):
    """Shapes for the world's own type values: {"duchy": "hexagon"}."""

    shapes: dict[str, str] = Field(default_factory=dict, max_length=200)


def _out(p: ChartPin) -> dict:
    return {"place_id": str(p.place_id), "container_id": str(p.container_id) if p.container_id else None,
            "x": p.x, "y": p.y}


def chart_of(db: Session, world: World) -> dict:
    pins = db.scalars(select(ChartPin).where(ChartPin.world_id == world.id).order_by(ChartPin.updated_at))
    return {"pins": [_out(p) for p in pins], "settings": {"shapes": dict((world.chart or {}).get("shapes") or {})}}


def _place(db: Session, world: World, pid: uuid.UUID | None) -> Entity | None:
    if pid is None:
        return None
    e = db.get(Entity, pid)
    if e is None or e.world_id != world.id or e.kind != "place":
        raise HTTPException(404, "No such place.")
    return e


def _set(db: Session, world: World, user: User, place_id: uuid.UUID, container_id: uuid.UUID | None, x: float,
         y: float) -> ChartPin:
    _place(db, world, place_id)
    _place(db, world, container_id)
    if container_id == place_id:
        raise HTTPException(422, "A place can't be pinned inside itself.")
    pin = db.scalar(select(ChartPin).where(ChartPin.place_id == place_id, ChartPin.container_id == container_id)
                    if container_id else
                    select(ChartPin).where(ChartPin.place_id == place_id, ChartPin.container_id.is_(None)))
    if pin is None:
        pin = ChartPin(world_id=world.id, place_id=place_id, container_id=container_id, x=x, y=y, updated_by=user.id)
        db.add(pin)
    else:
        pin.x, pin.y, pin.updated_by = x, y, user.id
    return pin


@router.get("/chart")
def get_chart(slug: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    world, _ = member_world(db, user, slug)
    return chart_of(db, world)


@router.put("/chart/pins/{place_id}")
def put_pin(slug: str, place_id: uuid.UUID, body: PinIn, db: Session = Depends(get_db),
            user: User = Depends(current_user)) -> dict:
    """Pin a place where it was dragged to, relative to its container (none: the top level)."""
    world, _ = member_world(db, user, slug)
    pin = _set(db, world, user, place_id, body.container_id, body.x, body.y)
    db.commit()
    return _out(pin)


@router.post("/chart/pins")
def put_pins(slug: str, body: PinsIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    """Pin several at once: Undo of a reset."""
    world, _ = member_world(db, user, slug)
    for p in body.pins:
        _set(db, world, user, p.place_id, p.container_id, p.x, p.y)
    db.commit()
    return chart_of(db, world)


@router.delete("/chart/pins")
def reset_pins(slug: str, container: list[uuid.UUID] | None = Query(None), db: Session = Depends(get_db),
               user: User = Depends(current_user)) -> dict:
    """Reset layout: unpin everything, or (with `container`, repeated) every pin inside those places: the chart sends
    a container and every place inside it as it draws them, since what is inside what is read with *as of*. Answers
    with the pins removed, for Undo."""
    world, _ = member_world(db, user, slug)
    pins = list(db.scalars(select(ChartPin).where(ChartPin.world_id == world.id)))
    if container:
        inside = set(container)
        pins = [p for p in pins if p.container_id in inside]
    removed = [_out(p) for p in pins]
    if pins:
        db.execute(delete(ChartPin).where(ChartPin.id.in_([p.id for p in pins])))
    db.commit()
    return {"removed": removed}


@router.put("/chart/settings")
def put_settings(slug: str, body: SettingsIn, db: Session = Depends(get_db),
                 user: User = Depends(current_user)) -> dict:
    """The chart's settings: shapes for the world's own type values."""
    world, _ = member_world(db, user, slug)
    shapes: dict[str, str] = {}
    for k, v in body.shapes.items():
        key = " ".join(k.split()).lower()[:100]
        if not key:
            continue
        if v not in SHAPES:
            raise HTTPException(422, f"No such shape: {v}.")
        shapes[key] = v
    world.chart = {**(world.chart or {}), "shapes": shapes}
    world.updated_by = user.id
    db.commit()
    return chart_of(db, world)
