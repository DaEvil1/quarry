"""The Guide's sandbox (docs/SPEC.md §15): a fresh copy of the demo world for each walkthrough, so a walkthrough can
change things without touching the writer's own worlds or the demo world they explore. One sandbox at a time: it
stays after its walkthrough, to look around in, until the next walkthrough replaces it or the writer deletes it."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..demo import create_demo
from ..models import User, World, WorldMember
from .deps import current_user
from .worlds import WorldOut, _unique, _world_out

router = APIRouter(prefix="/api/guide")

NAME = "The Ninefold Delta (guide sandbox)"


def _drop_sandboxes(db: Session, user: User) -> None:
    owned = select(WorldMember.world_id).where(WorldMember.user_id == user.id, WorldMember.role == "owner")
    db.execute(delete(World).where(World.sandbox.is_(True), World.id.in_(owned)))


@router.post("/sandbox", status_code=201)
def new_sandbox(user: User = Depends(current_user), db: Session = Depends(get_db)) -> WorldOut:
    """A new copy of the demo world, marked as a sandbox; any earlier sandbox of this writer goes first."""
    _drop_sandboxes(db, user)
    db.flush()
    world = create_demo(db, user)
    world.name = NAME
    world.slug = _unique("guide-sandbox", set(db.scalars(select(World.slug).where(World.id != world.id))))
    world.sandbox = True
    db.commit()
    db.refresh(world)
    return _world_out(world, "owner")


@router.delete("/sandbox", status_code=204)
def end_sandbox(user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    """Delete the sandbox, with everything done in it."""
    _drop_sandboxes(db, user)
    db.commit()
