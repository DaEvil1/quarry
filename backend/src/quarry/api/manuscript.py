"""The manuscript: chapters, their order and history, experiments (alternate drafts) and salvage.

Typing autosaves the working copy (PATCH with the version it started from). Snapshots (revisions) are taken by the
client at the moments the spec names (leaving, idle, long sessions, Ctrl+S) and by the server on every change of
state, so nothing that was ever in the book is lost.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import refresh_source
from ..models import Chapter, Decision, Entity, HarvestNote, Item, Mention, Project, Revision, User, World
from .deps import current_user
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")
BODY_MAX = 2_000_000


def words(text: str) -> int:
    return len(WORD_RE.findall(text))


# shapes --------------------------------------------------------------------------------------------------------


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class ChapterOut(BaseModel):
    id: uuid.UUID
    project: str
    title: str
    state: str
    position: int
    pov: Ref | None
    experiment_item_id: uuid.UUID | None
    replaces_id: uuid.UUID | None
    words: int
    version: int
    updated_at: datetime
    retired_at: datetime | None


class NoteOut(BaseModel):
    id: uuid.UUID
    body: str
    created_at: datetime


class ChapterDetail(ChapterOut):
    body: str
    mentions: list[dict]
    harvest_notes: list[NoteOut]
    # for an experiment: the chapter it would replace, and the item that tracks it
    replaces_title: str | None = None
    experiment_status: str | None = None


class ChapterIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=BODY_MAX)
    pov_entity_id: uuid.UUID | None = None


class ChapterUpdate(BaseModel):
    base_version: int
    title: str | None = Field(default=None, min_length=1, max_length=300)
    body: str | None = Field(default=None, max_length=BODY_MAX)
    pov_entity_id: uuid.UUID | None = None


class OrderIn(BaseModel):
    ids: list[uuid.UUID]


class SnapshotIn(BaseModel):
    reason: Literal["autosnap", "checkpoint", "conflict", "restore"] = "autosnap"
    label: str | None = Field(default=None, max_length=200)
    # only for a conflict copy (the text that lost to a newer save elsewhere) or a restore made offline (the text it
    # replaced, kept on the device until it could be sent)
    body: str | None = Field(default=None, max_length=BODY_MAX)


class RestoreIn(BaseModel):
    revision_id: uuid.UUID


class RetireIn(BaseModel):
    note: str | None = Field(default=None, max_length=5000)


class ExperimentIn(BaseModel):
    start: Literal["scratch", "copy"] = "copy"
    title: str | None = Field(default=None, max_length=300)


class CloseExperimentIn(BaseModel):
    outcome: Literal["accepted", "rejected", "harvested"]
    # a harvest note: what was alive in the draft that loses
    note: str | None = Field(default=None, max_length=5000)
    decision: str | None = Field(default=None, max_length=1000)
    decided_on: date | None = None


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


# helpers -------------------------------------------------------------------------------------------------------


def _project(world: World, slug: str) -> Project:
    for p in world.projects:
        if p.slug == slug:
            return p
    raise HTTPException(404, "No such project.")


def _chapter(db: Session, world: World, chapter_id: uuid.UUID) -> Chapter:
    ch = db.get(Chapter, chapter_id)
    if ch is None or ch.project_id not in {p.id for p in world.projects}:
        raise HTTPException(404, "No such chapter.")
    return ch


def _pov(db: Session, world: World, entity_id: uuid.UUID | None) -> uuid.UUID | None:
    if entity_id is None:
        return None
    e = db.get(Entity, entity_id)
    if e is None or e.world_id != world.id:
        raise HTTPException(422, "No such entry in this world's bible.")
    return e.id


def chapter_out(db: Session, world: World, ch: Chapter, names: dict[uuid.UUID, str] | None = None) -> ChapterOut:
    slugs = {p.id: p.slug for p in world.projects}
    pov = None
    if ch.pov_entity_id:
        name = names.get(ch.pov_entity_id) if names is not None else None
        if name is None:
            e = db.get(Entity, ch.pov_entity_id)
            name = e.name if e else None
        pov = Ref(id=ch.pov_entity_id, name=name) if name else None
    return ChapterOut(id=ch.id, project=slugs[ch.project_id], title=ch.title, state=ch.state, position=ch.position,
                      pov=pov, experiment_item_id=ch.experiment_item_id, replaces_id=ch.replaces_id,
                      words=words(ch.body), version=ch.version, updated_at=ch.updated_at, retired_at=ch.retired_at)


def chapter_detail(db: Session, world: World, ch: Chapter) -> ChapterDetail:
    base = chapter_out(db, world, ch)
    found = db.execute(
        select(Mention, Entity.name).join(Entity, Entity.id == Mention.entity_id)
        .where(Mention.source_table == "chapter", Mention.source_id == ch.id).order_by(Mention.start)
    ).all()
    mentions = [{"entity_id": str(m.entity_id), "entity_name": name, "start": m.start, "end": m.end,
                 "matched_text": m.matched_text, "kind": m.kind} for m, name in found]
    notes = [NoteOut(id=n.id, body=n.body, created_at=n.created_at) for n in
             db.scalars(select(HarvestNote).where(HarvestNote.chapter_id == ch.id).order_by(HarvestNote.created_at))]
    replaced = db.get(Chapter, ch.replaces_id) if ch.replaces_id else None
    item = db.get(Item, ch.experiment_item_id) if ch.experiment_item_id else None
    return ChapterDetail(**base.model_dump(), body=ch.body, mentions=mentions, harvest_notes=notes,
                         replaces_title=replaced.title if replaced else None,
                         experiment_status=item.status if item else None)


def snapshot(db: Session, ch: Chapter, reason: str, user: User, label: str | None = None,
             body: str | None = None) -> Revision | None:
    """Keep the chapter's text (or the given text) as a revision; an automatic one is skipped when nothing changed."""
    text = ch.body if body is None else body
    if reason == "autosnap":
        last = db.scalars(select(Revision).where(Revision.doc_table == "chapter", Revision.doc_id == ch.id)
                          .order_by(Revision.created_at.desc()).limit(1)).first()
        if last is not None and last.body == text and last.title == ch.title:
            return None
    rev = Revision(doc_table="chapter", doc_id=ch.id, version=ch.version, title=ch.title, body=text,
                   meta={"state": ch.state, "words": words(text)}, reason=reason, label=label, created_by=user.id)
    db.add(rev)
    db.flush()
    return rev


