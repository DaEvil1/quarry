# Research: how writers work, and what that means for Quarry

Four surveys made before building the world model (phases 6–9), and a second round comparing Quarry with other
tools (05–07). Each file cites its sources and marks how solid they are (the author's own words or research, versus
summaries and anecdote).

| File | About |
|---|---|
| [01-novelists-process.md](01-novelists-process.md) | how novelists draft, revise, keep notes and track continuity (about 30 sources) |
| [02-worldbuilding-bibles.md](02-worldbuilding-bibles.md) | series bibles, continuity editors, writers' rooms, fan wikis, common continuity errors |
| [03-writing-tools.md](03-writing-tools.md) | what writers praise and hate in 19 writing tools, especially name detection and hover cards |
| [04-drafting-flow.md](04-drafting-flow.md) | flow, interruptions and feedback while drafting, across kinds of writers (about 40 sources) |
| [05-world-anvil.md](05-world-anvil.md) | World Anvil's features and data model as of 2026, and which of its concepts fit Quarry |
| [06-worldbuilding-tools.md](06-worldbuilding-tools.md) | Kanka, LegendKeeper, Campfire, Obsidian and plugins, Aeon Timeline, Talmaara and other lore tools: mechanics and data models |
| [07-writing-tools-features.md](07-writing-tools-features.md) | Scrivener, Novelcrafter, Plottr, Dabble, WriterDuet and other writing, planning and revision tools: features and concepts |

## What it confirmed

- **No markup, no popups while typing.** Tools that detect names in plain prose and show them quietly are liked;
  autolinkers that flood suggestions are the main failure (World Anvil). Even Obsidian made hover previews
  optional behind a held key. Predictive suggestions measurably change what people write.
- **The bible is optional, and grows from the text.** Some authors keep almost nothing on paper; the big series
  end up with a wiki, a timeline spreadsheet and a continuity reader who adds facts *after* the text, with a
  page reference.
- **Aliases and spelling variants are the cheapest errors to catch**, and name detection feeds everything else.
- **Chapters as the clock fit how people work** (Rowling's chapter-by-subplot grid, script supervisors' "story
  days", Dickens's sheet per instalment).

## What it changes

1. **Facts and relationships carry their evidence.** Each can keep the passage that established it (chapter and
   quote). The quickest way to record one is selecting the passage. *(world model §2–3, §5)*
2. **Who knows what is a first-class relationship** (*knows*, time-bounded), and "have they met?" is answered from
   where characters have been. It is one of the most common continuity failures. *(§3, §7)*
3. **Contradictions are resolved, not just dismissed**: *fix the text*, *update the fact*, *intentional* (planted
   on purpose: never flagged again) or *later*. *(§7)*
4. **Drafting and revising are different moments.** Evaluation competes with producing text for the same working
   memory, and the pauses while typing are planning time. So the panel collects findings and shows them at
   natural breaks (opening it, a scene break, ending the session), not on a typing pause. A *Drafting / Revising*
   switch decides whether squiggles show inline. *(§5, §7)*
5. **Getting back in matters**: where you stopped, a one-line note to yourself at the end of a session shown when
   you return, and a key to stash a passing thought in the inbox without leaving the sentence. *(§7)*
6. **Spell-check must not flag invented names**: names are marked so the browser's checker skips them. *(§5)*
7. **Small editor rules from tool complaints**: typewriter scrolling recentres only while typing, never on a click;
   cards close on any keystroke; an option to show cards only while Ctrl is held; per-entry exclusions ("not in
   this sense", e.g. a name that is also a word). *(§2, §5)*

## Considered, and left for later

Each came up in the research and is worth having, but none is needed for the world model to be useful:

- a cuts bin (fragments cut from chapters, with their source, searchable, draggable back), extending Salvage;
- named revision passes ("draft 1", "structural", "polish") on snapshots;
- a chapter-by-thread grid (plot threads as rows), and a scene level below chapters;
- story time as dates or "N days after", travel times, ages from birth dates;
- a corkboard of chapter summaries.

## Not building

Calendars or astronomy engines, map-scale geography, mandatory templates, streaks or guilt prompts, anything that
rewrites the writer's text without being asked, and any suggestion of story content.

## Second round (competitors)

Files 05–07 compare Quarry with World Anvil, other worldbuilding tools and novel-writing tools. They confirm the
design: computed mentions with no markup, facts and relationships true from a chapter, and rule-based continuity
checks are things no surveyed tool does together (Talmaara comes closest, keyed on in-world dates). Nothing has been
scheduled from them yet. What they suggest:

**Cheap additions** (derived from data Quarry already has, or one optional field):

- a one-liner and a status per chapter, both optional;
- word history (new words per day) derived from revisions, with no input;
- on renaming an entry, keeping the old name as an alias;
- a family tree and kinship (siblings, grandparents) derived read-only from recorded relationships;
- reading the book filtered to the chapters or paragraphs where one entry appears;
- a heatmap of an entry's mentions across chapters on its page;
- a cuts bin (fragments cut from chapters, with their source);
- an overlay of what changed since a chosen checkpoint, while revising;
- project-wide find and replace.

**Later:**

- in-world date stored as one sortable number, shown as free text, with an "approximate" flag;
- told order versus happened order, once chapters have dates;
- ages computed as of a chapter, from a birth fact;
- map pins stored on place entries, so the map is a view of the bible;
- a general entries × chapters matrix (any kind or set of entries, not only characters);
- a thread grid, filled after writing.

**For co-writing:**

- a read-only share link to a frozen revision, whose comments become inbox items;
- roles (commenter first, editor later);
- a soft "someone is editing this chapter" lock on top of the existing conflict copies;
- DOCX and EPUB export.

**Not building:** secrets or per-reader visibility, calendar engines, scores on relationships, variables in prose,
templates and questionnaires, generators, streaks and deadlines.

**Name clash.** The Story Shack (thestoryshack.com) now sells a writing and worldbuilding app named "Quarry" (formerly
"Writer"), for the same audience ([06](06-worldbuilding-tools.md) §15).
