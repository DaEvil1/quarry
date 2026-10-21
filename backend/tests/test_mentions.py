"""The name matcher on its own: exact names, aliases, endings, multi-word names and near misses."""

from __future__ import annotations

import uuid

from quarry.mentions import Matcher
from quarry.models import Entity


def entity(name: str, *aliases: str, kind: str = "character") -> Entity:
    return Entity(id=uuid.uuid4(), name=name, aliases=list(aliases), kind=kind, body="", match_case=True,
                  first_name_alias=True, exclusions=[])


VARREN = entity("Varren", "the Grey Keeper")
HARBOUR = entity("Old Harbour", kind="place")
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


def test_capitals_optional_per_entry():
    rose = entity("Rose")
    rose.match_case = False
    m = Matcher([rose])
    assert [f.matched for f in m.scan("rose and Rose and ROSE's")] == ["rose", "Rose", "ROSE's"]


def test_first_names_of_characters():
    hale = entity("Varren Hale")
    lord = entity("Lord Mordoch")
    twins = [entity("Ada Kell"), entity("Ada Morn")]
    m = Matcher([hale, lord, *twins])
    # titles are skipped; a first name two people share belongs to neither; "The …" names have none
    assert [(f.matched, f.kind) for f in m.scan("Varren met Lord Mordoch. Mordoch nodded. Ada left.")] == [
        ("Varren", "alias"), ("Lord Mordoch", "exact"), ("Mordoch", "alias")]
    assert Matcher([entity("The Grey Keeper")]).scan("Grey skies") == []
    hale.first_name_alias = False
    assert [f.matched for f in Matcher([hale]).scan("Varren and Varren Hale")] == ["Varren Hale"]
    # a first name that is someone else's name is not taken over
    assert {f.entity_id for f in Matcher([hale, entity("Varren")]).scan("Varren")} != {hale.id}


def test_not_in_this_sense():
    rose = entity("Rose")
    rose.match_case = False
    rose.exclusions = ["rose garden", "the sun rose"]
    found = Matcher([rose]).scan("Rose walked to the rose garden as the sun rose.")
    assert [(f.start, f.matched) for f in found] == [(0, "Rose")]


def test_longest_match_wins_across_capitals_settings():
    harbour = entity("Old Harbour", kind="place")
    harbour.match_case = False
    old = entity("Old")
    found = Matcher([harbour, old]).scan("at old harbour, Old waits")
    assert [(f.matched, f.entity_id) for f in found] == [("old harbour", harbour.id), ("Old", old.id)]
