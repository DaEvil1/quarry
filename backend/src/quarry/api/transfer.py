"""Export a world as a folder of Markdown files (zipped), and restore such a zip as a new world.

The export is meant to be read without Quarry: plain Markdown with YAML frontmatter, one file per chapter, bible
entry, journal entry and item, plus Decisions.md and a compiled manuscript.md per project. Restore reads exactly
that layout back (the compiled manuscript is ignored). The full revision history stays in the database; an export
carries the texts as they are now, and under History/ a day-by-day sample of how they got there.

    <world>/world.md                                  name, slug, words marked "not a typo", relationship types
                                                      (with has_role), the per-label switches (fact_labels), the
                                                      one-at-a-time roles (roles), the unit of time (time_unit,
                                                      time_units), the premise, the chart (chart: its settings, and each pin
                                                      with its place and container ids)
    <world>/Bible/<Kind>/<Name>.md                    id, name, kind, aliases, project (its level; null for the
                                                      world), gender (when set), also (the kinds it is as well), an event's when (a chapter id, a
                                                      time, or "outside"), an era's colour, an event's tellings
                                                      (chapter and passage) and notes in the Journal (journal and
                                                      passage); facts and relationships with planned_in (a journal
                                                      id) and planned_evidence beside established_in and evidence,
                                                      and follows (the decisions they follow, by id) with dropped
                                                      (decision id: date) for one dropped by hand;
                                                      the notes
    <world>/Journal/<date> <title> (<id>).md          id, date, title, project; for a plan (docs/SPEC.md §18.5)
                                                      plan: true and chapters (the ids of the chapters it is for)
    <world>/Decisions.md                              one line per decision, its follow-ups as indented lines under
                                                      it (to do, done, dropped), worked out for the reader; only
                                                      the dropped ones whose row is gone are read back
    <world>/Planning/<status>/<date> <text> (<id>).md items for the whole world; `from:` the chapter or journal entry
                                                      an item came from (by id), with `passage:`
    <world>/Projects/<Name>/project.md                name, slug, kind, position, statuses (in order), gap_chapters,
                                                      byline (when it has one, docs/SPEC.md §19)
    <world>/Projects/<Name>/Manuscript/<NN> <Title>.md id, title, state, position, pov, summary, status, time (at,
                                                      end, label, approx, or "outside"), told_as
    <world>/Projects/<Name>/Experiments/<Title> (<id>).md  drafts: item and position among the item's drafts
    <world>/Projects/<Name>/Salvage/<Title> (<id>).md retired chapters, with their harvest notes
    <world>/Projects/<Name>/Cuts/<date> <source title> (<id>).md   the cuts bin: id, chapter, chapter_title, cut_at,
                                                      put_back_at, put_back_to, before, after; the cut text
    <world>/Projects/<Name>/Planning/<status>/...     items for the project
    <world>/Projects/<Name>/manuscript.md             the current chapters in order (not read back)
    <world>/History/<Project>/<Title> (<id8>)/<at>.md dated earlier versions (docs/SPEC.md §20): chapter (or journal),
    <world>/History/Journal/<date> <title> (<id8>)/…  at, reason, label, title; the text. The export writes each
                                                      chapter's and journal entry's last revision of every day (UTC)
                                                      and every labelled checkpoint; Restore makes them revisions on
                                                      their dates, counted in the word history on their days
    <world>/Pictures/<name>-<id8>.<ext>               each picture's full file (docs/SPEC.md §17.6), stored without
                                                      being compressed again; world.md lists them (pictures: file
                                                      and name), an entry's frontmatter has its gallery (pictures:
                                                      file and caption, the main picture first), and a picture line
                                                      in any .md file links its picture by a path relative to that
                                                      file. Restore makes a picture of every JPEG, PNG and WebP under
                                                      Pictures/ and turns an image link on a line of its own that
                                                      points at one of them into a picture line.
"""

from __future__ import annotations

import math
import os
import posixpath
import re
import tempfile
import uuid
import zipfile
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime
from urllib.parse import unquote

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import refresh_world
from ..wordhistory import word_changes
from .followups import state_of, what_of
from ..models import (
    GENDERS,
    Revision,
    STARTING_STATUSES,
    Chapter,
    ChapterPlan,
    ChapterStatus,
    ChartPin,
    Cut,
    Decision,
    DecisionFollowup,
    DecisionLink,
    Entity,
    EntityPicture,
    ExperimentRange,
    Fact,
    FactLabel,
    HarvestNote,
    Item,
    ItemLink,
    JournalEntry,
    NameIgnore,
    Picture,
    PictureFile,
    Presence,
    Project,
    RelationType,
    Relationship,
    Role,
    Telling,
    User,
    World,
    WorldMember,
)
from ..margin import PICTURE_RE, without_margin_notes
from ..pictures import MAX_BYTES as MAX_PICTURE, PictureError, file_name, make, name_from_file, store
from .manuscript import snapshot
from ..vocabulary import STARTING_TYPES, place_new_types
from .chart import SHAPES as CHART_SHAPES
from .world import clean_role, has_role_label, seed_relation_types
from .deps import current_user
from .pictures import gallery_of
from .worlds import WorldOut, _unique, _world_out, clean_byline, member_world, slugify

router = APIRouter(prefix="/api/worlds")

FORMAT = 1
KIND_FOLDERS = {"character": "Characters", "place": "Places", "faction": "Factions", "culture": "Cultures",
                "species": "Species", "event": "Events", "object": "Objects", "term": "Terms", "other": "Other"}
# the zip is kept on disk and read a file at a time (docs/SPEC.md §17.6): up to 1 GB with its pictures, the .md files
# together at most 200 MB unpacked, each picture at most 25 MB, read no further than that whatever the zip claims
MAX_UPLOAD = 1024 * 1024 * 1024
MAX_UNPACKED = 200 * 1024 * 1024
PICTURE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
# a dated earlier version (docs/SPEC.md §20): read one at a time, apart from the 200 MB of the other .md files
MAX_HISTORY_FILE = 10 * 1024 * 1024
REVISION_FILE_REASONS = ("autosnap", "checkpoint", "start")
# an image link on a line of its own: ![caption](path), the path maybe in <…> (or, leniently, with plain spaces)
IMAGE_LINE_RE = re.compile(r"^([ \t]*)!\[([^\]\n]*)\]\((<[^>\n]+>|[^)\n]+)\)[ \t]*$", re.M)
DECISION_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2})(?: · \[([^\]]*)\])? (.*?)\s*<!-- (.*?) -->\s*$")
# a decision's follow-up under its line (docs/SPEC.md §16.6); "<!-- row -->" marks one whose row is in the export
FOLLOWUP_RE = re.compile(r"^\s+- (to do|done|dropped)(?: (\d{4}-\d{2}-\d{2}))?: (.*?)\s*(<!-- row -->)?\s*$")


def _safe(name: str, limit: int = 80) -> str:
    """A file or folder name that works on every system."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", name)
    name = " ".join(name.split()).strip(" .")[:limit].rstrip(" .")
    return name or "untitled"


# libyaml when it is there (it is in the image): a world of thousands of entries is thousands of front matters, and the
# pure-Python parser and emitter took most of a minute for them
YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
YAML_DUMPER = getattr(yaml, "CSafeDumper", yaml.SafeDumper)


def _doc(meta: dict, body: str) -> str:
    return "---\n" + yaml.dump(meta, Dumper=YAML_DUMPER, allow_unicode=True, sort_keys=False) + "---\n\n" + body


def _parse(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    meta = yaml.load(text[4:end], Loader=YAML_LOADER) or {}
    body = text[end + 5:]
    if body.startswith("\n"):
        body = body[1:]
    return (meta if isinstance(meta, dict) else {}), body


def _gap(v) -> int:  # type: ignore[no-untyped-def]
    """A project's gap length from project.md: 5 when missing (an export from before phase 11) or not a number."""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 5
    return n if 1 <= n <= 999 else 5


def _bound_meta(x) -> dict:  # type: ignore[no-untyped-def]
    """A fact's or relationship's time bounds and outside time in its frontmatter (only those set)."""
    out: dict = {}
    if x.outside_time:
        out["outside_time"] = True
    for side in ("from", "until"):
        t = getattr(x, f"{side}_time")
        if t is not None:
            out[f"{side}_time"] = float(t)
            if getattr(x, f"{side}_approx"):
                out[f"{side}_approx"] = True
    return out


