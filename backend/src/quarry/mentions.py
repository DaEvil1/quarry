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

from .margin import story_text
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


# a name starting with an article has no first name ("The Grey Keeper")
ARTICLES = {"the", "a", "an"}
# titles are skipped: "Lord Mordoch" is also matched as "Mordoch"
TITLES = {
    "lord", "lady", "sir", "dame", "king", "queen", "prince", "princess", "captain", "master", "mistress", "mister",
    "mr", "mrs", "ms", "miss", "dr", "saint", "st", "father", "mother", "brother", "sister", "uncle", "aunt",
    "general", "high", "old", "young",
}


def first_name_aliases(entities: Iterable[Entity]) -> dict[uuid.UUID, str]:
    """For characters with a multi-word name: their first word, when no other entry uses or claims it."""
    taken = {f.strip().lower() for e in entities for f in [e.name, *e.aliases] if f.strip()}
    claims: dict[str, list[tuple[uuid.UUID, str]]] = {}
    for e in entities:
        words = [w.strip(",.") for w in e.name.split()]
        if "character" not in [e.kind, *(e.also_kinds or [])] or not e.first_name_alias or len(words) < 2 or words[0].lower() in ARTICLES:
            continue
        while len(words) > 1 and words[0].lower() in TITLES:
            words = words[1:]
        first = words[0]
        if len(first) < 3 or first.lower() in TITLES or first == e.name:
            continue
        claims.setdefault(first.lower(), []).append((e.id, first))
    return {owners[0][0]: owners[0][1] for key, owners in claims.items() if len(owners) == 1 and key not in taken}


def article_forms(name: str) -> list[str]:
    """A name that starts with "The" also matches with "the" (mid-sentence), and the other way round: "The River
    Wardens" is "the River Wardens" in "the flag of the River Wardens"."""
    for a, b in (("The ", "the "), ("the ", "The ")):
        if name.startswith(a) and len(name) > len(a):
            return [name, b + name[len(a):]]
    return [name]


class Matcher:
    """Everything needed to scan the texts of one world."""

    def __init__(self, entities: Iterable[Entity], ignored: Iterable[str] = ()) -> None:
        entities = list(entities)
        firsts = first_name_aliases(entities)
        exact: dict[str, tuple[uuid.UUID, str]] = {}
        loose: dict[str, tuple[uuid.UUID, str]] = {}  # matched whatever the capitals (lowercase key)
        self.exclusions: dict[uuid.UUID, list[str]] = {}
        for e in entities:
            forms = [(e.name, "exact")] + [(a, "alias") for a in e.aliases] + (
                [(firsts[e.id], "alias")] if e.id in firsts else [])
            for f, kind in forms:
                f = f.strip()
                if not f:
                    continue
                if e.match_case:
                    for v in article_forms(f):
                        exact.setdefault(v, (e.id, kind))
                else:
                    loose.setdefault(f.lower(), (e.id, kind))
            if e.exclusions:
                self.exclusions[e.id] = [x.lower() for x in e.exclusions if x.strip()]
        self.exact, self.loose = exact, loose

        def alternation(forms: Iterable[str], flags: int = 0) -> re.Pattern[str] | None:
            # longest first, so "Old Harbour" wins over "Harbour"
            ordered = sorted(forms, key=len, reverse=True)
            if not ordered:
                return None
            return re.compile(r"(?<![\w'’-])(" + "|".join(re.escape(f) for f in ordered) + r")" + SUFFIX + r"(?![\w])",
                              flags)

        self.exact_re = alternation(exact)
        self.loose_re = alternation(loose, re.IGNORECASE)
        # single words of every name, for near misses; a word that is part of any name is never a typo
        self.known_words: set[str] = set()
        self.known_lower: set[str] = set()
        self.word_owner: dict[str, uuid.UUID] = {}
        for f, (eid, _) in [*exact.items(), *loose.items()]:
            for w in WORD_RE.findall(f):
                self.known_words.add(w)
                self.known_lower.add(w.lower())
                if len(w) >= NEAR_MIN:
                    self.word_owner.setdefault(w if f in exact else w.capitalize(), eid)
        self.candidates = list(self.word_owner)
        self.ignored = set(ignored)

    def _excluded(self, text_lower: str, eid: uuid.UUID, start: int, end: int,
                  cache: dict[uuid.UUID, list[tuple[int, int]]]) -> bool:
        phrases = self.exclusions.get(eid)
        if not phrases:
            return False
        if eid not in cache:
            spans = []
            for ph in phrases:
                i = text_lower.find(ph)
                while i >= 0:
                    spans.append((i, i + len(ph)))
                    i = text_lower.find(ph, i + 1)
            cache[eid] = spans
        return any(s <= start and end <= e for s, e in cache[eid])

    def scan(self, text: str, skip_entity: uuid.UUID | None = None) -> list[Found]:
        hits: list[tuple[int, int, uuid.UUID, str, str]] = []
        if self.exact_re is not None:
            for m in self.exact_re.finditer(text):
                eid, kind = self.exact[m.group(1)]
                hits.append((m.start(), m.end(), eid, m.group(0), kind))
        if self.loose_re is not None:
            for m in self.loose_re.finditer(text):
                eid, kind = self.loose[m.group(1).lower()]
                hits.append((m.start(), m.end(), eid, m.group(0), kind))
        # overlapping matches from the two lists: the longer one wins
        hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
        found: list[Found] = []
        taken: list[tuple[int, int]] = []
        lower = text.lower()
        cache: dict[uuid.UUID, list[tuple[int, int]]] = {}
        for start, end, eid, matched, kind in hits:
            if taken and start < taken[-1][1]:
                continue
            if self._excluded(lower, eid, start, end, cache):
                continue
            taken.append((start, end))
            if eid != skip_entity:
                found.append(Found(eid, start, end, matched, kind))
        if self.candidates:
            for m in WORD_RE.finditer(text):
                word = m.group(0)
                if not word[0].isupper() or any(s <= m.start() < e for s, e in taken):
                    continue
                base = POSSESSIVE_RE.sub("", word)
                if len(base) < NEAR_MIN or base in self.ignored or word in self.ignored:
                    continue
                if base.lower() in self.known_lower:
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
    if table == "chapter":
        text = story_text(text)
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
        _store(db, world_id, "chapter", c.id, m.scan(story_text(c.body)))
