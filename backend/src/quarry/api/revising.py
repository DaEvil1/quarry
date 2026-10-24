"""Revising and salvaging (SPEC §11): chapter statuses, the cuts bin, word history, a checkpoint of every chapter at
once, and find and replace across chapters.

Renames that keep the old name live with the bible (bible.py), and reading one entry's thread and the changes since a
checkpoint are worked out in the browser from the offline copy.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import matcher_for, refresh_source
from ..models import STARTING_STATUSES, Chapter, ChapterStatus, Cut, Project, Revision, User, World
from ..wordhistory import word_changes
from .deps import current_user
from .manuscript import (
    BODY_MAX,
    _chapter,
    _project,
    last_revision,
    project_statuses,
    restore_revision,
    snapshot,
    words,
)
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")


def seed_statuses(db: Session, project_id: uuid.UUID, labels: list[str] | tuple[str, ...] = STARTING_STATUSES) -> None:
    for i, label in enumerate(labels):
        db.add(ChapterStatus(project_id=project_id, label=label, position=i))


# chapter statuses ------------------------------------------------------------------------------------------------


class StatusIn(BaseModel):
    label: str = Field(min_length=1, max_length=100)


class StatusOrderIn(BaseModel):
    ids: list[uuid.UUID]


def _label(text: str) -> str:
    label = " ".join(text.split())
    if not label:
        raise HTTPException(422, "Give the status a name.")
    return label


def _status(db: Session, world: World, status_id: uuid.UUID) -> ChapterStatus:
    st = db.get(ChapterStatus, status_id)
    if st is None or st.project_id not in {p.id for p in world.projects}:
        raise HTTPException(404, "No such status.")
    return st


def _statuses_out(db: Session, project_id: uuid.UUID) -> list[dict]:
    """The project's statuses in order, each with how many chapters (current, experiments and retired) have it."""
    counts = dict(db.execute(select(Chapter.status_id, func.count()).where(Chapter.project_id == project_id,
                                                                           Chapter.status_id.is_not(None))
                             .group_by(Chapter.status_id)).all())
    return [{"id": str(s.id), "label": s.label, "position": s.position, "chapters": counts.get(s.id, 0)}
            for s in project_statuses(db, project_id)]


def _renumber_statuses(db: Session, project_id: uuid.UUID) -> None:
    for i, s in enumerate(project_statuses(db, project_id)):
        s.position = i


