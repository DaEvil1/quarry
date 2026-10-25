"""The manuscript: chapters, their order and history, experiments (alternate drafts) and salvage.

Typing autosaves the working copy (PATCH with the version it started from). Snapshots (revisions) are taken by the
client at the moments the spec names (leaving, idle, long sessions, Ctrl+S) and by the server on every change of
state, so nothing that was ever in the book is lost.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..margin import story_text
from ..mentions import COUNTED, refresh_source
from ..models import (
    Chapter,
    ChapterStatus,
    Decision,
    Entity,
    HarvestNote,
    Item,
    JournalEntry,
    Mention,
    Project,
    Revision,
    User,
    World,
)
from ..wordhistory import word_changes
from .deps import current_user
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")
BODY_MAX = 2_000_000


def words(text: str) -> int:
    """Words in the story: margin notes (%% lines) don't count."""
    return len(WORD_RE.findall(story_text(text)))


# shapes --------------------------------------------------------------------------------------------------------


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class StatusRef(BaseModel):
    id: uuid.UUID
    label: str
    position: int


class ChapterOut(BaseModel):
    id: uuid.UUID
    project: str
    title: str
    state: str
    position: int
    pov: Ref | None
    summary: str = ""
    status: StatusRef | None = None
    experiment_item_id: uuid.UUID | None
    words: int
    # when it is set and how it is told (docs/SPEC.md §13.1.2)
    time_at: float | None = None
    time_end: float | None = None
    time_label: str | None = None
    time_approx: bool = False
    outside_time: bool = False
    told_as: str | None = None
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
    # for a draft: its experiment (the range it would replace or where it adds, its drafts) and the item's status
    experiment: dict | None = None
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


class AboutIn(BaseModel):
    summary: str | None = Field(default=None, max_length=300)
    status_id: uuid.UUID | None = None
    # when it is set: a time (number, end, label, about) or outside time; and a mark, flashback or tale
    time_at: float | None = None
    time_end: float | None = None
    time_label: str | None = Field(default=None, max_length=200)
    time_approx: bool | None = None
    outside_time: bool | None = None
    told_as: Literal["flashback", "tale"] | None = None


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
    # the review's choices (docs/SPEC.md §13.6.2); rows not chosen get their default
    review: list[dict] = Field(default_factory=list, max_length=100_000)


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


def chapter_out(db: Session, world: World, ch: Chapter, names: dict[uuid.UUID, str] | None = None,
                statuses: dict[uuid.UUID, ChapterStatus] | None = None) -> ChapterOut:
    slugs = {p.id: p.slug for p in world.projects}
    pov = None
    if ch.pov_entity_id:
        name = names.get(ch.pov_entity_id) if names is not None else None
        if name is None:
            e = db.get(Entity, ch.pov_entity_id)
            name = e.name if e else None
        pov = Ref(id=ch.pov_entity_id, name=name) if name else None
    status = None
    if ch.status_id:
        st = statuses.get(ch.status_id) if statuses is not None else db.get(ChapterStatus, ch.status_id)
        status = StatusRef(id=st.id, label=st.label, position=st.position) if st else None
    from .storytime import times

    return ChapterOut(id=ch.id, project=slugs[ch.project_id], title=ch.title, state=ch.state, position=ch.position,
                      pov=pov, summary=ch.summary, status=status, experiment_item_id=ch.experiment_item_id,
                      words=words(ch.body), version=ch.version, updated_at=ch.updated_at, retired_at=ch.retired_at,
                      **times(ch))