def _renumber(db: Session, project_id: uuid.UUID) -> None:
    current = db.scalars(select(Chapter).where(Chapter.project_id == project_id, Chapter.state == "current")
                         .order_by(Chapter.position, Chapter.created_at)).all()
    for i, ch in enumerate(current):
        ch.position = i


def _next_position(db: Session, project_id: uuid.UUID) -> int:
    top = db.scalar(select(func.max(Chapter.position)).where(Chapter.project_id == project_id,
                                                            Chapter.state == "current"))
    return 0 if top is None else top + 1


def _conflict(db: Session, world: World, ch: Chapter) -> JSONResponse:
    return JSONResponse(status_code=409, content={
        "detail": "This chapter changed on another device. Here is the newer version.",
        "chapter": chapter_detail(db, world, ch).model_dump(mode="json")})


def _retire(db: Session, ch: Chapter, user: User, note: str | None) -> None:
    snapshot(db, ch, "state", user)
    ch.state = "retired"
    ch.retired_at = datetime.now(UTC)
    ch.version += 1
    ch.updated_by = user.id
    if note and note.strip():
        project = db.get(Project, ch.project_id)
        assert project is not None
        db.add(HarvestNote(world_id=project.world_id, chapter_id=ch.id, body=note.strip(), created_by=user.id))


# the manuscript ------------------------------------------------------------------------------------------------


