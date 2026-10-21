# Quarry — spec (draft 2)

A writing environment for long fiction set in shared worlds, built first for Thomas's current novel: capture sparks anywhere, triage them at the desk, keep a living bible of the world, and write the manuscript in a fast, dark, VS Code–feeling editor. Built around Thomas's existing process rather than a generic one.

Single-user today; the data model leaves room for co-writers later (§7).

## 1. Principles

1. **The process is the product.** The process runs spark → inbox → triage → canon/manuscript, with exploration allowed anywhere. The app models that loop directly.
2. **No AI in the creative path.** No generation, suggestions or critique of story content. Automation is limited to bookkeeping: mentions, name checks, counts, history and export.
3. **Nothing is ever lost.** Every meaningful state is versioned on the server and the database is backed up. "Export now" produces a folder of plain Markdown, so the book never depends on the app surviving.
4. **Writing never waits for the tool.** Each build phase is usable on its own. Prose can stay in other tools until the editor lands.
5. **Plain Markdown everywhere.** Prose, notes and bible entries are Markdown strings, so export is lossless.
6. **Cheap habits only.** Every ritual (status, decision line, harvest note) must take seconds, not minutes.
7. **No story content in this repo.** The code repo is public. Manuscripts, bible text and planning live only in the database and in exports. Tests use made-up fixtures.

## 2. Vocabulary

| Concept | What it is |
|---|---|
| **World** | A shared setting. Owns the bible. Holds any number of projects. Carries little else by default. |
| **Project** | One work in a world: a novel, novella, short story. Owns its manuscript. |
| **Chapter** | A unit of manuscript prose in a project. State is `current` (in the book), `experiment` (an alternate draft tied to an experiment item) or `retired` (salvage). Ordered by `position` among current chapters. Optional POV entity. |
| **Entity** | A bible page in a world: character, place, term, faction, object or other. Has a name, aliases and a body. Shared by every project in the world. |
| **Item** | Anything that needs attention: `spark`, `question`, `task` or `experiment`. Status is `open`, `accepted`, `rejected`, `harvested` or `deferred`. Belongs to a world and optionally to one project (an idea about the world in general has no project). Can link to entities and chapters. |
| **Journal entry** | Dated thinking-on-paper (the "What now?" kind of writing). World-level or project-level. Editable, but conceptually append-only. |
| **Decision** | A dated one-line verdict ("chapter 3 is now told by the sister"), optionally tied to the item it closes. World-level or project-level. |
| **Harvest note** | A short note on what was alive in a retired chapter or rejected experiment. Shown in the Salvage view. |
| **Revision** | An immutable snapshot of a document's body and metadata. |
| **Mention** | A computed occurrence of an entity (by name or alias) in any text. Never edited by hand. |
| **User** | A person who can sign in. Today there is exactly one. |

## 3. Data model (Postgres)

All tables carry `created_at` and `updated_at`. Mutable documents also carry `created_by`/`updated_by` (user ids), `version int` for optimistic concurrency and `change_seq bigint` for sync. Rows with a nullable `project_id` belong to the whole world when it is null.

```sql
users         (id, display_name, created_at)
worlds        (id, name, slug)
world_members (world_id, user_id, role)                         -- role: owner (only value for now)
projects      (id, world_id, name, slug, kind, position)        -- kind: novel|novella|short|other

chapters      (id, project_id, title, body, state,              -- current|experiment|retired
               position, pov_entity_id NULL, experiment_item_id NULL,
               version, change_seq, deleted_at NULL)

entities      (id, world_id, kind, name, aliases text[], body,
               version, change_seq, deleted_at NULL)

items         (id, world_id, project_id NULL, kind, title, body, status,
               closed_note NULL, closed_at NULL, source NULL,   -- "phone", "share:<app>", "desk"
               version, change_seq, deleted_at NULL)
item_links    (item_id, target_table, target_id)                -- entity/chapter/journal

journal       (id, world_id, project_id NULL, entry_date, title NULL, body,
               version, change_seq, deleted_at NULL)
decisions     (id, world_id, project_id NULL, decided_on, text, item_id NULL, change_seq)
harvest_notes (id, world_id, source_table, source_id, body, change_seq)

revisions     (id, doc_table, doc_id, version, title, body, meta jsonb,
               reason, created_by, created_at)                  -- append-only, never pruned
mentions      (source_table, source_id, entity_id, start, end, matched_text, kind)
                                                                -- kind: exact|alias|near_miss
name_ignores  (world_id, token)                                 -- near-misses marked "not a typo"

change_log    (seq bigserial, world_id, doc_table, doc_id, op)  -- feeds /sync
passkeys      (id, user_id, credential_id, public_key, sign_count, label, created_at, last_used_at)
recovery_codes(id, user_id, code_hash, used_at NULL)
sessions      (id, user_id, created_at, expires_at, user_agent)
```

