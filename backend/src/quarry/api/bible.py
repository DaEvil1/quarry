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
from sqlalchemy import any_, delete, func, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import forget_source, matcher_for, refresh_names, refresh_source
from ..models import (
    Chapter,
    Decision,
    DecisionLink,
    Entity,
    Item,
    ItemLink,
    JournalEntry,
    Mention,
    NameIgnore,
    User,
    World,
)
from .history import chapter_in_world, event_when, notes_of, tellings_of
from .world import entity_world_detail
from .deps import current_user
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

Kind = Literal["character", "place", "faction", "culture", "species", "event", "object", "term", "other"]
Gender = Literal["female", "male", "nonbinary"]
SOURCES = {"item": Item, "decision": Decision, "journal": JournalEntry, "entity": Entity, "chapter": Chapter}


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
    if isinstance(row, Chapter):
        return row.title
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
    summary: str = Field(default="", max_length=300)
    match_case: bool = True
    first_name_alias: bool = True
    exclusions: list[str] = Field(default_factory=list, max_length=50)
    # the level: a project's slug (an entry made from one of its chapters), or none for the world
    project: str | None = None
    gender: Gender | None = None


class EntityUpdate(BaseModel):
    base_version: int
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Kind | None = None
    aliases: list[str] | None = Field(default=None, max_length=50)
    body: str | None = Field(default=None, max_length=200_000)
    summary: str | None = Field(default=None, max_length=300)
    match_case: bool | None = None
    first_name_alias: bool | None = None
    exclusions: list[str] | None = Field(default=None, max_length=50)
    # a rename keeps the old name as another name, so the texts that still say it stay linked
    keep_old_name: bool = True
    # the level (a project's slug, or null for the world) and a character's gender (null is not set); only when sent
    project: str | None = None
    gender: Gender | None = None
    # an event's "when" (docs/SPEC.md §13.2.1): a chapter it happens in, a time, or outside time; only when sent
    time_chapter_id: uuid.UUID | None = None
    time_at: float | None = None
    time_end: float | None = None
    time_label: str | None = Field(default=None, max_length=200)
    time_approx: bool | None = None
    outside_time: bool | None = None
    # an era's colour: one of the palette's eight names
    era_colour: Literal["amber", "moss", "teal", "sky", "indigo", "plum", "rose", "rust"] | None = None
    # the kinds it is as well, in order (docs/SPEC.md §14.8); never the main kind
    also_kinds: list[Kind] | None = Field(default=None, max_length=10)


class EntityOut(BaseModel):
    id: uuid.UUID
    kind: str
    name: str
    aliases: list[str]
    body: str
    summary: str
    match_case: bool
    first_name_alias: bool
    exclusions: list[str]
    version: int
    updated_at: datetime
    mention_count: int = 0
    # after a rename: the old name, if it was kept as another name
    kept_alias: str | None = None
    # the project whose part of the bible it is in (its slug), or None for the world
    project: str | None = None
    gender: str | None = None
    # in the bible's list: the projects whose current chapters name it
    named_in: list[str] = Field(default_factory=list)
    # an event's "when" (a chapter, a time or outside time; null for not placed yet), and an era's colour
    when: dict | None = None
    era_colour: str | None = None
    # the kinds it is as well, in the order added (docs/SPEC.md §14.8)
    also_kinds: list[str] = Field(default_factory=list)


def clean_kinds(main: str, kinds: list[str]) -> list[str]:
    """Added kinds in order, each once, never the main kind."""
    out: list[str] = []
    for k in kinds:
        if k != main and k not in out:
            out.append(k)
    return out


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


def _out(e: Entity, count: int = 0, projects: dict[uuid.UUID, str] | None = None,
         named_in: list[str] | None = None) -> EntityOut:
    return EntityOut(id=e.id, kind=e.kind, name=e.name, aliases=list(e.aliases), body=e.body, summary=e.summary,
                     match_case=e.match_case, first_name_alias=e.first_name_alias, exclusions=list(e.exclusions),
                     version=e.version, updated_at=e.updated_at, mention_count=count,
                     project=(projects or {}).get(e.project_id) if e.project_id else None, gender=e.gender,
                     named_in=named_in or [], when=event_when(e), era_colour=e.era_colour,
                     also_kinds=list(e.also_kinds or []))


