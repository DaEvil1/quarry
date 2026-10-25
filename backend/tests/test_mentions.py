"""The name matcher on its own: exact names, aliases, endings, multi-word names and near misses."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from quarry.mentions import Matcher, first_name_aliases, scan_source
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


def test_a_leading_article_matches_either_way():
    wardens = entity("The River Wardens", "the Warden", kind="faction")
    m = Matcher([wardens])
    assert [f.matched for f in m.scan("The flag of the River Wardens. The Warden spoke. the river wardens")] == [
        "the River Wardens", "The Warden"]


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


def test_a_word_of_a_longer_name_is_a_near_miss_only_within_that_name():
    # the same cases as frontend/src/matcher.test.ts
    tamsin, oskar = entity("Tamsin Vey"), entity("Oskar Vey")
    years = entity("The Lock Years", kind="event")
    harbour = entity("Old Harbour", "Harbour Lights", kind="place")
    m = Matcher([tamsin, oskar, years, harbour])
    # a first name stands alone: its misspelling is one anywhere
    assert kinds("Oscar rowed. Tamsen waited.", m) == [("Oscar", "near_miss", oskar.id), ("Tamsen", "near_miss", tamsin.id)]
    # "Years" alone names nothing, so "Fears" is no misspelling of it; within the name it is
    assert kinds("Fears: that the delta is changing. Old Fears.", m) == []
    assert kinds("In the Lock Yeras. The Lock Yeras.", m) == [("Yeras", "near_miss", years.id)] * 2
    assert kinds("Harbor lights. Harbor Lightsome. Harbor. Sea-Old Harbor.", m) == []
    assert kinds("At Old Harbor's edge, under Harbor Lights.", m) == [
        ("Harbor", "near_miss", harbour.id), ("Harbor", "near_miss", harbour.id)]
    # without a first name, only the whole name with a word misspelt
    oskar.first_name_alias = False
    assert kinds("Oscar rowed. Oscar Vey rowed.", Matcher([oskar])) == [("Oscar", "near_miss", oskar.id)]
    assert [f.start for f in Matcher([oskar]).scan("Oscar rowed. Oscar Vey rowed.")] == [13]
    # a name matched whatever the capitals: the rest of it in any capitals
    loose = entity("Old Harbour", kind="place")
    loose.match_case = False
    assert kinds("OLD Harbor, old Harbor. Harbor.", Matcher([loose])) == [
        ("Harbor", "near_miss", loose.id), ("Harbor", "near_miss", loose.id)]


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
    # titles are skipped; a first name two people share is shared (ambiguous for each); "The …" names have none
    assert [(f.matched, f.kind) for f in m.scan("Varren met Lord Mordoch. Mordoch nodded. Ada left.")] == [
        ("Varren", "alias"), ("Lord Mordoch", "exact"), ("Mordoch", "alias"), ("Ada", "ambiguous"),
        ("Ada", "ambiguous")]
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


# shared names (docs/SPEC.md §14.10): the same table of cases as frontend/src/matcher.test.ts
CASES = json.loads((Path(__file__).parents[2] / "frontend/src/world/sharednames.cases.json").read_text("utf-8"))
SHARED = {e["id"]: Entity(id=uuid.uuid5(uuid.NAMESPACE_URL, e["id"]), name=e["name"], kind=e["kind"],
                          aliases=e.get("aliases", []), body="", match_case=e.get("match_case", True),
                          first_name_alias=True, exclusions=[]) for e in CASES["entities"]}
SHARED_KEY = {e.id: k for k, e in SHARED.items()}
SHARED_M = Matcher(SHARED.values())


def test_shared_first_names_are_given_to_each_claimant():
    assert {SHARED_KEY[eid]: first for eid, first in first_name_aliases(SHARED.values()).items()} == \
        CASES["first_names"]


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["about"])
def test_shared_names(case):
    found = scan_source(SHARED_M, case.get("source", "chapter"), case["text"])
    assert [[f.matched, f.kind, SHARED_KEY[f.entity_id]] for f in found] == case["expect"]


def test_shared_name_in_an_entrys_own_notes_means_itself():
    found = scan_source(SHARED_M, "entity", "Isolde keeps the lamp. Isolde Senn does not.", SHARED["marr"].id)
    assert [(f.matched, f.kind, SHARED_KEY[f.entity_id]) for f in found] == [("Isolde Senn", "exact", "senn")]


def test_the_branching_pattern_matches_what_the_plain_alternation_did():
    """The names are compiled letter by letter (fast with thousands of names); it must find exactly what the plain
    alternation of them, longest first, found."""
    import random
    import re

    from quarry.mentions import SUFFIX, trie_pattern

    rnd = random.Random(5)
    syl = ["ar", "an", "a", "bel", "be", "cor", "c", "dan", "el", "e", "is", "or", "o", "s", "’s"]
    names = sorted({"".join(rnd.choice(syl) for _ in range(rnd.randint(1, 3))).capitalize()
                    + (" " + rnd.choice(syl).capitalize() if rnd.random() < .3 else "") for _ in range(300)})
    names += ["The Grey Keeper", "the Grey Keeper", "Old Harbour", "Old"]
    words = [*names, *(n.lower() for n in names[:50]), "and", "Arx", "Belx", "O'", "-", "s"]
    for flags, forms in ((0, names), (re.IGNORECASE, [n.lower() for n in names])):
        plain = re.compile(r"(?<![\w'’-])(" + "|".join(re.escape(f) for f in sorted(forms, key=len, reverse=True))
                           + r")" + SUFFIX + r"(?![\w])", flags)
        trie = re.compile(r"(?<![\w'’-])(" + trie_pattern(forms) + r")" + SUFFIX + r"(?![\w])", flags)
        for _ in range(300):
            text = "".join(rnd.choice(words) + rnd.choice([" ", "", "'s ", ". ", "-", "s "]) for _ in range(40))
            assert [(m.span(), m.group(1)) for m in plain.finditer(text)] == \
                [(m.span(), m.group(1)) for m in trie.finditer(text)], text
