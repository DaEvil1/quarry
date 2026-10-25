"""Finding bible names in text, and words that look like misspellings of them.

Exact matches: an entity's name or one of its aliases, case-sensitive, on word boundaries, also with a plural or
possessive ending ("Varrens", "Varren's", "Varren’s"). Multi-word names match as a whole ("Old Harbour").

Near misses: a capitalised word of at least five letters that is no known name but is one edit away from a word of
one (two edits for words of seven letters or more; a swapped pair of letters counts as one edit), unless it was
marked "not a typo". They are stored against the entity they probably mean.

Shared names (docs/SPEC.md §14.10): a first name or other name that two or more entries claim. A bare use is
ambiguous (stored once per claimant, kind "ambiguous") until a choice line above it, `%% Isolde: Isolde Marr`,
says which entry or entries it means; it then counts as an ordinary mention of each one chosen. A choice holds to
the next choice for the same name or the end of the text. An entry's own name is never shared: it wins.

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
    kind: str  # exact | alias | near_miss | ambiguous


@dataclass(frozen=True)
class Choice:
    """A choice line: from `end` on, the shared name `key` (lowercase) means `ids`, or nobody in particular (None).
    A line whose words single out no claimant has no ids, (), and changes nothing."""

    start: int
    end: int
    key: str
    ids: tuple[uuid.UUID, ...] | None


# `%% Isolde: Isolde Marr`, `%% Isolde: Marr, Senn`, `%% Isolde: ?`
CHOICE_RE = re.compile(r"^[ \t]*%%[ \t]*([^:\n]*[^:\s])[ \t]*:[ \t]*([^\n]*?)[ \t]*$", re.M)


# a name starting with an article has no first name ("The Grey Keeper")
ARTICLES = {"the", "a", "an"}
# titles are skipped: "Lord Mordoch" is also matched as "Mordoch"
TITLES = {
    "lord", "lady", "sir", "dame", "king", "queen", "prince", "princess", "captain", "master", "mistress", "mister",
    "mr", "mrs", "ms", "miss", "dr", "saint", "st", "father", "mother", "brother", "sister", "uncle", "aunt",
    "general", "high", "old", "young",
}


def first_name_aliases(entities: Iterable[Entity]) -> dict[uuid.UUID, str]:
    """For characters with a multi-word name: their first word, unless an entry is called that. Two characters with
    the same first name both get it: it is then a shared name."""
    entities = list(entities)
    taken = {e.name.strip().lower() for e in entities if e.name.strip()}
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
    return {eid: first for key, owners in claims.items() if key not in taken for eid, first in owners}


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
        # every form, with the entries claiming it in the order met (a shared name has several)
        exact: dict[str, list[tuple[uuid.UUID, str]]] = {}
        loose: dict[str, list[tuple[uuid.UUID, str]]] = {}  # matched whatever the capitals (lowercase key)
        self.exclusions: dict[uuid.UUID, list[str]] = {}
        self.names: dict[uuid.UUID, str] = {}

        def claim(table: dict[str, list[tuple[uuid.UUID, str]]], form: str, eid: uuid.UUID, kind: str) -> None:
            owners = table.setdefault(form, [])
            if all(o != eid for o, _ in owners):
                owners.append((eid, kind))

        for e in entities:
            self.names[e.id] = e.name
            forms = [(e.name, "exact")] + [(a, "alias") for a in e.aliases] + (
                [(firsts[e.id], "alias")] if e.id in firsts else [])
            for f, kind in forms:
                f = f.strip()
                if not f:
                    continue
                if e.match_case:
                    for v in article_forms(f):
                        claim(exact, v, e.id, kind)
                else:
                    claim(loose, f.lower(), e.id, kind)
            if e.exclusions:
                self.exclusions[e.id] = [x.lower() for x in e.exclusions if x.strip()]
        # an entry's own name is never shared: where it is also someone's other name or first name, the name wins
        for table in (exact, loose):
            for form, owners in table.items():
                if len(owners) > 1 and any(k == "exact" for _, k in owners):
                    table[form] = [o for o in owners if o[1] == "exact"]
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
        for f, [(eid, _), *_others] in [*exact.items(), *loose.items()]:
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

    def claimants(self, form: str) -> list[tuple[uuid.UUID, str]]:
        """The entries a form (as written, without an ending) means, from both lists."""
        owners = list(self.exact.get(form, []))
        for o in self.loose.get(form.lower(), []):
            if all(eid != o[0] for eid, _ in owners):
                owners.append(o)
        return owners

    def choices(self, text: str) -> list[Choice]:
        """The choice lines in a text: margin-note lines that start with a shared name and a colon."""
        out: list[Choice] = []
        for m in CHOICE_RE.finditer(text):
            owners = [eid for eid, _ in self.claimants(m.group(1))]
            if len(owners) < 2:
                continue
            words = [w.strip() for w in m.group(2).split(",") if w.strip()]
            if words == ["?"]:
                out.append(Choice(m.start(), m.end(), m.group(1).lower(), None))
                continue
            chosen: list[uuid.UUID] = []
            for w in words:
                lw = w.lower()
                match = [o for o in owners if self.names[o].lower() == lw] or [
                    o for o in owners if lw in (x.lower() for x in WORD_RE.findall(self.names[o]))]
                if len(match) != 1:
                    chosen = []
                    break
                if match[0] not in chosen:
                    chosen.append(match[0])
            out.append(Choice(m.start(), m.end(), m.group(1).lower(), tuple(chosen)))
        return out

    def scan(self, text: str, skip_entity: uuid.UUID | None = None,
             choices: list[Choice] | None = None) -> list[Found]:
        hits: list[tuple[int, int, list[tuple[uuid.UUID, str]], str, str]] = []
        if self.exact_re is not None:
            for m in self.exact_re.finditer(text):
                hits.append((m.start(), m.end(), self.exact[m.group(1)], m.group(0), m.group(1).lower()))
        if self.loose_re is not None:
            for m in self.loose_re.finditer(text):
                hits.append((m.start(), m.end(), self.loose[m.group(1).lower()], m.group(0), m.group(1).lower()))
        # overlapping matches from the two lists: the longer one wins; the same span in both: everyone claiming it
        hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
        found: list[Found] = []
        taken: list[tuple[int, int]] = []
        lower = text.lower()
        cache: dict[uuid.UUID, list[tuple[int, int]]] = {}
        spans: list[tuple[int, int, list[tuple[uuid.UUID, str]], str, str]] = []
        for start, end, owners, matched, key in hits:
            owners = [o for o in owners if not self._excluded(lower, o[0], start, end, cache)]
            if not owners:
                continue
            if spans and (start, end) == spans[-1][:2]:
                spans[-1][2].extend(o for o in owners if all(o[0] != x for x, _ in spans[-1][2]))
                continue
            if taken and start < taken[-1][1]:
                continue
            taken.append((start, end))
            spans.append((start, end, list(owners), matched, key))
        settled = sorted((c for c in choices or [] if c.ids != ()), key=lambda c: c.end)
        for start, end, owners, matched, key in spans:
            if len(owners) == 1:
                eid, kind = owners[0]
                if eid != skip_entity:
                    found.append(Found(eid, start, end, matched, kind))
                continue
            if skip_entity is not None and any(eid == skip_entity for eid, _ in owners):
                continue  # in an entry's own notes, its own shared name means itself
            choice = next((c for c in reversed(settled) if c.key == key and c.end <= start), None)
            ids = [eid for eid in (choice.ids or ()) if any(eid == o for o, _ in owners)] if choice else []
            if ids:
                found.extend(Found(eid, start, end, matched, "alias") for eid in ids)
            else:
                found.extend(Found(eid, start, end, matched, "ambiguous") for eid, _ in owners)
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


def scan_source(m: Matcher, table: str, text: str, source_id: uuid.UUID | None = None) -> list[Found]:
    """The mentions in one stored text. A chapter is read without its margin notes and a journal entry without its
    choice lines (its other `%%` lines are ordinary text); both follow their choice lines."""
    if table == "chapter":
        return m.scan(story_text(text), choices=m.choices(text))
    if table == "journal":
        choices = m.choices(text)
        for c in choices:
            text = text[:c.start] + " " * (c.end - c.start) + text[c.end:]
        return m.scan(text, choices=choices)
    return m.scan(text, skip_entity=source_id if table == "entity" else None)


def refresh_source(db: Session, world_id: uuid.UUID, table: str, source_id: uuid.UUID, text: str,
                   matcher: Matcher | None = None) -> None:
    """Rescan one text after it was saved."""
    m = matcher or matcher_for(db, world_id)
    _store(db, world_id, table, source_id, scan_source(m, table, text, source_id))


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
        _store(db, world_id, "journal", j.id, scan_source(m, "journal", j.body))
    for e in db.scalars(select(Entity).where(Entity.world_id == world_id)):
        _store(db, world_id, "entity", e.id, m.scan(e.body, skip_entity=e.id))
    for c in db.scalars(select(Chapter).join(Project, Project.id == Chapter.project_id)
                        .where(Project.world_id == world_id)):
        _store(db, world_id, "chapter", c.id, scan_source(m, "chapter", c.body))