def _num(v) -> float | None:  # type: ignore[no-untyped-def]
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def _bounds_in(d: dict) -> dict:
    """Time bounds and outside time read back from a fact's or relationship's frontmatter."""
    if d.get("outside_time") is True:
        return {"outside_time": True}
    return {"outside_time": False, "from_time": _num(d.get("from_time")), "from_approx": d.get("from_approx") is True,
            "until_time": _num(d.get("until_time")), "until_approx": d.get("until_approx") is True}


def _planned_meta(x) -> dict:  # type: ignore[no-untyped-def]
    """Where a fact or relationship was planned (docs/SPEC.md §14.1.2), only when it was."""
    out: dict = {}
    if x.planned_in_journal_id:
        out["planned_in"] = str(x.planned_in_journal_id)
    if x.planned_evidence:
        out["planned_evidence"] = x.planned_evidence
    return out


def _time_in(meta: dict) -> dict:
    """A chapter's time and mark read back from its frontmatter."""
    t = meta.get("time")
    out: dict = {"told_as": meta.get("told_as") if meta.get("told_as") in ("flashback", "tale") else None}
    if t == "outside":
        out["outside_time"] = True
    elif isinstance(t, dict) and _num(t.get("at")) is not None:
        out |= {"time_at": _num(t.get("at")), "time_end": _num(t.get("end")),
                "time_label": (" ".join(str(t.get("label") or "").split()) or None),
                "time_approx": t.get("approx") is True}
    return out


def _spans_in(d: dict, chapter) -> dict:  # type: ignore[no-untyped-def]
    """A span read back: each side a chapter (relinked by id) or a time; outside time has none."""
    b = _bounds_in(d)
    if b["outside_time"]:
        return {"outside_time": True, "from_approx": False, "until_approx": False}
    out = {**b}
    for side in ("from", "until"):
        ch = chapter(d.get(side))
        out[f"{side}_chapter_id"] = ch if out[f"{side}_time"] is None else None
    return out


def _iso(v: datetime | date | None) -> str | None:
    return v.isoformat() if v is not None else None


def _when(v) -> datetime | None:  # type: ignore[no-untyped-def]
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day, tzinfo=UTC)
    d = datetime.fromisoformat(str(v))
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _day(v) -> date | None:  # type: ignore[no-untyped-def]
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def followup_lines(db: Session, d: Decision) -> list[str]:
    """A decision's follow-ups under its line in Decisions.md, worked out for the reader (docs/SPEC.md §16.6):
    `  - to do: … (planned fact)`, `  - done: … (task, accepted)`, `  - dropped 2026-10-22: …`. A dropped one whose row
    is still in the export says so (`<!-- row -->`): only the others are read back as follow-ups with no row."""
    fus = list(db.scalars(select(DecisionFollowup).where(DecisionFollowup.decision_id == d.id)
                          .order_by(DecisionFollowup.created_at, DecisionFollowup.id)))
    if not fus:
        return []
    facts = {f.id: f for f in db.scalars(select(Fact).where(Fact.id.in_([x.fact_id for x in fus if x.fact_id])))}
    rels = {r.id: r for r in db.scalars(select(Relationship).where(
        Relationship.id.in_([x.relationship_id for x in fus if x.relationship_id])))}
    items = {i.id: i for i in db.scalars(select(Item).where(Item.id.in_([x.item_id for x in fus if x.item_id])))}
    out: list[tuple[int, str]] = []
    for fu in fus:
        row = facts.get(fu.fact_id) or rels.get(fu.relationship_id)
        item = items.get(fu.item_id)
        state = state_of(fu, row.standing if row else None, item.status if item else None)
        what = fu.what
        if item is not None:
            what = f"{what[len('task: '):] if what.startswith('task: ') else what} (task, {item.status})"
        elif row is not None:
            what = f"{what} ({row.standing} {'fact' if fu.fact_id else 'relationship'})"
        if state == "dropped":
            when = fu.dropped_on or (item.closed_at.date() if item is not None and item.closed_at else None)
            mark = " <!-- row -->" if row is not None or item is not None else ""
            out.append((2, f"  - dropped{' ' + when.isoformat() if when else ''}: {what}{mark}"))
        else:
            out.append((0 if state == "todo" else 1, f"  - {'to do' if state == 'todo' else 'done'}: {what}"))
    return [line for _, line in sorted(out, key=lambda x: x[0])]


# export --------------------------------------------------------------------------------------------------------


