"""Export a world as a folder of Markdown files (zipped), and restore such a zip as a new world.

The export is meant to be read without Quarry: plain Markdown with YAML frontmatter, one file per chapter, bible
entry, journal entry and item, plus Decisions.md and a compiled manuscript.md per project. Restore reads exactly
that layout back (the compiled manuscript is ignored). Revision history stays in the database: an export carries
the texts as they are now.

    <world>/world.md                                  name, slug, words marked "not a typo"
    <world>/Bible/<Kind>/<Name>.md                    id, name, kind, aliases; the notes
    <world>/Journal/<date> <title> (<id>).md          id, date, title, project
    <world>/Decisions.md                              one line per decision
    <world>/Planning/<status>/<date> <text> (<id>).md items for the whole world
    <world>/Projects/<Name>/project.md                name, slug, kind, position, statuses (in order)
    <world>/Projects/<Name>/Manuscript/<NN> <Title>.md id, title, state, position, pov, summary, status
    <world>/Projects/<Name>/Experiments/<Title> (<id>).md
    <world>/Projects/<Name>/Salvage/<Title> (<id>).md retired chapters, with their harvest notes
    <world>/Projects/<Name>/Cuts/<date> <source title> (<id>).md   the cuts bin: id, chapter, chapter_title, cut_at,
                                                      put_back_at, put_back_to, before, after; the cut text
    <world>/Projects/<Name>/Planning/<status>/...     items for the project
    <world>/Projects/<Name>/manuscript.md             the current chapters in order (not read back)
"""

from __future__ import annotations

import io
import re
import uuid
import zipfile
from collections import defaultdict
from datetime import UTC, date, datetime

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..mentions import refresh_world
from ..models import (
    STARTING_STATUSES,
    Chapter,
    ChapterStatus,
    Cut,
    Decision,
    DecisionLink,
    Entity,
    Fact,
    HarvestNote,
    Item,
    ItemLink,
    JournalEntry,
    NameIgnore,
    Presence,
    Project,
    RelationType,
    Relationship,
    User,
    World,
    WorldMember,
)
from ..margin import without_margin_notes
from .manuscript import snapshot
from .world import seed_relation_types
from .deps import current_user
from .worlds import WorldOut, _unique, _world_out, member_world, slugify

router = APIRouter(prefix="/api/worlds")

FORMAT = 1
KIND_FOLDERS = {"character": "Characters", "place": "Places", "faction": "Factions", "culture": "Cultures",
                "event": "Events", "object": "Objects", "term": "Terms", "other": "Other"}
MAX_UPLOAD = 50 * 1024 * 1024
MAX_UNPACKED = 200 * 1024 * 1024
DECISION_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2})(?: · \[([^\]]*)\])? (.*?)\s*<!-- (.*?) -->\s*$")


