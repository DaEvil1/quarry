"""The name matcher on its own: exact names, aliases, endings, multi-word names and near misses."""

from __future__ import annotations

import uuid

from quarry.mentions import Matcher
from quarry.models import Entity


def entity(name: str, *aliases: str) -> Entity:
    return Entity(id=uuid.uuid4(), name=name, aliases=list(aliases), kind="character", body="")


VARREN = entity("Varren", "the Grey Keeper")
HARBOUR = entity("Old Harbour")
ISOLDE = entity("Isolde")
MORDOCH = entity("Mordoch")
M = Matcher([VARREN, HARBOUR, ISOLDE, MORDOCH])


def kinds(text: str, matcher: Matcher = M):
    return [(f.matched, f.kind, f.entity_id) for f in matcher.scan(text)]


def test_exact_names_with_endings():
    assert kinds("Varren walked. The Varrens argued. Varren's lamp, Varren’s boat.") == [
        ("Varren", "exact", VARREN.id),
        ("Varrens", "exact", VARREN.id),
        ("Varren's", "exact", VARREN.id),
        ("Varren’s", "exact", VARREN.id),
    ]


def test_aliases_and_multi_word_names():
    assert kinds("They met the Grey Keeper at Old Harbour.") == [
        ("the Grey Keeper", "alias", VARREN.id),
        ("Old Harbour", "exact", HARBOUR.id),
    ]


def test_word_boundaries_and_case():
    # part of a longer word, or not capitalised: not a mention
    assert kinds("Varrenholm is far. varren is lowercase.") == []


def test_near_misses():
    # a wrong letter, a swapped pair, a missing letter
    assert kinds("Isolda wrote to Modroch and Varen.") == [
        ("Isolda", "near_miss", ISOLDE.id),
        ("Modroch", "near_miss", MORDOCH.id),
        ("Varen", "near_miss", VARREN.id),
    ]


def test_near_miss_possessive_flags_the_name_part():
    (f,) = M.scan("Modroch's ship")
    assert (f.matched, f.start, f.end) == ("Modroch", 0, 7)


def test_not_flagged():
    # short words, words that are part of a name, other capitals, and words marked "not a typo"
    assert kinds("Isle. Harbour lights. Ocean. Thursday.") == []
    assert kinds("Isolda", Matcher([ISOLDE], ignored=["Isolda"])) == []
    assert kinds("ISOLDE shouted") == []


def test_far_words_are_not_near_misses():
    assert kinds("Mountains and Valleys") == []


def test_an_entity_does_not_mention_itself():
    assert M.scan("Varren is the keeper", skip_entity=VARREN.id) == []


def test_empty_world():
    assert Matcher([]).scan("Anything At All") == []