@router.get("/{slug}/export")
def export_world(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> FileResponse:
    world, _ = member_world(db, user, slug)
    root = _safe(world.slug)
    files: dict[str, str] = {}
    projects = {p.id: p for p in world.projects}
    project_dir = {p.id: f"{root}/Projects/{_safe(p.name)}" for p in world.projects}
    entities = list(db.scalars(select(Entity).where(Entity.world_id == world.id).order_by(Entity.name)))
    names = {e.id: e.name for e in entities}

    ignored = list(db.scalars(select(NameIgnore.token).where(NameIgnore.world_id == world.id).order_by(NameIgnore.token)))
    types = list(db.scalars(select(RelationType).where(RelationType.world_id == world.id).order_by(RelationType.position)))
    type_by_id = {t.id: t for t in types}
    switches = list(db.scalars(select(FactLabel).where(FactLabel.world_id == world.id)
                               .order_by(FactLabel.kind, FactLabel.label)))
    roles = list(db.scalars(select(Role).where(Role.world_id == world.id).order_by(Role.role)))
    pins = list(db.scalars(select(ChartPin).where(ChartPin.world_id == world.id).order_by(ChartPin.updated_at)))
    pictures = list(db.scalars(select(Picture).where(Picture.world_id == world.id)
                               .order_by(Picture.created_at, Picture.name)))
    picture_file = {str(p.id): f"Pictures/{file_name(p)}" for p in pictures}
    files[f"{root}/world.md"] = _doc({
        "quarry_export": FORMAT, "name": world.name, "slug": world.slug,
        "exported_at": datetime.now(UTC).isoformat(), "ignored_words": ignored,
        "relation_types": [{"a": t.a_kind, "b": t.b_kind, "label": t.label, "reverse": t.reverse_label,
                            "has_role": t.has_role} for t in types],
        "fact_labels": [{"kind": r.kind, "label": r.label, "several": r.several, "expected": r.expected,
                         "asked": r.asked} for r in switches],
        "roles": [{"role": r.role, "one_at_a_time": r.one_at_a_time} for r in roles],
        "time_unit": world.time_unit, "time_units": world.time_units, "premise": world.premise,
        "chart": {"settings": {"shapes": dict((world.chart or {}).get("shapes") or {})},
                  "pins": [{"place": str(p.place_id), "container": str(p.container_id) if p.container_id else None,
                            "x": p.x, "y": p.y} for p in pins]},
        "pictures": [{"file": picture_file[str(p.id)], "name": p.name} for p in pictures]}, "")

    # follow-ups (docs/SPEC.md §16.6): each row says which decisions it follows, and when one was dropped by hand
    fus = list(db.scalars(select(DecisionFollowup).join(Decision, Decision.id == DecisionFollowup.decision_id)
                          .where(Decision.world_id == world.id).order_by(DecisionFollowup.created_at)))
    follows: dict[uuid.UUID, list[DecisionFollowup]] = defaultdict(list)
    for fu in fus:
        row = fu.fact_id or fu.relationship_id or fu.item_id
        if row:
            follows[row].append(fu)

    def follows_meta(row_id: uuid.UUID) -> dict:
        mine = follows.get(row_id)
        if not mine:
            return {}
        out: dict = {"follows": [str(fu.decision_id) for fu in mine]}
        dropped = {str(fu.decision_id): fu.dropped_on.isoformat() for fu in mine if fu.dropped_on}
        if dropped:
            out["dropped"] = dropped
        return out

    facts: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for f in db.scalars(select(Fact).where(Fact.world_id == world.id).order_by(Fact.entity_id, Fact.position)):
        facts[f.entity_id].append({"label": f.label, "value": f.value, "standing": f.standing,
                                   "evidence": f.evidence, "note": f.note,
                                   "established_in": str(f.established_in_chapter_id) if f.established_in_chapter_id else None,
                                   "from": str(f.from_chapter_id) if f.from_chapter_id else None,
                                   "until": str(f.until_chapter_id) if f.until_chapter_id else None,
                                   **_bound_meta(f), **_planned_meta(f), **follows_meta(f.id)})
    rels: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for r in db.scalars(select(Relationship).where(Relationship.world_id == world.id).order_by(Relationship.created_at)):
        t = type_by_id[r.type_id]
        rels[r.a_id].append({"type": t.label, "type_kinds": [t.a_kind, t.b_kind], "to": str(r.b_id),
                             "to_name": names.get(r.b_id), "standing": r.standing, "evidence": r.evidence,
                             "note": r.note,
                             "established_in": str(r.established_in_chapter_id) if r.established_in_chapter_id else None,
                             "from": str(r.from_chapter_id) if r.from_chapter_id else None,
                             "until": str(r.until_chapter_id) if r.until_chapter_id else None})
        if r.role:
            rels[r.a_id][-1]["role"] = r.role
        rels[r.a_id][-1].update(_bound_meta(r))
        rels[r.a_id][-1].update(_planned_meta(r))
        rels[r.a_id][-1].update(follows_meta(r.id))

    tellings: dict[uuid.UUID, list[dict]] = defaultdict(list)
    event_notes: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for t in db.scalars(select(Telling).where(Telling.world_id == world.id).order_by(Telling.created_at)):
        if t.journal_id:
            event_notes[t.event_id].append({"journal": str(t.journal_id), "passage": t.passage})
        else:
            tellings[t.event_id].append({"chapter": str(t.chapter_id) if t.chapter_id else None, "passage": t.passage})
    presence: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for p in db.scalars(select(Presence).where(Presence.world_id == world.id).order_by(Presence.created_at)):
        presence[p.entity_id].append({"chapter": str(p.chapter_id), "place": str(p.place_id),
                                      "place_name": names.get(p.place_id), "note": p.note})

    for e in entities:
        meta = {"id": str(e.id), "name": e.name, "kind": e.kind, "aliases": list(e.aliases), "summary": e.summary,
                "match_case": e.match_case, "first_name_alias": e.first_name_alias,
                "exclusions": list(e.exclusions), "project": projects[e.project_id].slug if e.project_id else None}
        if e.gender:
            meta["gender"] = e.gender
        if e.also_kinds:
            meta["also"] = list(e.also_kinds)
        if facts.get(e.id):
            meta["facts"] = facts[e.id]
        if rels.get(e.id):
            meta["relationships"] = rels[e.id]
        if presence.get(e.id):
            meta["is_at"] = presence[e.id]
        # an event's when (docs/SPEC.md §13.2.1), kept whatever the kind is now, an era's colour and the tellings
        if e.outside_time:
            meta["when"] = "outside"
        elif e.time_chapter_id:
            meta["when"] = str(e.time_chapter_id)
        elif e.time_at is not None:
            meta["when"] = {"at": float(e.time_at), "end": float(e.time_end) if e.time_end is not None else None,
                            "label": e.time_label, "approx": e.time_approx}
        if e.era_colour:
            meta["colour"] = e.era_colour
        if tellings.get(e.id):
            meta["tellings"] = tellings[e.id]
        if event_notes.get(e.id):
            meta["notes"] = event_notes[e.id]
        gallery = gallery_of(db, e.id)
        if gallery:
            meta["pictures"] = [{"file": picture_file[g["id"]], "caption": g["caption"]} for g in gallery]
        files[f"{root}/Bible/{KIND_FOLDERS[e.kind]}/{_safe(e.name)}.md"] = _doc(meta, e.body)

    plan_for: dict[uuid.UUID, list[str]] = defaultdict(list)
    for jid, cid in db.execute(select(ChapterPlan.journal_id, ChapterPlan.chapter_id)
                               .join(JournalEntry, JournalEntry.id == ChapterPlan.journal_id)
                               .where(JournalEntry.world_id == world.id).order_by(ChapterPlan.created_at)).all():
        plan_for[jid].append(str(cid))
    for j in db.scalars(select(JournalEntry).where(JournalEntry.world_id == world.id).order_by(JournalEntry.entry_date)):
        title = j.title or j.body.split("\n", 1)[0][:40]
        jmeta = {"id": str(j.id), "date": j.entry_date.isoformat(), "title": j.title,
                 "project": projects[j.project_id].slug if j.project_id else None}
        if j.is_plan:
            # a plan and the chapters it is for (docs/SPEC.md §18.5): current, drafts or retired
            jmeta |= {"plan": True, "chapters": plan_for.get(j.id, [])}
        files[f"{root}/Journal/{j.entry_date} {_safe(title, 50)} ({str(j.id)[:8]}).md"] = _doc(jmeta, j.body)

    lines = ["# Decisions", ""]
    decision_tags: dict[uuid.UUID, list[str]] = defaultdict(list)
    for did, eid in db.execute(select(DecisionLink.decision_id, DecisionLink.entity_id)
                               .join(Decision, Decision.id == DecisionLink.decision_id)
                               .where(Decision.world_id == world.id)).all():
        decision_tags[did].append(str(eid))
    for d in db.scalars(select(Decision).where(Decision.world_id == world.id)
                        .order_by(Decision.decided_on, Decision.created_at)):
        proj = f" · [{projects[d.project_id].slug}]" if d.project_id else ""
        ids = f"id={d.id}" + (f" item={d.item_id}" if d.item_id else "") + (
            f" entities={','.join(sorted(decision_tags[d.id]))}" if decision_tags.get(d.id) else "")
        lines.append(f"- {d.decided_on.isoformat()}{proj} {d.text} <!-- {ids} -->")
        lines += followup_lines(db, d)
    files[f"{root}/Decisions.md"] = "\n".join(lines) + "\n"

    tags: dict[uuid.UUID, list[str]] = defaultdict(list)
    for item_id, target in db.execute(select(ItemLink.item_id, ItemLink.target_id).join(Item, Item.id == ItemLink.item_id)
                                      .where(Item.world_id == world.id, ItemLink.target_table == "entity")).all():
        if target in names:
            tags[item_id].append(names[target])
    origins: dict[uuid.UUID, dict] = {}
    # chapters an item is for besides where it came from: ticked when made from a plan (docs/SPEC.md §18.4)
    item_chapters: dict[uuid.UUID, list[str]] = defaultdict(list)
    for link in db.scalars(select(ItemLink).join(Item, Item.id == ItemLink.item_id)
                           .where(Item.world_id == world.id, ItemLink.target_table.in_(("chapter", "journal")))
                           .order_by(ItemLink.target_table)):
        # a journal entry wins over a chapter (sorted after it)
        if link.target_table == "chapter":
            item_chapters[link.item_id].append(str(link.target_id))
        origins[link.item_id] = {"from": {link.target_table: str(link.target_id)}, "passage": link.passage}
    ranges: dict[uuid.UUID, list[str]] = defaultdict(list)
    for r in db.scalars(select(ExperimentRange).join(Item, Item.id == ExperimentRange.item_id)
                        .where(Item.world_id == world.id).order_by(ExperimentRange.position)):
        ranges[r.item_id].append(str(r.chapter_id))
    for i in db.scalars(select(Item).where(Item.world_id == world.id).order_by(Item.created_at)):
        folder = project_dir[i.project_id] if i.project_id else root
        short = _safe(i.title or i.body.split("\n", 1)[0], 50)
        meta = {"id": str(i.id), "kind": i.kind, "status": i.status, "title": i.title,
                "project": projects[i.project_id].slug if i.project_id else None, "source": i.source,
                "created_at": _iso(i.created_at), "closed_at": _iso(i.closed_at), "closed_note": i.closed_note,
                "tags": sorted(tags.get(i.id, []))}
        meta.update(follows_meta(i.id))
        if i.id in origins:
            meta["from"] = origins[i.id]["from"]
            if origins[i.id]["passage"]:
                meta["passage"] = origins[i.id]["passage"]
            more = [c for c in item_chapters.get(i.id, []) if c != origins[i.id]["from"].get("chapter")]
            if more:
                meta["chapters"] = more
        # an experiment: the chapters it would replace, or where it adds (docs/SPEC.md §13.6.1)
        if i.kind == "experiment":
            if ranges.get(i.id):
                meta["replaces"] = ranges[i.id]
            if i.insert_at_chapter_id and i.insert_side:
                meta["insert"] = {i.insert_side: str(i.insert_at_chapter_id)}
        files[f"{folder}/Planning/{i.status}/{i.created_at:%Y-%m-%d} {short} ({str(i.id)[:8]}).md"] = _doc(meta, i.body)

    notes: dict[uuid.UUID, list[str]] = defaultdict(list)
    for n in db.scalars(select(HarvestNote).where(HarvestNote.world_id == world.id).order_by(HarvestNote.created_at)):
        notes[n.chapter_id].append(n.body)
    for p in world.projects:
        d = project_dir[p.id]
        statuses = list(db.scalars(select(ChapterStatus).where(ChapterStatus.project_id == p.id)
                                   .order_by(ChapterStatus.position, ChapterStatus.created_at)))
        status_label = {s.id: s.label for s in statuses}
        pmeta = {"name": p.name, "slug": p.slug, "kind": p.kind, "position": p.position,
                 "statuses": [s.label for s in statuses], "gap_chapters": p.gap_chapters}
        if p.byline:
            pmeta["byline"] = p.byline
        files[f"{d}/project.md"] = _doc(pmeta, "")
        chapters = list(db.scalars(select(Chapter).where(Chapter.project_id == p.id)
                                   .order_by(Chapter.position, Chapter.created_at)))
        # the byline under the title, in italics (docs/SPEC.md §19)
        compiled = [f"# {p.name}", "", *([f"*{p.byline}*", ""] if p.byline else [])]
        n = 0
        for ch in chapters:
            meta = {"id": str(ch.id), "title": ch.title, "state": ch.state, "position": ch.position,
                    "pov": names.get(ch.pov_entity_id) if ch.pov_entity_id else None,
                    "summary": ch.summary, "status": status_label.get(ch.status_id) if ch.status_id else None}
            if ch.outside_time:
                meta["time"] = "outside"
            elif ch.time_at is not None:
                meta["time"] = {"at": float(ch.time_at), "end": float(ch.time_end) if ch.time_end is not None else None,
                                "label": ch.time_label, "approx": ch.time_approx}
            if ch.told_as:
                meta["told_as"] = ch.told_as
            if ch.state == "current":
                n += 1
                path = f"{d}/Manuscript/{n:02d} {_safe(ch.title, 60)}.md"
                compiled += [f"## {ch.title}", "", without_margin_notes(ch.body).rstrip(), ""]
            elif ch.state == "experiment":
                meta |= {"item": str(ch.experiment_item_id) if ch.experiment_item_id else None}
                path = f"{d}/Experiments/{_safe(ch.title, 60)} ({str(ch.id)[:8]}).md"
            else:
                meta |= {"retired_at": _iso(ch.retired_at), "harvest_notes": notes.get(ch.id, [])}
                path = f"{d}/Salvage/{_safe(ch.title, 60)} ({str(ch.id)[:8]}).md"
            files[path] = _doc(meta, ch.body)
        files[f"{d}/manuscript.md"] = "\n".join(compiled) + "\n"
        for c in db.scalars(select(Cut).where(Cut.project_id == p.id).order_by(Cut.cut_at)):
            files[f"{d}/Cuts/{c.cut_at:%Y-%m-%d} {_safe(c.chapter_title, 50)} ({str(c.id)[:8]}).md"] = _doc(
                {"id": str(c.id), "chapter": str(c.chapter_id) if c.chapter_id else None,
                 "chapter_title": c.chapter_title, "cut_at": _iso(c.cut_at), "put_back_at": _iso(c.put_back_at),
                 "put_back_to": str(c.put_back_to) if c.put_back_to else None, "before": c.before,
                 "after": c.after}, c.body)

    # the documents whose dated versions go under History/ (docs/SPEC.md §20)
    history_docs: list[tuple[str, uuid.UUID, str]] = []
    for p in world.projects:
        for c in db.scalars(select(Chapter).where(Chapter.project_id == p.id).order_by(Chapter.position, Chapter.created_at)):
            history_docs.append(("chapter", c.id, f"{_safe(p.name)}/{_safe(c.title, 60)} ({str(c.id)[:8]})"))
    for j in db.scalars(select(JournalEntry).where(JournalEntry.world_id == world.id).order_by(JournalEntry.entry_date)):
        history_docs.append(("journal", j.id, f"Journal/{j.entry_date} {_safe(j.title or j.body.split(chr(10), 1)[0][:40], 50)} ({str(j.id)[:8]})"))

    # written to a file on disk, a picture at a time, and sent from there: never held in memory whole
    fd, tmp = tempfile.mkstemp(prefix="quarry-export-", suffix=".zip")
    try:
        with os.fdopen(fd, "wb") as out, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for path, text in files.items():
                z.writestr(path, _export_links(path, text, root, picture_file))
            # dated earlier versions (docs/SPEC.md §20), a document at a time
            for path, text in _history_files(db, root, history_docs):
                z.writestr(path, _export_links(path, text, root, picture_file))
            for p in pictures:
                data = db.scalar(select(PictureFile.data).where(PictureFile.picture_id == p.id,
                                                                 PictureFile.kind == "full"))
                if data is not None:
                    z.writestr(f"{root}/{picture_file[str(p.id)]}", bytes(data), compress_type=zipfile.ZIP_STORED)
                del data
    except BaseException:
        os.unlink(tmp)
        raise
    name = f"quarry-{world.slug}-{date.today().isoformat()}.zip"
    return FileResponse(tmp, media_type="application/zip", filename=name, background=BackgroundTask(os.unlink, tmp))


def _export_links(path: str, text: str, root: str, picture_file: dict[str, str]) -> str:
    """Picture lines link their picture by its path relative to the file (docs/SPEC.md §17.6), so the export shows its
    pictures in any Markdown reader. A picture that is gone stays `picture:<id>`."""
    if "picture:" not in text:
        return text
    here = posixpath.dirname(path)

    def link(m: re.Match) -> str:
        target = picture_file.get(m.group(2))
        if target is None:
            return m.group(0)
        return m.group(0).replace(f"picture:{m.group(2)}", posixpath.relpath(f"{root}/{target}", here), 1)

    return PICTURE_RE.sub(link, text)


# restore -------------------------------------------------------------------------------------------------------


def _zip_path(name: str) -> str | None:
    """A file's path in the zip with forward slashes, or None for a folder or a path that climbs out."""
    name = name.replace("\\", "/")
    if name.endswith("/") or ".." in name.split("/") or name.startswith("/"):
        return None
    return name


def _read_capped(z: zipfile.ZipFile, info: zipfile.ZipInfo, cap: int) -> bytes | None:
    """A file of the zip, or None when it is longer than `cap` (read no further, whatever the zip claims)."""
    try:
        with z.open(info) as f:
            data = f.read(cap + 1)
    except (zipfile.BadZipFile, OSError, NotImplementedError, RuntimeError):
        return None
    return None if len(data) > cap else data


def read_zip(z: zipfile.ZipFile) -> tuple[dict[str, str], dict[str, Callable[[], bytes | None]]]:
    """The .md files of a zip (path -> text), read one at a time and no further than 200 MB together, and its other
    files as loaders, read only when asked: a loader gives None for a file over 25 MB."""
    texts: dict[str, str] = {}
    others: dict[str, Callable[[], bytes | None]] = {}
    left = MAX_UNPACKED
    for info in z.infolist():
        name = _zip_path(info.filename)
        if name is None:
            continue
        if not name.endswith(".md"):
            others[name] = lambda i=info: _read_capped(z, i, MAX_PICTURE)  # type: ignore[misc]
            continue
        if name.count("/") >= 2 and name.split("/")[1] == "History":
            # dated earlier versions are read when their turn comes, one at a time (docs/SPEC.md §20)
            others[name] = lambda i=info: _read_capped(z, i, MAX_HISTORY_FILE)  # type: ignore[misc]
            continue
        data = _read_capped(z, info, left) if info.file_size <= left else None
        if data is None:
            raise HTTPException(422, "That zip is too big to restore.")
        left -= len(data)
        texts[name] = data.decode("utf-8", errors="replace")
    return texts, others


class RestoreOut(WorldOut):
    # the pictures made, and the files under Pictures/ that weren't taken (docs/SPEC.md §17.6)
    pictures: int = 0
    skipped: list[str] = []
    # the dated earlier versions made into revisions (docs/SPEC.md §20)
    history: int = 0


@router.post("/restore", status_code=201)
def restore_world(file: UploadFile = File(...), user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> RestoreOut:
    """Make a new world from an export zip. Ids are new; links between the files are kept. Not async: the upload is
    on disk already (FastAPI keeps it there), and the zip is read a file at a time in the thread pool."""
    f = file.file
    f.seek(0, os.SEEK_END)
    if f.tell() > MAX_UPLOAD:
        raise HTTPException(422, "That zip is too big to restore.")
    f.seek(0)
    try:
        z = zipfile.ZipFile(f)
    except zipfile.BadZipFile:
        raise HTTPException(422, "That file is not a zip.") from None
    report: dict = {}
    with z:
        texts, others = read_zip(z)
        world = restore_files(db, user, texts, others, report)
        db.commit()
    db.refresh(world)
    return RestoreOut(**_world_out(world, "owner").model_dump(), pictures=report.get("pictures", 0),
                      skipped=report.get("skipped", []), history=report.get("history", 0))


def _restore_pictures(db: Session, user: User, world: World, root: str, wmeta: dict,
                      others: dict[str, Callable[[], bytes | None]], report: dict) -> dict[str, uuid.UUID]:
    """Every JPEG, PNG and WebP under <world>/Pictures/ (at any depth) made into a picture, one at a time and flushed
    as it goes, named as world.md says or else from its file name. Returns the new pictures by their path in the
    zip; `report` gets how many and the files skipped."""
    named: dict[str, str] = {}
    for p in wmeta.get("pictures") or []:
        if isinstance(p, dict) and p.get("file") and str(p.get("name") or "").strip():
            named[posixpath.normpath(f"{root}/{p['file']}")] = " ".join(str(p["name"]).split())[:200]
    made: dict[str, uuid.UUID] = {}
    skipped: list[str] = []
    for path in sorted(others):
        if not path.startswith(f"{root}/Pictures/"):
            continue
        rel = path[len(root) + 1:]
        data = others[path]() if path.lower().endswith(PICTURE_EXTENSIONS) else None
        try:
            picture = make(data) if data is not None else None
        except PictureError:
            picture = None
        del data
        if picture is None:
            skipped.append(rel)
            continue
        made[path] = store(db, world.id, user.id, picture, named.get(path) or name_from_file(path)).id
        del picture
    report["pictures"] = len(made)
    report["skipped"] = skipped
    return made


def _restore_links(path: str, text: str, root: str, made: dict[str, uuid.UUID]) -> str:
    """An image link on a line of its own whose path, read relative to its file (or else to the world folder), is a
    picture in the zip becomes a picture line. Paths with %20 or in <…> are read too; links to web addresses or to
    files that aren't in the zip stay as written."""
    if "](" not in text:
        return text
    here = posixpath.dirname(path)

    def link(m: re.Match) -> str:
        target = m.group(3).strip()
        if target.startswith("<"):
            target = target[1:-1]
        if "://" in target or target.startswith(("picture:", "data:", "/", "#")):
            return m.group(0)
        target = unquote(target)
        for base in (here, root):
            pid = made.get(posixpath.normpath(posixpath.join(base, target)))
            if pid is not None:
                return f"{m.group(1)}![{m.group(2)}](picture:{pid})"
        return m.group(0)

    return IMAGE_LINE_RE.sub(link, text)


def _at(v) -> datetime | None:  # type: ignore[no-untyped-def]
    """A dated version's `at`: a timestamp (UTC when it says no zone), or a bare date meaning 12:00 UTC that day."""
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day, 12, tzinfo=UTC)
    try:
        text = str(v or "").strip()
        if len(text) == 10:
            return datetime.fromisoformat(text).replace(hour=12, tzinfo=UTC)
        d = datetime.fromisoformat(text)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _restore_history(db: Session, user: User, root: str, files: dict[str, str],
                     others: dict[str, Callable[[], bytes | None]], chapter_by_old: dict[str, uuid.UUID],
                     journal_by_old: dict[str, uuid.UUID], report: dict) -> dict[tuple[str, uuid.UUID], str]:
    """Each chapter's and journal entry's dated earlier versions, as revisions on their dates, in order. The first
    counts its words as written on its day (from empty) unless it is a start; each later one what changed since the
    one before. Files are read twice, one at a time: first for when and whose, then for the text, so a long history
    never sits in memory whole. Returns each document's last text, to compare with its current one."""
    from .journal import journal_words
    from .manuscript import words

    prefix = f"{root}/History/"
    loaders: dict[str, Callable[[], bytes | None]] = {p: f for p, f in others.items() if p.startswith(prefix) and p.endswith(".md")}
    for p, text in files.items():
        if p.startswith(prefix) and p.endswith(".md"):
            loaders[p] = lambda t=text: t.encode("utf-8")  # type: ignore[misc]

    def read(path: str) -> tuple[dict, str] | None:
        data = loaders[path]()
        if data is None:
            return None
        return _parse(data.decode("utf-8", errors="replace"))

    found: dict[tuple[str, uuid.UUID], list[tuple[datetime, str]]] = defaultdict(list)
    skipped = 0
    for path in sorted(loaders):
        parsed = read(path)
        if parsed is None:
            skipped += 1
            continue
        meta, _ = parsed
        at = _at(meta.get("at"))
        key: tuple[str, uuid.UUID] | None = None
        if meta.get("chapter") and str(meta["chapter"]) in chapter_by_old:
            key = ("chapter", chapter_by_old[str(meta["chapter"])])
        elif meta.get("journal") and str(meta["journal"]) in journal_by_old:
            key = ("journal", journal_by_old[str(meta["journal"])])
        if key is None or at is None:
            skipped += 1
            continue
        found[key].append((at, path))
    last: dict[tuple[str, uuid.UUID], str] = {}
    made = 0
    for (table, doc_id), versions in found.items():
        doc = db.get(Chapter if table == "chapter" else JournalEntry, doc_id)
        assert doc is not None
        previous: str | None = None
        for at, path in sorted(versions):
            parsed = read(path)
            if parsed is None:
                continue
            meta, body = parsed
            reason = str(meta.get("reason") or "autosnap")
            reason = reason if reason in REVISION_FILE_REASONS else "autosnap"
            added = removed = 0
            if reason != "start":
                added, removed = word_changes(previous or "", body)
            label = " ".join(str(meta.get("label") or "").split())[:200] or None
            title = " ".join(str(meta.get("title") or "").split())[:300] or (doc.title or "")
            info = ({"state": doc.state, "words": words(body)} if table == "chapter" else {"words": journal_words(body)})
            rev = Revision(doc_table=table, doc_id=doc_id, version=doc.version, title=title, body=body,
                           meta={**info, "added": added, "removed": removed}, reason=reason,
                           label=label if reason == "checkpoint" else None, created_by=user.id, created_at=at)
            db.add(rev)
            db.flush()
            db.expunge(rev)
            previous = body
            made += 1
        if previous is not None:
            last[(table, doc_id)] = previous
    report["history"] = made
    if skipped:
        report["history_skipped"] = skipped
    return last


def _history_files(db: Session, root: str, docs: list[tuple[str, uuid.UUID, str]]):  # type: ignore[no-untyped-def]
    """The dated versions an export carries (docs/SPEC.md §20): for each document, its last revision of every day it
    has revisions on (days in UTC) and every labelled checkpoint; never a conflict copy. Yields (path, text), one
    document's revisions read at a time."""
    for table, doc_id, folder in docs:
        rows = db.execute(select(Revision.created_at, Revision.body, Revision.reason, Revision.label, Revision.title)
                          .where(Revision.doc_table == table, Revision.doc_id == doc_id, Revision.reason != "conflict")
                          .order_by(Revision.created_at)).all()
        keep: dict[int, tuple] = {}
        last_of_day: dict[date, int] = {}
        for i, r in enumerate(rows):
            last_of_day[r.created_at.astimezone(UTC).date()] = i
            if r.label:
                keep[i] = r
        for i in last_of_day.values():
            keep[i] = rows[i]
        seen: set[str] = set()
        for i in sorted(keep):
            r = keep[i]
            at = r.created_at.astimezone(UTC)
            name = f"{at:%Y-%m-%d %H%M%S}"
            while name in seen:
                name += "+"
            seen.add(name)
            meta = {table: str(doc_id), "at": at.isoformat()}
            if r.reason in ("checkpoint", "start"):
                meta["reason"] = r.reason
            if r.label:
                meta["reason"] = "checkpoint"
                meta["label"] = r.label
            if r.title:
                meta["title"] = r.title
            yield f"{root}/History/{folder}/{name}.md", _doc(meta, r.body)
        del rows


def restore_files(db: Session, user: User, files: dict[str, str],
                  others: dict[str, Callable[[], bytes | None]] | None = None, report: dict | None = None) -> World:
    """Make a new world for `user` from the files of an export (path -> text) and its other files (path -> a loader of
    their bytes: the pictures). Flushed, not committed. `report` gets the pictures made and the files skipped."""
    report = {} if report is None else report
    world_files = [p for p in files if p.endswith("/world.md") and p.count("/") == 1]
    if len(world_files) != 1:
        raise HTTPException(422, "This is not a Quarry export (no world.md at the top).")
    root = world_files[0].rsplit("/", 1)[0]
    wmeta, _ = _parse(files[world_files[0]])
    if wmeta.get("quarry_export") != FORMAT:
        raise HTTPException(422, "This export comes from another version of Quarry.")

    def under(prefix: str) -> list[tuple[str, dict, str]]:
        out = []
        for path in sorted(files):
            if path.startswith(prefix):
                meta, body = _parse(files[path])
                out.append((path[len(prefix):], meta, body))
        return out

    name = " ".join(str(wmeta.get("name") or "Restored world").split())
    taken = set(db.scalars(select(World.slug)))
    world = World(name=name, slug=_unique(slugify(str(wmeta.get("slug") or name), "world"), taken),
                  time_unit=" ".join(str(wmeta.get("time_unit") or "year").split())[:40] or "year",
                  time_units=" ".join(str(wmeta.get("time_units") or "years").split())[:40] or "years",
                  premise=" ".join(str(wmeta.get("premise") or "").split())[:300] or None,
                  created_by=user.id, updated_by=user.id)
    db.add(world)
    db.flush()
    db.add(WorldMember(world_id=world.id, user_id=user.id, role="owner"))

    # the pictures first (docs/SPEC.md §17.6), then every text's image links to them become picture lines
    made = _restore_pictures(db, user, world, root, wmeta, others or {}, report)
    if made:
        files = {path: _restore_links(path, text, root, made) for path, text in files.items()}

    # projects, by their slug in the export
    # the relationship vocabulary: the export's, or the starting one for exports made before phase 6
    exported_types = wmeta.get("relation_types") or []
    type_by_key: dict[tuple[str, str, str], uuid.UUID] = {}
    if exported_types:
        # "has a role": the export's, or by label for an export from before phase 12 (as the migration did)
        with_roles = any(isinstance(t, dict) and "has_role" in t for t in exported_types)
        rows = []
        for i, t in enumerate(exported_types):
            label = str(t.get("label") or "linked to")
            rt = RelationType(world_id=world.id, a_kind=str(t.get("a") or "*"), b_kind=str(t.get("b") or "*"),
                              label=label, reverse_label=t.get("reverse"), position=i,
                              has_role=t.get("has_role") is True if with_roles else has_role_label(label))
            db.add(rt)
            rows.append(rt)
        # an export with no type touching species was made before the kind existed: it gets the species starting
        # types, each at the end of its pair (docs/SPEC.md §13.3)
        if not any("species" in (rt.a_kind, rt.b_kind) for rt in rows):
            wanted = [t for t in STARTING_TYPES if "species" in (t[0], t[1])]
            for (a, b, label, reverse), position in place_new_types(
                    [(rt.a_kind, rt.b_kind, rt.label, rt.reverse_label, rt.position) for rt in rows], wanted):
                for rt in rows:
                    if rt.position >= position:
                        rt.position += 1
                rt = RelationType(world_id=world.id, a_kind=a, b_kind=b, label=label, reverse_label=reverse,
                                  position=position, has_role=False)
                db.add(rt)
                rows.append(rt)
        db.flush()
        for rt in sorted(rows, key=lambda r: r.position):
            type_by_key.setdefault((rt.a_kind, rt.b_kind, rt.label), rt.id)
    else:
        seed_relation_types(db, world.id)
        db.flush()
        for rt in db.scalars(select(RelationType).where(RelationType.world_id == world.id)):
            type_by_key.setdefault((rt.a_kind, rt.b_kind, rt.label), rt.id)

    project_ids: dict[str, uuid.UUID] = {}
    project_dirs: dict[str, str] = {}
    # each project's statuses by label: the export's (in order), or the starting ones for exports made before phase 10
    status_ids: dict[uuid.UUID, dict[str, uuid.UUID]] = {}
    for rel, meta, _ in under(f"{root}/Projects/"):
        if rel.count("/") == 1 and rel.endswith("/project.md"):
            folder = rel.split("/", 1)[0]
            pslug = _unique(slugify(str(meta.get("slug") or meta.get("name") or folder), "project"),
                            set(project_ids))
            p = Project(world_id=world.id, name=str(meta.get("name") or folder), slug=pslug,
                        kind=meta.get("kind") if meta.get("kind") in ("novel", "novella", "short", "other") else "novel",
                        position=int(meta["position"]) if meta.get("position") is not None else len(project_ids),
                        gap_chapters=_gap(meta.get("gap_chapters")), byline=clean_byline(meta.get("byline")),
                        created_by=user.id,
                        updated_by=user.id)
            db.add(p)
            db.flush()
            project_ids[str(meta.get("slug") or pslug)] = p.id
            project_dirs[folder] = str(meta.get("slug") or pslug)
            labels = meta["statuses"] if isinstance(meta.get("statuses"), list) else list(STARTING_STATUSES)
            status_ids[p.id] = {}
            for label in labels:
                label = " ".join(str(label).split())[:100]
                if label and label not in status_ids[p.id]:
                    st = ChapterStatus(project_id=p.id, label=label, position=len(status_ids[p.id]))
                    db.add(st)
                    db.flush()
                    status_ids[p.id][label] = st.id

    def status_of(project_id: uuid.UUID, label) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
        """A status a chapter names that project.md doesn't list is added at the end."""
        label = " ".join(str(label or "").split())[:100]
        if not label:
            return None
        known = status_ids[project_id]
        if label not in known:
            st = ChapterStatus(project_id=project_id, label=label, position=len(known))
            db.add(st)
            db.flush()
            known[label] = st.id
        return known[label]

    def project_of(slug_or_none) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
        return project_ids.get(str(slug_or_none)) if slug_or_none else None

    # the bible
    entity_by_old: dict[str, uuid.UUID] = {}
    # facts and relationships point at chapters, so they are restored after the chapters
    world_model: list[tuple[Entity, dict]] = []
    entity_by_name: dict[str, uuid.UUID] = {}
    names_seen: set[str] = set()
    for rel, meta, body in under(f"{root}/Bible/"):
        kind = meta.get("kind") if meta.get("kind") in KIND_FOLDERS else "other"
        ename = " ".join(str(meta.get("name") or rel.rsplit("/", 1)[-1][:-3]).split())
        if ename.lower() in names_seen:
            continue
        names_seen.add(ename.lower())
        # the level: a project's slug in the export (a missing or unknown one, as before phase 11, is the world)
        level = project_of(meta.get("project")) if len(project_ids) > 1 else None
        # the id given here, so the entries are written in one go after the loop rather than one round trip each
        e = Entity(id=uuid.uuid4(), world_id=world.id, kind=kind, name=ename,
                   aliases=[str(a) for a in meta.get("aliases") or []],
                   body=body, summary=str(meta.get("summary") or ""), match_case=meta.get("match_case") is not False,
                   first_name_alias=meta.get("first_name_alias") is not False,
                   exclusions=[str(x) for x in meta.get("exclusions") or []], project_id=level,
                   gender=meta.get("gender") if meta.get("gender") in GENDERS else None,
                   # the kinds it is as well, in order (none in an export from before phase 13)
                   also_kinds=[k for i, k in enumerate(str(x) for x in (meta.get("also") or []))
                               if k in KIND_FOLDERS and k != kind and k not in [str(y) for y in (meta.get("also") or [])][:i]],
                   created_by=user.id, updated_by=user.id)
        db.add(e)
        entity_by_name[ename] = e.id
        if meta.get("id"):
            entity_by_old[str(meta["id"])] = e.id
        world_model.append((e, meta))
    db.flush()
    # galleries in order with their captions; a picture that isn't in the zip, or is named twice, is left out
    for e, meta in world_model:
        seen: list[uuid.UUID] = []
        for g in meta.get("pictures") or []:
            pid = made.get(posixpath.normpath(f"{root}/{g['file']}")) if isinstance(g, dict) and g.get("file") else None
            if pid is not None and pid not in seen:
                db.add(EntityPicture(entity_id=e.id, picture_id=pid, position=len(seen),
                                     caption=" ".join(str(g.get("caption") or "").split())))
                seen.append(pid)

    # items: the world's own Planning/ and each project's
    item_by_old: dict[str, uuid.UUID] = {}
    # experiments' ranges and places, relinked once the chapters exist
    item_ranges: list[tuple[Item, dict]] = []
    tags: list[ItemLink] = []
    # where items came from (a chapter or journal entry), relinked once those exist
    item_origins: list[tuple[Item, dict]] = []
    # tasks that follow decisions, linked once the decisions are made
    item_follows: list[tuple[Item, dict]] = []
    planning = [(None, rel, meta, body) for rel, meta, body in under(f"{root}/Planning/")]
    for folder, pslug in project_dirs.items():
        planning += [(pslug, rel, meta, body) for rel, meta, body in under(f"{root}/Projects/{folder}/Planning/")]
    for pslug, _rel, meta, body in planning:
        status = meta.get("status") if meta.get("status") in ("open", "accepted", "rejected", "harvested",
                                                               "deferred") else "open"
        kind = meta.get("kind") if meta.get("kind") in ("spark", "question", "task", "experiment") else "spark"
        i = Item(id=uuid.uuid4(), world_id=world.id, project_id=project_of(meta.get("project") or pslug), kind=kind,
                 title=meta.get("title"), body=body or "(empty)", status=status, source=meta.get("source"),
                 closed_at=_when(meta.get("closed_at")), closed_note=meta.get("closed_note"),
                 created_by=user.id, updated_by=user.id)
        if _when(meta.get("created_at")):
            i.created_at = _when(meta.get("created_at"))
        db.add(i)
        if meta.get("id"):
            item_by_old[str(meta["id"])] = i.id
        if meta.get("follows"):
            item_follows.append((i, meta))
        if kind == "experiment":
            item_ranges.append((i, meta))
        for tag in meta.get("tags") or []:
            if str(tag) in entity_by_name:
                tags.append(ItemLink(item_id=i.id, target_table="entity", target_id=entity_by_name[str(tag)]))
        if isinstance(meta.get("from"), dict):
            item_origins.append((i, meta))
    # the items first, then their tags
    db.flush()
    db.add_all(tags)

    # chapters: current, experiments, salvage
    chapter_by_old: dict[str, uuid.UUID] = {}
    restored: list[Chapter] = []
    pending_replaces: list[tuple[Chapter, str]] = []
    for folder, pslug in project_dirs.items():
        pid = project_ids[pslug]
        for sub, state in (("Manuscript", "current"), ("Experiments", "experiment"), ("Salvage", "retired")):
            for rel, meta, body in under(f"{root}/Projects/{folder}/{sub}/"):
                title = str(meta.get("title") or rel[:-3])
                pov = entity_by_name.get(str(meta.get("pov"))) if meta.get("pov") else None
                ch = Chapter(project_id=pid, title=title, body=body, state=state,
                             position=int(meta.get("position") or 0), pov_entity_id=pov,
                             experiment_item_id=item_by_old.get(str(meta.get("item"))) if meta.get("item") else None,
                             retired_at=_when(meta.get("retired_at")) if state == "retired" else None,
                             summary=" ".join(str(meta.get("summary") or "").split())[:300],
                             status_id=status_of(pid, meta.get("status")), **_time_in(meta),
                             created_by=user.id, updated_by=user.id)
                if state == "retired" and ch.retired_at is None:
                    ch.retired_at = datetime.now(UTC)
                db.add(ch)
                db.flush()
                # restored text is where the chapter starts, not a day's writing: after its dated versions, if any
                restored.append(ch)
                if meta.get("id"):
                    chapter_by_old[str(meta["id"])] = ch.id
                if meta.get("replaces"):
                    pending_replaces.append((ch, str(meta["replaces"])))
                for note in meta.get("harvest_notes") or []:
                    db.add(HarvestNote(world_id=world.id, chapter_id=ch.id, body=str(note), created_by=user.id))
    def chapter(old) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
        return chapter_by_old.get(str(old)) if old else None

    # each experiment's range (or where it adds); a draft from an older export with `replaces: <id>` gives its
    # experiment a range of that one chapter
    ranged: set[uuid.UUID] = set()
    for it, meta in item_ranges:
        olds = meta.get("replaces")
        olds = olds if isinstance(olds, list) else ([olds] if olds else [])
        for n, old in enumerate(x for x in (chapter_by_old.get(str(o)) for o in olds) if x):
            db.add(ExperimentRange(item_id=it.id, chapter_id=old, position=n))
            ranged.add(it.id)
        ins = meta.get("insert")
        if isinstance(ins, dict):
            for side in ("before", "after"):
                if chapter(ins.get(side)):
                    it.insert_at_chapter_id, it.insert_side = chapter(ins.get(side)), side
    for ch, old in pending_replaces:
        target = chapter_by_old.get(old)
        if ch.experiment_item_id and target and ch.experiment_item_id not in ranged:
            db.add(ExperimentRange(item_id=ch.experiment_item_id, chapter_id=target, position=0))
            ranged.add(ch.experiment_item_id)

    # the cuts bin, each relinked to its source chapter (and the one it was put back into) by id
    for folder, pslug in project_dirs.items():
        for _rel, meta, body in under(f"{root}/Projects/{folder}/Cuts/"):
            if not body:
                continue
            db.add(Cut(world_id=world.id, project_id=project_ids[pslug], chapter_id=chapter(meta.get("chapter")),
                       chapter_title=str(meta.get("chapter_title") or "")[:300], body=body,
                       before=str(meta.get("before") or ""), after=str(meta.get("after") or ""),
                       cut_at=_when(meta.get("cut_at")) or datetime.now(UTC), put_back_at=_when(meta.get("put_back_at")),
                       put_back_to=chapter(meta.get("put_back_to")), created_by=user.id))

    # the journal, before what was planned in it, kept by its old ids
    journal_by_old: dict[str, uuid.UUID] = {}
    for _rel, meta, body in under(f"{root}/Journal/"):
        j = JournalEntry(world_id=world.id, project_id=project_of(meta.get("project")),
                         entry_date=_day(meta.get("date")) or date.today(), title=meta.get("title"), body=body,
                         is_plan=meta.get("plan") is True, created_by=user.id, updated_by=user.id)
        db.add(j)
        db.flush()
        if meta.get("id"):
            journal_by_old[str(meta["id"])] = j.id
        # a plan's chapters, relinked through the chapters' ids (docs/SPEC.md §18.5); one it can't find is skipped
        linked: set[uuid.UUID] = set()
        for old in meta.get("chapters") if isinstance(meta.get("chapters"), list) else []:
            cid = chapter(old)
            if cid is not None and cid not in linked:
                linked.add(cid)
                db.add(ChapterPlan(chapter_id=cid, journal_id=j.id, created_by=user.id))
        if linked:
            j.is_plan = True

    def journal(old) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
        return journal_by_old.get(str(old)) if old else None

    for i, meta in item_origins:
        src = meta["from"]
        passage = str(meta.get("passage") or "").strip() or None
        for table, find in (("chapter", chapter), ("journal", journal)):
            target = find(src.get(table))
            if target is not None:
                db.add(ItemLink(item_id=i.id, target_table=table, target_id=target, passage=passage))
        # the chapters it is for besides (made from a plan, docs/SPEC.md §18.4)
        done = {chapter(src.get("chapter"))}
        for old in meta.get("chapters") if isinstance(meta.get("chapters"), list) else []:
            cid = chapter(old)
            if cid is not None and cid not in done:
                done.add(cid)
                db.add(ItemLink(item_id=i.id, target_table="chapter", target_id=cid))

    standings = ("canon", "planned", "rumour")
    # rows that follow decisions, linked once the decisions are made (they come after)
    following: list[tuple[str, object, dict]] = []
    for e, meta in world_model:
        for i, f in enumerate(meta.get("facts") or []):
            fact = Fact(world_id=world.id, entity_id=e.id, label=str(f.get("label") or "note")[:100],
                        value=str(f.get("value") or ""), position=i,
                        standing=f.get("standing") if f.get("standing") in standings else "canon",
                        evidence=f.get("evidence"), note=f.get("note"),
                        established_in_chapter_id=chapter(f.get("established_in")),
                        planned_in_journal_id=journal(f.get("planned_in")), planned_evidence=f.get("planned_evidence"),
                        **_spans_in(f, chapter), created_by=user.id, updated_by=user.id)
            db.add(fact)
            if f.get("follows"):
                following.append(("fact", fact, f))
        for r in meta.get("relationships") or []:
            other = entity_by_old.get(str(r.get("to"))) or entity_by_name.get(str(r.get("to_name")))
            kinds = r.get("type_kinds") or ["*", "*"]
            type_id = type_by_key.get((str(kinds[0]), str(kinds[1]), str(r.get("type"))))
            if other is None or type_id is None:
                continue
            rel = Relationship(world_id=world.id, type_id=type_id, a_id=e.id, b_id=other,
                               standing=r.get("standing") if r.get("standing") in standings else "canon",
                               evidence=r.get("evidence"), note=r.get("note"), role=clean_role(r.get("role")),
                               established_in_chapter_id=chapter(r.get("established_in")),
                               planned_in_journal_id=journal(r.get("planned_in")),
                               planned_evidence=r.get("planned_evidence"),
                               **_spans_in(r, chapter), created_by=user.id, updated_by=user.id)
            db.add(rel)
            if r.get("follows"):
                following.append(("relationship", rel, r))

    # events' when, eras' colours and tellings, relinked to the chapters by id
    colours = ("amber", "moss", "teal", "sky", "indigo", "plum", "rose", "rust")
    for e, meta in world_model:
        when = meta.get("when")
        if when == "outside":
            e.outside_time = True
        elif isinstance(when, dict) and _num(when.get("at")) is not None:
            e.time_at, e.time_end = _num(when.get("at")), _num(when.get("end"))
            e.time_label = " ".join(str(when.get("label") or "").split()) or None
            e.time_approx = when.get("approx") is True
        elif isinstance(when, str) and chapter(when):
            e.time_chapter_id = chapter(when)
        if meta.get("colour") in colours:
            e.era_colour = meta["colour"]
        for t in meta.get("tellings") or []:
            if isinstance(t, dict) and str(t.get("passage") or "").strip():
                db.add(Telling(world_id=world.id, event_id=e.id, chapter_id=chapter(t.get("chapter")),
                               passage=str(t["passage"]), created_by=user.id))
        # notes in the Journal (docs/SPEC.md §14.1.2); one whose entry isn't in the export keeps its passage
        for t in meta.get("notes") or []:
            if isinstance(t, dict) and str(t.get("passage") or "").strip():
                db.add(Telling(world_id=world.id, event_id=e.id, journal_id=journal(t.get("journal")),
                               passage=str(t["passage"]), created_by=user.id))

    for e, meta in world_model:
        for p in meta.get("is_at") or []:
            place = entity_by_old.get(str(p.get("place"))) or entity_by_name.get(str(p.get("place_name")))
            ch = chapter(p.get("chapter"))
            if place is not None and ch is not None:
                db.add(Presence(world_id=world.id, entity_id=e.id, place_id=place, chapter_id=ch,
                                note=p.get("note"), created_by=user.id))

    # the chart (none in an export from before phase 12d: it starts laid out automatically), relinked by id
    chart = wmeta.get("chart") if isinstance(wmeta.get("chart"), dict) else {}
    settings = chart.get("settings") if isinstance(chart.get("settings"), dict) else {}
    shapes = settings.get("shapes") if isinstance(settings.get("shapes"), dict) else {}
    world.chart = {"shapes": {" ".join(str(k).split()).lower()[:100]: str(v) for k, v in shapes.items()
                              if str(k).strip() and str(v) in CHART_SHAPES}}
    pinned: set[tuple[uuid.UUID, uuid.UUID | None]] = set()
    for p in chart.get("pins") or []:
        if not isinstance(p, dict) or not all(math.isfinite(_num(p.get(k)) or math.nan) for k in ("x", "y")):
            continue
        place = entity_by_old.get(str(p.get("place")))
        container = entity_by_old.get(str(p.get("container"))) if p.get("container") else None
        if place is None or (p.get("container") and container is None) or (place, container) in pinned:
            continue
        pinned.add((place, container))
        db.add(ChartPin(world_id=world.id, place_id=place, container_id=container, x=float(_num(p["x"])),
                        y=float(_num(p["y"])), updated_by=user.id))

    decisions = files.get(f"{root}/Decisions.md", "")
    decision_by_old: dict[str, uuid.UUID] = {}
    d: Decision | None = None
    for line in decisions.splitlines():
        m = DECISION_RE.match(line)
        if not m:
            # a dropped follow-up whose row is gone (docs/SPEC.md §16.6): the others are worked out from the rows
            f = FOLLOWUP_RE.match(line)
            if f and d is not None and f.group(1) == "dropped" and not f.group(4) and f.group(3).strip():
                db.add(DecisionFollowup(decision_id=d.id, what=f.group(3).strip(), created_by=user.id,
                                        dropped_on=_day(f.group(2)) if f.group(2) else None))
            continue
        refs = dict(part.split("=", 1) for part in m.group(4).split() if "=" in part)
        d = Decision(world_id=world.id, project_id=project_of(m.group(2)), decided_on=date.fromisoformat(m.group(1)),
                     text=m.group(3), item_id=item_by_old.get(refs.get("item", "")), created_by=user.id,
                     updated_by=user.id)
        db.add(d)
        db.flush()
        if refs.get("id"):
            decision_by_old[refs["id"]] = d.id
        for old in filter(None, refs.get("entities", "").split(",")):
            if old in entity_by_old:
                db.add(DecisionLink(decision_id=d.id, entity_id=entity_by_old[old]))
    # the rows that follow decisions (none in an export from before phase 14: its decisions come back settled)
    db.flush()
    for table, row, meta in [*following, *(("item", i, m) for i, m in item_follows)]:
        dropped = meta.get("dropped") if isinstance(meta.get("dropped"), dict) else {}
        olds = meta.get("follows") if isinstance(meta.get("follows"), list) else []
        for old in dict.fromkeys(str(x) for x in olds):
            if old in decision_by_old:
                db.add(DecisionFollowup(decision_id=decision_by_old[old], what=what_of(db, world, table, row),
                                        dropped_on=_day(dropped.get(old)) if dropped.get(old) else None,
                                        created_by=user.id, **{f"{table}_id": row.id}))

    # dated earlier versions (docs/SPEC.md §20), then each chapter's start where its text is newer than them
    last = _restore_history(db, user, root, files, others or {}, chapter_by_old, journal_by_old, report)
    for ch in restored:
        if ch.body.strip() and last.get(("chapter", ch.id)) != ch.body:
            snapshot(db, ch, "start", user)

    for token in wmeta.get("ignored_words") or []:
        db.add(NameIgnore(world_id=world.id, token=str(token)))

    # the per-label switches (none in an export from before phase 11)
    switched: set[tuple[str, str]] = set()
    for r in wmeta.get("fact_labels") or []:
        if not isinstance(r, dict):
            continue
        kind, label = str(r.get("kind") or ""), " ".join(str(r.get("label") or "").split())[:100]
        if kind not in KIND_FOLDERS or not label or (kind, label.lower()) in switched:
            continue
        switched.add((kind, label.lower()))
        db.add(FactLabel(world_id=world.id, kind=kind, label=label, several=r.get("several") is True,
                         expected=r.get("expected") is True, asked=r.get("asked") is True))

    # the one-at-a-time roles (none in an export from before phase 12)
    roles_seen: set[str] = set()
    for r in wmeta.get("roles") or []:
        role = clean_role(str(r.get("role") or "")) if isinstance(r, dict) else None
        if not role or role.lower() in roles_seen:
            continue
        roles_seen.add(role.lower())
        db.add(Role(world_id=world.id, role=role, one_at_a_time=r.get("one_at_a_time") is True))

    db.flush()
    refresh_world(db, world.id)
    return world
