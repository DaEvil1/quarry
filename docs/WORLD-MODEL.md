# The world model (phases 6–9)

The manuscript stays plain text. Behind it, the world becomes **data**: who and what exists, how they are connected,
and when each of those things is true. Quarry keeps the two joined while you write: names in the prose link to the
data, and the data tells you what you have and haven't settled. Think of LaTeX: you write text, and the structure
around it is checked and assembled for you, but with nothing to learn and no markup to type.

This builds on what exists (entities, aliases, mentions, the name check, tags) and stays inside the principles:

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
| Place | anything with a where: regions, cities, houses, rooms |
| Faction | groups with a will: houses, guilds, armies, cults |
| Culture | peoples, religions, traditions, languages |
| Event | something that happened, at a place, with participants, in a chapter |
| Object | things that matter: a logbook, a ship, a sword |
| Term | lore and concepts: a magic system, a title, a law |
| Other | everything else |

The nav lists the kinds under **World**, each with its count, instead of one "Bible" entry. The bible page per kind
is a table with search and the kind's own columns.

## 2. An entry

Every entry has:

- **Name** and **other names**, shown at the top of the entry and editable in place.
- **One line** (a summary shown when hovering a name anywhere) and **notes** (free Markdown).
- **Matching:**
  - *Match capitals exactly* is on by default; switch it off for names that are never ordinary words.
  - For characters with a multi-word name, the *first name* also matches unless another entry claims it.
- **Facts**: labelled values, optionally true only for a stretch of the story (§4).
  - Some are suggested per kind, e.g. a character's *status* (alive, dead, missing), *age* and *role*.
  - You can add your own (*eye colour: grey*).
  - "Status: dead from chapter 9" is a fact like any other.
- **Relationships** (§3), shown grouped by type, with the other entry's one-liner.
- What exists today stays: mentions, first appearance, tagged items, possible misspellings, and now the
  **decisions** that are tagged with it or name it.

## 3. Relationships

A relationship joins two entries with a **type**, in a direction where it matters. For example, *Varren is the
father of Isolde* is read back from Isolde's side as *Isolde is the daughter of Varren*.

Each world starts with a vocabulary per pair of kinds, and you can rename, add or remove types:

| Between | Starting types |
|---|---|
| Character – character | parent/child, sibling, married, lovers, friends, rivals, enemies, serves/served by, mentor/student, knows |
| Character – place | lives in, born in, rules, works at, imprisoned in, visits |
| Character – faction | member of, leads, founded, opposes |
| Character – culture | belongs to, converted to |
| Character – object | owns, carries, made, seeks |
| Place – place | inside/contains, borders, road to, sea route to |
| Faction – faction | allied, at war, vassal of/overlord of, splinter of |
| Faction – place | controls, based in, claims |
| Event – anything | took part in, happened at, caused, followed from |

A relationship can also carry:

- **When it holds**: *from* a chapter and/or *until* a chapter (§4). Left empty, it holds throughout.
- **Standing**: *canon* (true in the book), *planned* (true in your head, not on the page yet) or *rumour*
  (believed by someone in the story). Graphs and checks can include or leave out planned and rumour.
- **Where it was established**: the chapter, set automatically when you record it from the editor.
- **A note.**

Connections you never record still count as **evidence**: two names in the same paragraph, a character in a
chapter that mentions a place. Evidence is shown, never stored as fact (§6).

## 4. Story time

The **chapter is the clock**:

- Story order is the series order of projects in a world, then chapter order within each.
- Facts and relationships hold *from* and *until* chapters.
- Every entry page has an **"as of chapter …"** selector that shows what is true at that point.

**Where everyone is.** A grid with characters down the side and chapters across. Each cell shows:

- **Recorded**: an explicit "is at" (one click in the editor: *Varren is at Old Harbour in this chapter*).
- **Derived**: a place mentioned in the same paragraph as the character, shown fainter.
- **Present**: mentioned in the chapter, place unknown.

**In-world dates** come later: an optional date per chapter (free text with a sortable value), added without
changing anything above.

