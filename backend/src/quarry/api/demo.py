"""Load the demo world (quarry/demo.py) for the signed-in writer: a made-up story that uses every part of Quarry."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..demo import create_demo
from ..models import User
from .deps import current_user
from .worlds import WorldOut, _world_out

router = APIRouter(prefix="/api/worlds")


@router.post("/demo", status_code=201)
def load_demo(user: User = Depends(current_user), db: Session = Depends(get_db)) -> WorldOut:
    """A new copy of the demo world each time (its address gets a number if one is already there)."""
    world = create_demo(db, user)
    db.commit()
    db.refresh(world)
    return _world_out(world, "owner")