def chapter_detail(db: Session, world: World, ch: Chapter) -> ChapterDetail:
    base = chapter_out(db, world, ch)
    found = db.execute(
        select(Mention, Entity.name, Entity.kind).join(Entity, Entity.id == Mention.entity_id)
        .where(Mention.source_table == "chapter", Mention.source_id == ch.id).order_by(Mention.start, Entity.name)
    ).all()
    mentions = [{"entity_id": str(m.entity_id), "entity_name": name, "entity_kind": ekind, "start": m.start,
                 "end": m.end, "matched_text": m.matched_text, "kind": m.kind} for m, name, ekind in found]
    notes = [NoteOut(id=n.id, body=n.body, created_at=n.created_at) for n in
             db.scalars(select(HarvestNote).where(HarvestNote.chapter_id == ch.id).order_by(HarvestNote.created_at))]
    item = db.get(Item, ch.experiment_item_id) if ch.experiment_item_id else None
    experiment = None
    if item is not None:
        from .restructure import experiment_info

        info = experiment_info(db, world, item)
        experiment = {k: info[k] for k in ("id", "title", "status", "range", "insert", "lost", "replaced_by")}
        experiment["drafts"] = [{"id": d["id"], "title": d["title"], "position": d["position"]} for d in info["drafts"]]
    return ChapterDetail(**base.model_dump(), body=ch.body, mentions=mentions, harvest_notes=notes,
                         experiment=experiment, experiment_status=item.status if item else None)


def last_revision(db: Session, chapter_id: uuid.UUID) -> Revision | None:
    """The chapter's latest revision on its own line (conflict copies are side copies)."""
    return db.scalars(select(Revision).where(Revision.doc_table == "chapter", Revision.doc_id == chapter_id,
                                             Revision.reason != "conflict")
                      .order_by(Revision.created_at.desc()).limit(1)).first()


def snapshot(db: Session, ch: Chapter, reason: str, user: User, label: str | None = None,
             body: str | None = None) -> Revision | None:
    """Keep the chapter's text (or the given text) as a revision; an automatic one is skipped when nothing changed.
    The words added and removed since the chapter's previous revision are kept with it, for the word history; a start
    or a conflict copy counts as none."""
    text = ch.body if body is None else body
    if reason == "autosnap":
        last = db.scalars(select(Revision).where(Revision.doc_table == "chapter", Revision.doc_id == ch.id)
                          .order_by(Revision.created_at.desc()).limit(1)).first()
        if last is not None and last.body == text and last.title == ch.title:
            return None
    added = removed = 0
    if reason not in ("start", "conflict"):
        prev = last_revision(db, ch.id)
        added, removed = word_changes(prev.body if prev is not None else "", text)
    rev = Revision(doc_table="chapter", doc_id=ch.id, version=ch.version, title=ch.title, body=text,
                   meta={"state": ch.state, "words": words(text), "added": added, "removed": removed},
                   reason=reason, label=label, created_by=user.id)
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
    """The current chapters in order, the open experiments (each with the range it would replace, or where it adds,
    and its drafts), the POV tally and the total word count."""
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    rows = db.scalars(select(Chapter).where(Chapter.project_id == project.id, Chapter.state != "retired")
                      .order_by(Chapter.position, Chapter.created_at)).all()
    names = dict(db.execute(select(Entity.id, Entity.name).where(Entity.world_id == world.id)).all())
    statuses = project_statuses(db, project.id)
    by_id = {s.id: s for s in statuses}
    current = [chapter_out(db, world, c, names, by_id) for c in rows if c.state == "current"]
    from .restructure import experiments_in

    # each open experiment: its range (or where it adds) and its drafts in order (docs/SPEC.md §13.6.1)
    experiments = experiments_in(db, world, project.id)
    tally = Counter(c.pov.name for c in current if c.pov)
    retired = db.scalar(select(func.count()).select_from(Chapter).where(Chapter.project_id == project.id,
                                                                       Chapter.state == "retired"))
    # how far along the book is: chapters and words per status, in the project's order, then those with none
    status_tally = []
    for s in [*statuses, None]:
        group = [c for c in current if (c.status.id if c.status else None) == (s.id if s else None)]
        status_tally.append({"id": str(s.id) if s else None, "label": s.label if s else None,
                             "chapters": len(group), "words": sum(c.words for c in group)})
    return {"chapters": current, "experiments": experiments,
            "pov_tally": [{"name": n, "chapters": k} for n, k in tally.most_common()],
            "words": sum(c.words for c in current), "retired": retired or 0,
            "statuses": [StatusRef(id=s.id, label=s.label, position=s.position) for s in statuses],
            "status_tally": status_tally,
            "cast": cast(db, world, [c.id for c in rows if c.state == "current"])}


