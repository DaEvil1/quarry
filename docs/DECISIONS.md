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