@router.get("/projects/{project_slug}/chapters")
def manuscript(slug: str, project_slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """The current chapters in order, experiments (each under the chapter it would replace), the POV tally and the
    total word count."""
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    rows = db.scalars(select(Chapter).where(Chapter.project_id == project.id, Chapter.state != "retired")
                      .order_by(Chapter.position, Chapter.created_at)).all()
    names = dict(db.execute(select(Entity.id, Entity.name).where(Entity.world_id == world.id)).all())
    current = [chapter_out(db, world, c, names) for c in rows if c.state == "current"]
    experiments = [chapter_out(db, world, c, names) for c in rows if c.state == "experiment"]
    tally = Counter(c.pov.name for c in current if c.pov)
    retired = db.scalar(select(func.count()).select_from(Chapter).where(Chapter.project_id == project.id,
                                                                       Chapter.state == "retired"))
    return {"chapters": current, "experiments": experiments,
            "pov_tally": [{"name": n, "chapters": k} for n, k in tally.most_common()],
            "words": sum(c.words for c in current), "retired": retired or 0}


@router.post("/projects/{project_slug}/chapters", status_code=201)
def create_chapter(slug: str, project_slug: str, body: ChapterIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> ChapterDetail:
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    title = " ".join(body.title.split())
    if not title:
        raise HTTPException(422, "Give the chapter a title.")
    ch = Chapter(project_id=project.id, title=title, body=body.body, position=_next_position(db, project.id),
                 pov_entity_id=_pov(db, world, body.pov_entity_id), created_by=user.id, updated_by=user.id)
    db.add(ch)
    db.flush()
    refresh_source(db, world.id, "chapter", ch.id, ch.body)
    db.commit()
    return chapter_detail(db, world, ch)


@router.put("/projects/{project_slug}/chapter-order")
def reorder(slug: str, project_slug: str, body: OrderIn, user: User = Depends(current_user),
            db: Session = Depends(get_db)) -> list[ChapterOut]:
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    current = {c.id: c for c in db.scalars(select(Chapter).where(Chapter.project_id == project.id,
                                                                  Chapter.state == "current"))}
    if len(body.ids) != len(current) or set(body.ids) != set(current):
        raise HTTPException(422, "Send every current chapter exactly once.")
    for i, cid in enumerate(body.ids):
        current[cid].position = i
    db.commit()
    return [chapter_out(db, world, current[cid]) for cid in body.ids]


@router.get("/projects/{project_slug}/salvage")
def salvage(slug: str, project_slug: str, q: str | None = Query(None, max_length=200),
            user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Retired chapters with their harvest notes, newest first; `q` searches titles, text and notes."""
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    query = select(Chapter).where(Chapter.project_id == project.id, Chapter.state == "retired")
    if q and q.strip():
        like = f"%{q.strip()}%"
        noted = select(HarvestNote.chapter_id).where(HarvestNote.body.ilike(like))
        query = query.where(or_(Chapter.title.ilike(like), Chapter.body.ilike(like), Chapter.id.in_(noted)))
    out = []
    for ch in db.scalars(query.order_by(Chapter.retired_at.desc().nulls_last())):
        notes = db.scalars(select(HarvestNote).where(HarvestNote.chapter_id == ch.id)
                           .order_by(HarvestNote.created_at)).all()
        hit = None
        if q and q.strip():
            i = ch.body.lower().find(q.strip().lower())
            if i >= 0:
                hit = {"before": ("…" if i > 60 else "") + ch.body[max(0, i - 60):i],
                       "match": ch.body[i:i + len(q.strip())],
                       "after": ch.body[i + len(q.strip()):i + len(q.strip()) + 60]}
        out.append({**chapter_out(db, world, ch).model_dump(mode="json"),
                    "harvest_notes": [NoteOut(id=n.id, body=n.body, created_at=n.created_at).model_dump(mode="json")
                                      for n in notes],
                    "match": hit})
    return out


# one chapter ---------------------------------------------------------------------------------------------------


@router.get("/chapters/{chapter_id}")
def get_chapter(slug: str, chapter_id: uuid.UUID, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> ChapterDetail:
    world, _ = member_world(db, user, slug)
    return chapter_detail(db, world, _chapter(db, world, chapter_id))


@router.patch("/chapters/{chapter_id}")
def update_chapter(slug: str, chapter_id: uuid.UUID, body: ChapterUpdate, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    if ch.version != body.base_version:
        return _conflict(db, world, ch)
    if body.title is not None:
        title = " ".join(body.title.split())
        if not title:
            raise HTTPException(422, "Give the chapter a title.")
        ch.title = title
    if body.body is not None:
        ch.body = body.body
    if "pov_entity_id" in body.model_fields_set:
        ch.pov_entity_id = _pov(db, world, body.pov_entity_id)
    ch.version += 1
    ch.updated_by = user.id
    db.flush()
    if body.body is not None:
        refresh_source(db, world.id, "chapter", ch.id, ch.body)
    db.commit()
    return chapter_detail(db, world, ch)


@router.delete("/chapters/{chapter_id}", status_code=204)
def delete_chapter(slug: str, chapter_id: uuid.UUID, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> None:
    """Only an empty chapter with no history can be deleted (a mistake); anything else is retired instead."""
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    has_history = db.scalar(select(func.count()).select_from(Revision).where(Revision.doc_table == "chapter",
                                                                            Revision.doc_id == ch.id))
    if ch.body.strip() or has_history or ch.state == "experiment":
        raise HTTPException(409, "Only an empty chapter can be deleted. Retire it instead; it stays in Salvage.")
    project_id = ch.project_id
    db.delete(ch)
    db.flush()
    _renumber(db, project_id)
    db.commit()


@router.post("/chapters/{chapter_id}/revisions", status_code=201)
def take_snapshot(slug: str, chapter_id: uuid.UUID, body: SnapshotIn, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    if body.body is not None and body.reason not in ("conflict", "restore"):
        raise HTTPException(422, "Only a conflict copy or an offline restore brings its own text.")
    rev = snapshot(db, ch, body.reason, user, label=(body.label or "").strip() or None, body=body.body)
    db.commit()
    return {"id": str(rev.id) if rev else None, "skipped": rev is None}


@router.get("/chapters/{chapter_id}/revisions")
def revisions(slug: str, chapter_id: uuid.UUID, user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    rows = db.scalars(select(Revision).where(Revision.doc_table == "chapter", Revision.doc_id == ch.id)
                      .order_by(Revision.created_at.desc()))
    return [{"id": str(r.id), "version": r.version, "title": r.title, "reason": r.reason, "label": r.label,
             "words": r.meta.get("words", words(r.body)), "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/revisions/{revision_id}")
def revision(slug: str, revision_id: uuid.UUID, user: User = Depends(current_user),
             db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    r = db.get(Revision, revision_id)
    if r is None:
        raise HTTPException(404, "No such revision.")
    _chapter(db, world, r.doc_id)
    return {"id": str(r.id), "version": r.version, "title": r.title, "body": r.body, "reason": r.reason,
            "label": r.label, "created_at": r.created_at.isoformat()}


@router.post("/chapters/{chapter_id}/restore")
def restore(slug: str, chapter_id: uuid.UUID, body: RestoreIn, user: User = Depends(current_user),
            db: Session = Depends(get_db)) -> ChapterDetail:
    """Put a revision's text back. The text it replaces is kept as a revision first."""
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    r = db.get(Revision, body.revision_id)
    if r is None or r.doc_table != "chapter" or r.doc_id != ch.id:
        raise HTTPException(404, "No such revision of this chapter.")
    snapshot(db, ch, "restore", user, label=f"Before restoring {r.created_at:%Y-%m-%d %H:%M}")
    ch.body = r.body
    ch.title = r.title or ch.title
    ch.version += 1
    ch.updated_by = user.id
    db.flush()
    refresh_source(db, world.id, "chapter", ch.id, ch.body)
    db.commit()
    return chapter_detail(db, world, ch)


@router.post("/chapters/{chapter_id}/retire")
def retire(slug: str, chapter_id: uuid.UUID, body: RetireIn, user: User = Depends(current_user),
           db: Session = Depends(get_db)) -> ChapterDetail:
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    if ch.state != "current":
        raise HTTPException(409, "Only a chapter in the book can be retired. Close an experiment instead.")
    _retire(db, ch, user, body.note)
    db.flush()
    _renumber(db, ch.project_id)
    db.commit()
    return chapter_detail(db, world, ch)


@router.post("/chapters/{chapter_id}/reinstate")
def reinstate(slug: str, chapter_id: uuid.UUID, user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> ChapterDetail:
    """Bring a retired chapter back into the book, at the end."""
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    if ch.state != "retired":
        raise HTTPException(409, "This chapter is not retired.")
    snapshot(db, ch, "state", user)
    ch.state = "current"
    ch.retired_at = None
    ch.position = _next_position(db, ch.project_id)
    ch.version += 1
    ch.updated_by = user.id
    db.commit()
    return chapter_detail(db, world, ch)


@router.post("/chapters/{chapter_id}/harvest-notes", status_code=201)
def add_note(slug: str, chapter_id: uuid.UUID, body: NoteIn, user: User = Depends(current_user),
             db: Session = Depends(get_db)) -> NoteOut:
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    n = HarvestNote(world_id=world.id, chapter_id=ch.id, body=body.body.strip(), created_by=user.id)
    db.add(n)
    db.commit()
    return NoteOut(id=n.id, body=n.body, created_at=n.created_at)


@router.delete("/harvest-notes/{note_id}", status_code=204)
def delete_note(slug: str, note_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    world, _ = member_world(db, user, slug)
    n = db.get(HarvestNote, note_id)
    if n is None or n.world_id != world.id:
        raise HTTPException(404, "No such note.")
    db.delete(n)
    db.commit()


# experiments ---------------------------------------------------------------------------------------------------


@router.post("/chapters/{chapter_id}/experiments", status_code=201)
def start_experiment(slug: str, chapter_id: uuid.UUID, body: ExperimentIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> ChapterDetail:
    """An alternate draft of a chapter, tracked by an experiment item in the inbox. From scratch (the old text stays
    out of sight while writing) or from a copy."""
    world, _ = member_world(db, user, slug)
    original = _chapter(db, world, chapter_id)
    if original.state != "current":
        raise HTTPException(409, "Experiments start from a chapter in the book.")
    title = " ".join((body.title or original.title).split()) or original.title
    item = Item(world_id=world.id, project_id=original.project_id, kind="experiment",
                body=f"Rewrite of “{original.title}” ({'from scratch' if body.start == 'scratch' else 'from a copy'})",
                source="desk", created_by=user.id, updated_by=user.id)
    db.add(item)
    db.flush()
    ch = Chapter(project_id=original.project_id, title=title, body="" if body.start == "scratch" else original.body,
                 state="experiment", position=original.position, pov_entity_id=original.pov_entity_id,
                 experiment_item_id=item.id, replaces_id=original.id, created_by=user.id, updated_by=user.id)
    db.add(ch)
    db.flush()
    refresh_source(db, world.id, "chapter", ch.id, ch.body)
    refresh_source(db, world.id, "item", item.id, item.body)
    db.commit()
    return chapter_detail(db, world, ch)


@router.post("/chapters/{chapter_id}/close-experiment")
def close_experiment(slug: str, chapter_id: uuid.UUID, body: CloseExperimentIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> ChapterDetail:
    """accepted: the draft takes the old chapter's place and the old one is retired. harvested or rejected: the draft
    is retired. A note becomes a harvest note on whichever text leaves the book."""
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    if ch.state != "experiment":
        raise HTTPException(409, "This chapter is not an experiment.")
    snapshot(db, ch, "state", user)
    if body.outcome == "accepted":
        old = db.get(Chapter, ch.replaces_id) if ch.replaces_id else None
        if old is not None and old.state == "current":
            ch.position = old.position
            _retire(db, old, user, body.note)
        else:
            ch.position = _next_position(db, ch.project_id)
        ch.state = "current"
        ch.version += 1
        ch.updated_by = user.id
    else:
        _retire(db, ch, user, body.note)
    db.flush()
    _renumber(db, ch.project_id)
    item = db.get(Item, ch.experiment_item_id) if ch.experiment_item_id else None
    if item is not None and item.status == "open":
        item.status = body.outcome
        item.closed_at = datetime.now(UTC)
        item.closed_note = (body.note or "").strip() or None
        item.version += 1
        item.updated_by = user.id
    text = " ".join((body.decision or "").split())
    if text:
        d = Decision(world_id=world.id, project_id=ch.project_id, decided_on=body.decided_on or date.today(),
                     text=text, item_id=item.id if item else None, created_by=user.id, updated_by=user.id)
        db.add(d)
        db.flush()
        refresh_source(db, world.id, "decision", d.id, d.text)
    db.commit()
    return chapter_detail(db, world, ch)


# the offline copy ---------------------------------------------------------------------------------------------

LOCAL_REVISIONS = 30


@router.get("/offline")
def offline_pack(slug: str, since: datetime | None = None, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    """What a device needs to keep its offline copy of the world's chapters up to date: every chapter changed (or
    given a new revision) since `since`, with its last 30 revisions, and the ids of all chapters that still exist."""
    world, _ = member_world(db, user, slug)
    now = datetime.now(UTC)
    project_ids = [p.id for p in world.projects]
    all_ids = list(db.scalars(select(Chapter.id).where(Chapter.project_id.in_(project_ids)))) if project_ids else []
    q = select(Chapter).where(Chapter.project_id.in_(project_ids)) if project_ids else None
    changed: list[Chapter] = []
    if q is not None:
        if since is not None:
            if since.tzinfo is None:
                since = since.replace(tzinfo=UTC)
            fresh = select(Revision.doc_id).where(Revision.doc_table == "chapter", Revision.created_at > since)
            q = q.where(or_(Chapter.updated_at > since, Chapter.id.in_(fresh)))
        changed = list(db.scalars(q))
    chapters, revisions = [], []
    for ch in changed:
        chapters.append(chapter_detail(db, world, ch).model_dump(mode="json"))
        for r in db.scalars(select(Revision).where(Revision.doc_table == "chapter", Revision.doc_id == ch.id)
                            .order_by(Revision.created_at.desc()).limit(LOCAL_REVISIONS)):
            revisions.append({"id": str(r.id), "chapter_id": str(ch.id), "version": r.version, "title": r.title,
                              "body": r.body, "reason": r.reason, "label": r.label,
                              "words": r.meta.get("words", words(r.body)), "created_at": r.created_at.isoformat()})
    return {"now": now.isoformat(), "chapters": chapters, "revisions": revisions,
            "chapter_ids": [str(i) for i in all_ids]}