def project_statuses(db: Session, project_id: uuid.UUID) -> list[ChapterStatus]:
    return list(db.scalars(select(ChapterStatus).where(ChapterStatus.project_id == project_id)
                           .order_by(ChapterStatus.position, ChapterStatus.created_at)))


def cast(db: Session, world: World, chapter_ids: list[uuid.UUID], limit: int = 8) -> dict[str, list[dict]]:
    """Per chapter, the characters and places named in it, most named first."""
    if not chapter_ids:
        return {}
    rows = db.execute(
        select(Mention.source_id, Entity.id, Entity.name, Entity.kind, func.count())
        .join(Entity, Entity.id == Mention.entity_id)
        .where(Mention.source_table == "chapter", Mention.source_id.in_(chapter_ids), Mention.kind.in_(COUNTED),
               Entity.kind.in_(("character", "place")))
        .group_by(Mention.source_id, Entity.id, Entity.name, Entity.kind)
    ).all()
    out: dict[str, list[dict]] = defaultdict(list)
    for source, eid, name, kind, n in rows:
        out[str(source)].append({"id": str(eid), "name": name, "kind": kind, "count": n})
    return {k: sorted(v, key=lambda x: (x["kind"] != "character", -x["count"], x["name"]))[:limit] for k, v in out.items()}


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
    from .restructure import salvage_extra

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
                    "match": hit, **salvage_extra(db, world, ch)})
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


