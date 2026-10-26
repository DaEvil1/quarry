"""The journal: dated thinking on paper, for the whole world or one project.

Since phase 13 (docs/SPEC.md §14.1.1) an entry is written in the chapter editor and saved like a chapter: typing
autosaves the text with the version it started from (a conflict answers with the newer entry), snapshots are kept as
revisions on the same rules, and History restores them. The date and the project are labels, saved without the
version check. An entry made offline brings the id chosen on the device, so sending it twice makes one entry.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import forget_source, refresh_source
from ..models import (
    Chapter,
    ChapterPlan,
    Decision,
    DecisionLink,
    Entity,
    Fact,
    Item,
    ItemLink,
    JournalEntry,
    JournalNote,
    Mention,
    Relationship,
    Revision,
    Telling,
    User,
    World,
)
from ..margin import without_pictures
from ..wordhistory import word_changes
from .deps import current_user
from .items import WORLD_ONLY, project_by_slug
from .worlds import member_world

router = APIRouter(prefix="/api/worlds/{slug}")

BODY_MAX = 2_000_000
WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")


def journal_words(text: str) -> int:
    """Words in an entry. A `%%` line is ordinary text in the Journal: the whole entry is a note to yourself. A picture
    line isn't counted (docs/SPEC.md §17.3)."""
    return len(WORD_RE.findall(without_pictures(text)))


class EntryOut(BaseModel):
    id: uuid.UUID
    entry_date: date
    title: str | None
    body: str
    project: str | None
    version: int
    words: int = 0
    created_at: datetime
    updated_at: datetime
    # decisions and changes since its date touching what it names (docs/SPEC.md §14.5); on the list only
    since: int | None = None
    # a plan, and the chapters it is for (docs/SPEC.md §18.1)
    is_plan: bool = False
    chapters: list[dict] = Field(default_factory=list)


class EntryDetail(EntryOut):
    mentions: list[dict] = Field(default_factory=list)


class EntryIn(BaseModel):
    # chosen by the device for an entry made offline, so sending it twice makes one entry
    id: uuid.UUID | None = None
    entry_date: date | None = None
    title: str | None = Field(default=None, max_length=300)
    body: str = Field(default="", max_length=BODY_MAX)
    project: str | None = None


class EntryUpdate(BaseModel):
    base_version: int
    entry_date: date | None = None
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=BODY_MAX)
    project: str | None = None


class AboutIn(BaseModel):
    entry_date: date | None = None
    project: str | None = None
    # the Plan switch (docs/SPEC.md §18.1): off removes its links to chapters
    is_plan: bool | None = None


class SnapshotIn(BaseModel):
    reason: str = Field(default="autosnap", pattern="^(autosnap|checkpoint|conflict|restore)$")
    label: str | None = Field(default=None, max_length=200)
    # only for a conflict copy or a restore made offline (see the chapters' snapshots)
    body: str | None = Field(default=None, max_length=BODY_MAX)


class RestoreIn(BaseModel):
    revision_id: uuid.UUID


def chapter_ref(ch: Chapter, slugs: dict[uuid.UUID, str]) -> dict:
    """A chapter as a plan names it: `chapter 4, The Quay`, a draft, or `in Salvage`."""
    return {"id": str(ch.id), "title": ch.title, "state": ch.state, "project": slugs.get(ch.project_id),
            "n": ch.position + 1 if ch.state == "current" else None}