@router.get("/projects/{project_slug}/statuses")
def list_statuses(slug: str, project_slug: str, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    return _statuses_out(db, _project(world, project_slug).id)


@router.post("/projects/{project_slug}/statuses", status_code=201)
def add_status(slug: str, project_slug: str, body: StatusIn, user: User = Depends(current_user),
               db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    top = db.scalar(select(func.max(ChapterStatus.position)).where(ChapterStatus.project_id == project.id))
    db.add(ChapterStatus(project_id=project.id, label=_label(body.label), position=0 if top is None else top + 1))
    db.commit()
    return _statuses_out(db, project.id)


@router.patch("/statuses/{status_id}")
def rename_status(slug: str, status_id: uuid.UUID, body: StatusIn, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> list[dict]:
    """Renaming a status renames it on every chapter that has it (they point at the row)."""
    world, _ = member_world(db, user, slug)
    st = _status(db, world, status_id)
    st.label = _label(body.label)
    db.commit()
    return _statuses_out(db, st.project_id)


@router.delete("/statuses/{status_id}")
def remove_status(slug: str, status_id: uuid.UUID, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> list[dict]:
    """Chapters that had it go back to no status."""
    world, _ = member_world(db, user, slug)
    st = _status(db, world, status_id)
    project_id = st.project_id
    db.delete(st)
    db.flush()
    _renumber_statuses(db, project_id)
    db.commit()
    return _statuses_out(db, project_id)


@router.put("/projects/{project_slug}/status-order")
def order_statuses(slug: str, project_slug: str, body: StatusOrderIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    by_id = {s.id: s for s in project_statuses(db, project.id)}
    if len(body.ids) != len(by_id) or set(body.ids) != set(by_id):
        raise HTTPException(422, "Send every status of the project exactly once.")
    for i, sid in enumerate(body.ids):
        by_id[sid].position = i
    db.commit()
    return _statuses_out(db, project.id)


# the cuts bin ------------------------------------------------------------------------------------------------------


class CutIn(BaseModel):
    # chosen on the device, so a cut sent twice (offline, then retried) is kept once
    id: uuid.UUID
    chapter_id: uuid.UUID
    body: str = Field(min_length=1, max_length=BODY_MAX)
    before: str = Field(default="", max_length=200)
    after: str = Field(default="", max_length=200)
    cut_at: datetime | None = None


class PutBackIn(BaseModel):
    chapter_id: uuid.UUID


def cut_out(db: Session, c: Cut, slugs: dict[uuid.UUID, str], q: str | None = None) -> dict:
    source = db.get(Chapter, c.chapter_id) if c.chapter_id else None
    target = db.get(Chapter, c.put_back_to) if c.put_back_to else None
    match = None
    if q:
        i = c.body.lower().find(q.lower())
        if i >= 0:
            match = {"before": ("…" if i > 60 else "") + c.body[max(0, i - 60):i], "match": c.body[i:i + len(q)],
                     "after": c.body[i + len(q):i + len(q) + 60]}
    return {"id": str(c.id), "project": slugs.get(c.project_id), "body": c.body, "before": c.before, "after": c.after,
            "words": words(c.body), "cut_at": c.cut_at.isoformat(),
            "chapter": {"id": str(source.id), "title": source.title, "state": source.state} if source else None,
            "chapter_title": c.chapter_title,
            "put_back_at": c.put_back_at.isoformat() if c.put_back_at else None,
            "put_back_to": {"id": str(target.id), "title": target.title} if target else None,
            "match": match}


def _cut(db: Session, world: World, cut_id: uuid.UUID) -> Cut:
    c = db.get(Cut, cut_id)
    if c is None or c.world_id != world.id:
        raise HTTPException(404, "No such cut.")
    return c


@router.post("/cuts", status_code=201)
def add_cut(slug: str, body: CutIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """A passage cut from a chapter into its project's bin. The chapter's own change is an ordinary save."""
    world, _ = member_world(db, user, slug)
    slugs = {p.id: p.slug for p in world.projects}
    known = db.get(Cut, body.id)
    if known is not None:
        if known.world_id != world.id:
            raise HTTPException(409, "That id is taken.")
        return cut_out(db, known, slugs)
    ch = _chapter(db, world, body.chapter_id)
    c = Cut(id=body.id, world_id=world.id, project_id=ch.project_id, chapter_id=ch.id, chapter_title=ch.title,
            body=body.body, before=body.before, after=body.after, cut_at=body.cut_at or datetime.now(UTC),
            created_by=user.id)
    if c.cut_at.tzinfo is None:
        c.cut_at = c.cut_at.replace(tzinfo=UTC)
    db.add(c)
    db.commit()
    return cut_out(db, c, slugs)


@router.get("/projects/{project_slug}/cuts")
def list_cuts(slug: str, project_slug: str, q: str | None = Query(None, max_length=200),
              put_back: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """The project's bin, newest first; `q` searches the text and the source chapter's title. Cuts that were put back
    are left out unless asked for."""
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    query = select(Cut).where(Cut.project_id == project.id)
    if not put_back:
        query = query.where(Cut.put_back_at.is_(None))
    needle = (q or "").strip()
    if needle:
        like = f"%{needle}%"
        query = query.where(or_(Cut.body.ilike(like), Cut.chapter_title.ilike(like)))
    slugs = {p.id: p.slug for p in world.projects}
    return [cut_out(db, c, slugs, needle or None) for c in db.scalars(query.order_by(Cut.cut_at.desc()))]


@router.get("/chapters/{chapter_id}/cuts")
def chapter_cuts(slug: str, chapter_id: uuid.UUID, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> list[dict]:
    """The cuts from this chapter still in the bin, newest first (for the editor's side panel)."""
    world, _ = member_world(db, user, slug)
    ch = _chapter(db, world, chapter_id)
    slugs = {p.id: p.slug for p in world.projects}
    rows = db.scalars(select(Cut).where(Cut.chapter_id == ch.id, Cut.put_back_at.is_(None))
                      .order_by(Cut.cut_at.desc()))
    return [cut_out(db, c, slugs) for c in rows]


@router.post("/cuts/{cut_id}/put-back")
def put_back(slug: str, cut_id: uuid.UUID, body: PutBackIn, user: User = Depends(current_user),
             db: Session = Depends(get_db)) -> dict:
    """The cut went back into a chapter (the editor made that edit): it stays in the bin, marked put back."""
    world, _ = member_world(db, user, slug)
    c = _cut(db, world, cut_id)
    ch = _chapter(db, world, body.chapter_id)
    c.put_back_at = datetime.now(UTC)
    c.put_back_to = ch.id
    db.commit()
    return cut_out(db, c, {p.id: p.slug for p in world.projects})


@router.delete("/cuts/{cut_id}", status_code=204)
def undo_cut(slug: str, cut_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    """Only for Undo right after cutting: the text went back, so the cut goes. Cuts are otherwise never deleted."""
    world, _ = member_world(db, user, slug)
    db.delete(_cut(db, world, cut_id))
    db.commit()


# word history ----------------------------------------------------------------------------------------------------


@router.get("/projects/{project_slug}/word-history")
def word_history(slug: str, project_slug: str, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    """Words written and cut per revision of the project's chapters (whatever their state), with when; the browser
    sums them per day in its own time zone. `pending` is the working text against each chapter's last revision, which
    counts for today. Starts and conflict copies count as nothing."""
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    chapters = list(db.scalars(select(Chapter).where(Chapter.project_id == project.id)))
    titles = {c.id: c.title for c in chapters}
    rows = db.execute(select(Revision.doc_id, Revision.created_at, Revision.meta)
                      .where(Revision.doc_table == "chapter", Revision.doc_id.in_(list(titles)),
                             Revision.reason.not_in(("start", "conflict")))
                      .order_by(Revision.created_at)).all() if titles else []
    revisions = [{"at": at.isoformat(), "chapter_id": str(doc), "added": int(meta.get("added", 0)),
                  "removed": int(meta.get("removed", 0))}
                 for doc, at, meta in rows if meta.get("added") or meta.get("removed")]
    pending = []
    for c in chapters:
        last = last_revision(db, c.id)
        base = last.body if last is not None else ""
        if base != c.body:
            added, removed = word_changes(base, c.body)
            if added or removed:
                pending.append({"chapter_id": str(c.id), "added": added, "removed": removed})
    return {"revisions": revisions, "pending": pending, "chapters": {str(k): v for k, v in titles.items()}}


# a checkpoint of every chapter -----------------------------------------------------------------------------------


class CheckpointAllIn(BaseModel):
    label: str = Field(min_length=1, max_length=200)


@router.post("/projects/{project_slug}/checkpoint")
def checkpoint_all(slug: str, project_slug: str, body: CheckpointAllIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> dict:
    """One labelled checkpoint of every current chapter and experiment, so one label covers the whole book."""
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    label = " ".join(body.label.split())
    if not label:
        raise HTTPException(422, "Give the checkpoint a label.")
    chapters = db.scalars(select(Chapter).where(Chapter.project_id == project.id, Chapter.state != "retired"))
    n = 0
    for ch in chapters:
        snapshot(db, ch, "checkpoint", user, label=label)
        n += 1
    db.commit()
    return {"chapters": n, "label": label}


# find and replace across chapters --------------------------------------------------------------------------------


class FindIn(BaseModel):
    find: str = Field(min_length=1, max_length=200)
    match_case: bool = True
    whole_words: bool = True
    scope: Literal["project", "world"] = "project"


class ChosenIn(BaseModel):
    id: uuid.UUID
    version: int
    # where each chosen hit starts, in the text the preview was made from
    hits: list[int] = Field(max_length=10_000)


class ReplaceIn(FindIn):
    replace: str = Field(default="", max_length=200)
    chapters: list[ChosenIn] = Field(max_length=2_000)


class UndoChapterIn(BaseModel):
    id: uuid.UUID
    revision_id: uuid.UUID
    version: int


class UndoReplaceIn(BaseModel):
    chapters: list[UndoChapterIn] = Field(max_length=2_000)


def find_pattern(find: str, match_case: bool, whole_words: bool) -> re.Pattern[str]:
    """Plain text, no patterns. Whole words: no letter or digit right before or after (an ending like "'s" is fine)."""
    core = re.escape(find)
    if whole_words:
        if re.match(r"\w", find[0]):
            core = r"(?<!\w)" + core
        if re.match(r"\w", find[-1]):
            core += r"(?!\w)"
    return re.compile(core, 0 if match_case else re.IGNORECASE)


def _context(text: str, start: int, end: int, n: int = 8) -> tuple[str, str]:
    """About `n` words either side of a hit, within its paragraph."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end < 0 else line_end
    before_words = re.findall(r"\S+\s*", text[max(line_start, start - 300):start])
    after_words = re.findall(r"\s*\S+", text[end:min(line_end, end + 300)])
    before = "".join(before_words[-n:])
    after = "".join(after_words[:n])
    if len(before_words) > n or (start - 300 > line_start):
        before = "…" + before
    if len(after_words) > n or (end + 300 < line_end):
        after += "…"
    return before, after


def _searched(db: Session, world: World, project: Project, scope: str) -> list[tuple[Chapter, Project]]:
    """Current chapters and experiments (never retired ones), in story order: projects in order, each project's
    chapters in order, its experiments after them."""
    projects = sorted(world.projects, key=lambda p: (p.position, p.created_at)) if scope == "world" else [project]
    out: list[tuple[Chapter, Project]] = []
    for p in projects:
        rows = db.scalars(select(Chapter).where(Chapter.project_id == p.id, Chapter.state != "retired")
                          .order_by(Chapter.position, Chapter.created_at)).all()
        out += [(c, p) for c in rows if c.state == "current"] + [(c, p) for c in rows if c.state == "experiment"]
    return out


@router.post("/projects/{project_slug}/find")
def find(slug: str, project_slug: str, body: FindIn, user: User = Depends(current_user),
         db: Session = Depends(get_db)) -> dict:
    """Every hit, grouped by chapter in story order, with each chapter's version for the replace that may follow."""
    world, _ = member_world(db, user, slug)
    project = _project(world, project_slug)
    pattern = find_pattern(body.find, body.match_case, body.whole_words)
    chapters, total = [], 0
    for ch, p in _searched(db, world, project, body.scope):
        hits = []
        for m in pattern.finditer(ch.body):
            before, after = _context(ch.body, m.start(), m.end())
            hits.append({"start": m.start(), "end": m.end(), "before": before, "match": m.group(0), "after": after})
        if hits:
            total += len(hits)
            chapters.append({"id": str(ch.id), "title": ch.title, "state": ch.state, "project": p.slug,
                             "project_name": p.name, "version": ch.version, "hits": hits})
    return {"chapters": chapters, "total": total}


def replace_label(find: str, replace: str) -> str:
    label = f'Before replacing "{find}" with "{replace}"' if replace else f'Before deleting "{find}"'
    return label[:200]


@router.post("/projects/{project_slug}/replace")
def replace(slug: str, project_slug: str, body: ReplaceIn, user: User = Depends(current_user),
            db: Session = Depends(get_db)) -> dict:
    """Replace the chosen hits, in one transaction. A chapter that changed since the preview is skipped; every other
    one gets a checkpoint named for the replace first, then its hits (each checked to still read the same)."""
    world, _ = member_world(db, user, slug)
    _project(world, project_slug)
    pattern = find_pattern(body.find, body.match_case, body.whole_words)
    label = replace_label(body.find, body.replace)
    matcher = matcher_for(db, world.id)
    done, skipped, replaced = [], [], 0
    for chosen in body.chapters:
        ch = _chapter(db, world, chosen.id)
        if ch.state == "retired":
            skipped.append({"id": str(ch.id), "title": ch.title, "reason": "retired"})
            continue
        if ch.version != chosen.version:
            skipped.append({"id": str(ch.id), "title": ch.title, "reason": "changed since the preview"})
            continue
        found = {m.start(): m.end() for m in pattern.finditer(ch.body)}
        starts = sorted({s for s in chosen.hits if s in found}, reverse=True)
        if not starts:
            continue
        rev = snapshot(db, ch, "checkpoint", user, label=label)
        text = ch.body
        for s in starts:
            text = text[:s] + body.replace + text[found[s]:]
        ch.body = text
        ch.version += 1
        ch.updated_by = user.id
        db.flush()
        refresh_source(db, world.id, "chapter", ch.id, ch.body, matcher)
        replaced += len(starts)
        done.append({"id": str(ch.id), "title": ch.title, "replaced": len(starts), "version": ch.version,
                     "revision_id": str(rev.id) if rev else None})
    db.commit()
    return {"replaced": replaced, "chapters": done, "skipped": skipped, "label": label}


@router.post("/projects/{project_slug}/replace/undo")
def undo_replace(slug: str, project_slug: str, body: UndoReplaceIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> dict:
    """Put each chapter back to its checkpoint from before the replace, if it hasn't changed since. The replaced text
    is kept as a revision, as every restore does."""
    world, _ = member_world(db, user, slug)
    _project(world, project_slug)
    restored, skipped = [], []
    for item in body.chapters:
        ch = _chapter(db, world, item.id)
        r = db.get(Revision, item.revision_id)
        if r is None or r.doc_table != "chapter" or r.doc_id != ch.id:
            raise HTTPException(404, "No such revision of this chapter.")
        if ch.version != item.version:
            skipped.append({"id": str(ch.id), "title": ch.title, "reason": "changed since the replace"})
            continue
        restore_revision(db, world, ch, r, user)
        restored.append({"id": str(ch.id), "title": ch.title, "version": ch.version})
    db.commit()
    return {"restored": restored, "skipped": skipped}
