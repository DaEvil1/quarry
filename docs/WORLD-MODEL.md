# The world model (phases 6–9)

The manuscript stays plain text. Behind it, the world becomes **data**: who and what exists, how they are connected,
and when each of those things is true. Quarry keeps the two joined while you write: names in the prose link to the
data, and the data tells you what you have and haven't settled. Think of LaTeX: you write text, and the structure
around it is checked and assembled for you, but with nothing to learn and no markup to type.

This builds on what exists (entities, aliases, mentions, the name check, tags) and on the research in
[research/](research/README.md). It stays inside the principles:

- **No AI in the story.** Every suggestion below is a rule applied to your own data: "these two share a scene and
  nothing connects them", never "here is what could happen".
- **Cheap habits only.** Recording a connection takes one click from where you noticed it. Nothing has to be filled
  in up front; an empty field is fine forever.
- **Prose stays pure.** The compiled manuscript and the export contain only your text.

Examples here use made-up names.

## 1. Kinds of things

| Kind | For |
|---|---|
| Character | people, and anyone who acts |
| Species | kinds of being: peoples, beasts, spirits, ancient races (from phase 12, [SPEC.md](SPEC.md) §13.3) |
| Place | anything with a where: regions, cities, houses, rooms |
| Faction | groups with a will: houses, guilds, armies, cults |
| Culture | what people share: religions, traditions, languages |
| Event | something that happened, at a place, with participants, in a chapter |
| Object | things that matter: a logbook, a ship, a sword |
| Term | lore and concepts: a magic system, a title, a law |
| Other | everything else |

From phase 13 an entry can also **add a kind** and stay one entry: a world that is a place and acts is a place that
is also a character, listed under both ([SPEC.md](SPEC.md) §14.8).

The nav lists the kinds under **World**, each with its count, instead of one "Bible" entry. The bible page per kind
is a table with search and the kind's own columns.

## 2. An entry

Every entry has:

- **Name** and **other names**, shown at the top of the entry and editable in place.
- **One line** (a summary shown when hovering a name anywhere) and **notes** (free Markdown).
- **Matching:**
  - *Match capitals exactly* is on by default; switch it off for names that are never ordinary words.
  - For characters with a multi-word name, the *first name* also matches unless another entry is called that.
    A first name or other name that two entries claim is *shared*: a bare use is ambiguous until a margin-note
    line such as `%% Isolde: Isolde Marr` says who it means from there on ([SPEC.md](SPEC.md) §14.10).
  - *Not in this sense*: phrases where the name is an ordinary word ("rose garden" for a character called Rose),
    added from the card when a match is wrong, so it is never matched there again.
- **Facts**: labelled values, optionally true only for a stretch of the story (§4).
  - Some are suggested per kind, e.g. a character's *status* (alive, dead, missing), *age* and *role*.
  - You can add your own (*eye colour: grey*).
  - "Status: dead from chapter 9" is a fact like any other.
  - A fact can keep its **evidence**: the chapter and the passage that established it. Selecting a passage in a
    chapter and recording a fact from it fills both in. From phase 13 a fact can also say where it was
    **planned**: a journal entry and its passage, never a place in the story. Anything recorded outside a chapter
    starts as *planned*, and stays so until it is in the book or marked canon ([SPEC.md](SPEC.md) §14.1.2).
- **Relationships** (§3), shown grouped by type, with the other entry's one-liner.
- What exists today stays: mentions, first appearance, tagged items, possible misspellings, and now the
  **decisions** that are tagged with it or name it.

## 3. Relationships

A relationship joins two entries with a **type**, in a direction where it matters. For example, *Varren is the
father of Isolde* is read back from Isolde's side as *Isolde is the daughter of Varren*.

**Any kind can be related to any kind.** Each world starts with a vocabulary per pair of kinds; you can rename,
add or remove types, and every pair also has a plain *linked to* for when you don't want to name the connection yet:

