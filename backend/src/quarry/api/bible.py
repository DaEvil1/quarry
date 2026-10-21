"""The bible (a world's entities), where each is mentioned, and the name check (near misses and their fixes)."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import refresh_source, refresh_world
from ..models import Decision, Entity, Item, ItemLink, JournalEntry, Mention, NameIgnore, User, World
from .deps import current_user
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

Kind = Literal["character", "place", "term", "faction", "object", "other"]
SOURCES = {"item": Item, "decision": Decision, "journal": JournalEntry, "entity": Entity}


def text_of(row) -> str:  # type: ignore[no-untyped-def]
    return row.text if isinstance(row, Decision) else row.body


def set_text(row, value: str) -> None:  # type: ignore[no-untyped-def]
    if isinstance(row, Decision):
        row.text = value
    else:
        row.body = value


def title_of(row) -> str:  # type: ignore[no-untyped-def]
    if isinstance(row, Entity):
        return row.name
    if getattr(row, "title", None):
        return row.title
    return text_of(row).split("\n", 1)[0][:120]


def snippet(text: str, start: int, end: int, room: int = 60) -> dict:
    a, b = max(0, start - room), min(len(text), end + room)
    return {"before": ("…" if a else "") + text[a:start], "match": text[start:end],
            "after": text[end:b] + ("…" if b < len(text) else "")}


# shapes --------------------------------------------------------------------------------------------------------


class EntityIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Kind = "character"
    aliases: list[str] = Field(default_factory=list, max_length=50)
    body: str = Field(default="", max_length=200_000)


class EntityUpdate(BaseModel):
    base_version: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Kind | None = None
    aliases: list[str] | None = Field(default=None, max_length=50)
    body: str | None = Field(default=None, max_length=200_000)


class EntityOut(BaseModel):
    id: uuid.UUID
    kind: str
    name: str
    aliases: list[str]
    body: str
    version: int
    updated_at: datetime
    mention_count: int = 0


def _clean_aliases(name: str, aliases: list[str]) -> list[str]:
    out: list[str] = []
    for a in aliases:
        a = " ".join(a.split())[:200]
        if a and a != name and a not in out:
            out.append(a)
    return out


def _entity(db: Session, world: World, entity_id: uuid.UUID) -> Entity:
    e = db.get(Entity, entity_id)
    if e is None or e.world_id != world.id:
        raise HTTPException(404, "No such entry in the bible.")
    return e


def _out(e: Entity, count: int = 0) -> EntityOut:
    return EntityOut(id=e.id, kind=e.kind, name=e.name, aliases=list(e.aliases), body=e.body, version=e.version,
                     updated_at=e.updated_at, mention_count=count)


def _name_taken(db: Session, world: World, name: str, other_than: uuid.UUID | None = None) -> bool:
    q = select(Entity.id).where(Entity.world_id == world.id, func.lower(Entity.name) == name.lower())
    if other_than:
        q = q.where(Entity.id != other_than)
    return db.scalar(q) is not None


# entities ------------------------------------------------------------------------------------------------------


@router.get("/entities")
def list_entities(slug: str, kind: Kind | None = None, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> list[EntityOut]:
    world, _ = member_world(db, user, slug)
    q = select(Entity).where(Entity.world_id == world.id)
    if kind:
        q = q.where(Entity.kind == kind)
    counts = dict(db.execute(
        select(Mention.entity_id, func.count()).where(Mention.world_id == world.id, Mention.kind != "near_miss")
        .group_by(Mention.entity_id)).all())
    return [_out(e, counts.get(e.id, 0)) for e in db.scalars(q.order_by(func.lower(Entity.name)))]


@router.post("/entities", status_code=201)
def create_entity(slug: str, body: EntityIn, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> EntityOut:
    world, _ = member_world(db, user, slug)
    name = " ".join(body.name.split())
    if not name:
        raise HTTPException(422, "Give it a name.")
    if _name_taken(db, world, name):
        raise HTTPException(409, "The bible already has an entry with that name.")
    e = Entity(world_id=world.id, kind=body.kind, name=name, aliases=_clean_aliases(name, body.aliases),
               body=body.body, created_by=user.id, updated_by=user.id)
    db.add(e)
    db.flush()
    refresh_world(db, world.id)
    db.commit()
    return _out(e)


@router.get("/entities/{entity_id}")
def get_entity(slug: str, entity_id: uuid.UUID, user: User = Depends(current_user),
               db: Session = Depends(get_db)) -> dict:
    """The entry, every place it is mentioned (grouped by project), items that mention it without being tagged
    with it, and near misses that probably mean it."""
    world, _ = member_world(db, user, slug)
    e = _entity(db, world, entity_id)
    projects = {p.id: p.slug for p in world.projects}
    rows = db.scalars(select(Mention).where(Mention.entity_id == e.id).order_by(Mention.source_table, Mention.start))
    by_source: dict[tuple[str, uuid.UUID], list[Mention]] = defaultdict(list)
    for m in rows:
        by_source[(m.source_table, m.source_id)].append(m)
    linked = set(db.scalars(select(ItemLink.item_id).where(ItemLink.target_table == "entity",
                                                           ItemLink.target_id == e.id)))
    mentions, near = [], []
    unlinked = []
    for (table, sid), ms in by_source.items():
        row = db.get(SOURCES[table], sid)
        if row is None:
            continue
        text = text_of(row)
        hits = [m for m in ms if m.kind != "near_miss"]
        misses = [m for m in ms if m.kind == "near_miss"]
        base = {"source_table": table, "source_id": str(sid), "title": title_of(row),
                "project": projects.get(getattr(row, "project_id", None)), "version": row.version
                if hasattr(row, "version") else None}
        if hits:
            entry = {**base, "count": len(hits), "snippet": snippet(text, hits[0].start, hits[0].end)}
            mentions.append(entry)
            if table == "item" and sid not in linked:
                unlinked.append(entry)
        for m in misses:
            near.append({**base, "token": m.matched_text, "snippet": snippet(text, m.start, m.end)})
    linked_items = [
        {"id": str(i.id), "title": title_of(i), "status": i.status, "project": projects.get(i.project_id)}
        for i in db.scalars(select(Item).where(Item.id.in_(linked)).order_by(Item.created_at.desc()))
    ] if linked else []
    order = {"item": 0, "journal": 1, "decision": 2, "entity": 3}
    mentions.sort(key=lambda m: (m["project"] or "", order[m["source_table"]], m["title"]))
    return {"entity": _out(e, sum(m["count"] for m in mentions)), "mentions": mentions, "unlinked": unlinked,
            "linked_items": linked_items, "near_misses": near}


@router.patch("/entities/{entity_id}")
def update_entity(slug: str, entity_id: uuid.UUID, body: EntityUpdate, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    world, _ = member_world(db, user, slug)
    e = _entity(db, world, entity_id)
    if e.version != body.base_version:
        return JSONResponse(status_code=409, content={
            "detail": "This entry changed on another device. Here is the newer version.",
            "entity": _out(e).model_dump(mode="json")})
    names_changed = False
    if body.name is not None:
        name = " ".join(body.name.split())
        if not name:
            raise HTTPException(422, "Give it a name.")
        if _name_taken(db, world, name, other_than=e.id):
            raise HTTPException(409, "The bible already has an entry with that name.")
        names_changed |= name != e.name
        e.name = name
    if body.aliases is not None:
        aliases = _clean_aliases(e.name, body.aliases)
        names_changed |= aliases != list(e.aliases)
        e.aliases = aliases
    if body.kind is not None:
        e.kind = body.kind
    if body.body is not None:
        e.body = body.body
    e.version += 1
    e.updated_by = user.id
    db.flush()
    if names_changed:
        refresh_world(db, world.id)
    else:
        refresh_source(db, world.id, "entity", e.id, e.body)
    db.commit()
    return _out(e)


@router.delete("/entities/{entity_id}", status_code=204)
def delete_entity(slug: str, entity_id: uuid.UUID, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    e = _entity(db, world, entity_id)
    db.execute(delete(ItemLink).where(ItemLink.target_table == "entity", ItemLink.target_id == e.id))
    db.delete(e)
    db.flush()
    refresh_world(db, world.id)
    db.commit()


# the name check ------------------------------------------------------------------------------------------------


class IgnoreIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class ReplaceIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    entity_id: uuid.UUID
    # only in this text; without it, everywhere the near miss appears
    source_table: Literal["item", "decision", "journal", "entity"] | None = None
    source_id: uuid.UUID | None = None


@router.get("/near-misses")
def near_misses(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Every word that looks like a misspelled name, grouped by the word, with where it appears."""
    world, _ = member_world(db, user, slug)
    rows = db.execute(
        select(Mention, Entity.name).join(Entity, Entity.id == Mention.entity_id)
        .where(Mention.world_id == world.id, Mention.kind == "near_miss")
        .order_by(Mention.matched_text, Mention.source_table)
    ).all()
    projects = {p.id: p.slug for p in world.projects}
    groups: dict[tuple[str, uuid.UUID], dict] = {}
    for m, name in rows:
        g = groups.setdefault((m.matched_text, m.entity_id), {
            "token": m.matched_text, "entity": {"id": str(m.entity_id), "name": name}, "count": 0, "sources": []})
        g["count"] += 1
        row = db.get(SOURCES[m.source_table], m.source_id)
        if row is not None:
            g["sources"].append({"source_table": m.source_table, "source_id": str(m.source_id),
                                 "title": title_of(row), "project": projects.get(getattr(row, "project_id", None)),
                                 "snippet": snippet(text_of(row), m.start, m.end)})
    return sorted(groups.values(), key=lambda g: (-g["count"], g["token"]))