def _slugs(world: World) -> dict[uuid.UUID, str]:
    return {p.id: p.slug for p in world.projects}


def _level(world: World, slug: str | None) -> uuid.UUID | None:
    """The project an entry lives in, by its slug; None for the world. A world with one project keeps everything in
    the world (docs/SPEC.md §12.4)."""
    if not slug:
        return None
    for p in world.projects:
        if p.slug == slug:
            return p.id if len(world.projects) > 1 else None
    raise HTTPException(422, "No such project in this world.")


def named_in_projects(db: Session, world: World) -> dict[uuid.UUID, list[str]]:
    """For each entry, the projects whose current chapters name it (from the stored mentions), in project order."""
    order = {p.id: (p.position, p.created_at) for p in world.projects}
    slugs = _slugs(world)
    rows = db.execute(
        select(Mention.entity_id, Chapter.project_id).join(Chapter, Chapter.id == Mention.source_id)
        .where(Mention.world_id == world.id, Mention.source_table == "chapter", Mention.kind != "near_miss",
               Chapter.state == "current").distinct()).all()
    out: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for eid, pid in rows:
        out[eid].append(pid)
    return {eid: [slugs[p] for p in sorted(ps, key=lambda p: order[p])] for eid, ps in out.items()}


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
        # an entry of more than one kind is listed under each (docs/SPEC.md §14.8)
        q = q.where((Entity.kind == kind) | (literal(kind) == any_(Entity.also_kinds)))
    counts = dict(db.execute(
        select(Mention.entity_id, func.count()).where(Mention.world_id == world.id, Mention.kind != "near_miss")
        .group_by(Mention.entity_id)).all())
    slugs = _slugs(world)
    named = named_in_projects(db, world)
    return [_out(e, counts.get(e.id, 0), slugs, named.get(e.id)) for e in db.scalars(q.order_by(func.lower(Entity.name)))]


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
               body=body.body, summary=" ".join(body.summary.split()), match_case=body.match_case,
               first_name_alias=body.first_name_alias, exclusions=_clean_aliases("", body.exclusions),
               project_id=_level(world, body.project), gender=body.gender, created_by=user.id, updated_by=user.id)
    before = matcher_for(db, world.id)
    db.add(e)
    db.flush()
    refresh_names(db, world.id, before, also=[("entity", e.id)])
    db.commit()
    return _out(e, 0, _slugs(world))


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
    order = {"chapter": 0, "item": 1, "journal": 2, "decision": 3, "entity": 4}
    positions = {}
    for (table, sid) in by_source:
        if table == "chapter":
            c = db.get(Chapter, sid)
            if c is not None:
                positions[str(sid)] = (c.state != "current", c.position)
    mentions.sort(key=lambda m: (m["project"] or "", order[m["source_table"]],
                                 positions.get(m["source_id"], (False, 0)), m["title"]))
    # first appearance in each project: the earliest current chapter that names it
    first = {}
    for m in mentions:
        if m["source_table"] == "chapter" and m["project"] and positions.get(m["source_id"], (True, 0))[0] is False:
            pos = positions[m["source_id"]][1]
            if m["project"] not in first or pos < first[m["project"]]["position"]:
                first[m["project"]] = {"project": m["project"], "chapter_id": m["source_id"], "title": m["title"],
                                       "position": pos}
    # decisions tagged with it, then those that name it
    tagged = set(db.scalars(select(DecisionLink.decision_id).where(DecisionLink.entity_id == e.id)))
    named = {uuid.UUID(m["source_id"]) for m in mentions if m["source_table"] == "decision"}
    decisions = [{"id": str(d.id), "decided_on": d.decided_on.isoformat(), "text": d.text,
                  "project": projects.get(d.project_id), "tagged": d.id in tagged}
                 for d in db.scalars(select(Decision).where(Decision.id.in_(tagged | named))
                                     .order_by(Decision.decided_on.desc()))] if tagged | named else []
    return {"entity": _out(e, sum(m["count"] for m in mentions), projects), "mentions": mentions, "unlinked": unlinked,
            "linked_items": linked_items, "near_misses": near, "first_appearance": list(first.values()),
            "decisions": decisions, **entity_world_detail(db, world, e),
            # an event's tellings (Told in, docs/SPEC.md §13.2.3)
            "tellings": tellings_of(db, world, e.id) if e.kind == "event" else [],
            # and its notes in the Journal (Noted in, docs/SPEC.md §14.1.2)
            "notes": notes_of(db, world, e.id) if e.kind == "event" else []}