| Between | Starting types |
|---|---|
| Character – character | parent/child, sibling, married, lovers, friends, rivals, enemies, serves/served by, mentor/student, knows, knows about (one way), has met; possesses/possessed by, ancestor/descendant (phase 12) |
| Character – place | lives in, born in, rules, works at, imprisoned in, visits |
| Character – faction | member of, leads, founded, opposes |
| Character – culture | belongs to, converted to |
| Character – object | owns, carries, made, seeks, lost, guards |
| Character – event | witnessed (from phase 11, [SPEC.md](SPEC.md) §12.5) |
| Character – species | is a/includes, appears as/the guise of (from phase 12, [SPEC.md](SPEC.md) §13.3) |
| Species – species | descended from/ancestor of, related to, preys on/prey of |
| Species – place | native to/home of |
| Culture – species, faction – species | culture of/has culture, made up of/makes up |
| Place – place | inside/contains, borders, road to, sea route to |
| Faction – faction | allied, at war, vassal of/overlord of, splinter of |
| Faction – place | controls, based in, claims |
| Faction – object | owns, symbol of, seeks, guards |
| Faction – culture | rooted in, persecutes |
| Object – object | part of/has part, key to, copy of, paired with |
| Object – place | kept at, hidden in, made in, lost at |
| Object – culture | sacred to, made by |
| Culture – place | native to, spread to |
| Culture – culture | descended from, related to |
| Term – anything | applies to, practised by, origin |
| Event – anything | took part in, happened at, caused, followed from, involved |

A relationship can also carry:

- **When it holds**: *from* a chapter and/or *until* a chapter (§4), or from phase 12 an in-world time instead of a
  chapter. Left empty, it holds throughout.
- **A role** (from phase 12), on types marked *has a role* such as *member of* and *leads*: `Captain`
  ([SPEC.md](SPEC.md) §13.4).
- **Standing**: *canon* (true in the book), *planned* (true in your head, not on the page yet) or *rumour*
  (believed by someone in the story). Graphs and checks can include or leave out planned and rumour.
- **Evidence**: the chapter where it was established and, optionally, the passage (as for facts). Set
  automatically when it is recorded from the editor.
- **A note.**

**Who knows what** is one of the most common continuity failures, so *knows* and *knows about* are ordinary,
time-bounded relationships ("Isolde knows about the second logbook from chapter 7"), and *have they met?* is
answered from the chapters where both were present (§4), until you record otherwise.

Connections you never record still count as **evidence**: two names in the same paragraph, a character in a
chapter that mentions a place. Evidence is shown, never stored as fact (§7).

## 4. Story time

The **chapter is the clock**, and from phase 12 the chapters can be set in **in-world time**
([SPEC.md](SPEC.md) §13.1):

- **Told order** is the series order of projects in a world, then chapter order within each: the order the reader
  meets things in.
- A chapter can say **when it is set**: one sortable number in the world's unit (years by default), with an optional
  free label (`800 years before the Founding`), an *about* tick and an optional end. There is no calendar: no months,
  moons or date arithmetic, only numbers that sort. A chapter can also be marked as **told as a tale or flashback**.
- A time can also be **outside time**: a plane beyond the world, an afterlife, a vision, a myth or a prophecy.
  Chapters, events, facts and relationships outside time are never placed on the axis or compared, and are always
  shown under *as of*, labelled as such.
- Named **eras** (events of the type *era*, each with a colour) tint every time shown with their name:
  `year 312 · the Lamp Years`.
- **Happened order** sorts chapters by when they are set, then by told order. A chapter with no time carries on from
  the last chapter before it that has one and isn't a tale or flashback; a tale or flashback with no time is set
  sometime before the story. **With no times and no marks, happened order is told order**, and everything works as it
  did before phase 12.
- Facts and relationships hold *from* and *until* chapters, read in **happened** order, or *from* and *until* an
  in-world time, for history before the book. So someone recorded dead in chapter 9 is alive in a tale set centuries
  earlier, wherever the tale sits in the book. A time bound outlives restructuring, where a chapter bound has to be
  reviewed when its chapter is retired ([SPEC.md](SPEC.md) §13.6).
- Every entry page has an **"as of chapter …"** selector that shows what is true at that point; once the world uses
  times, it also takes a time.
- The rule for which order is used: **told order is the reader's** (the manuscript, the mentions strip and its gaps,
  first appearance, reading one entry's thread); **happened order is the world's** (facts and relationships, *as of*,
  the cards and the cast, the family tree, the Continuity checks, ages).

**Where everyone is.** A grid with characters down the side and chapters across. Each cell shows:

