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

Mentions are recomputed whenever a text is saved. When names change (an entry added, renamed or deleted, its other
names, kinds, capitals or "not in this sense" phrases, or a "not a typo" word), only the texts the change can reach
are rescanned: those that contain a name or a word of a name that changed (a shared name changes with any of its
claimants' names, which its choice lines are read by), or a word close enough to one to be a near miss of it
(`refresh_names`). A world grows to millions of words, and rescanning all of it for every new entry took seconds,
then minutes.
"""

from __future__ import annotations

import re
import threading
import uuid
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass

from rapidfuzz import process
from rapidfuzz.distance import OSA
from sqlalchemy import delete, select
from sqlalchemy import text as sql
from sqlalchemy.orm import Session

from .margin import story_text
from .models import Chapter, Decision, Entity, Item, JournalEntry, Mention, NameIgnore, Project, World

SUFFIX = r"(?:'s|’s|s)?"
# what counts as naming an entry: a name or other name, or a shared name settled for it; an ambiguous one never counts
COUNTED = ("exact", "alias")
# bumped when the matcher reads texts differently: worlds whose stored mentions are older are worked out again
MENTIONS_VERSION = 1
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


def trie_pattern(forms: Iterable[str]) -> str:
    """The names as one pattern that branches letter by letter ("Old H(?:arbour|all)"), trying the longer names first.
    It matches exactly what the plain alternation of them, longest first, matches; but a regular expression tries a
    plain alternation's names one by one at every place in the text, and a world has thousands of them."""
    root: dict = {}
    for f in forms:
        node = root
        for ch in f:
            node = node.setdefault(ch, {})
        node[""] = {}

    def emit(node: dict) -> str:
        alts = [re.escape(ch) + emit(node[ch]) for ch in sorted(node) if ch]
        if not alts:
            return ""
        if len(alts) == 1 and "" not in node:
            return alts[0]
        # a name that ends here is tried after every longer one through here
        return "(?:" + "|".join(alts) + ("|)" if "" in node else ")")

    return emit(root)


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
            # the longest name that fits wins, so "Old Harbour" wins over "Old"
            body = trie_pattern(forms)
            if not body:
                return None
            return re.compile(r"(?<![\w'’-])(" + body + r")" + SUFFIX + r"(?![\w])", flags)

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
        # the candidates by length (a word is only compared with those it could be one or two edits from), the order
        # they were met in (ties go to the first), and each word's verdict so far
        self.by_length: dict[int, list[str]] = {}
        for w in self.candidates:
            self.by_length.setdefault(len(w), []).append(w)
        self.order = {w: i for i, w in enumerate(self.candidates)}
        self.near_cache: dict[str, str | None] = {}

    def nearest(self, base: str) -> str | None:
        """The candidate `base` is most likely a misspelling of (the first met, of equally close ones), or None."""
        if base in self.near_cache:
            return self.near_cache[base]
        limit = 1 if len(base) <= 6 else 2
        best: tuple[float, int, str] | None = None
        for n in range(len(base) - limit, len(base) + limit + 1):
            bucket = self.by_length.get(n)
            hit = process.extractOne(base, bucket, scorer=OSA.distance, score_cutoff=limit) if bucket else None
            if hit is not None and (best is None or (hit[1], self.order[hit[0]]) < best[:2]):
                best = (hit[1], self.order[hit[0]], hit[0])
        if len(self.near_cache) > 50_000:
            self.near_cache.clear()
        self.near_cache[base] = best[2] if best else None
        return self.near_cache[base]

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
            # the words come in order, and so do the names found (they don't overlap): one pass over both
            t = 0
            for m in WORD_RE.finditer(text):
                word = m.group(0)
                while t < len(taken) and taken[t][1] <= m.start():
                    t += 1
                if not word[0].isupper() or (t < len(taken) and taken[t][0] <= m.start()):
                    continue
                base = POSSESSIVE_RE.sub("", word)
                if len(base) < NEAR_MIN or base in self.ignored or word in self.ignored:
                    continue
                if base.lower() in self.known_lower:
                    continue
                best = self.nearest(base)
                if best is None:
                    continue
                eid = self.word_owner[best]
                if eid != skip_entity:
                    found.append(Found(eid, m.start(), m.start() + len(base), base, "near_miss"))
        found.sort(key=lambda f: f.start)
        return found


# everything a matcher is built from, hashed by the database: kinds (a character's first name), names, other names,
# capitals, first names, "not in this sense" phrases and "not a typo" words, in the order the matcher meets them
NAMES_KEY = sql("""
SELECT md5(coalesce(string_agg(concat_ws(chr(31), id::text, kind, array_to_string(also_kinds, chr(30)), name,
                                         array_to_string(aliases, chr(30)), match_case::text, first_name_alias::text,
                                         array_to_string(exclusions, chr(30))),
                               chr(29) ORDER BY created_at, id), ''))
    || md5(coalesce((SELECT string_agg(token, chr(29) ORDER BY token) FROM name_ignores WHERE world_id = :w), ''))
FROM entities WHERE world_id = :w
""")
_matchers: OrderedDict[uuid.UUID, tuple[str, Matcher]] = OrderedDict()
_matchers_lock = threading.Lock()
KEEP_MATCHERS = 4


def matcher_for(db: Session, world_id: uuid.UUID) -> Matcher:
    """The world's matcher as its names are now (in this transaction). Built once per set of names and kept: a chapter
    save in a world of thousands of entries would otherwise spend most of its time building it again."""
    key = db.execute(NAMES_KEY, {"w": world_id}).scalar_one()
    with _matchers_lock:
        kept = _matchers.get(world_id)
        if kept is not None and kept[0] == key:
            _matchers.move_to_end(world_id)
            return kept[1]
    # oldest first: when two entries claim a name, or two names are equally close to a near miss, the same one wins on
    # every build (and a rescan after a change can tell which texts that touches)
    entities = db.scalars(select(Entity).where(Entity.world_id == world_id)
                          .order_by(Entity.created_at, Entity.id)).all()
    ignored = db.scalars(select(NameIgnore.token).where(NameIgnore.world_id == world_id)).all()
    m = Matcher(entities, ignored)
    with _matchers_lock:
        _matchers[world_id] = (key, m)
        _matchers.move_to_end(world_id)
        while len(_matchers) > KEEP_MATCHERS:
            _matchers.popitem(last=False)
    return m


def _rows(world_id: uuid.UUID, table: str, source_id: uuid.UUID, found: list[Found]) -> list[dict]:
    return [{"world_id": world_id, "source_table": table, "source_id": source_id, "entity_id": f.entity_id,
             "start": f.start, "end": f.end, "matched_text": f.matched[:200], "kind": f.kind} for f in found]


COLUMNS = ("world_id", "source_table", "source_id", "entity_id", "start", "end", "matched_text", "kind")


def _insert(db: Session, rows: list[dict]) -> None:
    """Store mentions with COPY, in this transaction: a world rescan writes tens of thousands of them, and an INSERT
    per row (what an ORM or an executemany sends) took seconds."""
    if not rows:
        return
    db.flush()
    raw = db.connection().connection.driver_connection
    columns = ", ".join(f'"{c}"' for c in COLUMNS)
    with raw.cursor() as cur, cur.copy(f"COPY mentions ({columns}) FROM STDIN") as copy:
        for r in rows:
            copy.write_row([r[c] for c in COLUMNS])


def _forget(db: Session, sources: list[tuple[str, uuid.UUID]]) -> None:
    for table in {t for t, _ in sources}:
        ids = [sid for t, sid in sources if t == table]
        for i in range(0, len(ids), 5000):
            db.execute(delete(Mention).where(Mention.source_table == table, Mention.source_id.in_(ids[i:i + 5000])))


def _lock(db: Session, world_id: uuid.UUID) -> None:
    """One writer of a world's mentions at a time, until the transaction ends: two saves rescanning overlapping texts
    at once would otherwise wait on each other's rows and could deadlock."""
    db.execute(sql("SELECT pg_advisory_xact_lock(:k)"), {"k": world_id.int % (2 ** 63)})


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
    found = scan_source(m, table, text, source_id)
    _lock(db, world_id)
    _forget(db, [(table, source_id)])
    _insert(db, _rows(world_id, table, source_id, found))


def forget_source(db: Session, table: str, source_id: uuid.UUID) -> None:
    db.execute(delete(Mention).where(Mention.source_table == table, Mention.source_id == source_id))


def _texts(db: Session, world_id: uuid.UUID) -> Iterable[tuple[str, uuid.UUID, str]]:
    """Every text of a world that names are found in: (source table, id, the text as stored)."""
    for table, model, column in (("item", Item, Item.body), ("decision", Decision, Decision.text),
                                 ("journal", JournalEntry, JournalEntry.body), ("entity", Entity, Entity.body)):
        for sid, body in db.execute(select(model.id, column).where(model.world_id == world_id)):
            yield table, sid, body
    for sid, body in db.execute(select(Chapter.id, Chapter.body).join(Project, Project.id == Chapter.project_id)
                                .where(Project.world_id == world_id)):
        yield "chapter", sid, body


def refresh_world(db: Session, world_id: uuid.UUID) -> None:
    """Rescan every text of a world: a restored one, or one whose mentions are older than the matcher."""
    m = matcher_for(db, world_id)
    w = db.get(World, world_id)
    if w is not None:
        w.mentions_version = MENTIONS_VERSION
    _lock(db, world_id)
    db.execute(delete(Mention).where(Mention.world_id == world_id))
    rows: list[dict] = []
    for table, sid, body in _texts(db, world_id):
        rows += _rows(world_id, table, sid, scan_source(m, table, body, sid))
    _insert(db, rows)


@dataclass
class Delta:
    """What a change of names can reach: names whose owner, kind or "not in this sense" phrases changed (lower case);
    single words that became or stopped being part of a name or "not a typo" (lower case); and the near-miss candidates
    that changed (as spelled)."""

    forms: set[str]
    words: set[str]
    near: list[str]

    @property
    def empty(self) -> bool:
        return not (self.forms or self.words or self.near)

    def reaches(self, text: str) -> bool:
        """Whether a scan of `text` could come out differently. Errs on the side of yes."""
        if self.forms:
            lower = text.lower()
            if any(f in lower for f in self.forms):
                return True
        if not (self.words or self.near):
            return False
        for word in {w for w in WORD_RE.findall(text) if w[0].isupper()}:
            base = POSSESSIVE_RE.sub("", word)
            if base.lower() in self.words or word.lower() in self.words:
                return True
            if self.near and len(base) >= NEAR_MIN:
                limit = 1 if len(base) <= 6 else 2
                if process.extractOne(base, self.near, scorer=OSA.distance, score_cutoff=limit) is not None:
                    return True
        return False


def delta(before: Matcher, after: Matcher) -> Delta:
    """What changed between two builds of a world's matcher."""

    def table(m: Matcher, d: dict[str, list[tuple[uuid.UUID, str]]]) -> dict[str, tuple]:
        # each form's claimants with their "not in this sense" phrases; for a shared name also their names, which its
        # choice lines are read by
        return {f: tuple((eid, kind, tuple(m.exclusions.get(eid, ())), m.names.get(eid) if len(owners) > 1 else None)
                         for eid, kind in owners) for f, owners in d.items()}

    forms: set[str] = set()
    for b, a in ((table(before, before.exact), table(after, after.exact)),
                 (table(before, before.loose), table(after, after.loose))):
        forms |= {f.lower() for f in b.keys() | a.keys() if b.get(f) != a.get(f)}
    # (shorter words are never near misses, so a change to them reaches nothing)
    words = {w for w in (before.known_lower ^ after.known_lower) | {w.lower() for w in before.ignored ^ after.ignored}
             if len(w) >= NEAR_MIN}
    # a candidate whose owner changed; and every word of a changed name, since which of two equally close candidates
    # wins depends on the order the names were met in
    changed = {w.lower() for w in before.word_owner.keys() | after.word_owner.keys()
               if before.word_owner.get(w) != after.word_owner.get(w)}
    for f in forms:
        changed |= {w for w in WORD_RE.findall(f) if len(w) >= NEAR_MIN}
    near = sorted({w for w in [*before.candidates, *after.candidates] if w.lower() in changed})
    return Delta(forms, words, near)


def refresh_names(db: Session, world_id: uuid.UUID, before: Matcher,
                  also: Iterable[tuple[str, uuid.UUID]] = ()) -> int:
    """After names changed: rescan the texts the change can reach, and those in `also` (a new entry's own page).
    `before` is the world's matcher from before the change. Answers how many texts were rescanned."""
    after = matcher_for(db, world_id)
    d = delta(before, after)
    extra = set(also)
    if d.empty and not extra:
        return 0
    _lock(db, world_id)
    changed: list[tuple[str, uuid.UUID]] = []
    rows: list[dict] = []
    for table, sid, body in _texts(db, world_id):
        if (table, sid) in extra or d.reaches(body):
            changed.append((table, sid))
            rows += _rows(world_id, table, sid, scan_source(after, table, body, sid))
    _forget(db, changed)
    _insert(db, rows)
    return len(changed)


def rescan_stale(db: Session) -> int:
    """Work out the mentions again for every world whose stored ones are older than the matcher (at startup, after an
    upgrade that reads texts differently). Committed per world; answers how many were done."""
    done = 0
    for world_id in list(db.scalars(select(World.id).where(World.mentions_version < MENTIONS_VERSION))):
        refresh_world(db, world_id)
        w = db.get(World, world_id)
        if w is not None:
            w.mentions_version = MENTIONS_VERSION
        db.commit()
        done += 1
    return done