@router.patch("/entities/{entity_id}")
def update_entity(slug: str, entity_id: uuid.UUID, body: EntityUpdate, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    world, _ = member_world(db, user, slug)
    e = _entity(db, world, entity_id)
    if e.version != body.base_version:
        return JSONResponse(status_code=409, content={
            "detail": "This entry changed on another device. Here is the newer version.",
            "entity": _out(e, 0, _slugs(world)).model_dump(mode="json")})
    before = matcher_for(db, world.id)
    names_changed = False
    old_name = e.name
    aliases = _clean_aliases(old_name, body.aliases) if body.aliases is not None else list(e.aliases)
    kept = None
    if body.name is not None:
        name = " ".join(body.name.split())
        if not name:
            raise HTTPException(422, "Give it a name.")
        if _name_taken(db, world, name, other_than=e.id):
            raise HTTPException(409, "The bible already has an entry with that name.")
        names_changed |= name != e.name
        e.name = name
        if name != old_name:
            # promoting another name ("Varren Hale" over "Varren"): it is the name now, and the old one takes its place
            at = aliases.index(name) if name in aliases else len(aliases)
            aliases = [a for a in aliases if a != name]
            if body.keep_old_name and _keeps(db, world, e, old_name, name, aliases):
                aliases.insert(at, old_name)
                kept = old_name
    if body.aliases is not None or kept is not None or aliases != list(e.aliases):
        aliases = _clean_aliases(e.name, aliases)
        names_changed |= aliases != list(e.aliases)
        e.aliases = aliases
    before_kinds = [e.kind, *(e.also_kinds or [])]
    if body.kind is not None:
        e.kind = body.kind
    if body.also_kinds is not None or body.kind is not None:
        e.also_kinds = clean_kinds(e.kind, body.also_kinds if body.also_kinds is not None else list(e.also_kinds or []))
    # first names belong to characters only (whichever of its kinds)
    names_changed |= ("character" in before_kinds) != ("character" in [e.kind, *e.also_kinds])
    if body.body is not None:
        e.body = body.body
    if "project" in body.model_fields_set:
        e.project_id = _level(world, body.project)
    if "gender" in body.model_fields_set:
        e.gender = body.gender
    sent = body.model_fields_set
    if sent & {"time_chapter_id", "time_at", "time_end", "time_label", "time_approx", "outside_time"}:
        # one of them: in a chapter, a time, or outside time (or none: not placed yet)
        if "time_chapter_id" in sent:
            e.time_chapter_id = chapter_in_world(db, world, body.time_chapter_id)
        for field in ("time_at", "time_end"):
            if field in sent:
                setattr(e, field, getattr(body, field))
        if "time_label" in sent:
            e.time_label = " ".join((body.time_label or "").split()) or None
        for flag in ("time_approx", "outside_time"):
            if flag in sent and getattr(body, flag) is not None:
                setattr(e, flag, getattr(body, flag))
        if e.outside_time:
            e.time_chapter_id = e.time_at = e.time_end = e.time_label = None
            e.time_approx = False
        elif e.time_chapter_id is not None or e.time_at is None:
            e.time_at = e.time_end = e.time_label = None
            e.time_approx = False
        if e.time_at is not None and e.time_end is not None and e.time_end < e.time_at:
            raise HTTPException(422, "A span ends after it starts.")
    if "era_colour" in sent:
        e.era_colour = body.era_colour
    if body.summary is not None:
        e.summary = " ".join(body.summary.split())
    for flag in ("match_case", "first_name_alias"):
        value = getattr(body, flag)
        if value is not None and value != getattr(e, flag):
            setattr(e, flag, value)
            names_changed = True
    if body.exclusions is not None:
        exclusions = _clean_aliases("", body.exclusions)
        names_changed |= exclusions != list(e.exclusions)
        e.exclusions = exclusions
    e.version += 1
    e.updated_by = user.id
    db.flush()
    if names_changed:
        refresh_names(db, world.id, before, also=[("entity", e.id)])
    else:
        refresh_source(db, world.id, "entity", e.id, e.body, before)
    db.commit()
    out = _out(e, 0, _slugs(world))
    out.kept_alias = kept
    return out


def _squash(name: str) -> str:
    return "".join(name.split()).lower()


def _keeps(db: Session, world: World, e: Entity, old: str, new: str, aliases: list[str]) -> bool:
    """Whether a rename keeps the old name as another name: not for a change of capitals or spacing, not when it is
    one of its other names already, and not when another entry is called that (it would match two entries)."""
    if _squash(old) == _squash(new) or old.lower() in {a.lower() for a in aliases}:
        return False
    for other in db.scalars(select(Entity).where(Entity.world_id == world.id, Entity.id != e.id)):
        if old.lower() in {f.lower() for f in [other.name, *other.aliases]}:
            return False
    return True


@router.delete("/entities/{entity_id}", status_code=204)
def delete_entity(slug: str, entity_id: uuid.UUID, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    e = _entity(db, world, entity_id)
    before = matcher_for(db, world.id)
    db.execute(delete(ItemLink).where(ItemLink.target_table == "entity", ItemLink.target_id == e.id))
    db.delete(e)
    # what its own page named goes with it
    forget_source(db, "entity", e.id)
    db.flush()
    refresh_names(db, world.id, before)
    db.commit()


# the name check ------------------------------------------------------------------------------------------------


class IgnoreIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class ReplaceIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    entity_id: uuid.UUID
    # only in this text; without it, everywhere the near miss appears
    source_table: Literal["item", "decision", "journal", "entity", "chapter"] | None = None
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
    # the texts they are in, a query per kind of text rather than one each
    texts: dict[tuple[str, uuid.UUID], object] = {}
    for table in {m.source_table for m, _ in rows}:
        model = SOURCES[table]
        ids = list({m.source_id for m, _ in rows if m.source_table == table})
        texts.update(((table, r.id), r) for r in db.scalars(select(model).where(model.id.in_(ids))))
    groups: dict[tuple[str, uuid.UUID], dict] = {}
    for m, name in rows:
        g = groups.setdefault((m.matched_text, m.entity_id), {
            "token": m.matched_text, "entity": {"id": str(m.entity_id), "name": name}, "count": 0, "sources": []})
        g["count"] += 1
        row = texts.get((m.source_table, m.source_id))
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
    before = matcher_for(db, world.id)
    try:
        db.add(NameIgnore(world_id=world.id, token=token))
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"token": token}
    refresh_names(db, world.id, before)
    db.commit()
    return {"token": token}


@router.delete("/name-ignores/{token}", status_code=204)
def remove_ignore(slug: str, token: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    before = matcher_for(db, world.id)
    db.execute(delete(NameIgnore).where(NameIgnore.world_id == world.id, NameIgnore.token == token))
    refresh_names(db, world.id, before)
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
    rewritten = []
    for table, sid in db.execute(q).all():
        row = db.get(SOURCES[table], sid)
        if row is None:
            continue
        new, n = pattern.subn(e.name, text_of(row))
        if n:
            if isinstance(row, Chapter):
                from .manuscript import snapshot

                snapshot(db, row, "autosnap", user)
            set_text(row, new)
            if hasattr(row, "version"):
                row.version += 1
            row.updated_by = user.id
            changed += n
            rewritten.append((table, row))
    db.flush()
    matcher = matcher_for(db, world.id)
    for table, row in rewritten:
        refresh_source(db, world.id, table, row.id, text_of(row), matcher)
    db.commit()
    return {"replaced": changed}