- **Recorded**: an explicit "is at" (one click in the editor: *Varren is at Old Harbour in this chapter*).
- **Derived**: a place mentioned in the same paragraph as the character, shown fainter.
- **Present**: mentioned in the chapter, place unknown.

It keeps told order, with a switch to happened order once chapters have times.

**History and the Timeline.** Events get a time (or a chapter they happen in), and one Timeline page shows the world
in happened order or told order, with the book as a band among the world's history, eras as background bands,
births, deaths and movements, and lanes per character or faction ([SPEC.md](SPEC.md) §13.2).

## 5. Writing in the editor

The rule: **nothing ever appears under the cursor or takes the keyboard while you type.** No dropdowns, no
completion lists, no dialogs. The world shows itself around the text, never in its way.

- **Names light up as you type.** The editor colours every known name by kind, the moment it's written: characters
  one colour, places another, factions, objects and the rest their own. The matching runs in the browser on the
  names kept on the device, so it doesn't wait for a save and works offline. The colours are quiet tints in both
  themes, and can be switched off ("plain text" mode).
- **Hover (or long-press on the phone) shows the card**: the one-liner, key facts *as of this chapter*, and the
  closest relationships, with a link to the entry. The card never takes focus; moving on hides it.
- **Likely misspellings** keep their wavy underline. **Possible new names** (a capitalised word that recurs and
  isn't in the bible) get a faint dotted underline, so they can be dealt with later in the panel, or not at all.
- **Everything else waits in the side panel** (§7): suggestions arrive there quietly, sorted by strength, and can be
  ignored for as long as you like. The panel can be closed; focus mode hides it.

**Passive while typing, one gesture away when wanted.** Drafting and classifying pull in opposite directions, so the
editor answers *intent*, never keystrokes:

- **Typing is sacred.** While keys are being pressed, and for about a second after, nothing opens, even if the
  pointer rests on a word. Only colours and underlines update.
- **The quick-fix strip.** Pointing at a marked word for a moment shows one row of small chips just below it,
  about one line high. It never takes focus, never moves the text, and disappears when the pointer leaves or
  typing resumes. One click acts:
  - *Likely misspelling* (wavy): `Varren? → Replace · Another spelling · Not a typo`
  - *Possible new name* (dotted): `+ Character · Place · Faction · Object · … · Not a name`. The word is in the bible
    and coloured at once.
  - *Known name*: its card (one-liner, facts as of this chapter, closest relationships) with `Link to…` for
    recording a relationship.
- **Selection is intent too.** Selecting words (a multi-word name, a lowercase thing the detector would never
  guess) offers the same strip: `+ Character / Place / …` or `Another name of…`.
- **Keyboard, like an IDE quick fix.** With the cursor in a marked word, **Alt+Enter** opens the strip with the
  keyboard in it: arrows to choose, Enter to apply, Esc straight back to the text.
- **A classifying pass.** **F8** jumps to the next marked word in the chapter with its strip open, for sweeping
  through new names after a drafting session, like a spell-check pass.
- **On the phone**, a long-press opens the strip.
- What exists stays: autosave, snapshots, focus mode, typewriter scrolling, word count.

**Drafting and revising.** A switch in the editor:

- *Drafting* (the default): names are coloured and cards work, but no wavy or dotted underlines are drawn, and the
  side panel collects its findings without showing new ones until a natural break: opening the panel, a scene
  break (a blank line after `***`), or the end of the session.
- *Revising*: underlines inline, and the panel shows everything as it is found.

Pauses while typing are where writers plan the next sentence (research/04), so nothing is ever shown because typing
paused.

**Small rules**, from what writers complain about in other tools:

- Typewriter scrolling recentres only while typing, never when you click or select.
- Cards close on any keystroke. A setting shows them only while Ctrl is held.
- Names are marked for the browser's spell-check to skip, so invented names aren't flagged.
- New entries start as just a name; nothing has to be filled in.

**Settings** (per device): colours by kind on/off and per kind, underlines in Drafting on/off, card delay, cards
only with Ctrl, typing quiet period, text size and line width, and the default mode.

## 6. Views

- **Relationship graph.** Entries as nodes and relationships as edges. You can:
  - filter by kind, type and standing;
  - pick an *as of chapter*;
  - centre on one entry to see first- and second-order links;
  - colour **clusters**: groups more connected inside than outside, computed from recorded relationships, with
    co-occurrence as an option.
- **Place tree.** Places nested by *inside/contains*, with who lives or is there at a chosen chapter.
- **Cast per chapter.** On the manuscript page, the characters and places of each chapter.
- **The chart** (from phase 12, [SPEC.md](SPEC.md) §13.7): a schematic map of the places, drawn from how they nest,
  border and connect, with shapes by type, pins to shape it by hand, and an optional *as of*.
- **Later: your own map.** Upload a map image, pin places on it, and see who is where as of a chapter. The chart
  doesn't replace it.

## 7. The writing companion

A panel beside the editor (and a **Checks** page for the whole world) that keeps the world and the prose in step.
Each line has one-click actions and can be dismissed for good.

**Five editors.** The findings are grouped into editors, each a lens with one focus. Each is a tab in the panel,
can be switched off, and has its own "show inline while Revising" setting; Drafting silences them all. They are
collections of rule-based findings, nothing more: none of them rewrites a sentence or suggests story content.

| Editor | Looks at |
|---|---|
| **Proofreader** | spelling (aware of the bible's names), likely misspelled names, doubled words, the same word repeated close together, stray spaces and punctuation, optionally very long sentences |
| **Continuity** | the checks below: dead but mentioned, two places at once, conflicting facts, knowing too early |
| **Connections** | unrecorded connections by strength, have they met, where are they |
| **Archivist** | the bible itself: possible new names, entries without a one-liner, entries never mentioned, other names worth adding |
| **Loose ends** | your own threads: open items and questions tied to the chapter, TK placeholders, margin notes, the note to yourself |

The sections below describe what each editor finds.

**In this chapter**

- The **cast**: everyone mentioned, with what is true *as of this chapter*: status, where they are, and how they
  are connected to each other.
- **Unrecorded connections**, for any two kinds (a character and an object, a faction and a place …), with a
  strength from how close they appear:
  - **strong**: in the same sentence;
  - **medium**: in the same paragraph;
  - **weak**: only in the same chapter.

  Repeats add up ("Varren and the logbook share a sentence three times here"). Strong ones come first; weak ones
  are folded away unless asked for. *Record how* opens the relationship picker with this chapter as *established
  in*; *Not connected* silences the pair.
- **Unknown names**: a capitalised word used repeatedly (not only at sentence starts) that isn't in the bible.
  → *Add as character / place / …*, or *Not a name*.
- **Where are they?**: a character with several places in their paragraphs and no "is at" for this chapter.
  → pick one.

**Getting back in.** When a chapter opens, the panel shows where you stopped and, if you left one, a one-line note
to yourself ("what's next") asked for, skippably, when you leave the chapter. A key stashes a passing thought in the
inbox, tagged with the chapter, without leaving the sentence.

**Checks** (rules over recorded data, listed per chapter):

- Mentioned in a chapter where they are recorded dead (or before they are born or introduced).
- Recorded at two places in the same chapter.
- A POV character who isn't mentioned in their own chapter.
- A relationship *from* a chapter that comes after its *until*.
- A place inside itself (cycles in the place tree).
- Two values of the same fact that hold at the same time (eye colour grey from chapter 1, brown from chapter 4),
  unless the label is marked as holding several values ([SPEC.md](SPEC.md) §12.6.4).
- Knowing too early: a *knows* that starts after a chapter where the character acts on it is only flagged when
  you have recorded the act; nothing is guessed from prose.

Each finding says what it found and where, and is **resolved** rather than just dismissed: *fix the text*, *update
the fact*, *intentional* (planted on purpose: never flagged again) or *later* (kept on a list).

**Margin notes.** A line starting with `%%` in a chapter is a note to yourself. It is shown dimmed, ignored by the
word count and left out of the compiled manuscript and the export's `manuscript.md`. It is still exported (in the
chapter file) so nothing is lost. A margin note of the form `%% Isolde: Isolde Marr` is also a choice: it
says which entry a shared name means from that line on ([SPEC.md](SPEC.md) §14.10).

## 8. Data model additions

```sql
entities          + summary text, match_case bool, first_name_alias bool         -- kinds gain culture, event
entities          + exclusions text[]                                              -- "not in this sense"
facts             (id, entity_id, label, value, from_chapter_id NULL, until_chapter_id NULL,
                   standing, established_in_chapter_id NULL, evidence NULL, note, version)
relation_types    (id, world_id, a_kind, b_kind, label, reverse_label NULL, symmetric, position)
relationships     (id, world_id, type_id, a_id, b_id, from_chapter_id NULL, until_chapter_id NULL,
                   standing, established_in_chapter_id NULL, evidence NULL, note, version)
presence          (id, entity_id, place_id, chapter_id, note)                     -- explicit "is at"
decision_links    (decision_id, entity_id)
resolutions       (world_id, rule, key, outcome, note)                            -- intentional / later / not connected
session_notes     (chapter_id, user_id, note, cursor, updated_at)                 -- getting back in
chapters          + time_at, time_end, time_label, time_approx, told_as             -- phase 12, SPEC.md §13.8
map_images, map_pins                                                              -- later
```

Co-occurrence (two entries in the same sentence, paragraph or chapter) is computed from the mentions on save, and
stored per chapter with its strength for the graph and the companion. The browser does the same matching live for
highlighting; the server's result is the one that is stored.

## 9. Phases

6. **The bible as data.**
   - The kinds in the nav, a page per kind, and the entry page reworked: one-liner, other names in place, matching
     options (capitals, first names, *not in this sense*), facts with evidence, and decisions about it.
   - Live highlighting by kind in the editor and hover cards (§5), with the matching running in the browser, the
     small rules, the settings, and the quick-fix strip for misspellings, known names and selections.
   - Relationships with the starting vocabulary and an editor for it.
   - Faction and place hierarchies via relationships, and Culture as a new kind.
   - *Done when* Varren's page shows that he is Isolde's father, lives in Old Harbour and belongs to the Lamp
     Guild, Isolde's page shows the reverse, and typing their names in a chapter colours them by kind at once,
     with their cards on hover and no popup while typing.
7. **Story time and events.**
   - *From/until* on facts and relationships, *as of chapter* on entry pages, and the Event kind.
   - "Is at" presence, and the Where-everyone-is grid.
   - *Done when* "Varren: dead from chapter 9" makes his page show *alive* as of chapter 8 and *dead* as of
     chapter 9, and the grid shows where each character is per chapter, recorded and derived.
8. **Views.**
   - The relationship graph (filters, as of chapter, first and second order, clusters), the place tree, and the
     cast per chapter.
   - *Done when* centring on a character shows who they know directly and through one other person, and the graph
     separates two groups that only know each other through one character.
9. **The writing companion.**
   - The editor panel with its five editors (Proofreader, Continuity, Connections, Archivist, Loose ends):
     cast as of this chapter, unrecorded connections by strength, possible new names, where are they, the
     proofreading rules; Drafting/Revising, getting back in (session note, stash a thought), the Checks page with
     resolutions, Alt+Enter and F8, and margin notes.
   - *Done when*, writing a scene with two unconnected characters and a new name, the panel offers to record their
     connection and to add the name, each in one click, and a character recorded dead who appears later is listed
     on Checks.
10. **Revising and salvaging** (a cuts bin, chapter summaries and statuses, changes since a labelled checkpoint, and
    more) is designed in [SPEC.md](SPEC.md) §11.
11. **More views of the bible** (a mentions strip per entry, a family tree with kin worked out, a grid of any
    entries across chapters, world entries and project entries, labels and values) is designed in [SPEC.md](SPEC.md) §12.
12. **Time, history and kinds of being** (in-world time under the chapters, happened and told order, the Timeline and
    history, recording an event from a passage, ages, Species, roles in groups, more starting vocabulary,
    restructuring across several chapters, and the chart) is designed in [SPEC.md](SPEC.md) §13.
13. **Planning before writing** (the editor's world tools in the Journal, planned in the Journal and canon in the
    book, reading an entry's thread through the planning, sparks and questions from a passage, a front page for the
    world, "since this was written", "Include planned" on the checks, cause arrows on the Timeline, and entries of
    more than one kind) is designed in [SPEC.md](SPEC.md) §14.

**Later:** map images with pins, and from the research: a chapter-by-thread grid, scenes below
chapters, and a corkboard (research/README.md).

## 10. Not planned

- Anything that writes, rewrites or proposes story content.
- Automatic relationship *types* from the prose: the companion shows evidence, you name the connection.
- A rigid schema per kind: suggested fields only, anything can be added or left empty.
