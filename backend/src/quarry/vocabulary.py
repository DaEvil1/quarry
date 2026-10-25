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
    # a spirit in someone, and lineages across centuries where the generations between aren't recorded
    ("character", "character", "possesses", "possessed by"),
    ("character", "character", "ancestor of", "descendant of"),
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
    # character – species: what someone is (several allowed, time-bounded), and an outward form or disguise
    ("character", "species", "is a", "includes"),
    ("character", "species", "appears as", "the guise of"),
    # character – object
    ("character", "object", "owns", "owned by"),
    ("character", "object", "carries", "carried by"),
    ("character", "object", "made", "made by"),
    ("character", "object", "seeks", "sought by"),
    ("character", "object", "lost", "lost by"),
    ("character", "object", "guards", "guarded by"),
    # character – event: a witness was there and saw it (not the same as taking part)
    ("character", "event", "witnessed", "witnessed by"),
    # place – place
    ("place", "place", "inside", "contains"),
    ("place", "place", "borders", None),
    ("place", "place", "road to", None),
    ("place", "place", "sea route to", None),
    # directions, read by the chart (north is up): each pair is one type and its reverse
    ("place", "place", "north of", "south of"),
    ("place", "place", "east of", "west of"),
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
    # species – species / place, and the cultures and factions of a species
    ("species", "species", "descended from", "ancestor of"),
    ("species", "species", "related to", None),
    ("species", "species", "preys on", "prey of"),
    ("species", "place", "native to", "home of"),
    ("culture", "species", "culture of", "has culture"),
    ("faction", "species", "made up of", "makes up"),
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

# the relationship types whose relationships carry a role in the group: on to start, by label (any capitals)
HAS_ROLE_LABELS = ("member of", "leads", "serves", "works at")

# fact labels offered when adding a fact (anything else can be typed). A list in the code, not stored per world, so
# every world offers a new one at once. Gender is a field on characters, not a fact; "pronouns" stays, for nuance.
# "name meaning" is offered on every kind (a term's "meaning" stays the meaning of the term).
SUGGESTED_FACTS: dict[str, list[str]] = {
    "character": ["status", "age", "role", "appearance", "eye colour", "hair", "voice", "occupation", "pronunciation",
                  "pronouns", "name meaning"],
    "place": ["type", "population", "climate", "ruler", "known for", "pronunciation", "name meaning"],
    "faction": ["type", "size", "motto", "symbol", "goal", "name meaning"],
    "culture": ["language", "faith", "customs", "homeland", "name meaning"],
    # a species is described with facts, not fields (docs/SPEC.md §13.3)
    "species": ["form", "sapient", "size", "lifespan", "habitat", "diet", "reproduction", "appearance",
                "pronunciation", "name meaning"],
    # "when" is a field on events now (docs/SPEC.md §13.2.1); existing "when" facts stay, as facts
    "event": ["type", "outcome", "name meaning"],
    "object": ["material", "appearance", "power", "age", "name meaning"],
    "term": ["meaning", "usage", "name meaning"],
    "other": ["name meaning"],
}

# values offered for a label after the values in use (without counts), so a new world has something to pick from.
# Not stored, like the suggested facts: every world gets them at once. Era, birth and death are read by the Timeline,
# the place types by the chart.
SUGGESTED_VALUES: dict[tuple[str, str], list[str]] = {
    ("place", "type"): ["world", "plane", "land", "region", "sea", "lake", "river", "island", "mountain", "forest",
                        "reef", "city", "town", "village", "district", "building", "room"],
    ("event", "type"): ["era", "war", "battle", "founding", "treaty", "betrayal", "birth", "death", "festival",
                        "wedding", "coronation"],
    ("species", "form"): ["humanoid", "beast", "aquatic", "amorphous", "spirit", "plant"],
    ("species", "sapient"): ["yes", "no", "partly"],
    ("species", "size"): ["tiny", "small", "human-sized", "large", "huge"],
    ("species", "diet"): ["plants", "meat", "anything", "none"],
}


def fits(kind: str, side: str) -> bool:
    return side == "*" or side == kind


def reads_same(a: tuple[str, str, str, str | None], b: tuple[str, str, str, str | None]) -> bool:
    """Two types read the same: they join the same pair of kinds (either way round, "*" fitting any) and share a
    reading, whatever the capitals (docs/SPEC.md §13.3: a world that has one already doesn't get another)."""
    def words(t):  # type: ignore[no-untyped-def]
        return {" ".join(x.split()).lower() for x in (t[2], t[3] or "") if x and x.strip()}
    same_way = fits(a[0], b[0]) and fits(a[1], b[1]) or fits(b[0], a[0]) and fits(b[1], a[1])
    other_way = fits(a[0], b[1]) and fits(a[1], b[0]) or fits(b[1], a[0]) and fits(b[0], a[1])
    return (same_way or other_way) and bool(words(a) & words(b))


def place_new_types(existing: list[tuple[str, str, str, str | None, int]],
                    wanted: list[tuple[str, str, str, str | None]]) -> list[tuple[tuple[str, str, str, str | None], int]]:
    """Where each wanted type goes in a world's list, as (type, position): at the end of its pair (after the last type
    joining the same two kinds), or at the end of the list; none for a type the world reads the same already. Positions
    are for inserting one after another, in order, shifting what follows."""
    rows = [list(r) for r in existing]
    out = []
    for t in wanted:
        if any(reads_same((a, b, label, reverse), t) for a, b, label, reverse, _ in rows):
            continue
        pair = [p for a, b, _, _, p in rows if (a, b) == (t[0], t[1])]
        position = max(pair) + 1 if pair else max((r[4] for r in rows), default=-1) + 1
        for r in rows:
            if r[4] >= position:
                r[4] += 1
        rows.append([*t, position])
        out.append((t, position))
    return out