def plan_chapters(db: Session, world: World, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    """The chapters each of these entries is a plan for, in book order (current first, then drafts, then Salvage)."""
    if not ids:
        return {}
    slugs = {p.id: p.slug for p in world.projects}
    order = {"current": 0, "experiment": 1, "retired": 2}
    rows = db.execute(select(ChapterPlan.journal_id, Chapter).join(Chapter, Chapter.id == ChapterPlan.chapter_id)
                      .where(ChapterPlan.journal_id.in_(ids))).all()
    out: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for jid, ch in sorted(rows, key=lambda r: (order.get(r[1].state, 3), r[1].position, r[1].title)):
        out[jid].append(chapter_ref(ch, slugs))
    return out


def _out(j: JournalEntry, world: World, chapters: list[dict] | None = None) -> EntryOut:
    slugs = {p.id: p.slug for p in world.projects}
    return EntryOut(id=j.id, entry_date=j.entry_date, title=j.title, body=j.body,
                    project=slugs.get(j.project_id) if j.project_id else None, version=j.version,
                    words=journal_words(j.body), created_at=j.created_at, updated_at=j.updated_at,
                    is_plan=j.is_plan, chapters=chapters or [])


def entry_out(db: Session, world: World, j: JournalEntry) -> EntryOut:
    return _out(j, world, plan_chapters(db, world, [j.id]).get(j.id))


def entry_detail(db: Session, world: World, j: JournalEntry) -> EntryDetail:
    found = db.execute(
        select(Mention, Entity.name, Entity.kind).join(Entity, Entity.id == Mention.entity_id)
        .where(Mention.source_table == "journal", Mention.source_id == j.id).order_by(Mention.start, Entity.name)
    ).all()
    mentions = [{"entity_id": str(m.entity_id), "entity_name": name, "entity_kind": ekind, "start": m.start,
                 "end": m.end, "matched_text": m.matched_text, "kind": m.kind} for m, name, ekind in found]
    return EntryDetail(**entry_out(db, world, j).model_dump(), mentions=mentions)


def _entry(db: Session, world: World, entry_id: uuid.UUID) -> JournalEntry:
    j = db.get(JournalEntry, entry_id)
    if j is None or j.world_id != world.id:
        raise HTTPException(404, "No such journal entry.")
    return j


def last_revision(db: Session, entry_id: uuid.UUID) -> Revision | None:
    return db.scalars(select(Revision).where(Revision.doc_table == "journal", Revision.doc_id == entry_id,
                                             Revision.reason != "conflict")
                      .order_by(Revision.created_at.desc()).limit(1)).first()


def snapshot(db: Session, j: JournalEntry, reason: str, user: User, label: str | None = None,
             body: str | None = None) -> Revision | None:
    """Keep the entry's text (or the given text) as a revision, as for chapters: an automatic one is skipped when
    nothing changed. The Journal isn't the book, so its revisions never count in the word history."""
    text = j.body if body is None else body
    title = j.title or ""
    if reason == "autosnap":
        last = db.scalars(select(Revision).where(Revision.doc_table == "journal", Revision.doc_id == j.id)
                          .order_by(Revision.created_at.desc()).limit(1)).first()
        if last is not None and last.body == text and last.title == title:
            return None
    added = removed = 0
    if reason not in ("start", "conflict"):
        prev = last_revision(db, j.id)
        added, removed = word_changes(prev.body if prev is not None else "", text)
    rev = Revision(doc_table="journal", doc_id=j.id, version=j.version, title=title, body=text,
                   meta={"words": journal_words(text), "added": added, "removed": removed},
                   reason=reason, label=label, created_by=user.id)
    db.add(rev)
    db.flush()
    return rev


def _conflict(db: Session, world: World, j: JournalEntry) -> JSONResponse:
    return JSONResponse(status_code=409, content={
        "detail": "This entry changed on another device. Here is the newer version.",
        "entry": entry_detail(db, world, j).model_dump(mode="json")})


def _query(world: World, project: str | None):  # type: ignore[no-untyped-def]
    q = select(JournalEntry).where(JournalEntry.world_id == world.id)
    if project == WORLD_ONLY:
        q = q.where(JournalEntry.project_id.is_(None))
    elif project:
        p = project_by_slug(world, project)
        assert p is not None
        q = q.where(JournalEntry.project_id == p.id)
    return q


@router.get("/journal")
def list_journal(slug: str, project: str | None = None, limit: int = Query(200, ge=1, le=5000),
                 plans: str | None = Query(None, pattern="^(1|unlinked)$"),
                 user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[EntryOut]:
    """Newest first. `plans=1`: only plans; `plans=unlinked`: plans linked to no chapter (docs/SPEC.md §18.3)."""
    world, _ = member_world(db, user, slug)
    q = _query(world, project)
    if plans:
        q = q.where(JournalEntry.is_plan.is_(True))
    if plans == "unlinked":
        q = q.where(~JournalEntry.id.in_(select(ChapterPlan.journal_id)))
    q = q.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc()).limit(limit)
    entries = list(db.scalars(q))
    counts = Since(db, world).counts(entries)
    chapters = plan_chapters(db, world, [j.id for j in entries if j.is_plan])
    return [_out(j, world, chapters.get(j.id)).model_copy(update={"since": counts.get(j.id, 0)}) for j in entries]


@router.post("/journal", status_code=201)
def create_entry(slug: str, body: EntryIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> EntryDetail:
    world, _ = member_world(db, user, slug)
    if body.id is not None:
        known = db.get(JournalEntry, body.id)
        if known is not None:
            if known.world_id != world.id:
                raise HTTPException(409, "That id is taken.")
            return entry_detail(db, world, known)
    p = project_by_slug(world, body.project)
    j = JournalEntry(world_id=world.id, project_id=p.id if p else None, entry_date=body.entry_date or date.today(),
                     title=(body.title or "").strip() or None, body=body.body, created_by=user.id,
                     updated_by=user.id)
    if body.id is not None:
        j.id = body.id
    db.add(j)
    db.flush()
    refresh_source(db, world.id, "journal", j.id, j.body)
    db.commit()
    return entry_detail(db, world, j)


@router.get("/journal/{entry_id}")
def get_entry(slug: str, entry_id: uuid.UUID, user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> EntryDetail:
    world, _ = member_world(db, user, slug)
    return entry_detail(db, world, _entry(db, world, entry_id))


@router.patch("/journal/{entry_id}")
def update_entry(slug: str, entry_id: uuid.UUID, body: EntryUpdate, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    if j.version != body.base_version:
        return _conflict(db, world, j)
    if body.entry_date is not None:
        j.entry_date = body.entry_date
    if "title" in body.model_fields_set:
        j.title = (body.title or "").strip() or None
    if body.body is not None:
        j.body = body.body
    if "project" in body.model_fields_set:
        p = project_by_slug(world, body.project)
        j.project_id = p.id if p else None
    j.version += 1
    j.updated_by = user.id
    db.flush()
    if body.body is not None:
        refresh_source(db, world.id, "journal", j.id, j.body)
    db.commit()
    return entry_detail(db, world, j)


@router.patch("/journal/{entry_id}/about")
def update_about(slug: str, entry_id: uuid.UUID, body: AboutIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> EntryOut:
    """The entry's date and project: labels, saved without the version check, so changing them never turns another
    device's next save into a conflict copy (as a chapter's summary)."""
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    if body.entry_date is not None:
        j.entry_date = body.entry_date
    if "project" in body.model_fields_set:
        p = project_by_slug(world, body.project)
        j.project_id = p.id if p else None
    if body.is_plan is not None:
        j.is_plan = body.is_plan
        if not body.is_plan:
            db.execute(delete(ChapterPlan).where(ChapterPlan.journal_id == j.id))
    j.updated_by = user.id
    db.commit()
    return entry_out(db, world, j)


def ties(db: Session, j: JournalEntry) -> dict:
    """What was planned in an entry, said before it is deleted."""
    def count(q) -> int:  # type: ignore[no-untyped-def]
        return int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)

    return {"facts": count(select(Fact.id).where(Fact.planned_in_journal_id == j.id)),
            "relationships": count(select(Relationship.id).where(Relationship.planned_in_journal_id == j.id)),
            "notes": count(select(Telling.id).where(Telling.journal_id == j.id)),
            "items": count(select(ItemLink.item_id).where(ItemLink.target_table == "journal",
                                                          ItemLink.target_id == j.id)),
            # the chapters it is the plan for (docs/SPEC.md §18.1)
            "plan_for": [{"id": str(c.id), "title": c.title, "state": c.state,
                          "n": c.position + 1 if c.state == "current" else None}
                         for c in db.scalars(select(Chapter).join(ChapterPlan, ChapterPlan.chapter_id == Chapter.id)
                                             .where(ChapterPlan.journal_id == j.id).order_by(Chapter.position))]}


@router.get("/journal/{entry_id}/ties")
def entry_ties(slug: str, entry_id: uuid.UUID, user: User = Depends(current_user),
               db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    return ties(db, _entry(db, world, entry_id))


@router.delete("/journal/{entry_id}", status_code=204)
def delete_entry(slug: str, entry_id: uuid.UUID, user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> None:
    """Facts, relationships and event notes planned in it keep their passage, without the entry (SET NULL); items
    made from it lose the link. Its revisions go with it."""
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    forget_source(db, "journal", j.id)
    db.execute(delete(ItemLink).where(ItemLink.target_table == "journal", ItemLink.target_id == j.id))
    db.execute(delete(Revision).where(Revision.doc_table == "journal", Revision.doc_id == j.id))
    db.delete(j)
    db.commit()


# revisions -----------------------------------------------------------------------------------------------------


@router.post("/journal/{entry_id}/revisions", status_code=201)
def take_snapshot(slug: str, entry_id: uuid.UUID, body: SnapshotIn, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    if body.body is not None and body.reason not in ("conflict", "restore"):
        raise HTTPException(422, "Only a conflict copy or an offline restore brings its own text.")
    rev = snapshot(db, j, body.reason, user, label=(body.label or "").strip() or None, body=body.body)
    db.commit()
    return {"id": str(rev.id) if rev else None, "skipped": rev is None}


@router.get("/journal/{entry_id}/revisions")
def revisions(slug: str, entry_id: uuid.UUID, user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> list[dict]:
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    rows = db.scalars(select(Revision).where(Revision.doc_table == "journal", Revision.doc_id == j.id)
                      .order_by(Revision.created_at.desc()))
    return [{"id": str(r.id), "version": r.version, "title": r.title, "reason": r.reason, "label": r.label,
             "words": r.meta.get("words", journal_words(r.body)), "created_at": r.created_at.isoformat()}
            for r in rows]


@router.post("/journal/{entry_id}/restore")
def restore(slug: str, entry_id: uuid.UUID, body: RestoreIn, user: User = Depends(current_user),
            db: Session = Depends(get_db)) -> EntryDetail:
    """Put a revision's text back. The text it replaces is kept as a revision first."""
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    r = db.get(Revision, body.revision_id)
    if r is None or r.doc_table != "journal" or r.doc_id != j.id:
        raise HTTPException(404, "No such revision of this entry.")
    snapshot(db, j, "restore", user, label=f"Before restoring {r.created_at:%Y-%m-%d %H:%M}")
    j.body = r.body
    j.title = r.title or j.title
    j.version += 1
    j.updated_by = user.id
    db.flush()
    refresh_source(db, world.id, "journal", j.id, j.body)
    db.commit()
    return entry_detail(db, world, j)


@router.get("/journal/{entry_id}/items")
def entry_items(slug: str, entry_id: uuid.UUID, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> list[dict]:
    """Open items linked to this entry (made from its passages, or stashed while writing it)."""
    from .companion import linked_items

    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    return linked_items(db, world, "journal", j.id)


# reading an entry's thread through the planning (docs/SPEC.md §14.2) --------------------------------------------


@router.get("/planning")
def planning(slug: str, entity: list[uuid.UUID] = Query(..., max_length=10), user: User = Depends(current_user),
             db: Session = Depends(get_db)) -> dict:
    """The items and decisions that name (any of their names, from the stored mentions) or are tagged with the given
    entries, open and closed, oldest first. Each says which of the entries it names and which it is tagged with, so
    the reading can mark "tagged" and keep only those about both for "With…". The journal part is read on the device."""
    world, _ = member_world(db, user, slug)
    wanted = set(entity)
    named: dict[tuple[str, uuid.UUID], set[uuid.UUID]] = {}
    for m in db.scalars(select(Mention).where(Mention.world_id == world.id, Mention.entity_id.in_(wanted),
                                              Mention.source_table.in_(("item", "decision")),
                                              Mention.kind.in_(("exact", "alias")))):
        named.setdefault((m.source_table, m.source_id), set()).add(m.entity_id)
    tagged: dict[tuple[str, uuid.UUID], set[uuid.UUID]] = {}
    for link in db.scalars(select(ItemLink).where(ItemLink.target_table == "entity", ItemLink.target_id.in_(wanted))):
        tagged.setdefault(("item", link.item_id), set()).add(link.target_id)
    for dl in db.scalars(select(DecisionLink).where(DecisionLink.entity_id.in_(wanted))):
        tagged.setdefault(("decision", dl.decision_id), set()).add(dl.entity_id)
    keys = set(named) | set(tagged)
    slugs = {p.id: p.slug for p in world.projects}

    def about(key: tuple[str, uuid.UUID]) -> dict:
        return {"names": sorted(str(x) for x in named.get(key, ())), "tagged": sorted(str(x) for x in tagged.get(key, ()))}

    item_ids = [k[1] for k in keys if k[0] == "item"]
    decision_ids = [k[1] for k in keys if k[0] == "decision"]
    items = [{"id": str(i.id), "kind": i.kind, "status": i.status, "title": i.title, "body": i.body,
              "closed_note": i.closed_note, "created_at": i.created_at.isoformat(),
              "project": slugs.get(i.project_id) if i.project_id else None, **about(("item", i.id))}
             for i in db.scalars(select(Item).where(Item.world_id == world.id, Item.id.in_(item_ids))
                                 .order_by(Item.created_at))] if item_ids else []
    decisions = [{"id": str(d.id), "decided_on": d.decided_on.isoformat(), "text": d.text,
                  "project": slugs.get(d.project_id) if d.project_id else None, **about(("decision", d.id))}
                 for d in db.scalars(select(Decision).where(Decision.world_id == world.id,
                                                            Decision.id.in_(decision_ids))
                                     .order_by(Decision.decided_on, Decision.created_at))] if decision_ids else []
    from .followups import counts_for

    counts = counts_for(db, [uuid.UUID(d["id"]) for d in decisions])
    for d in decisions:
        d["followups"] = counts.get(uuid.UUID(d["id"]))
    return {"items": items, "decisions": decisions}


# the note for next time (docs/SPEC.md §14.4) ---------------------------------------------------------------------


class NoteIn(BaseModel):
    note: str = Field(default="", max_length=2000)
    cursor: int = Field(default=0, ge=0)


@router.get("/journal/{entry_id}/session-note")
def get_note(slug: str, entry_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    n = db.get(JournalNote, (j.id, user.id))
    return {"note": n.note if n else "", "cursor": n.cursor if n else 0,
            "updated_at": n.updated_at.isoformat() if n and n.updated_at else None}


@router.put("/journal/{entry_id}/session-note")
def put_note(slug: str, entry_id: uuid.UUID, body: NoteIn, user: User = Depends(current_user),
             db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    n = db.get(JournalNote, (j.id, user.id))
    if n is None:
        n = JournalNote(journal_id=j.id, user_id=user.id)
        db.add(n)
    n.note = body.note.strip()
    n.cursor = body.cursor
    db.commit()
    db.refresh(n)
    return {"note": n.note, "cursor": n.cursor, "updated_at": n.updated_at.isoformat() if n.updated_at else None}


# since this was written (docs/SPEC.md §14.5) ----------------------------------------------------------------------


def _end_of(d: date) -> datetime:
    return datetime.combine(d, time.max, tzinfo=UTC)


def _later(*xs: datetime | None) -> datetime | None:
    xs2 = [x for x in xs if x is not None]
    return max(xs2) if xs2 else None


class Since:
    """What happened to the entries a journal entry names after its date, from links Quarry already keeps: decisions
    dated after it that name or are tagged with them; their facts and relationships recorded or changed since and
    their own pages changed since (each row once, on its later day); and later journal entries naming them. Rough:
    nothing removed is seen."""

    def __init__(self, db: Session, world: World) -> None:
        self.named: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        decision_named: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        for m in db.scalars(select(Mention).where(Mention.world_id == world.id, Mention.kind.in_(("exact", "alias")),
                                                  Mention.source_table.in_(("journal", "decision")))):
            (self.named if m.source_table == "journal" else decision_named)[m.source_id].add(m.entity_id)
        for dl in db.execute(select(DecisionLink).join(Decision, Decision.id == DecisionLink.decision_id)
                             .where(Decision.world_id == world.id)).scalars():
            decision_named[dl.decision_id].add(dl.entity_id)
        self.decisions = [(d, decision_named.get(d.id, set())) for d in
                          db.scalars(select(Decision).where(Decision.world_id == world.id)
                                     .order_by(Decision.decided_on.desc(), Decision.created_at.desc()))]
        self.facts = list(db.scalars(select(Fact).where(Fact.world_id == world.id)))
        self.rels = list(db.scalars(select(Relationship).where(Relationship.world_id == world.id)))
        self.entities = {e.id: e for e in db.scalars(select(Entity).where(Entity.world_id == world.id))}
        self.entries = {j.id: j for j in db.scalars(select(JournalEntry).where(JournalEntry.world_id == world.id))}

    def of(self, j: JournalEntry) -> dict:
        named = [e for e in sorted(self.named.get(j.id, set()), key=lambda x: self.entities[x].name.lower()
                                   if x in self.entities else "") if e in self.entities]
        after = _end_of(j.entry_date)
        out = []
        decisions_seen: set[uuid.UUID] = set()
        changes_seen: set[tuple[str, uuid.UUID]] = set()
        later_seen: set[uuid.UUID] = set()
        for eid in named:
            e = self.entities[eid]
            decisions = [{"id": str(d.id), "date": d.decided_on.isoformat(), "text": d.text}
                         for d, about in self.decisions if d.decided_on > j.entry_date and eid in about]
            decisions_seen |= {uuid.UUID(x["id"]) for x in decisions}
            changes = []
            for f in self.facts:
                when = _later(f.created_at, f.updated_at)
                if f.entity_id == eid and when is not None and when > after:
                    changes.append({"what": f"{f.label}{': ' + f.value if f.value else ''} recorded"
                                    if f.created_at > after else f"{f.label} changed", "date": when.date().isoformat()})
                    changes_seen.add(("fact", f.id))
            for r in self.rels:
                when = _later(r.created_at, r.updated_at)
                if eid in (r.a_id, r.b_id) and when is not None and when > after:
                    other = self.entities.get(r.b_id if r.a_id == eid else r.a_id)
                    changes.append({"what": f"relationship with {other.name if other else 'another entry'} "
                                    f"{'recorded' if r.created_at > after else 'changed'}",
                                    "date": when.date().isoformat()})
                    changes_seen.add(("rel", r.id))
            if e.updated_at is not None and e.updated_at > after:
                changes.append({"what": "page changed", "date": e.updated_at.date().isoformat()})
                changes_seen.add(("page", e.id))
            changes.sort(key=lambda c: c["date"], reverse=True)
            later = [x for x in self.entries.values()
                     if x.id != j.id and x.entry_date > j.entry_date and eid in self.named.get(x.id, set())]
            later_seen |= {x.id for x in later}
            out.append({"entity": {"id": str(e.id), "name": e.name, "kind": e.kind}, "decisions": decisions,
                        "changes": changes, "later": len(later)})
        edited = j.updated_at.date() if j.updated_at and j.updated_at.date() > j.entry_date else None
        return {"date": j.entry_date.isoformat(), "edited": edited.isoformat() if edited else None,
                "decisions": len(decisions_seen), "changes": len(changes_seen), "later": len(later_seen),
                "entities": [x for x in out if x["decisions"] or x["changes"] or x["later"]]}

    def counts(self, entries: list[JournalEntry]) -> dict[uuid.UUID, int]:
        """Per entry: its decisions and changes since (the dimmed "16 since" on the list)."""
        out = {}
        for j in entries:
            named = self.named.get(j.id, set())
            if not named:
                continue
            after = _end_of(j.entry_date)
            n = sum(1 for d, about in self.decisions if d.decided_on > j.entry_date and about & named)
            n += sum(1 for f in self.facts if f.entity_id in named and (_later(f.created_at, f.updated_at) or after) > after)
            n += sum(1 for r in self.rels if (r.a_id in named or r.b_id in named)
                     and (_later(r.created_at, r.updated_at) or after) > after)
            n += sum(1 for eid in named if eid in self.entities and self.entities[eid].updated_at
                     and self.entities[eid].updated_at > after)
            if n:
                out[j.id] = n
        return out


@router.get("/journal/{entry_id}/since")
def since(slug: str, entry_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    world, _ = member_world(db, user, slug)
    j = _entry(db, world, entry_id)
    return Since(db, world).of(j)