First appearance is computed, not stored: for each entity and project, the earliest current chapter (by position) with a mention.

Scale check: the current material is about 320 KB of text. Even 1,000 revisions of everything stays in the tens of MB, so the server keeps every revision forever.

## 4. Saving, revisions and sync

**Autosave vs. revisions.** Typing autosaves the working copy (debounced to about 1.5 s), which updates the row and bumps `version`. It does **not** create a revision on every keystroke. A revision is snapshotted when any of these happens:
- the document is closed or the app is backgrounded
- 5 minutes pass with no typing after edits
- 30 minutes of continuous editing pass
- an explicit **Checkpoint** (Ctrl+S), with an optional label ("before splitting chapter")
- any state change (chapter retired, item closed, etc.)

**Concurrency.** A write sends `base_version`. If the server's version differs, it returns `409` with the server copy. The client then saves its text as a **conflict copy** (a revision with `reason=conflict`) and shows both versions side by side. There are no automatic merges and no CRDTs; with one writer per document at a time, conflicts should be rare.

**Sync protocol.**
- `GET /api/sync?since=<seq>` returns every changed document the user can see since that cursor, plus deletions.
- Writes go through normal REST endpoints. Offline writes queue in a local outbox and replay in order when the device is back online.
- Each device keeps the full working set and the **last 30 revisions of every document** in IndexedDB (via Dexie). It calls `navigator.storage.persist()` on first run so Chrome on Android doesn't evict the data.

**History UI.** Every document has a History panel: a revision list, a word-level diff against the current text, and buttons to restore or copy a passage.

## 5. Mentions and the name checker

Entities are world-level, so mentions are computed across every project in the world. When the server saves any text body:

1. It tokenises the text and matches every entity name and alias in the world, case-sensitively on the initial capital and on word boundaries. The match tolerates the suffixes `s`, `'s` and `’s` (so "Varrens" and "Varren’s" both match Varren) and multi-word names ("Old Harbour", "Iron Vale").
2. It writes the matches to `mentions` (`exact` or `alias`).
3. It flags a **near miss** when a capitalised token matches no entity but is within edit distance 2 of an entity name or alias (and at least 5 characters long) and is not in `name_ignores`. A typo such as "Varen" for Varren would be flagged.

In the editor, near misses get a subtle squiggle. A quick action offers **Add as alias**, **Replace with…** or **Not a typo**.

Bible pages show:
- **Mentions** grouped by project, then by chapter, journal entry and item
- **Unlinked appearances in planning**, meaning journal entries and items that mention the entity but aren't linked to it
- **First appearance** per project

## 6. Screens

**Look and feel.** Same bones as dev-cockpit (and Gauntlet, which already copies it): its colour tokens from `dev_cockpit/web/static/cockpit.css` for light and dark, the dark left nav with the brand on top, cards on a quiet background, small pills for status and kind, and the system UI font. Quarry differs where writing needs it: the editor gets a serif or comfortable reading face at a 70ch measure, and the nav collapses on the phone into a bottom tab bar.

**Navigation.** URLs are scoped as `/w/<world>/…` for world views and `/w/<world>/p/<project>/…` for project views. A switcher at the top of the nav picks the world and project; the app remembers the last one used per device. A world with a single project behaves like that project. The Bible, the world inbox and the world journal sit at world level; Manuscript, Experiments and Salvage are per project; Triage, Board, Journal and Decisions can be filtered to one project or show the whole world.

