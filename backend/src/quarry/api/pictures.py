"""Pictures (docs/SPEC.md §17): uploaded into a world, kept in Postgres with a view copy and a thumb, placed in entries'
galleries and on picture lines in texts. Quarry stores and shows them; nothing reads what is in one."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..margin import PICTURE_RE
from ..models import (
    Chapter,
    Cut,
    Entity,
    EntityPicture,
    JournalEntry,
    Picture,
    PictureFile,
    User,
    World,
    WorldMember,
)
from ..pictures import MAX_BYTES, MEDIA_TYPES, TOO_BIG, PictureError, make, name_from_file, store
from .deps import current_user
from .worlds import member_world

router = APIRouter(prefix="/api")


class PictureOut(BaseModel):
    id: uuid.UUID
    name: str
    format: str
    width: int
    height: int
    size: int
    created_at: datetime


class PictureRename(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class GalleryPicture(BaseModel):
    picture: uuid.UUID
    caption: str = Field(default="", max_length=2000)


def picture_out(p: Picture) -> PictureOut:
    return PictureOut(id=p.id, name=p.name, format=p.format, width=p.width, height=p.height, size=p.size,
                      created_at=p.created_at)


def _picture(db: Session, user: User, picture_id: uuid.UUID) -> Picture:
    """A picture of a world the user is a member of (404 otherwise)."""
    p = db.scalars(select(Picture).join(WorldMember, WorldMember.world_id == Picture.world_id)
                   .where(Picture.id == picture_id, WorldMember.user_id == user.id)).first()
    if p is None:
        raise HTTPException(404, "No such picture.")
    return p


def gallery_of(db: Session, entity_id: uuid.UUID) -> list[dict]:
    """An entry's gallery in order (the first is its main picture), with each picture's size for the page."""
    rows = db.execute(select(EntityPicture, Picture).join(Picture, Picture.id == EntityPicture.picture_id)
                      .where(EntityPicture.entity_id == entity_id).order_by(EntityPicture.position)).all()
    return [{"id": str(p.id), "name": p.name, "caption": ep.caption, "width": p.width, "height": p.height}
            for ep, p in rows]


def main_pictures(db: Session, world_id: uuid.UUID) -> dict[uuid.UUID, uuid.UUID]:
    """Each entry's main picture (the first of its gallery), for its cards."""
    rows = db.execute(select(EntityPicture.entity_id, EntityPicture.picture_id).join(Entity, Entity.id == EntityPicture.entity_id)
                      .where(Entity.world_id == world_id, EntityPicture.position == 0)).all()
    return {e: p for e, p in rows}


def uses_in_world(db: Session, world: World) -> dict[str, dict[str, list[dict]]]:
    """Where each picture is used: the galleries that have it, and the texts with a picture line for it (chapters in
    every state, journal entries, entries' notes and the cuts bin; old revisions don't count)."""
    uses: dict[str, dict[str, list[dict]]] = defaultdict(lambda: {"entities": [], "texts": []})
    for ep, e in db.execute(select(EntityPicture, Entity).join(Entity, Entity.id == EntityPicture.entity_id)
                            .where(Entity.world_id == world.id).order_by(func.lower(Entity.name))).all():
        uses[str(ep.picture_id)]["entities"].append({"id": str(e.id), "name": e.name, "kind": e.kind})
    projects = {p.id: p.slug for p in world.projects}

    def scan(text: str, ref: dict) -> None:
        if "picture:" not in text:
            return
        for pid in dict.fromkeys(m.group(2) for m in PICTURE_RE.finditer(text)):
            uses[pid]["texts"].append(ref)

    if projects:
        for c in db.scalars(select(Chapter).where(Chapter.project_id.in_(list(projects)))
                            .order_by(Chapter.project_id, Chapter.state, Chapter.position)):
            scan(c.body, {"table": "chapter", "id": str(c.id), "title": c.title, "state": c.state,
                          "project": projects.get(c.project_id)})
        for c in db.scalars(select(Cut).where(Cut.project_id.in_(list(projects))).order_by(Cut.cut_at)):
            scan(c.body, {"table": "cut", "id": str(c.id), "title": c.chapter_title, "project": projects.get(c.project_id)})
    for j in db.scalars(select(JournalEntry).where(JournalEntry.world_id == world.id).order_by(JournalEntry.entry_date)):
        scan(j.body, {"table": "journal", "id": str(j.id), "title": j.title or j.body.split("\n", 1)[0][:60],
                      "date": j.entry_date.isoformat()})
    for e in db.scalars(select(Entity).where(Entity.world_id == world.id).order_by(func.lower(Entity.name))):
        scan(e.body, {"table": "entity", "id": str(e.id), "title": e.name, "kind": e.kind})
    return uses


def picture_index(db: Session, world_id: uuid.UUID) -> list[dict]:
    """Every picture of a world, small: what a text needs to draw a picture line before its picture loads."""
    return [{"id": str(i), "name": n, "width": w, "height": h}
            for i, n, w, h in db.execute(select(Picture.id, Picture.name, Picture.width, Picture.height)
                                         .where(Picture.world_id == world_id).order_by(Picture.created_at))]


# a world's pictures ----------------------------------------------------------------------------------------------


