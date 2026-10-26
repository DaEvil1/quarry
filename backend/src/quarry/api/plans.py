"""A chapter's plan (docs/SPEC.md §18): a journal entry marked as a plan and linked to the chapters it is for, read
beside the chapter. Linking marks it; a plan with no chapter yet waits on the project page until a chapter is
started from it. Nothing here writes or judges the plan: it is the writer's own text."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Chapter, ChapterPlan, JournalEntry, User, World
from .deps import current_user
from .journal import EntryOut, _entry, entry_out
from .manuscript import ChapterDetail, _chapter, _next_position, _project, chapter_detail
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")


class StartIn(BaseModel):
    project: str
    # the chapter to start it after; none for the end
    after: uuid.UUID | None = None


def link(db: Session, j: JournalEntry, chapter_id: uuid.UUID, user: User) -> None:
    """Link a plan to a chapter, marking it a plan; linking twice is the same as once."""
    j.is_plan = True
    db.execute(insert(ChapterPlan).values(chapter_id=chapter_id, journal_id=j.id, created_by=user.id)
               .on_conflict_do_nothing())


def plans_of(db: Session, chapter_id: uuid.UUID) -> list[dict]:
    """A chapter's plans, newest first (id, title, date)."""
    rows = db.scalars(select(JournalEntry).join(ChapterPlan, ChapterPlan.journal_id == JournalEntry.id)
                      .where(ChapterPlan.chapter_id == chapter_id)
                      .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc()))
    return [{"id": str(j.id), "title": j.title or j.body.split("\n", 1)[0][:60], "date": j.entry_date.isoformat()}
            for j in rows]


def plan_counts(db: Session, chapter_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """How many plans each chapter has, for the manuscript list."""
    if not chapter_ids:
        return {}
    return dict(db.execute(select(ChapterPlan.chapter_id, func.count()).where(ChapterPlan.chapter_id.in_(chapter_ids))
                           .group_by(ChapterPlan.chapter_id)).all())


def link_drafts(db: Session, drafts: list[Chapter], sources: list[Chapter], user: User) -> None:
    """Starting an experiment (docs/SPEC.md §18.4): each draft gets the plans of the chapters it replaces."""
    if not sources:
        return
    plans = list(dict.fromkeys(db.scalars(select(ChapterPlan.journal_id)
                                          .where(ChapterPlan.chapter_id.in_([c.id for c in sources]))
                                          .order_by(ChapterPlan.created_at))))
    for d in drafts:
        for jid in plans:
            db.execute(insert(ChapterPlan).values(chapter_id=d.id, journal_id=jid, created_by=user.id)
                       .on_conflict_do_nothing())


def _world_chapter(db: Session, world: World, chapter_id: uuid.UUID) -> Chapter:
    return _chapter(db, world, chapter_id)


@router.put("/journal/{entry_id}/chapters/{chapter_id}")
def link_chapter(slug: str, entry_id: uuid.UUID, chapter_id: uuid.UUID, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> EntryOut:
    """Link the entry to a chapter it is a plan for (saved without the version check, like its date)."""
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    ch = _world_chapter(db, world, chapter_id)
    link(db, j, ch.id, user)
    db.commit()
    return entry_out(db, world, j)


@router.delete("/journal/{entry_id}/chapters/{chapter_id}")
def unlink_chapter(slug: str, entry_id: uuid.UUID, chapter_id: uuid.UUID, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> EntryOut:
    """Unlink it; the entry stays a plan."""
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    db.query(ChapterPlan).filter(ChapterPlan.journal_id == j.id, ChapterPlan.chapter_id == chapter_id).delete()
    db.commit()
    return entry_out(db, world, j)


@router.post("/journal/{entry_id}/start-chapter", status_code=201)
def start_chapter(slug: str, entry_id: uuid.UUID, body: StartIn, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> ChapterDetail:
    """An empty current chapter where asked, titled as the plan is, with the plan linked (docs/SPEC.md §18.3). Undo is
    deleting it while it is still empty, as deleting a chapter allows."""
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    project = _project(world, body.project)
    title = " ".join((j.title or j.body.split("\n", 1)[0] or "New chapter").split())[:300] or "New chapter"
    if body.after is not None:
        after = _world_chapter(db, world, body.after)
        if after.project_id != project.id or after.state != "current":
            raise HTTPException(422, "Start it after a chapter of that book.")
        position = after.position + 1
        for c in db.scalars(select(Chapter).where(Chapter.project_id == project.id, Chapter.state == "current",
                                                  Chapter.position >= position)):
            c.position += 1
    else:
        position = _next_position(db, project.id)
    ch = Chapter(project_id=project.id, title=title, body="", position=position, created_by=user.id,
                 updated_by=user.id)
    db.add(ch)
    db.flush()
    link(db, j, ch.id, user)
    db.commit()
    return chapter_detail(db, world, ch)