### Phone (Android PWA, portrait first)

- **Capture.** This opens by default. It has one big text field, kind chips (spark / question / task), a project chip (defaults to the last used; "world" for ideas not tied to one book) and an entity tag with autocomplete. Save works offline and clears the screen for the next capture.
- **Share target.** The app registers as an Android share target (Web Share Target API). Sharing text or a link from a browser, an e-book reader or a chat app opens Capture prefilled, with `source=share:<app>` recorded where available.
- **Inbox.** Open items, newest first. Swiping closes an item.
- **Look up.** Search across the world, plus read-only entity and chapter views.
- **Journal.** Quick dated entries.

### Desk (keyboard-first, VS Code feel)

- **Command palette** (Ctrl+K): jump to any world, project, chapter, entity, item or command.
- **Triage.** The inbox, one item at a time. Keys: `a` accept, `r` reject, `h` harvest, `d` defer, `l` link to entity, `p` move to project, `e` edit. Closing can prompt for a one-line decision, which is optional and skippable with Enter.
- **Board.** Open items as columns by kind, filterable by project and entity. "Questions" is its own column.
- **Editor.** The chapter in CodeMirror 6, with a side panel showing the entities mentioned in this chapter, linked items, POV, the word count, and History.
- **Bible.** Entity pages with Markdown bodies, aliases and the mention panels from §5.
- **Manuscript.** The project's current chapters in drag-to-reorder order, with word counts, POV and a derived POV tally. Experiments appear indented under the chapter they would replace.
- **Experiments.** Starting an experiment creates an `experiment` item and a draft chapter; it can begin from scratch (the old chapter is hidden while writing) or from a copy. Closing it as *accepted* swaps the draft into the manuscript and retires the old chapter. Closing it as *harvested* or *rejected* retires the draft and asks for a harvest note.
- **Salvage.** Retired chapters, each with its harvest notes and full-text search.
- **Journal** and **Decisions**: chronological lists with search.

### Editor requirements

- CodeMirror 6 with Markdown language support, a VS Code–style dark theme (and light), soft wrap, and a centred measure of about 70ch.
- Toggleable focus mode (dims all but the current paragraph) and typewriter scrolling.
- Smart quotes and dashes optional. The source text uses curly quotes, so those are preserved.
- Must stay smooth on a 10k-word chapter on a mid-range Android phone.

## 7. Users and auth (passkeys)

- **Users from day one.** There is one user, but passkeys, sessions, revisions and `created_by`/`updated_by` all point at a user, and access goes through `world_members`. Co-writing later then means adding a second member and deciding what they may do, not reworking every table.
- **Passkeys in the app.** WebAuthn via `py_webauthn`. The Relying Party ID is the app's domain, served over HTTPS. Login lives in the app rather than behind an auth proxy, because an offline PWA, its service worker and the share target need API calls that fail cleanly with a 401 instead of being redirected to a login page.
- **Bootstrap.** With zero users, `/setup` accepts a one-time `SETUP_TOKEN` from the environment, creates the first user, a first world, and registers the first passkey. After that, setup is disabled.
- **More devices.** From a signed-in session, choose "Add passkey" (desktop and the Android phone via Google Password Manager).
- **Recovery.** Ten one-time recovery codes are generated at setup and stored hashed. A CLI command `quarry passkey reset <user>` recovers from the server shell.
- Sessions use an httpOnly, Secure, SameSite=Strict cookie with a 30-day sliding expiry. CSRF is covered by SameSite plus an Origin check. Login is rate-limited.

## 8. Export, backups and import

