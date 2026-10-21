"""The relationship types a world starts with, and the facts suggested per kind.

A type joins a kind on the A side to a kind on the B side ("*" is any kind). It reads forward as `label` (Varren
*parent of* Isolde) and backward as `reverse` (Isolde *child of* Varren); a symmetric type reads the same both ways.
A world's types can be renamed, added or removed; these are only the starting set (docs/WORLD-MODEL.md §3).
"""

from __future__ import annotations

# (a_kind, b_kind, label, reverse label or None when symmetric)
STARTING_TYPES: list[tuple[str, str, str, str | None]] = [
    # character – character
    ("character", "character", "parent of", "child of"),
    ("character", "character", "sibling of", None),
    ("character", "character", "married to", None),
    ("character", "character", "lover of", None),
    ("character", "character", "friend of", None),
    ("character", "character", "rival of", None),
    ("character", "character", "enemy of", None),
    ("character", "character", "serves", "served by"),
    ("character", "character", "mentor of", "student of"),
    ("character", "character", "knows", None),
    ("character", "character", "has met", None),
    # character – anything: what someone knows about
    ("character", "*", "knows about", "known to"),
    # character – place
    ("character", "place", "lives in", "home of"),
    ("character", "place", "born in", "birthplace of"),
    ("character", "place", "rules", "ruled by"),
    ("character", "place", "works at", "workplace of"),
    ("character", "place", "imprisoned in", "prison of"),
    ("character", "place", "visits", "visited by"),
    # character – faction
    ("character", "faction", "member of", "has member"),
    ("character", "faction", "leads", "led by"),
    ("character", "faction", "founded", "founded by"),
    ("character", "faction", "opposes", "opposed by"),
    # character – culture
    ("character", "culture", "belongs to", "includes"),
    ("character", "culture", "converted to", "converted"),
    # character – object
    ("character", "object", "owns", "owned by"),
    ("character", "object", "carries", "carried by"),
    ("character", "object", "made", "made by"),
    ("character", "object", "seeks", "sought by"),
    ("character", "object", "lost", "lost by"),
    ("character", "object", "guards", "guarded by"),
    # place – place
    ("place", "place", "inside", "contains"),
    ("place", "place", "borders", None),
    ("place", "place", "road to", None),
    ("place", "place", "sea route to", None),
    # faction – faction
    ("faction", "faction", "allied with", None),
    ("faction", "faction", "at war with", None),
    ("faction", "faction", "vassal of", "overlord of"),
    ("faction", "faction", "splinter of", "split into"),
    # faction – place / object / culture
    ("faction", "place", "controls", "controlled by"),
    ("faction", "place", "based in", "base of"),
    ("faction", "place", "claims", "claimed by"),
    ("faction", "object", "owns", "owned by"),
    ("object", "faction", "symbol of", "has as symbol"),
    ("faction", "object", "seeks", "sought by"),
    ("faction", "object", "guards", "guarded by"),
    ("faction", "culture", "rooted in", "root of"),
    ("faction", "culture", "persecutes", "persecuted by"),
    # object – object / place / culture
    ("object", "object", "part of", "has part"),
    ("object", "object", "key to", "opened by"),
    ("object", "object", "copy of", "original of"),
    ("object", "object", "paired with", None),
    ("object", "place", "kept at", "keeps"),
    ("object", "place", "hidden in", "hides"),
    ("object", "place", "made in", "where was made"),
    ("object", "place", "lost at", "where was lost"),
    ("object", "culture", "sacred to", "holds sacred"),
    ("culture", "object", "made", "made by"),
    # culture – place / culture
    ("culture", "place", "native to", "home of"),
    ("culture", "place", "spread to", "reached by"),
    ("culture", "culture", "descended from", "ancestor of"),
    ("culture", "culture", "related to", None),
    # terms (lore) and events
    ("term", "*", "applies to", "governed by"),
    ("*", "term", "practises", "practised by"),
    ("term", "*", "originated in", "origin of"),
    ("event", "*", "involved", "took part in"),
    ("event", "place", "happened at", "scene of"),
    ("event", "*", "caused", "caused by"),
    ("event", "event", "followed from", "led to"),
    # any pair, for when the connection doesn't have a name yet
    ("*", "*", "linked to", None),
]

# fact labels offered when adding a fact (anything else can be typed)
SUGGESTED_FACTS: dict[str, list[str]] = {
    "character": ["status", "age", "role", "appearance", "eye colour", "hair", "voice", "occupation"],
    "place": ["type", "population", "climate", "ruler", "known for"],
    "faction": ["type", "size", "motto", "symbol", "goal"],
    "culture": ["language", "faith", "customs", "homeland"],
    "event": ["when", "outcome"],
    "object": ["material", "appearance", "power", "age"],
    "term": ["meaning", "usage"],
    "other": [],
}
