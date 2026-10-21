"""Finding bible names in text, and words that look like misspellings of them.

Exact matches: an entity's name or one of its aliases, case-sensitive, on word boundaries, also with a plural or
possessive ending ("Varrens", "Varren's", "Varren’s"). Multi-word names match as a whole ("Old Harbour").

Near misses: a capitalised word of at least five letters that is no known name but is one edit away from a word of
one (two edits for words of seven letters or more; a swapped pair of letters counts as one edit), unless it was
marked "not a typo". They are stored against the entity they probably mean.

Mentions are recomputed whenever a text is saved, and for the whole world when names change. A world's text is
small (a novel and its notes are a few hundred kilobytes), so a full rescan stays well under a second.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from rapidfuzz import process
from rapidfuzz.distance import OSA
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Chapter, Decision, Entity, Item, JournalEntry, Mention, NameIgnore, Project

SUFFIX = r"(?:'s|’s|s)?"
# a word: letters, with apostrophes or hyphens inside ("O'Neil", "Sea-born")
WORD_RE = re.compile(r"(?<![\w'’-])[^\W\d_][^\W_]*(?:['’-][^\W_]+)*")
POSSESSIVE_RE = re.compile(r"(?:'s|’s)$")
NEAR_MIN = 5


@dataclass(frozen=True)
class Found:
    entity_id: uuid.UUID
    start: int
    end: int
    matched: str
    kind: str  # exact | alias | near_miss


class Matcher:
    """Everything needed to scan the texts of one world."""

    def __init__(self, entities: Iterable[Entity], ignored: Iterable[str] = ()) -> None:
        forms: list[tuple[str, uuid.UUID, str]] = []
        for e in entities:
            forms.append((e.name, e.id, "exact"))
            forms += [(a, e.id, "alias") for a in e.aliases if a.strip()]
        forms = [(f.strip(), eid, k) for f, eid, k in forms if f.strip()]
        # longest first, so "Old Harbour" wins over "Harbour"
        forms.sort(key=lambda f: len(f[0]), reverse=True)
        self.by_form = {}
        for f, eid, k in forms:
            self.by_form.setdefault(f, (eid, k))
        self.exact_re = (
            re.compile(r"(?<![\w'’-])(" + "|".join(re.escape(f) for f in self.by_form) + r")" + SUFFIX + r"(?![\w])")
            if self.by_form else None
        )
        # single words of every name, for near misses; a word that is part of any name is never a typo
        self.known_words: set[str] = set()
        self.word_owner: dict[str, uuid.UUID] = {}
        for f, (eid, _) in self.by_form.items():
            for w in WORD_RE.findall(f):
                self.known_words.add(w)
                if len(w) >= NEAR_MIN:
                    self.word_owner.setdefault(w, eid)
        self.candidates = list(self.word_owner)
        self.ignored = set(ignored)

    def scan(self, text: str, skip_entity: uuid.UUID | None = None) -> list[Found]:
        found: list[Found] = []
        taken: list[tuple[int, int]] = []
        if self.exact_re is not None:
            for m in self.exact_re.finditer(text):
                eid, kind = self.by_form[m.group(1)]
                taken.append((m.start(), m.end()))
                if eid != skip_entity:
                    found.append(Found(eid, m.start(), m.end(), m.group(0), kind))
        if self.candidates:
            for m in WORD_RE.finditer(text):
                word = m.group(0)
                if not word[0].isupper() or any(s <= m.start() < e for s, e in taken):
                    continue
                base = POSSESSIVE_RE.sub("", word)
                if len(base) < NEAR_MIN or base in self.known_words or base in self.ignored or word in self.ignored:
                    continue
                if base.lower() in {w.lower() for w in self.known_words}:
                    continue
                limit = 1 if len(base) <= 6 else 2
                best = process.extractOne(base, self.candidates, scorer=OSA.distance, score_cutoff=limit)
                if best is None:
                    continue
                eid = self.word_owner[best[0]]
                if eid != skip_entity:
                    found.append(Found(eid, m.start(), m.start() + len(base), base, "near_miss"))
        found.sort(key=lambda f: f.start)
        return found


def matcher_for(db: Session, world_id: uuid.UUID) -> Matcher:
    entities = db.scalars(select(Entity).where(Entity.world_id == world_id)).all()
    ignored = db.scalars(select(NameIgnore.token).where(NameIgnore.world_id == world_id)).all()
    return Matcher(entities, ignored)


def _store(db: Session, world_id: uuid.UUID, table: str, source_id: uuid.UUID, found: list[Found]) -> None:
    db.execute(delete(Mention).where(Mention.source_table == table, Mention.source_id == source_id))
    db.add_all(Mention(world_id=world_id, source_table=table, source_id=source_id, entity_id=f.entity_id,
                       start=f.start, end=f.end, matched_text=f.matched[:200], kind=f.kind) for f in found)


def refresh_source(db: Session, world_id: uuid.UUID, table: str, source_id: uuid.UUID, text: str,
                   matcher: Matcher | None = None) -> None:
    """Rescan one text after it was saved."""
    m = matcher or matcher_for(db, world_id)
    _store(db, world_id, table, source_id, m.scan(text, skip_entity=source_id if table == "entity" else None))


def forget_source(db: Session, table: str, source_id: uuid.UUID) -> None:
    db.execute(delete(Mention).where(Mention.source_table == table, Mention.source_id == source_id))


def refresh_world(db: Session, world_id: uuid.UUID) -> None:
    """Rescan every text of a world: names, aliases or "not a typo" words changed."""
    m = matcher_for(db, world_id)
    db.execute(delete(Mention).where(Mention.world_id == world_id))
    db.flush()
    for i in db.scalars(select(Item).where(Item.world_id == world_id)):
        _store(db, world_id, "item", i.id, m.scan(i.body))
    for d in db.scalars(select(Decision).where(Decision.world_id == world_id)):
        _store(db, world_id, "decision", d.id, m.scan(d.text))
    for j in db.scalars(select(JournalEntry).where(JournalEntry.world_id == world_id)):
        _store(db, world_id, "journal", j.id, m.scan(j.body))
    for e in db.scalars(select(Entity).where(Entity.world_id == world_id)):
        _store(db, world_id, "entity", e.id, m.scan(e.body, skip_entity=e.id))
    for c in db.scalars(select(Chapter).join(Project, Project.id == Chapter.project_id)
                        .where(Project.world_id == world_id)):
        _store(db, world_id, "chapter", c.id, m.scan(c.body))