- **Backups.** The Postgres server's own backups are the disaster-recovery path. Every revision lives in the database, so restoring the database restores the full history.
- **Export now.** Downloads a zip in the same layout as the Obsidian vault, one folder per world: `Bible/Characters`, `Bible/World`, `Journal/`, `Decisions.md`, and per project `Manuscript/`, `Planning/` (items) and `Old chapters & backstory/`, with YAML frontmatter carrying ids, status, links and aliases. Each project also gets a compiled `manuscript.md`.
- **Restore.** Imports an export zip into an empty world (or a new world), recreating worlds, projects, chapters, entities, items, journal, decisions and harvest notes from the files and their frontmatter. It is the only import path: there is no importer for other tools' formats.
- **Moving the existing material in.** Quarry starts empty. Once the editor is usable (after phase 4), Thomas provides the current Google Doc and Claude converts it by hand into the export layout: chapters, bible entries, planning notes as items or journal entries, and old chapters as retired chapters, with anything uncertain listed for Thomas to decide. The result is loaded with Restore and merged with whatever was captured in Quarry in the meantime. This is a one-time migration, done outside the repo.
- **Later, if wanted.** A scheduled export into a git repo (a local repo on the server, or a remote one) can be added as an optional setting. It is not part of the plan.

## 9. Tech stack, deploy and repo

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, py_webauthn, rapidfuzz (near misses) |
| DB | Postgres 16+, via `DATABASE_URL` (DigitalOcean managed cluster in production, a local container in development) |
| Frontend | Vue 3 + TypeScript + Vite, Pinia, vue-router, CodeMirror 6, Dexie, vite-plugin-pwa (Workbox) |
| Packaging | One image: FastAPI serves `/api` and the built SPA. GitHub Actions builds `ghcr.io/daevil1/quarry` on `master`. |
| Deploy | Same pattern as Gauntlet: the droplet runs the container from a compose file in `/srv/quarry`, bound to localhost, behind host nginx + certbot. One worker and a small DB pool: the droplet is shared, so no busy background work. |
| Tests | pytest (API, sync, mention matching), Vitest (stores, outbox), Playwright smoke test (capture offline → sync) |

```
quarry/                      # public GitHub repo (code only)
  backend/  app/ api/ models/ services/ mentions/ export/ auth/
            alembic/  tests/
  frontend/ src/ views/ components/ editor/ stores/ sync/
  deploy/   compose.yaml  .env.example
  docs/     SPEC.md  DECISIONS.md
```

## 10. Phases and "done when"

1. **Skeleton.** Repo, CI and image, compose, migrations (with users, worlds and projects), passkey setup and login with recovery codes, creating and switching worlds and projects, and the cockpit-style app shell on desktop and phone. *Done when* Thomas signs in with a passkey on the phone and the desktop and creates a world with a project in it.
2. **Capture and triage.** The phone Capture screen, share target, Inbox, desk Triage with keyboard closing, Decisions, and the offline outbox. *Done when* a spark shared from Chrome on Android while in airplane mode appears in desk Triage after reconnecting.
3. **Bible and mentions.** Entity editing, aliases, mentions, near-miss detection, and bible panels. *Done when* a misspelled entity name in a chapter or note is flagged and can be fixed or added as an alias in one action.
4. **Manuscript, editor, export and restore.** CodeMirror editor, autosave/revision rules, History with diffs, chapter ordering, POV tally, experiments and salvage, plus the export zip and Restore. *Done when* a full chapter rewrite via an experiment can be accepted, with the old version in Salvage and a harvest note attached, and exporting a world then restoring the zip into an empty database reproduces it.
   **Then the move:** the existing material comes in (§8) and writing moves into Quarry.
5. **Local history.** The 30-revision local cache with `storage.persist()`, and History that works offline. *Done when* the last 30 revisions of a chapter can be browsed and restored on the phone in airplane mode.

**Standing rule:** if two weeks pass without new story words, building pauses.

## 11. Out of scope (for now)

- AI features of any kind in the story path
- Co-writing features: inviting people, permissions beyond owner, comments, presence (the data model is ready for them; see §7)
- Rich text beyond Markdown
- Real-time collaborative editing or CRDTs
- Native apps (the PWA is enough on Android)
- A git mirror of the content (§8)

## 12. Open questions

- Should experiments also be allowed for entities ("what if this character were…") or only for chapters?
- Should journal entries be lockable after a period to keep them truly append-only, or stay freely editable?
- Is a light theme needed at all, or dark only?
- Do some bible pages belong to one project only (a character who exists in one novella), or is "world-level, mentioned in project X" always enough?
- The domain (likely `quarry.daevil1.com`), which fixes the passkey Relying Party ID.
