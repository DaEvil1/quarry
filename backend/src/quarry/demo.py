"""The demo world: a small, made-up story that uses every part of Quarry, so it can be tried without inventing
anything. It is written as the files of an export and loaded with the same code as Restore, then given the few
things an export doesn't carry (a thought stashed in a chapter, where the writer stopped, a few days of word history).
Its chapters have summaries and statuses, and a passage waits in the cuts bin.

The text is planted with what the writing companion looks for: a misspelled name (twice, so it is offered as another
spelling), a name the bible doesn't know yet, a doubled word, a TK, a margin note, a character named after their
recorded death, a point-of-view character who is never named, someone named before they are introduced, two
values of a fact at once, and characters who share sentences with no recorded relationship.

For the views of the bible (docs/SPEC.md §12) it has a family of three generations (a grandmother, her two children,
their children, so a cousin is worked out), gender set for most of them, an entry in each book's own bible, a witness,
a pronunciation, events with a type (expected for every event, so the one without it is a finding), and a label that
holds several values.

For species, roles and vocabulary (docs/SPEC.md §13.3–§13.5) it has three species (human, dog, and the marsh-wights
of the delta) with an "is a", an "appears as" and a "native to"; the Warden-Captain as a role on the River Wardens,
marked one at a time, with one clash planted; and an ancestor of the family, centuries back.

For time and restructuring (docs/SPEC.md §13.1, §13.6) its chapters are set in years: the first book in year 412, Ash
Season a year on, with a short tale set forty years before, in which Oskar (recorded dead in the present) appears
without a finding, and a last chapter outside time, where the drowned speak and Agathe (dead for twenty years) is named
without a finding either. Some of the family have births, so ages show (and Pell's age disagrees with his, planted).
Two chapters of Ash Season have an experiment across them; the first book has an experiment that only adds, a new
prologue before "The Crossing"; and the retired prologue still has a fact tied to it, with its evidence passage in it.

For history and the Timeline (docs/SPEC.md §13.2) it has a few events of history (the raising of the locks, recorded
from a passage of chapter 3 with its telling; the spring flood Agathe drowned in), two eras in their colours (the Lock
Years, and the Ash Summers nested in them), the Flood of Lanterns happening in a chapter, and a prophecy outside time.

For planning before writing (docs/SPEC.md §14.1–§14.3) its Journal goes back years: an entry of 2019, "What the
Wardens want", with a fact on the Wardens and an event (the First Toll) recorded from it as planned, the event's
passage kept as a note; an entry of 2021 with "??" markers; Hesper's trade, planned in an entry of 2014 and made canon
in "The Cartographer"; a question made from a passage of chapter 3; and a spark parked from the Journal.

For getting back in and checking (docs/SPEC.md §14.4–§14.9) it has a premise, a note for next time left in a journal
entry, an old entry with decisions and changes since, Brother Cade's death planned (a finding once "Include planned" is on),
four events joined by "caused" and "followed from" (the Mountain Fires placed after the Flood of Lanterns they caused,
which is a finding), and the Ninefold Delta, a place that is also a character. On the chart, Greywater and Marrow
Locks are pinned inside the delta (north and south), while Carrow Ferry between them is laid out automatically. The
world opens under the Writing focus; switch it to Planning on the front page to see the other layout.

For decisions with follow-ups (docs/SPEC.md §16) it has three decisions in the three states: Oskar's death settled, with
nothing to follow; Hesper's trade done, its planned fact made canon in "The Cartographer"; and Brother Cade's death one
of two to do, his death still planned from chapter 3 (which is written, so its Loose ends shows the gap and the front
page lists it under To follow through) and the task about the bells accepted.

For names shared by two entries (docs/SPEC.md §14.10) it has two Linnets, Linnet Dray and Linnet Sorrel the
lock-keeper, and "The Cartographer" calls one of them just "Linnet" before, between and after choice lines.

And a few things that test the screens' limits: an event and a place with long names, a chapter with a long title
(the last of Ash Season, in 414), five events within two years before the raising of the locks (a cluster on the
Timeline), a long era before the locks (the Open Water) with the Lock Works nested at its end, Ilse Marrow with eleven
relationships of different kinds, places nested six deep (the delta, the Reedmarch, Weirholm, the Old Wharf, the
Toll-House and a room in it), and births for seven of the characters.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .api.manuscript import words
from .api.transfer import FORMAT, KIND_FOLDERS, _doc, restore_files
from .models import Chapter, Item, ItemLink, JournalEntry, JournalNote, Project, Revision, SessionNote, User, World
from .wordhistory import word_changes
from .vocabulary import STARTING_TYPES

ROOT = "ninefold-delta-demo"
NAME = "The Ninefold Delta (demo)"
PREMISE = "A ferry-girl, a delta of nine channels, and the Wardens who would lock them."


def _p(*paragraphs: str) -> str:
    """A chapter or note: one paragraph per line, a blank line between."""
    return "\n\n".join(paragraphs) + "\n"


# ---- the bible ----------------------------------------------------------------------------------------------------

BIBLE: list[dict] = [
    {
        "id": "tamsin", "name": "Tamsin Vey", "kind": "character", "aliases": ["Tam"], "gender": "female",
        "summary": "The ferryman's daughter; seventeen, stubborn, better on the water than on land.",
        "facts": [
            {"label": "pronunciation", "value": "TAM-zin VAY"},
            {"label": "born", "value": "", "from_time": 395},
            # her age in the first book (Ash Season goes on to 414, when her birth makes her 19)
            {"label": "age", "value": "17", "until": "b1-c4"},
            {"label": "eye colour", "value": "green", "evidence": "her green eyes narrowed against the glare",
             "established_in": "b1-c1"},
            {"label": "occupation", "value": "ferry hand", "until": "b1-c2"},
            {"label": "occupation", "value": "novice at Saltreach Abbey", "from": "b1-c3"},
        ],
        "relationships": [
            {"type": "friend of", "type_kinds": ["character", "character"], "to": "pell"},
            {"type": "lives in", "type_kinds": ["character", "place"], "to": "carrow-ferry", "until": "b1-c2"},
            {"type": "lives in", "type_kinds": ["character", "place"], "to": "saltreach", "from": "b1-c3",
             "until": "b1-c4"},
            {"type": "lives in", "type_kinds": ["character", "place"], "to": "carrow-ferry", "from": "b2-c1"},
            {"type": "owns", "type_kinds": ["character", "object"], "to": "compass", "from": "b1-c3",
             "evidence": "The compass was hers now.", "established_in": "b1-c3"},
            {"type": "belongs to", "type_kinds": ["character", "culture"], "to": "delta-folk"},
            {"type": "practises", "type_kinds": ["*", "term"], "to": "tidecall"},
            {"type": "has met", "type_kinds": ["character", "character"], "to": "cade", "from": "b1-c2"},
            {"type": "is a", "type_kinds": ["character", "species"], "to": "human"},
        ],
        "is_at": [{"chapter": "b1-c1", "place": "carrow-ferry"}, {"chapter": "b1-c2", "place": "carrow-ferry"},
                  {"chapter": "b1-c3", "place": "saltreach", "note": "arrives at night"}],
        "body": _p("Learned the river before she learned to read. Keeps her father's habits: counts the bells, "
                   "watches the reeds for wind.",
                   "Wants: to keep the ferry. Fears: that the delta is changing faster than she can learn it."),
    },
    {
        "id": "oskar", "name": "Oskar Vey", "kind": "character", "gender": "male",
        "summary": "Tamsin's father, the ferryman at Carrow Ferry. Drowns on the night of the Flood of Lanterns.",
        "facts": [
            {"label": "occupation", "value": "ferryman"},
            {"label": "born", "value": "", "from_time": 350, "from_approx": True},
            {"label": "status", "value": "alive"},
            {"label": "status", "value": "dead", "from": "b1-c3", "evidence": "The river kept him.",
             "established_in": "b1-c2"},
        ],
        "relationships": [
            {"type": "parent of", "type_kinds": ["character", "character"], "to": "tamsin"},
            {"type": "lives in", "type_kinds": ["character", "place"], "to": "carrow-ferry"},
            {"type": "owns", "type_kinds": ["character", "object"], "to": "compass", "until": "b1-c2"},
            {"type": "opposes", "type_kinds": ["character", "faction"], "to": "wardens"},
        ],
        "body": _p("Quiet, funny when he forgets to be careful. Never paid the Wardens' toll on time."),
    },
    # the family: Agathe's children are Oskar and Linnet, so Tamsin and Corin are cousins (worked out, not recorded)
    {
        "id": "agathe", "name": "Agathe Vey", "kind": "character", "gender": "female",
        "summary": "Oskar's mother, the ferrywoman before him; drowned in a spring flood long before the story.",
        "facts": [{"label": "born", "value": "", "from_time": 322}, {"label": "status", "value": "dead", "from_time": 390}],
        "relationships": [
            {"type": "parent of", "type_kinds": ["character", "character"], "to": "oskar"},
            {"type": "parent of", "type_kinds": ["character", "character"], "to": "linnet"},
        ],
        "body": _p("Built the ferry house on its stilts. Tamsin has her hands, everyone says."),
    },
    {
        # the family goes back further than anyone recorded: the generations between aren't known
        "id": "wenna", "name": "Wenna the Ferrywoman", "kind": "character", "gender": "female",
        "summary": "The first to run a ferry at the widest crossing, centuries ago; the Veys say they come from her.",
        "facts": [{"label": "status", "value": "dead"}],
        "relationships": [{"type": "ancestor of", "type_kinds": ["character", "character"], "to": "agathe"}],
        "body": _p(""),
    },
    {
        "id": "mara", "name": "Mara Vey", "kind": "character", "gender": "female",
        "summary": "Tamsin's mother, lost to the river when Tamsin was small.",
        "facts": [{"label": "status", "value": "dead"}],
        "relationships": [
            {"type": "married to", "type_kinds": ["character", "character"], "to": "oskar"},
            {"type": "parent of", "type_kinds": ["character", "character"], "to": "tamsin"},
        ],
        "body": _p(""),
    },
    {
        "id": "linnet", "name": "Linnet Dray", "kind": "character", "gender": "female",
        "summary": "Oskar's sister, a net-maker in Greywater.",
        "facts": [{"label": "born", "value": "", "from_time": 358}],
        "relationships": [
            {"type": "parent of", "type_kinds": ["character", "character"], "to": "corin"},
            {"type": "lives in", "type_kinds": ["character", "place"], "to": "greywater"},
        ],
        "body": _p(""),
    },
    {
        "id": "linnet-sorrel", "name": "Linnet Sorrel", "kind": "character", "gender": "female",
        "summary": "Keeps the lower gates at Marrow Locks for the Wardens; shares a first name with Linnet Dray.",
        "relationships": [{"type": "works at", "type_kinds": ["character", "place"], "to": "marrow-locks"}],
        "body": _p(""),
    },
    {
        # gender not set: the family tree gives the general words for Corin (grandchild, sibling's child)
        "id": "corin", "name": "Corin Dray", "kind": "character", "project": "ash-season",
        "summary": "Linnet's child, Tamsin's cousin; came down from Greywater with the ash.",
        "facts": [{"label": "born", "value": "", "from_time": 396}],
        "body": _p("Only in Ash Season so far, so in that book's own bible."),
    },
    {
        "id": "ilse", "name": "Ilse Marrow", "kind": "character", "aliases": ["the Warden"], "gender": "female",
        "summary": "Warden-Captain of the River Wardens; keeps the locks and the tolls.",
        "facts": [
            {"label": "role", "value": "Warden-Captain"},
            {"label": "born", "value": "", "from_time": 371},
            # planted: two values at once (two drafts disagreed), for the Checks
            {"label": "eye colour", "value": "grey"},
            {"label": "eye colour", "value": "blue", "note": "the first draft said blue"},
        ],
        # many relationships, of many kinds, for her page and the graph
        "relationships": [
            {"type": "leads", "type_kinds": ["character", "faction"], "to": "wardens", "role": "Warden-Captain"},
            {"type": "rival of", "type_kinds": ["character", "character"], "to": "oskar"},
            {"type": "born in", "type_kinds": ["character", "place"], "to": "weirholm"},
            {"type": "works at", "type_kinds": ["character", "place"], "to": "marrow-locks"},
            {"type": "visits", "type_kinds": ["character", "place"], "to": "carrow-ferry", "from": "b1-c1"},
            {"type": "has met", "type_kinds": ["character", "character"], "to": "tamsin", "from": "b1-c1"},
            {"type": "mentor of", "type_kinds": ["character", "character"], "to": "harl"},
            {"type": "guards", "type_kinds": ["character", "object"], "to": "seal"},
            {"type": "knows about", "type_kinds": ["character", "*"], "to": "hesper", "from": "b1-c4"},
            {"type": "witnessed", "type_kinds": ["character", "event"], "to": "raising", "note": "at nine years old"},
            {"type": "is a", "type_kinds": ["character", "species"], "to": "human"},
        ],
        "is_at": [{"chapter": "b1-c4", "place": "marrow-locks"}],
        "body": _p("Not a villain: the locks are the only thing keeping the lower delta from flooding every spring, "
                   "and she is the only one who knows how to work them."),
    },
    {
        # planted: a second Warden-Captain from chapter 4, while Ilse still holds it (the role is one at a time)
        "id": "harl", "name": "Harl Brenner", "kind": "character", "gender": "male",
        "summary": "A lock-keeper of the River Wardens, promoted over the winter.",
        "relationships": [
            {"type": "member of", "type_kinds": ["character", "faction"], "to": "wardens", "role": "Lock-keeper",
             "until": "b1-c3"},
            {"type": "member of", "type_kinds": ["character", "faction"], "to": "wardens", "role": "Warden-Captain",
             "from": "b1-c4"},
        ],
        "body": _p(""),
    },
    {
        "id": "cade", "name": "Brother Cade", "kind": "character", "gender": "male",
        "summary": "A monk of the Ashen Order at Saltreach Abbey; takes Tamsin in.",
        "facts": [{"label": "age", "value": "about sixty", "standing": "planned"},
                  # planned, not on the page: with Include planned, Ash Season naming him is a finding (§14.6); it
                  # follows a decision, and chapter 3 is written, so its Loose ends shows the gap (§16.4)
                  {"label": "status", "value": "dead", "standing": "planned", "from": "b1-c3",
                   "follows": ["d-2026-10-08"]}],
        "relationships": [
            # he was on the causeway that night
            {"type": "witnessed", "type_kinds": ["character", "event"], "to": "flood"},
            {"type": "member of", "type_kinds": ["character", "faction"], "to": "ashen-order"},
            {"type": "mentor of", "type_kinds": ["character", "character"], "to": "tamsin", "from": "b1-c3"},
            {"type": "knows about", "type_kinds": ["character", "*"], "to": "compass", "from": "b1-c3"},
            # what he is, and what he looks like
            {"type": "is a", "type_kinds": ["character", "species"], "to": "marsh-wight"},
            {"type": "appears as", "type_kinds": ["character", "species"], "to": "human"},
        ],
        "body": _p("Keeps bees. Speaks to the dead as if they were in the next room."),
    },
    {
        "id": "pell", "name": "Pell", "kind": "character",
        # no one-liner on purpose: the Archivist asks for one; and an age that disagrees with his birth, for Checks
        "facts": [{"label": "born", "value": "", "from_time": 397}, {"label": "age", "value": "12"}],
        "relationships": [{"type": "friend of", "type_kinds": ["character", "character"], "to": "moss"}],
        "is_at": [{"chapter": "b1-c1", "place": "ferry-house"}],
        "body": _p("Runs errands along the landing for a coin or a story."),
    },
    {
        "id": "moss", "name": "Moss", "kind": "character",
        "summary": "Pell's dog: grey, wet, everywhere.",
        # "not a name in this sense": the word is also just moss
        "exclusions": ["moss grew"],
        "relationships": [{"type": "is a", "type_kinds": ["character", "species"], "to": "dog"}],
        "body": _p(""),
    },
    {
        "id": "hesper", "name": "Hesper Quill", "kind": "character", "gender": "female",
        "summary": "A cartographer from Greywater, mapping the delta's shifting channels.",
        # planted: named in book one before she is introduced in book two; and a label that holds several values
        "facts": [{"label": "introduced", "value": "", "from": "b2-c2"},
                  # planned in the Journal in 2014, then made canon in the chapter that shows it
                  {"label": "trade", "value": "cartographer", "established_in": "b2-c2",
                   "evidence": "Hesper Quill had been told the ferry at Carrow Ferry was run by a girl who knew the "
                               "channels better than any chart.",
                   "planned_in": "j-map", "planned_evidence": "Hesper Quill, a mapmaker",
                   # the follow-up of a decision, done (docs/SPEC.md §16)
                   "follows": ["d-2026-10-06"]},
                  {"label": "languages", "value": "Delta speech"},
                  {"label": "languages", "value": "the Greywater chart-cant"}],
        "relationships": [{"type": "lives in", "type_kinds": ["character", "place"], "to": "greywater"}],
        "body": _p("Draws maps that are out of date by the time the ink dries, and knows it."),
    },
    # places
    {
        "id": "delta", "name": "The Ninefold Delta", "kind": "place", "aliases": ["the delta"], "also": ["character"],
        "summary": "Nine channels, a thousand islands, and water that never stays where it was put.",
        # the chart (docs/SPEC.md §13.7): a land holding its towns, bordering the sea around an island
        "facts": [{"label": "type", "value": "land"},
                  {"label": "climate", "value": "wet springs, ash-grey summers when the mountains burn"},
                  # tied to the retired prologue, with its evidence there: still tied in Salvage, and the Archivist's
                  {"label": "shape", "value": "an open hand of nine channels", "from": "b1-s1",
                   "evidence": "the delta was a hand held open to the sea", "established_in": "b1-s1"}],
        "relationships": [{"type": "borders", "type_kinds": ["place", "place"], "to": "outer-sound"}],
        "body": _p("The river splits into nine channels before the sea. They move a little every year."),
    },
    {
        "id": "outer-sound", "name": "The Outer Sound", "kind": "place",
        "summary": "Grey water between the delta's mouths and the open sea.",
        "facts": [{"label": "type", "value": "sea"}],
        "body": _p(""),
    },
    {
        "id": "salt-flats", "name": "The Salt Flats", "kind": "place",
        "summary": "An island at high tide, a causeway at low.",
        "facts": [{"label": "type", "value": "island"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "outer-sound"}],
        "body": _p(""),
    },
    {
        "id": "carrow-ferry", "name": "Carrow Ferry", "kind": "place",
        "summary": "A village at the widest crossing; the last ferry the Wardens don't run.",
        "facts": [{"label": "type", "value": "village"}, {"label": "population", "value": "about two hundred"},
                  {"label": "known for", "value": "the last free crossing"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "delta"},
                          {"type": "north of", "type_kinds": ["place", "place"], "to": "marrow-locks"},
                          {"type": "sea route to", "type_kinds": ["place", "place"], "to": "salt-flats",
                           "note": "the ferry runs out at low tide"}],
        "body": _p(""),
    },
    {
        "id": "ferry-house", "name": "The Ferry House", "kind": "place",
        "summary": "The Veys' house on stilts above the landing.",
        "facts": [{"label": "type", "value": "building"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "carrow-ferry"}],
        "body": _p(""),
    },
    {
        "id": "saltreach", "name": "Saltreach Abbey", "kind": "place",
        "summary": "The Ashen Order's abbey on the salt flats, reachable only at low tide.",
        "facts": [{"label": "type", "value": "building"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "salt-flats"}],
        "body": _p(""),
    },
    {
        "id": "marrow-locks", "name": "Marrow Locks", "kind": "place",
        "summary": "The great locks of the lower delta, kept by the River Wardens.",
        "facts": [{"label": "type", "value": "fort"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "delta"}],
        "body": _p(""),
    },
    {
        # only in the first book so far, so in its own bible
        "id": "gatehouse", "name": "The Gatehouse", "kind": "place", "match_case": False,
        "project": "the-ferrymans-daughter",
        "summary": "Above the gates of Marrow Locks, where the Warden-Captain writes her reports.",
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "marrow-locks"}],
        "body": _p(""),
    },
    {
        "id": "greywater", "name": "Greywater", "kind": "place",
        "summary": "The market town upriver, where maps and rumours are sold.",
        "facts": [{"label": "type", "value": "town"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "delta"},
                          {"type": "north of", "type_kinds": ["place", "place"], "to": "carrow-ferry"},
                          {"type": "road to", "type_kinds": ["place", "place"], "to": "carrow-ferry",
                           "note": "the dyke road"}],
        "body": _p(""),
    },
    # nesting all the way down: the delta (a land), a region, a town, a district, a building, a room
    {
        "id": "reedmarch", "name": "The Reedmarch", "kind": "place",
        "summary": "The eastern marshes between the fourth and fifth channels, where the weirs are.",
        "facts": [{"label": "type", "value": "region"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "delta"},
                          {"type": "east of", "type_kinds": ["place", "place"], "to": "carrow-ferry"}],
        "body": _p(""),
    },
    {
        "id": "weirholm", "name": "Weirholm", "kind": "place",
        "summary": "A weir town on the fourth channel, where the Wardens counted their tolls before the locks.",
        "facts": [{"label": "type", "value": "town"}, {"label": "population", "value": "about six hundred"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "reedmarch"}],
        "body": _p(""),
    },
    {
        "id": "old-wharf", "name": "The Old Wharf", "kind": "place",
        "summary": "Weirholm's oldest quarter: tarred pilings, rope sheds and the toll-house.",
        "facts": [{"label": "type", "value": "district"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "weirholm"}],
        "body": _p(""),
    },
    {
        "id": "toll-house", "name": "The Toll-House", "kind": "place",
        "summary": "Where every boat on the fourth channel stopped to pay, before the locks made it pointless.",
        "facts": [{"label": "type", "value": "building"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "old-wharf"}],
        "body": _p(""),
    },
    {
        "id": "counting-room", "name": "The Counting Room Where the Lantern Tolls Were Weighed", "kind": "place",
        "summary": "An upper room of the toll-house, still smelling of lamp oil.",
        "facts": [{"label": "type", "value": "room"}],
        "relationships": [{"type": "inside", "type_kinds": ["place", "place"], "to": "toll-house"}],
        "body": _p(""),
    },
    # factions, culture, event, objects, terms
    {
        "id": "wardens", "name": "The River Wardens", "kind": "faction", "aliases": ["the Wardens"],
        "summary": "They keep the locks and take the tolls, and believe the river can be ruled.",
        "facts": [{"label": "motto", "value": "The water answers to the lock."},
                  # planned in the Journal (docs/SPEC.md §14.1.2)
                  {"label": "age", "value": "three hundred years", "standing": "planned", "planned_in": "j-wardens",
                   "planned_evidence": "The River Wardens have kept the locks for three hundred years"}],
        "relationships": [
            {"type": "controls", "type_kinds": ["faction", "place"], "to": "marrow-locks"},
            {"type": "allied with", "type_kinds": ["faction", "faction"], "to": "ashen-order", "standing": "rumour",
             "note": "what the ferry folk say"},
        ],
        "body": _p(""),
    },
    {
        "id": "ashen-order", "name": "The Ashen Order", "kind": "faction",
        "summary": "Monks who tend the drowned and keep the old charts.",
        "relationships": [{"type": "based in", "type_kinds": ["faction", "place"], "to": "saltreach"}],
        "body": _p(""),
    },
    # species
    {
        "id": "human", "name": "human", "kind": "species",
        "summary": "Most of the delta's people, and everyone who says they are.",
        "facts": [{"label": "form", "value": "humanoid"}, {"label": "sapient", "value": "yes"},
                  {"label": "lifespan", "value": "seventy years, if the river allows"}],
        "body": _p(""),
    },
    {
        "id": "dog", "name": "dog", "kind": "species",
        "facts": [{"label": "form", "value": "beast"}, {"label": "sapient", "value": "partly",
                                                         "note": "Moss would say yes"}],
        "body": _p(""),
    },
    {
        "id": "marsh-wight", "name": "marsh-wight", "kind": "species", "aliases": ["marsh-wights"],
        "summary": "Old spirits of the reed beds, who sometimes walk among people in borrowed faces.",
        "facts": [{"label": "form", "value": "spirit"}, {"label": "sapient", "value": "yes"},
                  {"label": "lifespan", "value": "unknown; longer than the abbey"},
                  {"label": "habitat", "value": "reed beds"}, {"label": "habitat", "value": "salt flats"},
                  {"label": "name meaning", "value": "\"wight of the marsh\", in the old delta speech"}],
        "relationships": [{"type": "native to", "type_kinds": ["species", "place"], "to": "delta"}],
        "body": _p("Nobody at Saltreach asks Brother Cade how old he is."),
    },
    {
        "id": "delta-folk", "name": "Delta folk", "kind": "culture",
        "summary": "The river people: boat-born, lantern-keeping, suspicious of anything built to last.",
        "facts": [{"label": "customs", "value": "a lantern set on the water for each of the drowned"}],
        "relationships": [{"type": "native to", "type_kinds": ["culture", "place"], "to": "delta"}],
        "body": _p(""),
    },
    {
        "id": "flood", "name": "The Flood of Lanterns", "kind": "event", "aliases": ["the Flood"], "when": "b1-c2",
        "summary": "The spring festival at the first high tide, when the delta floods and lanterns are set adrift.",
        "facts": [{"label": "type", "value": "festival"},
                  {"label": "when", "value": "every spring, at the first high tide"},
                  {"label": "outcome", "value": "the year Oskar drowned", "from": "b1-c2"}],
        "relationships": [
            {"type": "happened at", "type_kinds": ["event", "place"], "to": "carrow-ferry"},
            {"type": "involved", "type_kinds": ["event", "*"], "to": "oskar"},
        ],
        "body": _p(""),
    },
    {
        # no type yet, though every event is expected to have one: the Archivist asks for it
        "id": "fires", "name": "The Mountain Fires", "kind": "event", "aliases": ["the mountains burned"],
        "when": {"at": 413},
        "summary": "The summer the mountains burned and the ash came down the river for a month.",
        # planted: the fires (413) caused the Flood of Lanterns (412), which comes before them: a finding
        "relationships": [{"type": "followed from", "type_kinds": ["event", "event"], "to": "spring-flood"},
                          {"type": "caused", "type_kinds": ["event", "*"], "to": "flood"}],
        "body": _p(""),
    },
    # history: two eras (one nested in the other), the raising of the locks (told in chapter 3), a death, a prophecy
    {
        "id": "lock-years", "name": "The Lock Years", "kind": "event", "when": {"at": 380}, "colour": "teal",
        "summary": "Everything since the River Wardens raised the locks.",
        "facts": [{"label": "type", "value": "era"}],
        "body": _p(""),
    },
    {
        "id": "ash-summers", "name": "The Ash Summers", "kind": "event", "when": {"at": 410, "end": 414},
        "colour": "rust", "summary": "The years the mountains kept burning.",
        "facts": [{"label": "type", "value": "era"}],
        "body": _p(""),
    },
    # before the locks: a long era, with the years of building them nested at its end
    {
        "id": "open-water", "name": "The Open Water", "kind": "event", "when": {"at": 320, "end": 379},
        "colour": "sky", "summary": "Before the locks, when the nine channels went where they liked.",
        "facts": [{"label": "type", "value": "era"}],
        "body": _p(""),
    },
    {
        "id": "lock-works", "name": "The Lock Works", "kind": "event", "when": {"at": 376, "end": 379},
        "colour": "amber", "summary": "Four years of piling, digging and drowning, to build Marrow Locks.",
        "facts": [{"label": "type", "value": "era"}],
        "body": _p(""),
    },
    {
        "id": "raising", "name": "The Raising of the Locks", "kind": "event", "when": {"at": 380, "approx": True},
        "summary": "The River Wardens close the lower delta with the great locks.",
        "facts": [{"label": "type", "value": "founding"}],
        "relationships": [
            {"type": "involved", "type_kinds": ["event", "*"], "to": "wardens", "established_in": "b1-c3"},
            {"type": "happened at", "type_kinds": ["event", "place"], "to": "marrow-locks", "established_in": "b1-c3"},
            # cause arrows on the Timeline (docs/SPEC.md §14.7)
            {"type": "caused", "type_kinds": ["event", "*"], "to": "spring-flood"},
        ],
        "tellings": [{"chapter": "b1-c3", "passage": "Brother Cade said the River Wardens raised Marrow Locks the year "
                      "his own teacher was born, and that the Ninefold Delta has never forgiven them."}],
        "body": _p(""),
    },
    # the years before the raising, close together on the Timeline (a cluster when zoomed out)
    {
        "id": "survey", "name": "The Survey of the Nine Channels", "kind": "event", "when": {"at": 378},
        "summary": "The Wardens sound every channel, to learn where a lock would hold.",
        "facts": [{"label": "type", "value": "survey"}],
        "relationships": [{"type": "involved", "type_kinds": ["event", "*"], "to": "wardens"}],
        "body": _p(""),
    },
    {
        "id": "petition", "name": "The Ferrymen's Petition", "kind": "event", "when": {"at": 378},
        "summary": "The ferry folk ask the Wardens to leave one channel open. They are thanked, and refused.",
        "facts": [{"label": "type", "value": "petition"}, {"label": "outcome", "value": "refused"}],
        "relationships": [{"type": "involved", "type_kinds": ["event", "*"], "to": "agathe"},
                          {"type": "happened at", "type_kinds": ["event", "place"], "to": "toll-house"},
                          {"type": "followed from", "type_kinds": ["event", "event"], "to": "survey"}],
        "body": _p(""),
    },
    {
        "id": "gates-shut", "name": "The Night the Lower Gates Were Shut Against the Spring Tide", "kind": "event",
        "when": {"at": 379}, "summary": "The first trial of the half-built locks, a month too early.",
        "facts": [{"label": "type", "value": "flood"}],
        "relationships": [{"type": "involved", "type_kinds": ["event", "*"], "to": "wardens"},
                          {"type": "happened at", "type_kinds": ["event", "place"], "to": "marrow-locks"},
                          {"type": "caused", "type_kinds": ["event", "*"], "to": "diggers"}],
        "body": _p(""),
    },
    {
        "id": "diggers", "name": "The Drowning of the Lock Diggers", "kind": "event", "when": {"at": 379},
        "summary": "Forty diggers caught below the gates when the tide came over.",
        "facts": [{"label": "type", "value": "disaster"}],
        "relationships": [{"type": "happened at", "type_kinds": ["event", "place"], "to": "marrow-locks"}],
        "body": _p(""),
    },
    {
        "id": "riots", "name": "The Toll-House Riots", "kind": "event", "when": {"at": 379, "end": 380},
        "summary": "A winter of stones through the toll-house windows, and the Wardens' boats burned at their moorings.",
        "facts": [{"label": "type", "value": "riot"}],
        "relationships": [{"type": "involved", "type_kinds": ["event", "*"], "to": "wardens"},
                          {"type": "happened at", "type_kinds": ["event", "place"], "to": "toll-house"},
                          {"type": "followed from", "type_kinds": ["event", "event"], "to": "diggers"}],
        "body": _p(""),
    },
    {
        "id": "first-toll", "name": "The First Toll", "kind": "event",
        "summary": "The first toll the Wardens took, long before the locks.",
        "facts": [{"label": "type", "value": "founding"}],
        "relationships": [{"type": "involved", "type_kinds": ["event", "*"], "to": "wardens", "standing": "planned",
                           "planned_in": "j-wardens",
                           "planned_evidence": "The first toll was paid in lanterns, at the mouth of the Outer Sound."}],
        # recorded from the Journal: a note, not a telling, so it is not in the book yet
        "notes": [{"journal": "j-wardens",
                   "passage": "The first toll was paid in lanterns, at the mouth of the Outer Sound."}],
        "body": _p(""),
    },
    {
        "id": "spring-flood", "name": "The Spring Flood", "kind": "event", "when": {"at": 390},
        "summary": "The flood that took Agathe Vey and the old ferry house.",
        "facts": [{"label": "type", "value": "death"}],
        "relationships": [{"type": "involved", "type_kinds": ["event", "*"], "to": "agathe"},
                          {"type": "happened at", "type_kinds": ["event", "place"], "to": "carrow-ferry"}],
        "body": _p(""),
    },
    {
        "id": "opening", "name": "The Opening of the Hand", "kind": "event", "when": "outside",
        "summary": "What the delta folk say will come: the nine channels opening again, and the locks drowned.",
        "facts": [{"label": "type", "value": "prophecy"}],
        "body": _p(""),
    },
    {
        "id": "compass", "name": "The Brass Compass", "kind": "object", "aliases": ["the compass", "the brass compass"],
        "summary": "Oskar's compass. Its needle points home, never north.",
        "facts": [
            {"label": "material", "value": "brass, with a cracked glass"},
            {"label": "power", "value": "always points to home", "standing": "rumour"},
        ],
        "body": _p(""),
    },
    {
        "id": "seal", "name": "The Warden's Seal", "kind": "object", "aliases": [],
        "summary": "Stamped on every toll paper; to forge it is to be drowned.",
        "relationships": [{"type": "symbol of", "type_kinds": ["object", "faction"], "to": "wardens"}],
        "body": _p(""),
    },
    {
        "id": "tidecall", "name": "Tidecall", "kind": "term", "match_case": False,
        "summary": "Three long blasts on the horn: the ferry is crossing, keep clear.",
        "facts": [{"label": "meaning", "value": "the ferry is crossing"}],
        "relationships": [{"type": "originated in", "type_kinds": ["term", "*"], "to": "carrow-ferry"}],
        "body": _p(""),
    },
]

# every event is expected to have a type; a character's languages hold several values at once
FACT_LABELS = [
    {"kind": "event", "label": "type", "several": False, "expected": True, "asked": True},
    {"kind": "character", "label": "languages", "several": True, "expected": False, "asked": False},
    {"kind": "species", "label": "habitat", "several": True, "expected": False, "asked": False},
]

# only one Warden-Captain at a time (Harl's promotion is planted as a clash)
ROLES = [{"role": "Warden-Captain", "one_at_a_time": True}]

# ---- the manuscript ------------------------------------------------------------------------------------------------

BOOK_ONE = "The Ferryman's Daughter"
BOOK_TWO = "Ash Season"

CHAPTERS: list[dict] = [
    {
        "id": "b1-c1", "time": {"at": 412}, "summary": 'The Wardens come for the toll; Oskar gives Tamsin the compass.', "status": 'polished', "project": BOOK_ONE, "title": "The Crossing", "position": 0, "pov": "Tamsin Vey",
        "body": _p(
            "The tidecall went out over the water at first light, three long notes that set the herons lifting "
            "from the reeds. Tamsin Vey let the last one fade before she cast off, the way her father had taught "
            "her: you give the river time to hear you.",
            "Oskar was already at the stern, coiling rope he had coiled the night before. Moss grew thick on the "
            "pilings of the landing, and the ferry knocked against them like it was impatient. On the bank Pell "
            "was shouting something, and Moss was barking at whatever Pell was shouting about.",
            "\"Wardens,\" Oskar said, not looking up. \"Two boats. Coming down from the locks.\"",
            "Tamsin shaded her eyes. Her green eyes narrowed against the glare until she could make out the grey "
            "hulls and the flag of the River Wardens snapping above them. Ilse Marrow stood in the bow of the "
            "first boat, straight as a mooring post.",
            "***",
            "The Warden did not raise her voice. She never had to. \"The toll for the crossing at Carrow Ferry is "
            "due on the first of the month, Oskar Vey. It is the ninth.\"",
            "\"The river doesn't read your calendar,\" Oskar said.",
            "\"The river,\" said Ilse, \"answers to the lock.\" She held up a paper with the Warden's Seal on it, "
            "red as a fresh cut. Tamsen watched her father's jaw, and knew he would not pay, and knew he would "
            "pay later, in some way that cost more.",
            "When the Wardens had gone, Oskar put the brass compass into her hand. Its needle swung once and "
            "settled, pointing not north but back at the Ferry House on its stilts. \"Keep that dry,\" he said. "
            "\"It's the only thing on this river that knows where it's going.\"",
        ),
    },
    {
        "id": "b1-c2", "time": {"at": 412}, "summary": 'The Flood of Lanterns, and the night Oskar goes out on the water.', "status": 'rewritten', "project": BOOK_ONE, "title": "Lanterns on the Water", "position": 1, "pov": "Tamsin Vey",
        "body": _p(
            "The Flood of Lanterns came early that year. By dusk the water stood knee-deep in the lower lanes of "
            "Carrow Ferry, and every house had a lantern ready on its step, one for each of the drowned the "
            "family remembered.",
            "Tamsin set out four. Her mother, her grandmother, two uncles she had never met. Oscar set out none; "
            "he said the river already knew who it had taken.",
            "Then the bell at Saltreach Abbey began to ring across the flats, the the slow bell that meant "
            "someone was cut off by the tide. It rang TK times before her father reached for his coat.",
            "\"Not tonight,\" Tamsin said. \"Not in this.\"",
            "\"There are monks on the causeway,\" Oscar said. \"Brother Cade among them, if I know him.\"",
            "She went with him as far as the landing. The lanterns were already drifting out, hundreds of them, "
            "the whole delta lit like a field of small fires, and her father's boat went out among them and "
            "became one more light, and then it was hard to say which one.",
            "In the morning Brother Cade came to the Ferry House wet to the waist, holding his hat in both hands. "
            "Tamsin did not need him to say it. The river kept him.",
        ),
    },
    {
        "id": "b1-c3", "time": {"at": 412}, "summary": 'Tamsin at Saltreach Abbey with Brother Cade and the compass.', "status": 'rewritten', "project": BOOK_ONE, "title": "What the River Kept", "position": 2, "pov": "Tamsin Vey",
        "body": _p(
            "They never found Oskar. A boatman called Rook found the boat, upside down against the reeds below "
            "Marrow Locks, and towed it back without a word and without asking to be paid. Pell said that was "
            "how you knew Rook was frightened of something.",
            "%% Should Pell already know about the compass here? Check against chapter 1.",
            "Brother Cade said the River Wardens raised Marrow Locks the year his own teacher was born, and that the "
            "Ninefold Delta has never forgiven them.",
            "Brother Cade took Tamsin to Saltreach Abbey at low tide, across the causeway where the monks had "
            "been stranded. Pell walked with Brother Cade the whole way, asking him whether the dead could hear "
            "bells, and Brother Cade answered every question as if it were a serious one.",
            "The compass was hers now. In the abbey's cold guest room she held it under the lamp and watched the "
            "needle turn, slowly, until it pointed back across the flats toward Carrow Ferry. Home, then. Not "
            "here.",
            "\"Your father thought it was a trick of the brass,\" Brother Cade said from the doorway. \"I thought "
            "it was a prayer. We argued about it for twenty years.\"",
            "\"Who won?\"",
            "\"Neither of us. That's how you know it was a good argument.\"",
        ),
    },
    {
        "id": "b1-c4", "time": {"at": 412}, "summary": 'Ilse writes the report, and hears of a cartographer.', "status": 'raw', "project": BOOK_ONE, "title": "The Locks", "position": 3, "pov": "Ilse Marrow",
        # planted: told from Ilse's point of view, but she is never named in it
        "body": _p(
            "She wrote the report by lamplight in the gatehouse at Marrow Locks, while the water below the gates "
            "went on rising as if it had somewhere to be.",
            "One ferryman lost on the night of the Flood. One boat recovered. Toll for Carrow Ferry unpaid, "
            "debtor deceased. She looked at the last word for a long time before she let it stand.",
            "There was a rumour in Greywater, the clerk told her, of a cartographer called Hesper Quill who was "
            "mapping the channels for the Ashen Order, and who had asked to see the Wardens' charts. She "
            "underlined the name twice. Maps were how you took a river without a single boat.",
            "Down on the water, someone had set one more lantern adrift. It caught against the gate, turned, and "
            "went out.",
        ),
    },
    {
        "id": "b1-x1", "summary": 'Chapter two from the boat.', "status": 'raw', "project": BOOK_ONE, "title": "Lanterns on the Water (from the water)", "state": "experiment",
        "position": 4, "pov": "Tamsin Vey", "replaces": "b1-c2", "item": "item-experiment",
        "body": _p(
            "From the boat, the lanterns did not look like a field of fires. They looked like eyes. Her father "
            "rowed through them without hurrying, and Tamsin, who had followed him out after all, crouched in "
            "the bow and counted the ones she knew.",
        ),
    },
    {
        "id": "b1-s1", "summary": 'The delta as an open hand.', "status": 'raw', "project": BOOK_ONE, "title": "Prologue: The Delta Remembers", "state": "retired",
        "position": 5,
        "harvest_notes": ["The nine channels as the fingers of an open hand.", "Keep: lanterns as prayers nobody says aloud."],
        "body": _p(
            "Before the locks, before the Wardens, the delta was a hand held open to the sea, nine fingers of "
            "water that moved when they wished. The delta folk say it is still that hand, only closed for now, "
            "and that one day it will open again.",
        ),
    },
    {
        "id": "b2-c1", "time": {"at": 413}, "summary": 'A year on: ash on the river, Tamsin running the ferry alone.', "status": 'draft', "project": BOOK_TWO, "title": "Ash Season", "position": 0, "pov": "Tamsin Vey",
        "body": _p(
            "A year later the mountains burned, and the ash came down the river for a month, grey on the water, "
            "grey on the reeds, grey in the folds of every sail. Tamsin ran the ferry alone now. She blew the "
            "tidecall three times at every crossing, even when there was no one on the water to hear it.",
            "Pell had grown a hand taller and Moss had grown no smarter. They rode with her most mornings, Pell "
            "counting the drifting ash-islands, Moss barking at each one as if it might be a seal.",
            "Some days she took out the compass and let it point at the Ferry House, just to see it do it. On "
            "those days she thought of Oskar, and of the argument he never finished with Brother Cade.",
            "In Greywater, they said, a woman with ink-stained hands was asking for the best boat on the delta. Corin "
            "Dray, her cousin, had come down from Greywater with the first of the ash and never gone home.",
        ),
    },
    {
        "id": "b2-c2", "time": {"at": 413}, "summary": 'Hesper Quill comes to Carrow Ferry with her maps.', "status": 'sketch', "project": BOOK_TWO, "title": "The Cartographer", "position": 1, "pov": "Hesper Quill",
        "body": _p(
            "Hesper Quill had been told the ferry at Carrow Ferry was run by a girl who knew the channels better "
            "than any chart. She had been told this by three different people in Greywater, each of whom "
            "clearly expected her to be disappointed.",
            "The girl was waiting at the landing with the ash on her shoulders like a grey shawl. Tamsin Vey "
            "looked at Hesper's maps the way a fisherman looks at a net someone else has mended: politely, and "
            "without trust.",
            "\"These are wrong,\" Tamsin said.",
            "\"All maps of the delta are wrong,\" said Hesper. \"I'm trying to make one that's wrong more "
            "slowly.\"",
            # two Linnets: which one the bare name means is settled by a line, from there on (docs/SPEC.md §14.10)
            "Linnet sent word from the locks that the ash had reached the lower gates.",
            "%% Linnet: Linnet Sorrel",
            "Linnet kept the gates open a day longer than the Wardens allowed.",
            "%% Linnet: Linnet Dray",
            "In Greywater, Linnet read the letter twice and burned it.",
            "%% Linnet: ?",
            "Hesper asked which Linnet the ferry-folk meant, and nobody could say.",
        ),
    },
    {
        # a tale, set forty years before: Oskar is named in it, though he is recorded dead in the present
        "id": "b2-c3", "time": {"at": 372, "label": "forty years before the ash"}, "told_as": "tale",
        "summary": "Brother Cade tells of the night young Oskar first crossed in fog.", "status": "sketch",
        "project": BOOK_TWO, "title": "The Ferryman's Tale", "position": 2, "pov": None,
        "body": _p(
            "\"He was younger than you are now,\" Brother Cade said, \"and twice as sure of himself.\"",
            "Oskar Vey took the ferry out in a fog so thick the herons walked. He found the far landing by the sound "
            "of the bell, and came back by the sound of his mother calling, and never told anyone he had been afraid.",
        ),
    },
    # outside time (docs/SPEC.md §13.1.8): Agathe is recorded dead from year 390, and naming her here is no finding
    {
        "id": "b2-c4", "time": "outside", "summary": "The drowned under the Outer Sound speak to no one in particular.",
        "status": "sketch", "project": BOOK_TWO, "title": "What the Drowned Say", "position": 3, "pov": None,
        "body": _p(
            "Under the water there is no year. The drowned keep their lanterns lit and their names short.",
            "Agathe Vey says the river was never theirs to lock. The others agree, the way water agrees: by "
            "closing over the question.",
        ),
    },
    # a long title, for lists and headings; set the year the ash stopped
    {
        "id": "b2-c5", "time": {"at": 414}, "summary": "The ash stops, and the Wardens let three summers of grey water out.",
        "status": "sketch", "project": BOOK_TWO,
        "title": "The Morning the Ash Stopped Falling and the Wardens Opened the Lower Gates", "position": 4,
        "pov": "Tamsin Vey",
        "body": _p(
            "The ash stopped falling in the spring. Tamsin noticed it the way you notice a bell has stopped: by the "
            "quiet, a long while after.",
            "Linnet Sorrel sent word from Marrow Locks that the lower gates would open at the first high tide, and "
            "that anyone with a boat should be off the water by noon.",
            "Tamsin took the ferry out anyway, with Pell in the bow and Moss under the bench, and they watched the "
            "grey water of three summers go out past the Salt Flats to the sea.",
        ),
    },
    # an experiment that only adds (docs/SPEC.md §13.6): a new prologue before "The Crossing", replacing nothing
    {
        "id": "b1-x2", "summary": "A new opening: the compass, before anyone owns it.", "status": "raw",
        "project": BOOK_ONE, "title": "Before the Crossing", "state": "experiment", "position": 5, "pov": None,
        "item": "item-prologue",
        "body": _p("The compass lay in a drawer at Saltreach Abbey for thirty years, pointing at nothing anyone could "
                   "see, until the night Oskar Vey asked the brothers for something that would always find home."),
    },
    # an experiment across two chapters of Ash Season, from copies
    {
        "id": "b2-x1", "summary": "Ash Season told from the water.", "status": "sketch", "project": BOOK_TWO,
        "title": "Ash Season (from the water)", "state": "experiment", "position": 0, "pov": "Tamsin Vey",
        "item": "item-ash-season",
        "body": _p("The ash came down the river for a month, and Tamsin learned to read the water through it."),
    },
    {
        "id": "b2-x2", "summary": "Hesper's maps, from the ferry.", "status": "sketch", "project": BOOK_TWO,
        "title": "The Cartographer (from the water)", "state": "experiment", "position": 1, "pov": "Tamsin Vey",
        "item": "item-ash-season",
        "body": _p("Hesper Quill spread her maps across the ferry's bench, and the river moved under them."),
    },
]

PROJECTS = [
    # short chapters: three without a name make a gap on its mentions strip
    {"name": BOOK_ONE, "slug": "the-ferrymans-daughter", "kind": "novel", "position": 0,
     "statuses": ["raw", "rewritten", "polished"], "gap_chapters": 3},
    # each book names its own stages
    {"name": BOOK_TWO, "slug": "ash-season", "kind": "novella", "position": 1, "statuses": ["sketch", "draft", "clean"],
     "gap_chapters": 5},
]

# ---- revising: a passage in the cuts bin, and a few days of word history ------------------------------------------

# cut from "The Crossing" a week ago, between Oskar at the stern and the Wardens' boats
CUT = {
    "id": "cut-buoy", "chapter": "b1-c1", "after_paragraph": 1, "days_ago": 7,
    "body": "Upstream a bell-buoy knocked against its chain, the way it did when the tide turned early. Tamsin "
            "counted the knocks and lost count at nine, which her father said was the river's way of telling her "
            "to stop counting.",
}

# how the chapters grew: (days ago, paragraphs there were); the first is where the chapter's history starts, the
# last is the chapter as it is now. "The Crossing" also had the cut passage until the day it was cut.
HISTORY: dict[str, list[tuple[int, int]]] = {
    "b1-c1": [(12, 3), (10, 7), (9, 99)],
    "b1-c2": [(9, 2), (8, 99)],
    "b1-c3": [(6, 3), (5, 5), (3, 99)],
    "b1-c4": [(2, 1), (1, 99)],
    "b2-c1": [(4, 1), (3, 99)],
}

# ---- planning: the inbox, decisions and the journal ---------------------------------------------------------------

ITEMS: list[dict] = [
    {"id": "item-toll", "kind": "spark", "status": "open", "project": None, "source": "phone",
     "created_at": "2026-10-04T08:12:00+00:00", "tags": ["The River Wardens"],
     "body": "What if the Wardens' toll is paid in lanterns, not coin?"},
    {"id": "item-rook", "kind": "question", "status": "open", "project": "the-ferrymans-daughter", "source": "desk",
     "created_at": "2026-10-05T20:40:00+00:00", "tags": ["Pell"],
     "body": "Does Pell know who Rook is afraid of?"},
    {"id": "item-map", "kind": "task", "status": "open", "project": "the-ferrymans-daughter", "source": "desk",
     "created_at": "2026-10-06T09:00:00+00:00", "tags": ["The Flood of Lanterns", "The Ninefold Delta"],
     "body": "Work out which channels flood first, for the Flood of Lanterns chapter."},
    {"id": "item-brother", "kind": "spark", "status": "deferred", "project": None, "source": "phone",
     "created_at": "2026-10-02T23:05:00+00:00", "tags": ["Ilse Marrow"],
     "body": "A second ferry upriver, run by Ilse's brother?"},
    {"id": "item-death", "kind": "question", "status": "accepted", "project": "the-ferrymans-daughter",
     "source": "desk", "created_at": "2026-09-30T19:30:00+00:00", "closed_at": "2026-10-01T10:00:00+00:00",
     "closed_note": "Chapter 2. The first chapter needs him alive to give her the compass.", "tags": ["Oskar Vey"],
     "body": "Does Oskar die in chapter 1 or chapter 2?"},
    # made from a passage of chapter 3 (docs/SPEC.md §14.3.1)
    {"id": "item-locks", "kind": "question", "status": "open", "project": "the-ferrymans-daughter", "source": "desk",
     "created_at": "2026-10-09T20:00:00+00:00", "tags": ["Marrow Locks"],
     "from": {"chapter": "b1-c3"}, "passage": "Brother Cade said the River Wardens raised Marrow Locks",
     "body": "How far upriver do the locks reach?\n\n> Brother Cade said the River Wardens raised Marrow Locks"},
    # parked from the Journal: an old idea kept without it waiting in the inbox
    {"id": "item-lantern-toll", "kind": "spark", "status": "deferred", "project": None, "source": "desk",
     "created_at": "2026-10-09T20:05:00+00:00", "tags": ["The River Wardens"],
     "from": {"journal": "j-wardens"}, "passage": "The first toll was paid in lanterns",
     "body": "> The first toll was paid in lanterns"},
    {"id": "item-experiment", "kind": "experiment", "status": "open", "project": "the-ferrymans-daughter",
     "source": "desk", "created_at": "2026-10-07T21:00:00+00:00", "tags": [],
     "title": "Lanterns on the Water (from the water)",
     "body": "Try chapter 2 from the boat, with Tamsin following him out."},
    {"id": "item-ash-season", "kind": "experiment", "status": "open", "project": "ash-season",
     "source": "desk", "created_at": "2026-10-08T21:00:00+00:00", "tags": [],
     "title": "Ash Season, from the water", "replaces": ["b2-c1", "b2-c2"],
     "body": "Both opening chapters of Ash Season from the ferry."},
    # a task that follows a decision, done (docs/SPEC.md §16): tied to chapter 3 and Brother Cade
    {"id": "item-bells", "kind": "task", "status": "accepted", "project": "the-ferrymans-daughter", "source": "desk",
     "created_at": "2026-10-08T21:10:00+00:00", "closed_at": "2026-10-12T09:00:00+00:00", "tags": ["Brother Cade"],
     "from": {"chapter": "b1-c3"}, "follows": ["d-2026-10-08"],
     "body": "Let Pell ask about the bells before Cade dies"},
    {"id": "item-prologue", "kind": "experiment", "status": "open", "project": "the-ferrymans-daughter",
     "source": "desk", "created_at": "2026-10-10T21:00:00+00:00", "tags": [],
     "title": "Before the Crossing", "insert": {"before": "b1-c1"},
     "body": "Open with the compass instead of the toll? Nothing would be replaced."},
]

# the chart (docs/SPEC.md §13.7.3): two places pinned inside the delta, relative to its centre; the rest lay out
CHART_PINS = [
    {"place": "greywater", "container": "delta", "x": -20, "y": -90},
    {"place": "marrow-locks", "container": "delta", "x": 20, "y": 90},
]

DECISIONS = [
    ("2026-10-01", "the-ferrymans-daughter", "Oskar dies in chapter 2, not chapter 1.", "item-death", ["oskar"]),
    ("2026-10-03", None, "The compass points home, never north; nobody in the delta knows why.", None, ["compass"]),
    ("2026-10-05", "ash-season", "Ash Season is told mostly by Tamsin, with one chapter from Hesper.", None,
     ["tamsin", "hesper"]),
    # decisions with follow-ups (docs/SPEC.md §16): one done (her trade, canon in "The Cartographer"), one not (his
    # death still planned, the task about the bells accepted); Oskar's above stays settled, so all three states show
    ("2026-10-06", "ash-season", "Hesper is a cartographer, and Ash Season shows her at her maps", None, ["hesper"]),
    ("2026-10-08", "the-ferrymans-daughter", "Brother Cade dies at Saltreach, in What the River Kept", None, ["cade"]),
]

JOURNAL = [
    # years of planning before the book (docs/SPEC.md §14)
    {"id": "j-map", "date": "2014-05-11", "title": "The first map", "project": None,
     "body": _p("Someone has to map the delta, and the map has to be wrong by the time it is finished. Hesper Quill, "
                "a mapmaker from Greywater, who knows her maps go out of date.",
                "Ilse Marrow wants the delta mapped so it can be locked.")},
    {"id": "j-wardens", "date": "2019-03-02", "title": "What the Wardens want", "project": None,
     "body": _p("The River Wardens have kept the locks for three hundred years, since the Raising of the Locks. Ilse "
                "Marrow knows the toll is older than the locks; Tamsin doesn't.",
                "The first toll was paid in lanterns, at the mouth of the Outer Sound. That is why the Flood of "
                "Lanterns frightens them.")},
    {"id": "j-loose", "date": "2021-08-14", "title": "Loose threads", "project": "ash-season",
     "body": _p("Hesper's age ?? maybe forty, maybe older than Ilse.",
                "Where does Corin sleep when he comes down from Greywater (??)",
                "???",
                "The ash should reach Carrow Ferry before Hesper does.")},
    {"id": "j1", "date": "2026-10-02", "title": "Why a ferry?", "project": None,
     "body": _p("A ferry is a story that goes back and forth: the same crossing, a different person every time. "
                "Tamsin can stay in one place and still meet everyone in the delta.",
                "The River Wardens want the crossing because whoever holds the crossings holds the delta.")},
    {"id": "j2", "date": "2026-10-06", "title": "Ash as a clock", "project": "ash-season",
     "body": _p("In Ash Season the ash is the clock: thick in the first chapter, thinning as the book goes on. "
                "Hesper's maps should change as the water clears.")},
]


# ---- as export files ---------------------------------------------------------------------------------------------

def demo_files() -> dict[str, str]:
    """The demo world as the files of an export (path -> text)."""
    files: dict[str, str] = {}
    files[f"{ROOT}/world.md"] = _doc({
        "quarry_export": FORMAT, "name": NAME, "slug": ROOT, "ignored_words": [],
        "relation_types": [{"a": a, "b": b, "label": label, "reverse": reverse} for a, b, label, reverse in STARTING_TYPES],
        "fact_labels": FACT_LABELS,
        "roles": ROLES,
        "premise": PREMISE,
        "chart": {"settings": {"shapes": {}}, "pins": CHART_PINS},
    }, "")
    names = {e["id"]: e["name"] for e in BIBLE}
    for e in BIBLE:
        meta = {"id": e["id"], "name": e["name"], "kind": e["kind"], "aliases": e.get("aliases", []),
                "summary": e.get("summary", ""), "match_case": e.get("match_case", True), "first_name_alias": True,
                "exclusions": e.get("exclusions", []), "project": e.get("project")}
        if e.get("gender"):
            meta["gender"] = e["gender"]
        if e.get("also"):
            meta["also"] = e["also"]
        if e.get("facts"):
            meta["facts"] = [{"label": f["label"], "value": f["value"], "standing": f.get("standing", "canon"),
                              "evidence": f.get("evidence"), "note": f.get("note"),
                              "established_in": f.get("established_in"), "from": f.get("from"),
                              "until": f.get("until"),
                              **{k: f[k] for k in ("from_time", "from_approx", "until_time", "outside_time",
                                                   "planned_in", "planned_evidence", "follows") if k in f}}
                             for f in e["facts"]]
        if e.get("relationships"):
            meta["relationships"] = [{"type": r["type"], "type_kinds": r["type_kinds"], "to": r["to"],
                                      "to_name": names[r["to"]], "standing": r.get("standing", "canon"),
                                      "evidence": r.get("evidence"), "note": r.get("note"),
                                      "established_in": r.get("established_in"), "from": r.get("from"),
                                      "until": r.get("until"), "role": r.get("role"),
                                      **{k: r[k] for k in ("planned_in", "planned_evidence") if k in r}}
                                     for r in e["relationships"]]
        if e.get("is_at"):
            meta["is_at"] = [{"chapter": p["chapter"], "place": p["place"], "place_name": names[p["place"]],
                              "note": p.get("note")} for p in e["is_at"]]
        for k in ("when", "colour", "tellings", "notes"):
            if e.get(k):
                meta[k] = e[k]
        files[f"{ROOT}/Bible/{KIND_FOLDERS[e['kind']]}/{e['name']}.md"] = _doc(meta, e.get("body", ""))

    folders = {p["name"]: f"{ROOT}/Projects/{p['name'].replace(chr(39), '')}" for p in PROJECTS}
    for p in PROJECTS:
        files[f"{folders[p['name']]}/project.md"] = _doc(p, "")
    for ch in CHAPTERS:
        state = ch.get("state", "current")
        meta = {"id": ch["id"], "title": ch["title"], "state": state, "position": ch["position"], "pov": ch.get("pov"),
                "summary": ch.get("summary", ""), "status": ch.get("status")}
        if ch.get("time"):
            meta["time"] = ch["time"]
        if ch.get("told_as"):
            meta["told_as"] = ch["told_as"]
        sub = {"current": "Manuscript", "experiment": "Experiments", "retired": "Salvage"}[state]
        if state == "experiment":
            meta |= {"item": ch.get("item")}
            if ch.get("replaces"):
                # the older layout (a draft that replaces one chapter), which Restore still reads
                meta["replaces"] = ch["replaces"]
        if state == "retired":
            meta |= {"harvest_notes": ch.get("harvest_notes", [])}
        files[f"{folders[ch['project']]}/{sub}/{ch['position'] + 1:02d} {ch['title'].replace(':', '')}.md"] = _doc(meta, ch["body"])

    slug_folder = {p["slug"]: folders[p["name"]] for p in PROJECTS}
    for i in ITEMS:
        folder = slug_folder[i["project"]] if i["project"] else ROOT
        meta = {k: i.get(k) for k in ("id", "kind", "status", "title", "project", "source", "created_at", "closed_at",
                                      "closed_note", "tags")}
        if i.get("replaces"):
            meta["replaces"] = i["replaces"]
        if i.get("insert"):
            meta["insert"] = i["insert"]
        for k in ("from", "passage", "follows"):
            if i.get(k):
                meta[k] = i[k]
        files[f"{folder}/Planning/{i['status']}/{i['id']}.md"] = _doc(meta, i["body"])

    lines = ["# Decisions", ""]
    for day, project, text, item, entities in DECISIONS:
        proj = f" · [{project}]" if project else ""
        refs = f"id=d-{day}" + (f" item={item}" if item else "") + (f" entities={','.join(entities)}" if entities else "")
        lines.append(f"- {day}{proj} {text} <!-- {refs} -->")
    files[f"{ROOT}/Decisions.md"] = "\n".join(lines) + "\n"

    for j in JOURNAL:
        files[f"{ROOT}/Journal/{j['date']} {j['title'].replace('?', '')}.md"] = _doc(
            {"id": j["id"], "date": j["date"], "title": j["title"], "project": j["project"]}, j["body"])

    source = next(c for c in CHAPTERS if c["id"] == CUT["chapter"])
    paragraphs = _paragraphs(source["body"])
    before = "\n\n".join(paragraphs[:CUT["after_paragraph"] + 1]) + "\n\n"
    after = "\n\n".join(paragraphs[CUT["after_paragraph"] + 1:])
    files[f"{folders[source['project']]}/Cuts/{CUT['id']}.md"] = _doc({
        "id": CUT["id"], "chapter": source["id"], "chapter_title": source["title"],
        "cut_at": (datetime.now(UTC) - timedelta(days=CUT["days_ago"])).isoformat(), "put_back_at": None,
        "before": before[-80:], "after": after[:80]}, CUT["body"] + "\n\n")
    return files


def _paragraphs(body: str) -> list[str]:
    return body.rstrip("\n").split("\n\n")


def _history(db: Session, world: World, user: User) -> None:
    """A few days of word history: each chapter's start moved back to where its history begins, with the text it
    had then, and a revision for each day it grew (and the day the passage now in the bin was cut)."""
    by_title = {c.title: c for c in db.scalars(select(Chapter).join(Project, Project.id == Chapter.project_id)
                                                .where(Project.world_id == world.id))}
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    for cid, steps in HISTORY.items():
        spec = next(c for c in CHAPTERS if c["id"] == cid)
        ch = by_title[spec["title"]]
        paragraphs = _paragraphs(ch.body)
        if cid == CUT["chapter"]:
            paragraphs.insert(CUT["after_paragraph"] + 1, CUT["body"])
        texts = ["\n\n".join(paragraphs[:n]) + "\n" for _, n in steps]
        days = [d for d, _ in steps]
        if cid == CUT["chapter"]:
            texts.append(ch.body)
            days.append(CUT["days_ago"])
        start = db.scalars(select(Revision).where(Revision.doc_table == "chapter", Revision.doc_id == ch.id,
                                                  Revision.reason == "start")).one()
        start.body = texts[0]
        start.created_at = now - timedelta(days=days[0], hours=3)
        start.meta = {**start.meta, "words": words(texts[0])}
        previous = texts[0]
        for day, text in zip(days[1:], texts[1:]):
            added, removed = word_changes(previous, text)
            db.add(Revision(doc_table="chapter", doc_id=ch.id, version=ch.version, title=ch.title, body=text,
                            meta={"state": ch.state, "words": words(text), "added": added, "removed": removed},
                            reason="autosnap", created_by=user.id, created_at=now - timedelta(days=day, hours=1)))
            previous = text
    db.flush()


def create_demo(db: Session, user: User) -> World:
    """Load the demo world for `user`, plus what an export doesn't carry. Flushed, not committed."""
    world = restore_files(db, user, demo_files())
    _history(db, world, user)
    chapters = {c.title: c for c in db.scalars(select(Chapter).join(Project, Project.id == Chapter.project_id)
                                                .where(Project.world_id == world.id))}
    third = chapters["What the River Kept"]
    # a thought stashed while writing chapter 3
    thought = Item(world_id=world.id, project_id=third.project_id, kind="spark", source="stash",
                   body="How many lanterns does the abbey set out for its own dead?", created_by=user.id,
                   updated_by=user.id)
    db.add(thought)
    db.flush()
    db.add(ItemLink(item_id=thought.id, target_table="chapter", target_id=third.id))
    # where the writer stopped last time, with a note for next time
    db.add(SessionNote(chapter_id=third.id, user_id=user.id, note="Tamsin opens the compass in front of Brother Cade",
                       cursor=third.body.find("Home, then.")))
    # and one in a journal entry (docs/SPEC.md §14.4)
    loose = db.scalars(select(JournalEntry).where(JournalEntry.world_id == world.id,
                                                  JournalEntry.title == "Loose threads")).one()
    db.add(JournalNote(journal_id=loose.id, user_id=user.id, note="Settle Hesper's age before chapter two of Ash Season",
                       cursor=len(loose.body)))
    db.flush()
    return world