def _safe(name: str, limit: int = 80) -> str:
    """A file or folder name that works on every system."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", name)
    name = " ".join(name.split()).strip(" .")[:limit].rstrip(" .")
    return name or "untitled"


def _doc(meta: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n\n" + body


def _parse(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    meta = yaml.safe_load(text[4:end]) or {}
    body = text[end + 5:]
    if body.startswith("\n"):
        body = body[1:]
    return (meta if isinstance(meta, dict) else {}), body


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


# export --------------------------------------------------------------------------------------------------------


@router.get("/{slug}/export")
def export_world(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
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
    files[f"{root}/world.md"] = _doc({
        "quarry_export": FORMAT, "name": world.name, "slug": world.slug,
        "exported_at": datetime.now(UTC).isoformat(), "ignored_words": ignored,
        "relation_types": [{"a": t.a_kind, "b": t.b_kind, "label": t.label, "reverse": t.reverse_label}
                           for t in types]}, "")

    facts: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for f in db.scalars(select(Fact).where(Fact.world_id == world.id).order_by(Fact.entity_id, Fact.position)):
        facts[f.entity_id].append({"label": f.label, "value": f.value, "standing": f.standing,
                                   "evidence": f.evidence, "note": f.note,
                                   "established_in": str(f.established_in_chapter_id) if f.established_in_chapter_id else None,
                                   "from": str(f.from_chapter_id) if f.from_chapter_id else None,
                                   "until": str(f.until_chapter_id) if f.until_chapter_id else None})
    rels: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for r in db.scalars(select(Relationship).where(Relationship.world_id == world.id).order_by(Relationship.created_at)):
        t = type_by_id[r.type_id]
        rels[r.a_id].append({"type": t.label, "type_kinds": [t.a_kind, t.b_kind], "to": str(r.b_id),
                             "to_name": names.get(r.b_id), "standing": r.standing, "evidence": r.evidence,
                             "note": r.note,
                             "established_in": str(r.established_in_chapter_id) if r.established_in_chapter_id else None,
                             "from": str(r.from_chapter_id) if r.from_chapter_id else None,
                             "until": str(r.until_chapter_id) if r.until_chapter_id else None})

    presence: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for p in db.scalars(select(Presence).where(Presence.world_id == world.id).order_by(Presence.created_at)):
        presence[p.entity_id].append({"chapter": str(p.chapter_id), "place": str(p.place_id),
                                      "place_name": names.get(p.place_id), "note": p.note})

    for e in entities:
        meta = {"id": str(e.id), "name": e.name, "kind": e.kind, "aliases": list(e.aliases), "summary": e.summary,
                "match_case": e.match_case, "first_name_alias": e.first_name_alias,
                "exclusions": list(e.exclusions)}
        if facts.get(e.id):
            meta["facts"] = facts[e.id]
        if rels.get(e.id):
            meta["relationships"] = rels[e.id]
        if presence.get(e.id):
            meta["is_at"] = presence[e.id]
        files[f"{root}/Bible/{KIND_FOLDERS[e.kind]}/{_safe(e.name)}.md"] = _doc(meta, e.body)

    for j in db.scalars(select(JournalEntry).where(JournalEntry.world_id == world.id).order_by(JournalEntry.entry_date)):
        title = j.title or j.body.split("\n", 1)[0][:40]
        files[f"{root}/Journal/{j.entry_date} {_safe(title, 50)} ({str(j.id)[:8]}).md"] = _doc(
            {"id": str(j.id), "date": j.entry_date.isoformat(), "title": j.title,
             "project": projects[j.project_id].slug if j.project_id else None}, j.body)

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
    files[f"{root}/Decisions.md"] = "\n".join(lines) + "\n"

    tags: dict[uuid.UUID, list[str]] = defaultdict(list)
    for item_id, target in db.execute(select(ItemLink.item_id, ItemLink.target_id).join(Item, Item.id == ItemLink.item_id)
                                      .where(Item.world_id == world.id, ItemLink.target_table == "entity")).all():
        if target in names:
            tags[item_id].append(names[target])
    for i in db.scalars(select(Item).where(Item.world_id == world.id).order_by(Item.created_at)):
        folder = project_dir[i.project_id] if i.project_id else root
        short = _safe(i.title or i.body.split("\n", 1)[0], 50)
        files[f"{folder}/Planning/{i.status}/{i.created_at:%Y-%m-%d} {short} ({str(i.id)[:8]}).md"] = _doc(
            {"id": str(i.id), "kind": i.kind, "status": i.status, "title": i.title,
             "project": projects[i.project_id].slug if i.project_id else None, "source": i.source,
             "created_at": _iso(i.created_at), "closed_at": _iso(i.closed_at), "closed_note": i.closed_note,
             "tags": sorted(tags.get(i.id, []))}, i.body)

    notes: dict[uuid.UUID, list[str]] = defaultdict(list)
    for n in db.scalars(select(HarvestNote).where(HarvestNote.world_id == world.id).order_by(HarvestNote.created_at)):
        notes[n.chapter_id].append(n.body)
    for p in world.projects:
        d = project_dir[p.id]
        statuses = list(db.scalars(select(ChapterStatus).where(ChapterStatus.project_id == p.id)
                                   .order_by(ChapterStatus.position, ChapterStatus.created_at)))
        status_label = {s.id: s.label for s in statuses}
        files[f"{d}/project.md"] = _doc({"name": p.name, "slug": p.slug, "kind": p.kind, "position": p.position,
                                         "statuses": [s.label for s in statuses]}, "")
        chapters = list(db.scalars(select(Chapter).where(Chapter.project_id == p.id)
                                   .order_by(Chapter.position, Chapter.created_at)))
        compiled = [f"# {p.name}", ""]
        n = 0
        for ch in chapters:
            meta = {"id": str(ch.id), "title": ch.title, "state": ch.state, "position": ch.position,
                    "pov": names.get(ch.pov_entity_id) if ch.pov_entity_id else None,
                    "summary": ch.summary, "status": status_label.get(ch.status_id) if ch.status_id else None}
            if ch.state == "current":
                n += 1
                path = f"{d}/Manuscript/{n:02d} {_safe(ch.title, 60)}.md"
                compiled += [f"## {ch.title}", "", without_margin_notes(ch.body).rstrip(), ""]
            elif ch.state == "experiment":
                meta |= {"replaces": str(ch.replaces_id) if ch.replaces_id else None,
                         "item": str(ch.experiment_item_id) if ch.experiment_item_id else None}
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

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, text in files.items():
            z.writestr(path, text)
    name = f"quarry-{world.slug}-{date.today().isoformat()}.zip"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# restore -------------------------------------------------------------------------------------------------------


def _read_zip(data: bytes) -> dict[str, str]:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise HTTPException(422, "That file is not a zip.") from None
    total = sum(i.file_size for i in z.infolist())
    if total > MAX_UNPACKED:
        raise HTTPException(422, "That zip is too big to restore.")
    files = {}
    for info in z.infolist():
        name = info.filename.replace("\\", "/")
        if info.is_dir() or not name.endswith(".md") or ".." in name.split("/") or name.startswith("/"):
            continue
        files[name] = z.read(info).decode("utf-8")
    return files


@router.post("/restore", status_code=201)
async def restore_world(file: UploadFile = File(...), user: User = Depends(current_user),
                        db: Session = Depends(get_db)) -> WorldOut:
    """Make a new world from an export zip. Ids are new; links between the files are kept."""
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(422, "That zip is too big to restore.")
    world = restore_files(db, user, _read_zip(data))
    db.commit()
    db.refresh(world)
    return _world_out(world, "owner")


def restore_files(db: Session, user: User, files: dict[str, str]) -> World:
    """Make a new world for `user` from the files of an export (path -> text). Flushed, not committed."""
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
                  created_by=user.id, updated_by=user.id)
    db.add(world)
    db.flush()
    db.add(WorldMember(world_id=world.id, user_id=user.id, role="owner"))

    # projects, by their slug in the export
    # the relationship vocabulary: the export's, or the starting one for exports made before phase 6
    exported_types = wmeta.get("relation_types") or []
    type_by_key: dict[tuple[str, str, str], uuid.UUID] = {}
    if exported_types:
        for i, t in enumerate(exported_types):
            rt = RelationType(world_id=world.id, a_kind=str(t.get("a") or "*"), b_kind=str(t.get("b") or "*"),
                              label=str(t.get("label") or "linked to"), reverse_label=t.get("reverse"), position=i)
            db.add(rt)
            db.flush()
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
    for rel, meta, body in under(f"{root}/Bible/"):
        kind = meta.get("kind") if meta.get("kind") in KIND_FOLDERS else "other"
        ename = " ".join(str(meta.get("name") or rel.rsplit("/", 1)[-1][:-3]).split())
        if ename.lower() in {n.lower() for n in entity_by_name}:
            continue
        e = Entity(world_id=world.id, kind=kind, name=ename, aliases=[str(a) for a in meta.get("aliases") or []],
                   body=body, summary=str(meta.get("summary") or ""), match_case=meta.get("match_case") is not False,
                   first_name_alias=meta.get("first_name_alias") is not False,
                   exclusions=[str(x) for x in meta.get("exclusions") or []], created_by=user.id, updated_by=user.id)
        db.add(e)
        db.flush()
        entity_by_name[ename] = e.id
        if meta.get("id"):
            entity_by_old[str(meta["id"])] = e.id
        world_model.append((e, meta))

    # items: the world's own Planning/ and each project's
    item_by_old: dict[str, uuid.UUID] = {}
    planning = [(None, rel, meta, body) for rel, meta, body in under(f"{root}/Planning/")]
    for folder, pslug in project_dirs.items():
        planning += [(pslug, rel, meta, body) for rel, meta, body in under(f"{root}/Projects/{folder}/Planning/")]
    for pslug, _rel, meta, body in planning:
        status = meta.get("status") if meta.get("status") in ("open", "accepted", "rejected", "harvested",
                                                               "deferred") else "open"
        kind = meta.get("kind") if meta.get("kind") in ("spark", "question", "task", "experiment") else "spark"
        i = Item(world_id=world.id, project_id=project_of(meta.get("project") or pslug), kind=kind,
                 title=meta.get("title"), body=body or "(empty)", status=status, source=meta.get("source"),
                 closed_at=_when(meta.get("closed_at")), closed_note=meta.get("closed_note"),
                 created_by=user.id, updated_by=user.id)
        if _when(meta.get("created_at")):
            i.created_at = _when(meta.get("created_at"))
        db.add(i)
        db.flush()
        if meta.get("id"):
            item_by_old[str(meta["id"])] = i.id
        for tag in meta.get("tags") or []:
            if str(tag) in entity_by_name:
                db.add(ItemLink(item_id=i.id, target_table="entity", target_id=entity_by_name[str(tag)]))

    # chapters: current, experiments, salvage
    chapter_by_old: dict[str, uuid.UUID] = {}
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
                             status_id=status_of(pid, meta.get("status")),
                             created_by=user.id, updated_by=user.id)
                if state == "retired" and ch.retired_at is None:
                    ch.retired_at = datetime.now(UTC)
                db.add(ch)
                db.flush()
                if ch.body.strip():
                    # restored text is where the chapter starts, not a day's writing
                    snapshot(db, ch, "start", user)
                if meta.get("id"):
                    chapter_by_old[str(meta["id"])] = ch.id
                if meta.get("replaces"):
                    pending_replaces.append((ch, str(meta["replaces"])))
                for note in meta.get("harvest_notes") or []:
                    db.add(HarvestNote(world_id=world.id, chapter_id=ch.id, body=str(note), created_by=user.id))
    def chapter(old) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
        return chapter_by_old.get(str(old)) if old else None

    for ch, old in pending_replaces:
        ch.replaces_id = chapter_by_old.get(old)

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

    standings = ("canon", "planned", "rumour")
    for e, meta in world_model:
        for i, f in enumerate(meta.get("facts") or []):
            db.add(Fact(world_id=world.id, entity_id=e.id, label=str(f.get("label") or "note")[:100],
                        value=str(f.get("value") or ""), position=i,
                        standing=f.get("standing") if f.get("standing") in standings else "canon",
                        evidence=f.get("evidence"), note=f.get("note"),
                        established_in_chapter_id=chapter(f.get("established_in")),
                        from_chapter_id=chapter(f.get("from")), until_chapter_id=chapter(f.get("until")),
                        created_by=user.id, updated_by=user.id))
        for r in meta.get("relationships") or []:
            other = entity_by_old.get(str(r.get("to"))) or entity_by_name.get(str(r.get("to_name")))
            kinds = r.get("type_kinds") or ["*", "*"]
            type_id = type_by_key.get((str(kinds[0]), str(kinds[1]), str(r.get("type"))))
            if other is None or type_id is None:
                continue
            db.add(Relationship(world_id=world.id, type_id=type_id, a_id=e.id, b_id=other,
                                standing=r.get("standing") if r.get("standing") in standings else "canon",
                                evidence=r.get("evidence"), note=r.get("note"),
                                established_in_chapter_id=chapter(r.get("established_in")),
                                from_chapter_id=chapter(r.get("from")), until_chapter_id=chapter(r.get("until")),
                                created_by=user.id, updated_by=user.id))

    for e, meta in world_model:
        for p in meta.get("is_at") or []:
            place = entity_by_old.get(str(p.get("place"))) or entity_by_name.get(str(p.get("place_name")))
            ch = chapter(p.get("chapter"))
            if place is not None and ch is not None:
                db.add(Presence(world_id=world.id, entity_id=e.id, place_id=place, chapter_id=ch,
                                note=p.get("note"), created_by=user.id))

    for _rel, meta, body in under(f"{root}/Journal/"):
        db.add(JournalEntry(world_id=world.id, project_id=project_of(meta.get("project")),
                            entry_date=_day(meta.get("date")) or date.today(), title=meta.get("title"), body=body,
                            created_by=user.id, updated_by=user.id))

    decisions = files.get(f"{root}/Decisions.md", "")
    for line in decisions.splitlines():
        m = DECISION_RE.match(line)
        if not m:
            continue
        refs = dict(part.split("=", 1) for part in m.group(4).split() if "=" in part)
        d = Decision(world_id=world.id, project_id=project_of(m.group(2)), decided_on=date.fromisoformat(m.group(1)),
                     text=m.group(3), item_id=item_by_old.get(refs.get("item", "")), created_by=user.id,
                     updated_by=user.id)
        db.add(d)
        db.flush()
        for old in filter(None, refs.get("entities", "").split(",")):
            if old in entity_by_old:
                db.add(DecisionLink(decision_id=d.id, entity_id=entity_by_old[old]))

    for token in wmeta.get("ignored_words") or []:
        db.add(NameIgnore(world_id=world.id, token=str(token)))

    db.flush()
    refresh_world(db, world.id)
    return world
