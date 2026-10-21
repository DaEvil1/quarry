"""The signed-in user, and the worlds and projects they belong to."""

from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Project, User, World, WorldMember
from .deps import current_user

router = APIRouter(prefix="/api")

Kind = Literal["novel", "novella", "short", "other"]
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_MAX = 60
# letters that do not decompose into a base letter plus an accent
_TRANSLIT = str.maketrans({"æ": "ae", "Æ": "ae", "ø": "o", "Ø": "o", "œ": "oe", "Œ": "oe", "ß": "ss",
                           "þ": "th", "Þ": "th", "ð": "d", "Ð": "d", "đ": "d", "Đ": "d", "ł": "l", "Ł": "l"})


def slugify(name: str, fallback: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name.translate(_TRANSLIT)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug[:SLUG_MAX].rstrip("-") or fallback


def _unique(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    n = 2
    while f"{base[:SLUG_MAX - 4]}-{n}" in taken:
        n += 1
    return f"{base[:SLUG_MAX - 4]}-{n}"


def _check_slug(slug: str) -> str:
    slug = slug.strip().lower()
    if len(slug) > SLUG_MAX or not SLUG_RE.match(slug):
        raise HTTPException(422, "Use lowercase letters, digits and single hyphens in the address.")
    return slug


def _clean_name(name: str) -> str:
    name = " ".join(name.split())
    if not name:
        raise HTTPException(422, "Give it a name.")
    return name


# shapes --------------------------------------------------------------------------------------------------------


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: str
    position: int


class WorldOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: str
    projects: list[ProjectOut]


class UserOut(BaseModel):
    id: uuid.UUID
    display_name: str


class MeOut(BaseModel):
    user: UserOut
    worlds: list[WorldOut]


class MeUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class WorldIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class WorldUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=SLUG_MAX)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Kind = "novel"


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=SLUG_MAX)
    kind: Kind | None = None


class ProjectOrder(BaseModel):
    ids: list[uuid.UUID]


def _project_out(p: Project) -> ProjectOut:
    return ProjectOut(id=p.id, name=p.name, slug=p.slug, kind=p.kind, position=p.position)


def _world_out(w: World, role: str) -> WorldOut:
    return WorldOut(id=w.id, name=w.name, slug=w.slug, role=role, projects=[_project_out(p) for p in w.projects])


def _my_worlds(db: Session, user: User) -> list[WorldOut]:
    rows = db.execute(
        select(World, WorldMember.role)
        .join(WorldMember, WorldMember.world_id == World.id)
        .where(WorldMember.user_id == user.id)
        .options(selectinload(World.projects))
        .order_by(func.lower(World.name))
    ).all()
    return [_world_out(w, role) for w, role in rows]


def member_world(db: Session, user: User, slug: str) -> tuple[World, str]:
    """The world with this address, if the user is a member of it (404 otherwise), and their role."""
    row = db.execute(
        select(World, WorldMember.role)
        .join(WorldMember, WorldMember.world_id == World.id)
        .where(WorldMember.user_id == user.id, World.slug == slug)
        .options(selectinload(World.projects))
    ).first()
    if row is None:
        raise HTTPException(404, "No such world.")
    return row[0], row[1]


def _project(world: World, slug: str) -> Project:
    for p in world.projects:
        if p.slug == slug:
            return p
    raise HTTPException(404, "No such project.")


# me ------------------------------------------------------------------------------------------------------------


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> MeOut:
    return MeOut(user=UserOut(id=user.id, display_name=user.display_name), worlds=_my_worlds(db, user))


@router.patch("/me")
def update_me(body: MeUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)) -> UserOut:
    user.display_name = _clean_name(body.display_name)
    db.commit()
    return UserOut(id=user.id, display_name=user.display_name)


# worlds --------------------------------------------------------------------------------------------------------


@router.get("/worlds")
def list_worlds(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[WorldOut]:
    return _my_worlds(db, user)


@router.post("/worlds", status_code=201)
def create_world(body: WorldIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> WorldOut:
    name = _clean_name(body.name)
    taken = set(db.scalars(select(World.slug)).all())
    w = World(name=name, slug=_unique(slugify(name, "world"), taken), created_by=user.id, updated_by=user.id)
    db.add(w)
    db.flush()
    db.add(WorldMember(world_id=w.id, user_id=user.id, role="owner"))
    db.commit()
    return _world_out(w, "owner")


@router.get("/worlds/{slug}")
def get_world(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> WorldOut:
    w, role = member_world(db, user, slug)
    return _world_out(w, role)


@router.patch("/worlds/{slug}")
def update_world(slug: str, body: WorldUpdate, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> WorldOut:
    w, role = member_world(db, user, slug)
    if body.name is not None:
        w.name = _clean_name(body.name)
    if body.slug is not None:
        new = _check_slug(body.slug)
        if new != w.slug and db.scalar(select(World.id).where(World.slug == new)) is not None:
            raise HTTPException(409, "Another world already uses that address.")
        w.slug = new
    w.updated_by = user.id
    db.commit()
    return _world_out(w, role)


# projects ------------------------------------------------------------------------------------------------------


@router.post("/worlds/{slug}/projects", status_code=201)
def create_project(slug: str, body: ProjectIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> ProjectOut:
    w, _ = member_world(db, user, slug)
    name = _clean_name(body.name)
    taken = {p.slug for p in w.projects}
    position = max((p.position for p in w.projects), default=-1) + 1
    p = Project(world_id=w.id, name=name, slug=_unique(slugify(name, "project"), taken), kind=body.kind,
                position=position, created_by=user.id, updated_by=user.id)
    db.add(p)
    db.commit()
    return _project_out(p)


@router.patch("/worlds/{slug}/projects/{project_slug}")
def update_project(slug: str, project_slug: str, body: ProjectUpdate, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> ProjectOut:
    w, _ = member_world(db, user, slug)
    p = _project(w, project_slug)
    if body.name is not None:
        p.name = _clean_name(body.name)
    if body.kind is not None:
        p.kind = body.kind
    if body.slug is not None:
        new = _check_slug(body.slug)
        if new != p.slug and any(o.slug == new for o in w.projects):
            raise HTTPException(409, "Another project in this world already uses that address.")
        p.slug = new
    p.updated_by = user.id
    db.commit()
    return _project_out(p)


@router.put("/worlds/{slug}/project-order")
def reorder_projects(slug: str, body: ProjectOrder, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> list[ProjectOut]:
    w, _ = member_world(db, user, slug)
    by_id = {p.id: p for p in w.projects}
    if len(body.ids) != len(by_id) or set(body.ids) != set(by_id):
        raise HTTPException(422, "Send every project in the world exactly once.")
    for i, pid in enumerate(body.ids):
        by_id[pid].position = i
    db.commit()
    return [_project_out(by_id[pid]) for pid in body.ids]
