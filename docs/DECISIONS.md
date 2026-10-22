# Decisions

Dated one-line verdicts. The reasoning lives in the spec and in PR discussions.

- 2026-10-20: Build a custom app instead of adopting Obsidian or Scrivener, so the tool fits the process rather than the other way round.
- 2026-10-20: Postgres is the source of truth; CodeMirror 6 for the editor; FastAPI + Vue 3 PWA; Android phone; passkey login in the app.
- 2026-10-21: Name is Quarry.
- 2026-10-21: No content git repo. Database backups plus "Export now" cover safety; a git mirror may come back later as an option.
- 2026-10-21: A world level sits above projects. The bible belongs to the world; manuscripts belong to projects; items, journal and decisions can be either.
- 2026-10-21: A users table from day one (single user for now), because co-writing is a real possibility.
- 2026-10-21: The code repo is public, so no story content is ever committed; tests use made-up fixtures.
- 2026-10-21: Deploy like Gauntlet (droplet, host nginx, managed Postgres, image from GHCR), not on Komodo.
- 2026-10-21: No importer for the Google Doc or the Obsidian vault. Quarry starts empty; after phase 4 the doc is converted by hand into the export layout and loaded with Restore.
- 2026-10-21: Phase 1 live at quarry.daevil1.com. Passkeys from 1Password don't reach Chrome on Android (Pixel 8, Android 17), so the phone has its own passkey; Quarry needs no change for either.
- 2026-10-21: Capture's entity tag moves to phase 3, where entities exist. Phase 2 links captures to a project or the whole world only.
- 2026-10-21: On the phone, tapping an item opens its actions instead of swipe gestures; every close can be undone.
- 2026-10-21: Offline in phase 2 means new captures and opening the app; the inbox and triage need the network until the local copy in phase 5.
- 2026-10-21: The Journal is built in phase 3. The spec described it but gave it no phase, and the planning essays need a home before the move after phase 4.
- 2026-10-21: Near misses: one edit for words of 5–6 letters, two for 7 or more, with a swapped pair counting as one edit (OSA distance). Two edits on short words flagged too many ordinary words.
- 2026-10-21: Mentions are recomputed on save, and for the whole world when names, aliases or "not a typo" words change; fast enough at a novel's scale, so no background jobs.
- 2026-10-21: Chapters are never deleted once they hold text or history: they are retired to Salvage, and can be put back. Only an empty, history-less chapter (a mistake) can be deleted.
- 2026-10-21: Experiment items are closed from their chapter (accept/harvest/reject), not from the inbox, so the manuscript and the item can't disagree.
- 2026-10-21: Restore always makes a new world with new ids; it never merges into an existing one. History (revisions) is not exported.
- 2026-10-21: Linking items to chapters is allowed by the data model but has no screen yet; tags on items stay bible entries for v1.
- 2026-10-21: The offline copy covers chapters and their last 30 revisions (sync per world, by time); the rest of a world is read online. The spec's general `change_log` sync wasn't needed for v1.
- 2026-10-21: Text typed in a chapter is kept on the device until the server confirms it; a draft over an older version becomes a conflict revision rather than overwriting anything.
- 2026-10-22: After using v1, the bible becomes a world model: entries with facts and typed relationships, story time, graphs and a writing companion (docs/WORLD-MODEL.md), as phases 6–9.
- 2026-10-22: Chapters are the story clock (facts and relationships hold from/until chapters); in-world dates come later.
- 2026-10-22: Relationship graph and place tree first; uploaded map images with pins later.
- 2026-10-22: New kinds Event and Culture; lore stays in Term.
- 2026-10-22: Research (docs/research/) adds to the world model: evidence on facts and relationships, knows/has met, resolved findings (intentional/later), Drafting vs Revising, getting back in, spell-check skipping names, per-entry "not in this sense". A cuts bin, revision passes, a thread grid, scenes and a corkboard wait for later.
- 2026-10-22: The companion's findings are grouped into five editors (Proofreader, Continuity, Connections, Archivist, Loose ends): tabs that can be switched off, all rule-based, all silent while Drafting.
- 2026-10-22: Phase 6: names are matched in the browser by a port of the server's matcher, from cards kept on the device; the server stays the source for mentions and counts.
- 2026-10-22: Writing preferences are per device (localStorage), not per user: a phone and a desk want different text sizes and card timings.
- 2026-10-22: Selecting a known name shows its card; on Android a long-press selects the word, so that is the phone's long-press without custom touch handling.
- 2026-10-22: Performance budget for typing: press-to-paint within two frames for a 10,000-word chapter and 400 entries, also at 4× slower CPU. Met after remembering each word's misspelling verdict and each paragraph's names, updating the word count when typing pauses, and keeping the chapter sidebar out of per-keystroke re-renders.
- 2026-10-22: Phase 7: a fact with a "from" chapter takes over from earlier facts with the same label, so "status: dead from chapter 9" needs no end date on "alive". Spans are inclusive and must run forwards.
- 2026-10-22: "Is at" is one place per character per chapter; moving within a chapter is a note, not a second row. Derived places (named in the same paragraph) are computed when the grid is read, never stored.
- 2026-10-22: Story order is project order, then chapter order; experiments and retired chapters are outside it, and a span bounded by one simply ignores that bound.