@router.post("/worlds/{slug}/pictures", status_code=201)
def upload_picture(slug: str, file: UploadFile = File(...), user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> PictureOut:
    """One file, made into a picture of the world (docs/SPEC.md §17.4). Not async: making it takes a moment of CPU,
    which runs in the thread pool rather than holding up every other request."""
    world, _ = member_world(db, user, slug)
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, TOO_BIG)
    try:
        made = make(data)
    except PictureError as e:
        raise HTTPException(422, str(e)) from None
    del data
    p = store(db, world.id, user.id, made, name_from_file(file.filename))
    db.commit()
    return picture_out(p)


@router.get("/worlds/{slug}/pictures")
def list_pictures(slug: str, uses: bool = False, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> dict:
    """Every picture in the world, newest first; with `uses`, where each is used (the Pictures page)."""
    world, _ = member_world(db, user, slug)
    pictures = list(db.scalars(select(Picture).where(Picture.world_id == world.id)
                               .order_by(Picture.created_at.desc(), Picture.name)))
    where = uses_in_world(db, world) if uses else {}
    out = []
    for p in pictures:
        row = picture_out(p).model_dump(mode="json")
        if uses:
            row["uses"] = where.get(str(p.id), {"entities": [], "texts": []})
        out.append(row)
    return {"pictures": out, "count": len(pictures), "bytes": sum(p.size for p in pictures)}


@router.get("/worlds/{slug}/pictures/index")
def list_index(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    return picture_index(db, world.id)


@router.get("/worlds/{slug}/pictures/whereabouts")
def whereabouts(slug: str, ids: str = Query(default="", max_length=4000), user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> dict[str, str]:
    """Why each of these pictures can't be shown in this world: `deleted`, or `elsewhere` (a line copied from another
    world). A picture of this world is answered as `here`."""
    world, _ = member_world(db, user, slug)
    wanted = []
    for x in ids.split(","):
        try:
            wanted.append(uuid.UUID(x.strip()))
        except ValueError:
            continue
    found = dict(db.execute(select(Picture.id, Picture.world_id).where(Picture.id.in_(wanted[:100])))
                 .all()) if wanted else {}
    return {str(i): ("deleted" if i not in found else "here" if found[i] == world.id else "elsewhere")
            for i in wanted[:100]}


@router.patch("/pictures/{picture_id}")
def rename_picture(picture_id: uuid.UUID, body: PictureRename, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> PictureOut:
    p = _picture(db, user, picture_id)
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(422, "A picture needs a name.")
    p.name = name
    db.commit()
    return picture_out(p)


@router.delete("/pictures/{picture_id}", status_code=204, response_model=None)
def delete_picture(picture_id: uuid.UUID, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> Response:
    """Only a picture used nowhere; otherwise 409 with where it is used."""
    p = _picture(db, user, picture_id)
    world = db.get(World, p.world_id)
    assert world is not None
    used = uses_in_world(db, world).get(str(p.id))
    if used and (used["entities"] or used["texts"]):
        return JSONResponse(status_code=409, content={"detail": "This picture is used.", "uses": used})
    db.delete(p)
    db.commit()
    return Response(status_code=204)


@router.get("/pictures/{picture_id}/{kind}")
def picture_file(picture_id: uuid.UUID, kind: str, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> Response:
    """A picture's file: `full` (in its own format), `view` or `thumb` (WebP). Its files never change."""
    if kind not in ("full", "view", "thumb"):
        raise HTTPException(404, "No such file.")
    p = _picture(db, user, picture_id)
    data = db.scalar(select(PictureFile.data).where(PictureFile.picture_id == p.id, PictureFile.kind == kind))
    if data is None:
        raise HTTPException(404, "No such file.")
    fmt = p.format if kind == "full" else "webp"
    ext = {"jpeg": "jpg"}.get(fmt, fmt)
    filename = f"{p.name}.{ext}" if kind == "full" else f"{p.name}-{kind}.{ext}"
    return Response(bytes(data), media_type=MEDIA_TYPES[fmt], headers={
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, max-age=31536000, immutable",
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
    })


# an entry's gallery ------------------------------------------------------------------------------------------------


@router.put("/worlds/{slug}/entities/{entity_id}/pictures")
def set_gallery(slug: str, entity_id: uuid.UUID, body: list[GalleryPicture], user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> list[dict]:
    """The entry's gallery, in order (the first is its main picture). Not a revision: saved at once."""
    world, _ = member_world(db, user, slug)
    e = db.get(Entity, entity_id)
    if e is None or e.world_id != world.id:
        raise HTTPException(404, "No such entry.")
    ids = [g.picture for g in body]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "A picture is in a gallery once.")
    known = set(db.scalars(select(Picture.id).where(Picture.world_id == world.id, Picture.id.in_(ids)))) if ids else set()
    if known != set(ids):
        raise HTTPException(422, "That picture is not in this world.")
    db.execute(delete(EntityPicture).where(EntityPicture.entity_id == e.id))
    for i, g in enumerate(body):
        db.add(EntityPicture(entity_id=e.id, picture_id=g.picture, position=i, caption=" ".join(g.caption.split())))
    db.commit()
    return gallery_of(db, e.id)