@router.patch("/chapters/{chapter_id}/about")
def update_about(slug: str, chapter_id: uuid.UUID, body: AboutIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> ChapterOut:
    """The chapter's one-line summary, its status, when it is set and how it is told. Labels, not text: no version
    check and no new version, so setting them on the manuscript list never turns another device's next save into a
    conflict copy."""
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    if body.summary is not None:
        ch.summary = " ".join(body.summary.split())
    if "status_id" in body.model_fields_set:
        if body.status_id is not None:
            st = db.get(ChapterStatus, body.status_id)
            if st is None or st.project_id != ch.project_id:
                raise HTTPException(422, "No such status in this project.")
        ch.status_id = body.status_id
    sent = body.model_fields_set
    for field in ("time_at", "time_end", "time_approx", "outside_time", "told_as"):
        if field in sent:
            setattr(ch, field, getattr(body, field) if field not in ("time_approx", "outside_time")
                    else bool(getattr(body, field)))
    if "time_label" in sent:
        ch.time_label = " ".join((body.time_label or "").split()) or None
    if ch.outside_time and "time_at" in sent and body.time_at is not None:
        ch.outside_time = False
    if ch.outside_time or ch.time_at is None:
        # outside time has no number; and a label, an end or "about" mean nothing without one
        ch.time_at = ch.time_end = ch.time_label = None
        ch.time_approx = False
    if ch.time_end is not None and ch.time_at is not None and ch.time_end < ch.time_at:
        raise HTTPException(422, "A span ends after it starts.")
    ch.updated_by = user.id
    db.commit()
    return chapter_out(db, world, ch)


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
    if r.doc_table == "journal":
        j = db.get(JournalEntry, r.doc_id)
        if j is None or j.world_id != world.id:
            raise HTTPException(404, "No such revision.")
    else:
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
    restore_revision(db, world, ch, r, user)
    db.commit()
    return chapter_detail(db, world, ch)


def restore_revision(db: Session, world: World, ch: Chapter, r: Revision, user: User) -> None:
    """Put a revision's text back, keeping the text it replaces as a revision first. Flushed, not committed."""
    snapshot(db, ch, "restore", user, label=f"Before restoring {r.created_at:%Y-%m-%d %H:%M}")
    ch.body = r.body
    ch.title = r.title or ch.title
    ch.version += 1
    ch.updated_by = user.id
    db.flush()
    refresh_source(db, world.id, "chapter", ch.id, ch.body)


@router.post("/chapters/{chapter_id}/retire")
def retire(slug: str, chapter_id: uuid.UUID, body: RetireIn, user: User = Depends(current_user),
           db: Session = Depends(get_db)) -> ChapterDetail:
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    if ch.state == "retired":
        raise HTTPException(409, "This chapter is in Salvage already.")
    from .restructure import Choice, RetireManyIn, retire_many

    out = retire_many(slug, RetireManyIn(ids=[ch.id], review=[Choice(**c) for c in body.review],
                                         notes={str(ch.id): body.note} if body.note else {}), user, db)
    db.refresh(ch)
    detail = chapter_detail(db, world, ch)
    return JSONResponse(content={**detail.model_dump(mode="json"), "review": out})


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
    """An alternate draft of a chapter, tracked by an experiment item in the inbox: an experiment whose range is this
    one chapter (docs/SPEC.md §13.6.1). From scratch or from a copy."""
    world, _ = member_world(db, user, slug)
    original = _chapter(db, world, chapter_id)
    if original.state != "current":
        raise HTTPException(409, "Experiments start from a chapter in the book.")
    title = " ".join((body.title or original.title).split()) or original.title
    from .restructure import new_experiment

    project = db.get(Project, original.project_id)
    assert project is not None
    _, drafts = new_experiment(db, world, user, project, title, body.start, [original], None)
    db.commit()
    return chapter_detail(db, world, drafts[0])


@router.post("/chapters/{chapter_id}/close-experiment")
def close_experiment(slug: str, chapter_id: uuid.UUID, body: CloseExperimentIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> ChapterDetail:
    """Close this draft's experiment (docs/SPEC.md §13.6.1). accepted: the drafts take the range's place and the range
    is retired. harvested or rejected: the drafts are retired. A note becomes a harvest note on what leaves the book;
    the review of what is tied to it takes its defaults."""
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    if ch.state != "experiment" or ch.experiment_item_id is None:
        raise HTTPException(409, "This chapter is not an experiment.")
    from .restructure import CloseIn, close

    item = db.get(Item, ch.experiment_item_id)
    assert item is not None
    close(db, world, user, item, CloseIn(outcome=body.outcome, note=body.note, decision=body.decision,
                                         decided_on=body.decided_on))
    db.commit()
    db.refresh(ch)
    return chapter_detail(db, world, ch)


# the offline copy ---------------------------------------------------------------------------------------------

LOCAL_REVISIONS = 30


@router.get("/offline")
def offline_pack(slug: str, since: datetime | None = None, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    """What a device needs to keep its offline copy of the world's chapters and journal entries up to date: every
    chapter and entry changed (or given a new revision) since `since`, each with its last 30 revisions, and the ids of
    all chapters and entries that still exist (docs/SPEC.md §14.1.1)."""
    world, _ = member_world(db, user, slug)
    now = datetime.now(UTC)
    project_ids = [p.id for p in world.projects]
    all_ids = list(db.scalars(select(Chapter.id).where(Chapter.project_id.in_(project_ids)))) if project_ids else []
    q = select(Chapter).where(Chapter.project_id.in_(project_ids)) if project_ids else None
    changed: list[Chapter] = []
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    if q is not None:
        if since is not None:
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
    from .journal import entry_detail, journal_words

    jq = select(JournalEntry).where(JournalEntry.world_id == world.id)
    if since is not None:
        fresh = select(Revision.doc_id).where(Revision.doc_table == "journal", Revision.created_at > since)
        jq = jq.where(or_(JournalEntry.updated_at > since, JournalEntry.id.in_(fresh)))
    journal = []
    for j in db.scalars(jq):
        journal.append(entry_detail(db, world, j).model_dump(mode="json"))
        for r in db.scalars(select(Revision).where(Revision.doc_table == "journal", Revision.doc_id == j.id)
                            .order_by(Revision.created_at.desc()).limit(LOCAL_REVISIONS)):
            revisions.append({"id": str(r.id), "chapter_id": str(j.id), "version": r.version, "title": r.title,
                              "body": r.body, "reason": r.reason, "label": r.label,
                              "words": r.meta.get("words", journal_words(r.body)),
                              "created_at": r.created_at.isoformat()})
    journal_ids = db.scalars(select(JournalEntry.id).where(JournalEntry.world_id == world.id))
    return {"now": now.isoformat(), "chapters": chapters, "revisions": revisions,
            "chapter_ids": [str(i) for i in all_ids], "journal": journal,
            "journal_ids": [str(i) for i in journal_ids]}
