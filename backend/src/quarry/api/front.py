"""A world's front page (docs/SPEC.md §14.4): getting back in after weeks or years away. The latest notes for next
time (from chapters and journal entries), what happened lately, the latest decisions and the open questions. Worked
out when asked, from revisions and from when rows were created or last changed: nothing is logged, so it is a rough
picture (a row changed twice counts once, on the later day; nothing removed is seen). Grouping by day happens in the
browser, in its own time zone."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Chapter,
    Decision,
    Entity,
    Fact,
    Item,
    JournalEntry,
    JournalNote,
    Relationship,
    Revision,
    SessionNote,
    User,
)
from .deps import current_user
from .followups import counts_for, followup_list, open_decisions
from .manuscript import words
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

# how many of the latest events of each sort are sent: enough for the last ten days with activity in any world
LATELY_ROWS = 3000
# how many decisions To follow through lists before "N more"
FOLLOW_THROUGH = 5


def _iso(x: datetime | None) -> str | None:
    return x.isoformat() if x else None


def _later(a: datetime | None, b: datetime | None) -> datetime | None:
    return max(x for x in (a, b) if x is not None) if (a or b) else None


@router.get("/front")
def front(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    projects = {p.id: p for p in world.projects}
    slugs = {p.id: p.slug for p in world.projects}
    chapters = {c.id: c for c in db.scalars(select(Chapter).where(Chapter.project_id.in_(list(projects))))} if projects else {}

    # where you left off: the notes for next time, newest first
    notes = []
    for n in db.scalars(select(SessionNote).where(SessionNote.user_id == user.id,
                                                  SessionNote.chapter_id.in_(list(chapters)))) if chapters else []:
        c = chapters[n.chapter_id]
        if c.state == "retired" or not (n.note or n.cursor):
            continue
        notes.append({"source": "chapter", "id": str(c.id), "title": c.title, "project": slugs.get(c.project_id),
                      "position": c.position + 1 if c.state == "current" else None, "note": n.note, "cursor": n.cursor,
                      "updated_at": _iso(n.updated_at)})
    for n, j in db.execute(select(JournalNote, JournalEntry).join(JournalEntry, JournalEntry.id == JournalNote.journal_id)
                           .where(JournalNote.user_id == user.id, JournalEntry.world_id == world.id)).all():
        if not (n.note or n.cursor):
            continue
        notes.append({"source": "journal", "id": str(j.id), "title": j.title, "date": j.entry_date.isoformat(),
                      "project": slugs.get(j.project_id) if j.project_id else None, "note": n.note, "cursor": n.cursor,
                      "updated_at": _iso(n.updated_at)})
    notes.sort(key=lambda x: (bool(x["note"]), x["updated_at"] or ""), reverse=True)

    # lately: what changed, as events the browser groups by day
    events: list[dict] = []
    if chapters:
        for doc, at, meta in db.execute(
            select(Revision.doc_id, Revision.created_at, Revision.meta)
            .where(Revision.doc_table == "chapter", Revision.doc_id.in_(list(chapters)),
                   Revision.reason.not_in(("start", "conflict")))
            .order_by(Revision.created_at.desc()).limit(LATELY_ROWS)
        ).all():
            if meta.get("added"):
                events.append({"kind": "words", "at": _iso(at), "project": slugs.get(chapters[doc].project_id),
                               "n": int(meta["added"])})
        # the working text against each chapter's last revision counts on the day it was last saved, as in the
        # word history
        from .manuscript import last_revision
        from ..wordhistory import word_changes

        for c in chapters.values():
            if c.state == "retired":
                continue
            last = last_revision(db, c.id)
            base = last.body if last is not None else ""
            if base != c.body:
                added, _removed = word_changes(base, c.body)
                if added:
                    events.append({"kind": "words", "at": _iso(c.updated_at), "project": slugs.get(c.project_id),
                                   "n": added})
    for j in db.scalars(select(JournalEntry).where(JournalEntry.world_id == world.id)
                        .order_by(JournalEntry.updated_at.desc()).limit(LATELY_ROWS)):
        events.append({"kind": "journal", "at": _iso(_later(j.created_at, j.updated_at)), "id": str(j.id)})
    for e in db.scalars(select(Entity).where(Entity.world_id == world.id).order_by(Entity.updated_at.desc())
                        .limit(LATELY_ROWS)):
        events.append({"kind": "entity", "at": _iso(_later(e.created_at, e.updated_at)), "id": str(e.id),
                       "name": e.name, "entity_kind": e.kind, "added": e.updated_at is None or e.created_at == e.updated_at})
    for table, kind in ((Fact, "fact"), (Relationship, "relationship")):
        for at in db.scalars(select(func.greatest(table.created_at, table.updated_at)).where(table.world_id == world.id)
                             .order_by(table.updated_at.desc()).limit(LATELY_ROWS)):
            events.append({"kind": kind, "at": _iso(at)})
    for i in db.scalars(select(Item).where(Item.world_id == world.id, Item.kind != "experiment")
                        .order_by(Item.created_at.desc()).limit(LATELY_ROWS)):
        events.append({"kind": "captured", "at": _iso(i.created_at), "item_kind": i.kind})
        if i.closed_at is not None:
            events.append({"kind": "closed", "at": _iso(i.closed_at), "item_kind": i.kind})
    for d in db.scalars(select(Decision).where(Decision.world_id == world.id)
                        .order_by(Decision.decided_on.desc()).limit(LATELY_ROWS)):
        events.append({"kind": "decision", "day": d.decided_on.isoformat()})

    decisions = [{"id": str(d.id), "decided_on": d.decided_on.isoformat(), "text": d.text,
                  "project": slugs.get(d.project_id) if d.project_id else None}
                 for d in db.scalars(select(Decision).where(Decision.world_id == world.id)
                                     .order_by(Decision.decided_on.desc(), Decision.created_at.desc()).limit(5))]
    counts = counts_for(db, [uuid.UUID(d["id"]) for d in decisions])
    for d in decisions:
        d["followups"] = counts.get(uuid.UUID(d["id"]))
    # to follow through (docs/SPEC.md §16.5): the decisions with open follow-ups, oldest first, five; each with the
    # first written chapter one of its planned changes is tied to
    waiting = open_decisions(db, world)
    follow = []
    if waiting:
        rows = list(db.scalars(select(Decision).where(Decision.id.in_(list(waiting)))
                               .order_by(Decision.decided_on, Decision.created_at).limit(FOLLOW_THROUGH)))
        for d in rows:
            written = next((x["written"] for x in followup_list(db, world, d) if x["written"]), None)
            follow.append({"id": str(d.id), "decided_on": d.decided_on.isoformat(), "text": d.text,
                           "project": slugs.get(d.project_id) if d.project_id else None,
                           "followups": waiting[d.id], "written": written})
    open_q = select(Item).where(Item.world_id == world.id, Item.kind == "question", Item.status == "open")
    questions = [{"id": str(i.id), "title": i.title, "body": i.body, "created_at": _iso(i.created_at),
                  "project": slugs.get(i.project_id) if i.project_id else None}
                 for i in db.scalars(open_q.order_by(Item.created_at.desc()).limit(5))]
    count = db.scalar(select(func.count()).select_from(open_q.subquery())) or 0
    oldest = db.scalar(select(func.min(Item.created_at)).where(Item.world_id == world.id, Item.kind == "question",
                                                               Item.status == "open"))

    # each project's words and when it was last written in
    project_rows = []
    for p in world.projects:
        mine = [c for c in chapters.values() if c.project_id == p.id and c.state == "current"]
        last = db.scalar(select(func.max(Revision.created_at)).where(
            Revision.doc_table == "chapter", Revision.doc_id.in_([c.id for c in chapters.values() if c.project_id == p.id]),
            Revision.reason.not_in(("start", "conflict")))) if mine else None
        project_rows.append({"slug": p.slug, "words": sum(words(c.body) for c in mine), "chapters": len(mine),
                             "last_written": _iso(_later(last, max((c.updated_at for c in mine), default=None)))})
    return {"premise": world.premise, "notes": notes, "lately": events, "decisions": decisions,
            "follow_through": {"decisions": follow, "count": len(waiting)},
            "questions": {"latest": questions, "count": count, "oldest": _iso(oldest)}, "projects": project_rows}