## 5. Views

- **Relationship graph.** Entries as nodes and relationships as edges. You can:
  - filter by kind, type and standing;
  - pick an *as of chapter*;
  - centre on one entry to see first- and second-order links;
  - colour **clusters**: groups more connected inside than outside, computed from recorded relationships, with
    co-occurrence as an option.
- **Place tree.** Places nested by *inside/contains*, with who lives or is there at a chosen chapter.
- **Cast per chapter.** On the manuscript page, the characters and places of each chapter.
- **Later: your own map.** Upload a map image, pin places on it, and see who is where as of a chapter.

## 6. The writing companion

A panel beside the editor (and a **Checks** page for the whole world) that keeps the world and the prose in step.
Each line has one-click actions and can be dismissed for good.

**In this chapter**

- The **cast**: everyone mentioned, with what is true *as of this chapter*: status, where they are, and how they
  are connected to each other.
- **Unrecorded connections**: "Varren and Isolde share a paragraph three times here and nothing connects them."
  → *Record how* opens the relationship picker, with this chapter as *established in*.
- **Unknown names**: a capitalised word used repeatedly (not only at sentence starts) that isn't in the bible.
  → *Add as character / place / …*, or *Not a name*.
- **Where are they?**: a character with several places in their paragraphs and no "is at" for this chapter.
  → pick one.

**Checks** (rules over recorded data, listed per chapter):

- Mentioned in a chapter where they are recorded dead (or before they are born or introduced).
- Recorded at two places in the same chapter.
- A POV character who isn't mentioned in their own chapter.
- A relationship *from* a chapter that comes after its *until*.
- A place inside itself (cycles in the place tree).

Each check says what it found and where. "Fine as it is" silences that one finding.

**Margin notes.** A line starting with `%%` in a chapter is a note to yourself. It is shown dimmed, ignored by the
word count and left out of the compiled manuscript and the export's `manuscript.md`. It is still exported (in the
chapter file) so nothing is lost.

## 7. Data model additions

```sql
entities          + summary text, match_case bool, first_name_alias bool         -- kinds gain culture, event
facts             (id, entity_id, label, value, from_chapter_id NULL, until_chapter_id NULL,
                   standing, established_in_chapter_id NULL, note, version)
relation_types    (id, world_id, a_kind, b_kind, label, reverse_label NULL, symmetric, position)
relationships     (id, world_id, type_id, a_id, b_id, from_chapter_id NULL, until_chapter_id NULL,
                   standing, established_in_chapter_id NULL, note, version)
presence          (id, entity_id, place_id, chapter_id, note)                     -- explicit "is at"
decision_links    (decision_id, entity_id)
dismissals        (world_id, rule, key)                                           -- "fine as it is"
chapters          + in_world_date NULL (later)
map_images, map_pins                                                              -- later
```

Co-occurrence (two entries in one paragraph) is computed from the mentions on save, at paragraph level, and stored
per chapter for the graph and the companion.

## 8. Phases

6. **The bible as data.**
   - The kinds in the nav, a page per kind, and the entry page reworked: one-liner, other names in place, matching
     options, facts, and decisions about it.
   - Relationships with the starting vocabulary and an editor for it.
   - Faction and place hierarchies via relationships, and Culture as a new kind.
   - *Done when* Varren's page shows that he is Isolde's father, lives in Old Harbour and belongs to the Lamp
     Guild, and Isolde's page shows the reverse, with a one-liner on hover wherever their names appear.
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
   - The editor panel (cast as of this chapter, unrecorded connections, unknown names, where are they), the Checks
     page, dismissals, and margin notes.
   - *Done when*, writing a scene with two unconnected characters and a new name, the panel offers to record their
     connection and to add the name, each in one click, and a character recorded dead who appears later is listed
     on Checks.
10. **Later:** in-world dates, and map images with pins.

## 9. Not planned

- Anything that writes, rewrites or proposes story content.
- Automatic relationship *types* from the prose: the companion shows evidence, you name the connection.
- A rigid schema per kind: suggested fields only, anything can be added or left empty.