@router.get("/near-misses/count")
def near_miss_count(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    n = db.scalar(select(func.count(func.distinct(Mention.matched_text)))
                  .where(Mention.world_id == world.id, Mention.kind == "near_miss"))
    return {"words": n or 0}


@router.get("/name-ignores")
def list_ignores(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[str]:
    world, _ = member_world(db, user, slug)
    return list(db.scalars(select(NameIgnore.token).where(NameIgnore.world_id == world.id).order_by(NameIgnore.token)))


@router.post("/name-ignores", status_code=201)
def add_ignore(slug: str, body: IgnoreIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    token = body.token.strip()
    try:
        db.add(NameIgnore(world_id=world.id, token=token))
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"token": token}
    refresh_world(db, world.id)
    db.commit()
    return {"token": token}


@router.delete("/name-ignores/{token}", status_code=204)
def remove_ignore(slug: str, token: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    db.execute(delete(NameIgnore).where(NameIgnore.world_id == world.id, NameIgnore.token == token))
    refresh_world(db, world.id)
    db.commit()


@router.post("/near-misses/replace")
def replace_near_miss(slug: str, body: ReplaceIn, user: User = Depends(current_user),
                      db: Session = Depends(get_db)) -> dict:
    """Replace a misspelled word with the entity's name, in one text or everywhere it was flagged."""
    world, _ = member_world(db, user, slug)
    e = _entity(db, world, body.entity_id)
    q = select(Mention.source_table, Mention.source_id).where(
        Mention.world_id == world.id, Mention.kind == "near_miss", Mention.matched_text == body.token,
        Mention.entity_id == e.id).distinct()
    if body.source_table and body.source_id:
        q = q.where(Mention.source_table == body.source_table, Mention.source_id == body.source_id)
    pattern = re.compile(r"(?<![\w'’-])" + re.escape(body.token) + r"(?![\w])")
    changed = 0
    for table, sid in db.execute(q).all():
        row = db.get(SOURCES[table], sid)
        if row is None:
            continue
        new, n = pattern.subn(e.name, text_of(row))
        if n:
            set_text(row, new)
            if hasattr(row, "version"):
                row.version += 1
            row.updated_by = user.id
            changed += n
    db.flush()
    refresh_world(db, world.id)
    db.commit()
    return {"replaced": changed}
