# Quarry — spec (draft 2)

A writing environment for long fiction set in shared worlds, built first for Thomas's current novel: capture sparks anywhere, triage them at the desk, keep a living bible of the world, and write the manuscript in a fast, dark, VS Code–feeling editor. Built around Thomas's existing process rather than a generic one.

Single-user today; the data model leaves room for co-writers later (§7).

## 1. Principles

1. **The process is the product.** The process runs spark → inbox → triage → canon/manuscript, with exploration allowed anywhere. The app models that loop directly.
2. **No AI in the creative path.** No generation, suggestions or critique of story content. Automation is limited to bookkeeping: mentions, name checks, counts, history, export, and rule-based checks over the world's own data (the writing companion, [WORLD-MODEL.md](WORLD-MODEL.md) §7).
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
| **Entity** | A bible page in a world: character, species, place, faction, culture, event, object, term or other. Has a name, aliases and a body. Lives at world level (shared by every project) or in one project's part of the bible (§12.4); either way it is matched in every project. |
| **Item** | Anything that needs attention: `spark`, `question`, `task` or `experiment`. Status is `open`, `accepted`, `rejected`, `harvested` or `deferred`. Belongs to a world and optionally to one project (an idea about the world in general has no project). Can link to entities and chapters. |
| **Journal entry** | Dated thinking-on-paper (the "What now?" kind of writing). World-level or project-level. Editable, but conceptually append-only. From phase 13 written in the editor, with the world tools; facts and relationships can say they were planned in one (§14). |
| **Decision** | A dated one-line verdict ("chapter 3 is now told by the sister"), optionally tied to the item it closes. World-level or project-level. From phase 14 it can have follow-ups (planned facts and relationships, and tasks) that carry it out, and its state is worked out from them (§16). |
| **Harvest note** | A short note on what was alive in a retired chapter or rejected experiment. Shown in the Salvage view. |
| **Cut** | A passage cut from a chapter into the project's cuts bin, labelled with the chapter it came from. Shown in Salvage; can be put back (§11). |
| **Chapter status** | A pill per chapter (raw, rewritten, polished to start), renameable per project (§11). |
| **Revision** | An immutable snapshot of a document's body and metadata. |
| **Mention** | A computed occurrence of an entity (by name or alias) in any text. Never edited by hand. |
| **User** | A person who can sign in. Today there is exactly one. |

## 3. Data model (Postgres)

All tables carry `created_at` and `updated_at`. Mutable documents also carry `created_by`/`updated_by` (user ids), `version int` for optimistic concurrency and `change_seq bigint` for sync. Rows with a nullable `project_id` belong to the whole world when it is null. `change_seq` and `change_log` arrive with the local copy in phase 5; until then the only offline writes are new captures, which carry a client-chosen id so a retried capture is saved once.

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
sessions      (id, user_id, token_hash, created_at, expires_at, user_agent)  -- the cookie value is stored hashed
auth_challenges(id, purpose, challenge, user_id NULL, data jsonb, expires_at)  -- pending WebAuthn ceremonies, used once
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

**Sync (as built).**
- `GET /api/worlds/<world>/offline?since=<time>` returns every chapter changed (or given a new revision) since that time, with its **last 30 revisions**, and the ids of all chapters that still exist (so deletions reach the device). Each device syncs the world it has open: when it opens, when the connection comes back and every 15 minutes, into IndexedDB (via Dexie), pruning to 30 revisions per chapter. It calls `navigator.storage.persist()` at start so Chrome on Android doesn't evict the data.
- Writes go through normal REST endpoints. Offline, new captures queue in an outbox (phase 2); text typed in a chapter is kept on the device as a draft until the server confirms it, so a reload or a closed app loses nothing; a restore made offline is applied on the device and the text it replaced is sent as a revision when back online.
- A draft written on top of an older version than the server now has is not applied: it is kept as a conflict revision. A save whose answer was lost (signal dropped mid-save) is recognised on the retry and counts as saved.
- The bible, items, journal and decisions are read online; offline, the app opens, captures, and lists and edits chapters. A general `change_log` for everything was not needed for v1.

**History UI.** Every document has a History panel: a revision list, a word-level diff against the current text, and buttons to restore or copy a passage.

## 5. Mentions and the name checker

Entities are world-level, so mentions are computed across every project in the world. When the server saves any text body:

1. It tokenises the text and matches every entity name and alias in the world, case-sensitively on the initial capital and on word boundaries. The match tolerates the suffixes `s`, `'s` and `’s` (so "Varrens" and "Varren’s" both match Varren) and multi-word names ("Old Harbour", "Iron Vale").
2. It writes the matches to `mentions` (`exact` or `alias`).
3. It flags a **near miss** when a capitalised word of at least 5 letters is no known name but is one edit away from a word of an entity's name or alias (two edits for words of 7 letters or more; a swapped pair of letters counts as one edit), and is not in `name_ignores`. The word must be read as a name is: a word that is a name, alias or first name by itself counts anywhere, but a word of a longer name only with the rest of that name around it ("the Lock Yeras", not "Fears" alone for *The Lock Years*). A word that is part of any name, or differs from one only in capitals, is never flagged. A typo such as "Varen" for Varren would be flagged.

Wherever a text is shown (inbox, triage, and the editor from phase 4), near misses get a wavy underline. Clicking one offers **Replace with…** (in this text), **another spelling** (adds it as an alias) or **Not a typo**. The **Name check** page lists every near miss in the world, grouped by word, with the same fixes applied everywhere at once. Names in texts link to their bible page.

Bible pages show:
- **Mentions** grouped by project, then by chapter, journal entry and item
- **Unlinked appearances in planning**, meaning journal entries and items that mention the entity but aren't linked to it
- **First appearance** per project

## 6. Screens

**Look and feel.** Same bones as dev-cockpit (and Gauntlet, which already copies it): its colour tokens from `dev_cockpit/web/static/cockpit.css` for light and dark, the dark left nav with the brand on top, cards on a quiet background, small pills for status and kind, and the system UI font. Quarry differs where writing needs it: the editor gets a serif or comfortable reading face at a 70ch measure, and the nav collapses on the phone into a bottom tab bar.

**Navigation.** URLs are scoped as `/w/<world>/…` for world views and `/w/<world>/p/<project>/…` for project views. A switcher at the top of the nav picks the world and project; the app remembers the last one used per device. A world with a single project behaves like that project. The Bible, the world inbox and the world journal sit at world level; Manuscript, Experiments and Salvage are per project; Triage, Board, Journal and Decisions can be filtered to one project or show the whole world.

### Phone (Android PWA, portrait first)

- **Capture.** This opens by default (the installed app starts at `/capture`). It has one big text field, kind chips (spark / question / task) and project chips ("Whole world" for ideas not tied to one book); the last choice sticks per world. An entity tag with autocomplete comes with the bible in phase 3. Save works offline: the capture waits on the device (shown as "waiting to sync") and is sent when the connection is back, keeping the time it was written.
- **Share target.** The app registers as an Android share target (Web Share Target API). Sharing text or a link from a browser, an e-book reader or a chat app opens Capture prefilled, with `source=share:<app>` recorded where available.
- **Inbox.** Open items, newest first, with Deferred and Closed tabs and a project filter. Tapping an item opens it with Accept / Reject / Harvest / Defer, an optional decision line, edit and move; every close can be undone. Reading the inbox needs the network until phase 5.
- **Look up.** Search across the world, plus read-only entity and chapter views.
- **Journal.** Quick dated entries.

### Desk (keyboard-first, VS Code feel)

- **Command palette** (Ctrl+K): jump to any world, project, chapter, entity, item or command.
- **Triage.** The inbox, one item at a time. Keys: `a` accept, `r` reject, `h` harvest, `d` defer, `l` link to entity, `p` move to project, `e` edit. Closing can prompt for a one-line decision, which is optional and skippable with Enter.
- **Board.** Open items as columns by kind, filterable by project and entity. "Questions" is its own column.
- **Editor.** The chapter in CodeMirror 6, with a side panel showing the entities mentioned in this chapter, linked items, POV, the word count, and History.
- **Bible.** Entity pages with Markdown bodies, aliases and the mention panels from §5.
- **Manuscript.** The project's current chapters in drag-to-reorder order, with word counts, POV and a derived POV tally. Experiments appear indented under the chapter they would replace.
- **Experiments.** Starting an experiment creates an `experiment` item and a draft chapter; it can begin from scratch (the old chapter is hidden while writing) or from a copy. Closing it as *accepted* swaps the draft into the manuscript and retires the old chapter. Closing it as *harvested* or *rejected* retires the draft and asks for a harvest note. From phase 12 an experiment can replace a range of chapters with several drafts, and retiring reviews what is tied to the chapters first (§13.6).
- **Salvage.** Retired chapters, each with its harvest notes and full-text search.
- **Journal** and **Decisions**: chronological lists with search. From phase 13 a journal entry opens in the editor, with the world tools (§14.1).

### Editor requirements

- CodeMirror 6 with Markdown language support, a VS Code–style dark theme (and light), soft wrap, and a centred measure of about 70ch.
- Toggleable focus mode (dims all but the current paragraph) and typewriter scrolling.
- Smart quotes and dashes optional. The source text uses curly quotes, so those are preserved.
- Must stay smooth on a 10k-word chapter on a mid-range Android phone.

## 7. Users and auth (passkeys)

- **Users from day one.** There is one user, but passkeys, sessions, revisions and `created_by`/`updated_by` all point at a user, and access goes through `world_members`. Co-writing later then means adding a second member and deciding what they may do, not reworking every table.
- **Passkeys in the app.** WebAuthn via `py_webauthn`. The Relying Party ID is the app's domain, served over HTTPS. Login lives in the app rather than behind an auth proxy, because an offline PWA, its service worker and the share target need API calls that fail cleanly with a 401 instead of being redirected to a login page.
- **Bootstrap.** With zero users, `/setup` accepts a one-time `QUARRY_SETUP_TOKEN` from the environment, creates the first user and registers the first passkey, shows the recovery codes, then asks for the first world. After that, setup is disabled.
- **More devices.** From a signed-in session, choose "Add passkey" (desktop and the Android phone via Google Password Manager).
- **Recovery.** Ten one-time recovery codes are generated at setup and stored hashed. A CLI command `quarry passkey reset <user>` recovers from the server shell.
- Sessions use an httpOnly, Secure, SameSite=Strict cookie with a 30-day sliding expiry. CSRF is covered by SameSite plus an Origin check. Login is rate-limited.

## 8. Export, backups and import

- **Backups.** The Postgres server's own backups are the disaster-recovery path. Every revision lives in the database, so restoring the database restores the full history.
- **Export now.** Downloads a zip with one folder per world: `world.md`, `Bible/<Kind>/<Name>.md`, `Journal/`, `Decisions.md`, `Planning/<status>/` (items for the whole world), and per project `Projects/<Name>/` with `Manuscript/` (numbered in order), `Experiments/`, `Salvage/`, `Planning/` and a compiled `manuscript.md`. YAML frontmatter carries ids, state, POV, tags and aliases; the layout is documented in `backend/src/quarry/api/transfer.py`.
  From phase 10, chapters also carry their summary and status, `project.md` the project's statuses, and each project has a `Cuts/` folder (§11).
  From phase 11, bible entries also carry the project they belong to (`project:`, §12.4).
  From phase 12, chapters also carry when they are set and whether they are told as a tale or flashback, events their
  time and tellings, facts and relationships their time bounds, relationships their role, and `world.md` the time
  unit and the one-at-a-time roles (§13).
  From phase 13, facts and relationships also carry where they were planned (`planned_in:`, `planned_evidence:`),
  events their notes from the Journal, items the chapter or journal entry and passage they came from, entries their
  added kinds (`also:`), and `world.md` the premise (§14).
  From phase 14, facts, relationships and items also carry the decisions they follow (`follows:`), and `Decisions.md`
  lists each decision's follow-ups under it, with the dropped ones' words (§16).
  From phase 15, the export has a `Pictures/` folder with each picture's file, texts link their pictures by a path
  relative to the file, entries carry their gallery (`pictures:`) and `world.md` lists the pictures with their names;
  Restore links them up again, and takes zips of up to 1 GB (§17.6).
  From phase 16, journal entries also carry whether they are a plan and the chapters they are for (`plan:`,
  `chapters:`, §18).
  From phase 17, `project.md` carries the project's byline (`byline:`), and the compiled manuscript has it under the
  title (§19).
  From phase 18, the export has a `History/` folder with each chapter's and journal entry's last version of every day
  and its labelled checkpoints, and Restore makes them revisions on their dates (§20).
- **Restore.** Imports an export zip as a new world (with new ids; every link between files is kept), recreating projects, chapters (current, experiments, salvage with harvest notes), entities, items with their tags, journal, decisions and "not a typo" words from the files and their frontmatter. It is the only import path: there is no importer for other tools' formats. The full revision history stays in the database; from phase 18 an export carries a day-by-day sample of it (each day's last version and the labelled checkpoints), which Restore brings back on its dates (§20).
- **Moving the existing material in.** Quarry starts empty. Once the editor is usable (after phase 4), Thomas provides the current Google Doc and Claude converts it by hand into the export layout: chapters, bible entries, planning notes as items or journal entries, and old chapters as retired chapters, with anything uncertain listed for Thomas to decide. The result is loaded with Restore and merged with whatever was captured in Quarry in the meantime. This is a one-time migration, done outside the repo.
- **Later, if wanted.** A scheduled export into a git repo (a local repo on the server, or a remote one) can be added as an optional setting. It is not part of the plan.

## 9. Tech stack, deploy and repo

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, py_webauthn, rapidfuzz (near misses), Pillow (pictures, from phase 15) |
| DB | Postgres 16+, via `DATABASE_URL` (DigitalOcean managed cluster in production, a local container in development) |
| Frontend | Vue 3 + TypeScript + Vite, Pinia, vue-router, CodeMirror 6, Dexie, vite-plugin-pwa (Workbox) |
| Packaging | One image: FastAPI serves `/api` and the built SPA. GitHub Actions builds `ghcr.io/daevil1/quarry` on `master`. |
| Deploy | Same pattern as Gauntlet: the droplet runs the container from a compose file in `/srv/quarry`, bound to `127.0.0.1:8091`, behind host nginx + certbot (docs/deploy.md). One worker and a small DB pool: the droplet is shared, so no busy background work. |
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
2. **Capture and triage.** The phone Capture screen, share target, Inbox, desk Triage with keyboard closing (oldest first; `a` `r` `h` `d`, `e` edit, `p` project, `1`–`3` kind, `j`/`k`, `u` undo), Decisions, the offline outbox, and an app shell that opens without a network. *Done when* a spark shared from Chrome on Android while in airplane mode appears in desk Triage after reconnecting.
3. **Bible, mentions and journal.** Entity editing, aliases, mentions, near-miss detection, the Name check page, bible panels, `item_links` (tag on Capture, in the inbox, `l` in triage), and the Journal. *Done when* a misspelled entity name in a chapter or note is flagged and can be fixed or added as an alias in one action.
4. **Manuscript, editor, export and restore.** CodeMirror editor (focus mode, typewriter scrolling, name squiggles with in-editor fixes), autosave/revision rules, History with word diffs and restore, chapter ordering (drag or arrows), POV tally, first appearance on bible pages, experiments and salvage with harvest notes, plus the export zip and Restore. Chapters live at `/w/<world>/chapters/<id>`. *Done when* a full chapter rewrite via an experiment can be accepted, with the old version in Salvage and a harvest note attached, and exporting a world then restoring the zip into an empty database reproduces it.
   **Then the move:** the existing material comes in (§8) and writing moves into Quarry.
5. **Local history.** The offline copy of every chapter with its last 30 revisions, `storage.persist()`, drafts that survive reloads, History and restore offline, the manuscript list offline, and an *Offline copy* section in Settings. *Done when* the last 30 revisions of a chapter can be browsed and restored on the phone in airplane mode.

**Standing rule:** if two weeks pass without new story words, building pauses.

6–9. **The world model**: the bible as data, relationships, story time, graphs and the writing companion. Designed in [WORLD-MODEL.md](WORLD-MODEL.md), with the phases and their *done when* in its §9.

10. **Revising and salvaging**: renames that keep the old name, chapter summaries and statuses, a cuts bin, reading one entry's thread, word history, changes since a checkpoint, and find and replace across chapters. Designed in §11, with a *done when* per part.
11. **More views of the bible**: a mentions strip on each entry page, a family tree with kin worked out, a grid of any entries across chapters, world entries and project entries, the *witnessed* type, a *gender* field on characters and a *pronunciation* fact, and labels and values (value suggestions, filtering by a value, a Labels page, labels with several values, expected labels). Designed in §12, with a *done when* per part.
12. **Time, history and kinds of being**: in-world time on one axis under the chapters (a sortable number with a free label), chapters set in time and marked as told as a tale or flashback, facts, relationships and the checks read in happened order, a Timeline with happened and told orders, history, recording an event from a passage, ages, Species as a ninth kind, roles in groups with a one-at-a-time check, more starting vocabulary, restructuring (experiments across several chapters, and a review of everything tied to chapters before they are retired), and the chart (a schematic map of how places nest, border and connect). Designed in §13, with a *done when* per part; built as four phases, in the order 12c, 12a, 12b, 12d (§13.9).
13. **Planning before writing**: journal entries in the editor with the world tools, what was planned in the
    Journal kept beside what is canon in the book (recording a fact from a passage, *Make it canon here*), reading an
    entry's thread through the planning, sparks and questions from a passage, loose ends in the Journal, a front page
    for getting back into a world, "since this was written" on journal entries, "Include planned" on the Continuity
    checks, cause arrows on the Timeline, entries of more than one kind, and a focus per world (writing or
    planning), and names shared by two entries, settled by a line in the text. Designed in §14, with a *done when* per
    part; built after phase 12 is merged, as build phases 13a, 13b and 13c (§14.12).
14. **Decisions with follow-ups**: a decision can have follow-ups (planned facts and relationships made or attached
    from it, and tasks linked to chapters), an optional `+ follow-up` step after closing an item with a decision line,
    a state worked out from them (settled, *n of m to do*, done), a line in a written chapter's Loose ends when a
    planned change from a decision is tied to it but not yet canon, a Decisions filter and a front page list. Designed
    in §16, with a *done when* per part.
15. **Pictures**: pictures in a world, uploaded from the desk or the phone and kept in Postgres at most 2400 px, with a
    view copy and a thumb; a gallery on any bible entry, with captions and a main picture at the top of its page and on
    its cards; a picture on a line of its own in chapters, journal entries and entries' notes, drawn under its line in
    the editor and left out of the counts and the compiled manuscript; the pictures of the offline copy kept on the
    phone; a Pictures page in World settings; and pictures in the export and Restore. Designed in §17, with a *done
    when* per part.
16. **A chapter's plan**: a journal entry can be marked as a plan and linked to the chapters it is for (several plans
    per chapter, several chapters per plan), opened beside the chapter half and half on the desk (and flipped to on the
    phone) in the journal editor so planning goes on while writing, a plan with no chapter yet waiting on the project
    page until *Start a chapter from it*, and items and facts from a plan reaching its chapter. Designed in §18, with a
    *done when* per part.
17. **A byline**: one optional line on a project, set in its Edit form and shown under its title on the project page,
    the Read page and the compiled manuscript, and carried by the export (§19).
18. **Dated earlier versions in the export**: the export carries each chapter's and journal entry's last version of
    every day and its labelled checkpoints under `History/`, and Restore makes them revisions on their dates, counted in
    the word history on their days, so a book brought in from elsewhere keeps when it was written (§20).

## 11. Revising and salvaging (phase 10)

Phases 1–9 serve writing forward. Phase 10 serves the other half of the work: going back over chapters, rewriting
them and keeping what was cut. Each part is small, built on what exists (revisions, Salvage, the manuscript list,
margin notes, mentions, the Drafting/Revising switch), and can ship on its own. The ideas come from the second round
of research ([research/README.md](research/README.md#second-round-competitors), "Second round"). The principles hold: nothing here writes or
suggests story content, nothing has to be filled in, and the compiled manuscript stays pure prose.

Examples use made-up names.

### 11.1 A rename keeps the old name

Renaming an entry (on its page, in the bible table, anywhere its name is edited) keeps the old name as another name,
so chapters that still say the old name stay linked to it.

- The server adds the old name to the other names in the same save and says so. A toast reads
  `Kept "Varren" as another name · Remove · Replace in the text…`.
  - **Remove** takes it out again in one click. Old spellings in the text then show up as possible misspellings or
    new names, as they would today.
  - **Replace in the text…** opens find and replace (§11.7), filled in with the old and new names, whole words, match
    capitals.
- Nothing is offered when:
  - only the capitals or spacing changed (`varren` → `Varren`);
  - the old name is already one of its other names;
  - the old name is another entry's name or other name (it would match two entries).
- If the new name was one of the other names (promoting `Varren Hale` over `Varren`), it leaves the other names,
  since it is now the name, and the old name takes its place there.

**Data:** none. `PATCH /entities/<id>` gains `keep_old_name` (default true) and answers with `kept_alias`.

*Done when* renaming Varren to Varran leaves "Varren" under his other names, a chapter that says "Varren" still
colours it as him, and one click on Remove takes it away.

### 11.2 A summary and a status per chapter

Each chapter can have a **one-line summary** and a **status**. Both are optional and start empty.

- **Summary.** On the manuscript list, under the title, in muted text, edited in place (like an entry's one-liner).
  Also in the editor's side panel. One line, up to 300 characters. It is the seed of a corkboard later.
- **Status.** A small pill beside the title. Clicking it shows the project's statuses to pick from, plus *none*.
  - Each project starts with **raw**, **rewritten** and **polished**. They are renamed, added, removed and ordered on
    the project page.
  - Removing a status that is in use says how many chapters have it; they go back to *none*.
  - Pills get stronger by position: the first is faint, the last is the strongest. Nothing is red.
- **On the manuscript list**, next to the POV tally, a status tally with words: `9 raw (31k) · 4 rewritten (14k) ·
  1 polished (3k) · 2 none`.
- Experiments and retired chapters keep their summary and status; Salvage shows them.
- **Export** writes `summary` and `status` (the label) into each chapter's frontmatter, and the project's statuses in
  order into `project.md` (`statuses: [raw, rewritten, polished]`). **Restore** reads them back; a status a chapter
  names that `project.md` doesn't list is added at the end. The compiled `manuscript.md` is unchanged.

**Data:**

```sql
chapter_statuses  (id, project_id, label, position)            -- raw, rewritten, polished for each project
chapters          + summary text default '', status_id NULL    -- ON DELETE SET NULL
```

Statuses are rows, so renaming *rewritten* to *second draft* renames it on every chapter that has it.

*Done when* the manuscript list shows a summary and a status for each chapter, renaming *rewritten* renames every
pill that says it, and exporting and restoring the world keeps the summaries, statuses and their order.

### 11.3 The cuts bin

A place for passages that don't belong where they are but are too good to lose.

- **Cutting.** Select text in the editor and press **Ctrl+Shift+X**. The selection leaves the chapter and becomes a
  cut in the project's bin, labelled with the chapter it came from. A toast says `Cut 84 words to the bin · Undo`;
  Undo puts the text back and removes the cut. (Plain Ctrl+Z also brings the text back, but leaves the cut in the bin
  as a copy.) On the phone, the selection strip gets a *Cut to bin* chip.
- **Offline.** Cutting works offline: the cut waits in the outbox with an id chosen on the device, as captures do,
  and the chapter's own change is a normal draft. Reading the bin needs the network, like Salvage today.
- **In Salvage.** Salvage gets two tabs, *Retired chapters* and *Cuts*, and its search covers both. Each cut shows its
  source chapter (a link), when it was cut, its word count and its text (long ones folded).
- **In the editor.** The side panel lists the cuts from this chapter, newest first.
- **Putting back.**
  - From the editor's list: **Put back where it was** inserts the cut where it was taken from, found by the text
    around it (kept at cut time). If that text is gone or found twice, the cut goes in at the cursor instead.
    **Insert at cursor** puts it at the cursor.
  - From Salvage: **Put back** opens the source chapter (or one you pick) and does the same.
  - Either way it is an ordinary edit (Ctrl+Z undoes it). The cut stays in the bin, marked *put back* with the date
    and chapter, and is hidden unless *Show put back* is on. **Copy** copies it without putting it back.
- **What a cut is not.** Cuts aren't matched for mentions or near misses, aren't counted in any word count, and aren't
  part of the compiled manuscript. Cuts aren't deleted (nothing is lost; search keeps a big bin usable).
- **Export** writes `Projects/<Name>/Cuts/<date> <source title> (<id>).md` per cut, with frontmatter `id`,
  `chapter` (the source chapter's id), `chapter_title`, `cut_at`, `put_back_at`, `before` and `after`; the body is
  the cut text. **Restore** reads them back and relinks the source chapter by id.

**Data:**

```sql
cuts  (id, world_id, project_id, chapter_id NULL,     -- source chapter; ON DELETE SET NULL
       chapter_title,                                  -- the title when cut, for when the chapter is gone
       body, before, after,                            -- up to 80 characters either side, to find the place again
       cut_at, put_back_at NULL, put_back_to NULL,     -- the chapter it went back into
       created_by)
```

*Done when* cutting a paragraph with Ctrl+Shift+X (also offline) puts it in Salvage under *Cuts* labelled with its
chapter, searching Salvage for a word in it finds it, *Put back where it was* returns it to its old place, and
exporting and restoring the world keeps every cut with its source chapter.

### 11.4 Reading one entry's thread

From an entry's page, **Read where Varren appears** opens the story filtered to him: read-only, in story order
(project order, then chapter order, as for story time in [WORLD-MODEL.md](WORLD-MODEL.md) §4).

- **Two ways to read**, a switch at the top:
  - *Paragraphs* (the default): each paragraph that names him, under its chapter's title. Between paragraphs that
    aren't next to each other, a quiet `⋯ 14 paragraphs` that opens those paragraphs in place when clicked.
  - *Chapters*: every chapter that names him, in full.
- A paragraph is a line, as in the companion. Names are coloured as in the editor; his own are marked more strongly.
- **Margin notes are shown**, dimmed as in the editor. In *Paragraphs*, a `%%` line right before or after a shown
  paragraph comes with it, and a margin note that names him is a hit of its own: notes to yourself about a character
  belong in this reading.
- A count at the top: `Varren: 212 paragraphs in 31 chapters`.
- Each paragraph and chapter title links into the editor at that place, for when a fix is needed.
- Current chapters only. A switch adds experiments and retired chapters, after the story and labelled as such.
- **A second entry.** *With…* at the top picks one more entry (any kind). The reading then keeps only the paragraphs,
  or in *Chapters* the chapters, that name both: `Varren and Isolde: 18 paragraphs in 9 chapters`.
  - Both entries' names are marked strongly. A margin note is a hit of its own only when it names both.
  - Each relationship on an entry's page also has *Read together*, which opens this reading for the two of them.
  - Removing the second entry goes back to reading one. Two is the most; this is a reading, not a query.
- **Built on the device**, from the offline copy of the chapters and the same matcher that colours names (other
  names, first names and *not in this sense* included), so it works on the phone with no network.

**Data:** none. A route, `/w/<world>/bible/<id>/read`, with `?with=<id>` for a second entry.

*Done when* Varren's page opens a reading of every paragraph that names him (by any of his names), in story order
across the world's projects, with the margin notes beside them shown, on the phone in airplane mode too; and adding
Isolde with *With…* (or *Read together* on their relationship) leaves only the paragraphs that name both, and in
*Chapters* only the chapters that name both.

### 11.5 Word history

How many words went into the project each day, worked out from revisions. Nothing new to type or set.

- **On the project page**, a small chart: one bar per day for the last eight weeks, with *a year* (by week) and *all*
  (by month) as other ranges.
  - The bar is words **written**; words **cut** show as a fainter bar below the line.
  - Hovering a bar shows the date, written, cut and the chapters touched. The range's total is shown under it.
- **No streaks, goals, targets or reminders.** Days without writing are empty, never marked. Nothing counts days in a
  row, and no colour says a day was good or bad.
- **How it is counted.**
  - When a revision is taken, the server compares its text with the chapter's previous revision (a word diff, as in
    History, on the text without margin notes) and keeps the words added and removed in the revision's `meta`, so
    nothing is diffed again when the chart is read.
  - A day's figure is the sum over that day's revisions of all the project's chapters, whatever their state, plus,
    for today, the working text against its last revision. Days follow the browser's time zone.
  - Conflict copies are skipped: they are side copies, not the chapter's line.
  - A chapter that doesn't start empty (Restore, the demo, an experiment started as a copy) gets a first revision
    with the new reason `start`, which counts as no words. So restoring a world or copying a chapter isn't a huge day.
    From phase 18 a restored chapter's dated earlier versions come first, counted on their own days (§20); its start
    is only for text newer than them.
  - It is a rough picture: moving a passage from one chapter to another, a restore, a put-back cut or a find and
    replace count as cut in one place and written in another.
- **Existing history.** The migration works out the words for every existing revision. Each chapter's first revision
  counts as its start (no words), since there is no way to tell how it began; the history of the move from the Google
  Doc therefore starts clean.

**Data:**

```sql
revisions  + reason 'start'
           + meta.added, meta.removed                 -- words since the chapter's previous revision
```

*Done when* after writing in two chapters on one day and cutting a scene the next, the project page shows both days
with their written and cut words, and a restored world shows no words on the day it was restored.

### 11.6 Changes since a checkpoint

While **Revising**, the editor can mark what changed since a labelled checkpoint, so a second pass can see what the
first one touched.

- **Choosing.** In the editor's side panel, *Show changes since* lists the chapter's labelled checkpoints (the Ctrl+S
  ones with a label, and labelled ones Quarry takes, such as before a restore or a find and replace), newest first,
  and *nothing*.
  - The choice is remembered per project on the device, by label. Opening another chapter with a checkpoint of the
    same label shows its changes too; a chapter without one says so.
  - **Checkpoint every chapter…** on the project page takes a labelled checkpoint of every current chapter and
    experiment at once (`before the polish`), so one label covers the whole book.
- **What shows.**
  - Added or changed words get a soft tint, and the lines they are on a bar in the margin.
  - Removed text leaves a small mark; resting on it (never while typing) shows what was there.
  - A line in the panel counts it: `312 words changed, 4 passages removed since "before the polish"`.
- **When.** Only in Revising; Drafting shows nothing. It is worked out again when typing pauses (as the Revising
  findings are), paragraph by paragraph first and then word by word inside changed paragraphs, so it stays within the
  typing budget on a 10,000-word chapter. The tint is separate from name colours and the companion's underlines.
- **Offline.** It uses the revisions on the device. A checkpoint older than the device's last 30 revisions is fetched
  the first time (online) and then kept on the device.

**Data:** none; derived from revisions.

*Done when*, with a checkpoint labelled "before the polish" in every chapter, editing a paragraph in Revising tints
the changed words and marks a deleted sentence, switching to Drafting hides it, and opening the next chapter shows
its changes since the same label.

### 11.7 Find and replace across chapters

The editor's search (Ctrl+F) covers one chapter. This covers them all.

- **Opening.** Ctrl+Shift+H in the editor, *Find in all chapters…* in the editor's search panel, the project page,
  the command palette, or *Replace in the text…* after a rename (§11.1). It is a page:
  `/w/<world>/p/<project>/replace`.
- **Finding.** Plain text (no patterns), with *match capitals* and *whole words*, both on by default. It searches
  current chapters and experiments, margin notes included; retired chapters are left as they were. A scope switch
  extends it to every project in the world.
- **The preview** lists every hit, grouped by chapter in story order: about eight words either side, the found text
  struck through and the replacement beside it. Every hit and every chapter has a checkbox, all on. The button says
  what it will do: `Replace 41 in 12 chapters` (or `Delete 41…` with an empty replacement). With no replacement typed,
  the page is just a project-wide find, each hit linking into its chapter.
- **Replacing**, on the server, in one transaction, for each chapter with chosen hits:
  1. If the chapter changed since the preview (another device saved), it is skipped and listed as *changed since the
     preview*.
  2. Otherwise it takes a checkpoint labelled `Before replacing "Varren" with "Varran"`,
  3. replaces the chosen hits (each checked to still read the same at its place), bumps the version and refreshes
     mentions.
- **Undo.** The toast and the page offer **Undo**, which restores each chapter to that checkpoint if it hasn't changed
  since (restore keeps the replaced text as a revision, as always). Later, the checkpoint is in each chapter's
  History like any other.
- **Drafts and devices.** Before the preview, this device sends any chapter text it still holds. It needs the
  network, and says so offline. A device with an older copy open gets a conflict copy on its next save, as today.

**Data:** none. `POST /projects/<project>/find` (the hits, with each chapter's version) and
`POST /projects/<project>/replace` (the chosen hits and those versions).

*Done when* replacing "Varren" with "Varran" previews every hit in every chapter, unticking two leaves those two
alone, every changed chapter has a checkpoint named for the replace in its History, and Undo puts every chapter back.

### 11.8 Data model, in one place

```sql
chapter_statuses  (id, project_id, label, position)                                  -- §11.2
chapters          + summary text, status_id NULL                                     -- §11.2
cuts              (id, world_id, project_id, chapter_id NULL, chapter_title, body,
                   before, after, cut_at, put_back_at NULL, put_back_to NULL, created_by)  -- §11.3
revisions         + reason 'start'; meta + added, removed                            -- §11.5
```

Renames, reading one entry, changes since a checkpoint, and find and replace add no tables.

**Phase 10 is done when** each part's *done when* above holds, and the demo world has summaries, statuses, a cut
and a few days of word history to show.

## 12. More views of the bible (phase 11)

Phase 10 served the manuscript. Phase 11 goes back to the bible, with new ways to look at what Quarry already
stores: mentions, relationships, "is at" and the story order. Nothing new has to be filled in: the new fields have
defaults (a project's gap length, §12.1; an entry's level, §12.4, which is set for you; a character's gender, §12.5,
not set until chosen), §12.5 also adds one relationship type and one suggested fact, and §12.6 makes the facts typed
so far easier to keep consistent, with one small table of per-label switches.
The ideas come from the second round of research ([research/README.md](research/README.md#second-round-competitors),
"Cheap additions" and "Later"). The principles hold: nothing here writes or suggests story content, and anything
worked out (gaps, kin, shared chapters) is shown, never stored.

Examples use made-up names: Varren is the father of Isolde and Oswin, Oswin the father of Mirelle, and Varren
marries Seyla in chapter 3.

### 12.1 A mentions strip on each entry page

Under the head of every entry page (any kind), a strip shows where in the story the entry is named, so a character
who vanishes for ten chapters is seen at a glance.

- **The strip.** One small cell per current chapter, in story order (project order, then chapter order, as
  everywhere). With more than one project, each project is its own row, with its name before it.
  - A chapter that names the entry is filled; the more often, the stronger, in three steps by thirds of the entry's
    own busiest chapter, so a minor object's strip still shows its peaks. A chapter that doesn't is an empty outline.
  - A chapter told from the entry's point of view (its POV) has a small bar under its cell.
  - Resting on a cell (long-press on the phone) shows the chapter's number and title and `named 4 times` or
    `not named`. Clicking opens the chapter.
- **Gaps.** A run of chapters without the entry, between two that name it, is a gap once it reaches the project's
  *gap length*: a quiet bracket under the run says `10 chapters`.
  - The gap length is a setting on the project page, 5 chapters to start, since a novella of short chapters and a
    novel of long ones need different lengths.
  - Gaps cross from one project into the next, since the story does; such a gap uses the length of the project it
    starts in.
- **A line above the strip** sums it up:
  `In 31 of 48 chapters · first in 2 · last in 45 · longest gap: 10 chapters (12–21) · not named in the last 3`.
  The last part shows only when the entry isn't named in the book's last chapters.
- **As of.** With the page's *as of chapter …* set, that chapter is marked on the strip and the chapters after it
  are dimmed: they are later in the story.
- **What counts.** The mentions Quarry already stores for chapters: any of the entry's names, first names included,
  margin notes left out. Experiments and retired chapters are outside the story order, so not in the strip; the
  Mentions list below still has them.
- **On the phone**, cells keep a minimum width and a project's row wraps onto more lines; nothing scrolls sideways.

**Data:** the entry page already gets each chapter that names the entry with a count, and the cards keep the story
order on the device. `GET /timeline` gains each chapter's POV entry, for the bar, and each project's gap length.

```sql
projects  + gap_chapters int default 5
```

Export writes it into `project.md` (`gap_chapters: 5`); Restore reads it back, and an older export gets 5.

*Done when* Isolde, named in chapters 1–3 and 14–20 of 20, has a strip filled at 1–3 and 14–20 with a gap labelled
`10 chapters` under 4–13 and the line saying so, her POV chapters are marked, and setting *as of* chapter 10 dims
11–20.

### 12.2 A family tree

A tree drawn from the parent/child and *married* relationships already recorded. Kin that follows from them
(siblings, grandparents, cousins …) is worked out and shown dimmed, never stored.

- **Where.** A third tab on the Graph page, *Family*, next to *Relationships* and *Places*
  (`/w/<world>/graph?view=family&centre=<id>`). A character's page with any parent, child or married relationship
  gets a *Family tree* link, centred on them. The tab's own picker lists everyone in a family.
- **What counts as family.** Character–character types read as parenthood or marriage, the way the place tree reads
  *inside* (so renamed or added types still count):
  - **parent**: a label ending in `parent of`, `father of` or `mother of` (so *adoptive parent of* counts), or a
    reverse label ending in `child of`, `son of` or `daughter of`;
  - **married**: `married to`, `spouse of`, `husband of`, `wife of` or `wed to`;
  - a recorded **sibling of** is drawn too.

  Every other type is left out of the tree.
- **The drawing.** Everyone connected to the centred character through those links, generations top to bottom.
  - Couples sit side by side, joined by a double line; a couple who are both recorded parents of a child but not
    married are joined by a single line. Children hang from their parents, or from one parent when only one is
    recorded.
  - Recorded siblings with no recorded parent hang together from a small `?`.
  - A parent type other than the plain one (*adoptive parent of*) shows its label on the line, lighter.
  - *Planned* and *rumour* relationships are dashed, and the graph's standing switches hide them (a rumoured father
    is a plot, so they show by default).
  - Each person shows their name (coloured as a character), a `†` when their *status* is *dead* as of the chosen
    chapter, and, small and dimmed under the name, how they are related to the centre: `granddaughter`, `cousin`,
    `stepmother`. Resting on a name shows the one-liner; clicking it centres the tree on them; a link opens the
    entry.
- **Kin worked out** from the recorded links:
  - **sibling** (a shared parent; *half-sibling* when each also has a parent the other doesn't);
  - **grandparent / grandchild**, and *great-* for each generation further, up to four; beyond that, *ancestor* and
    *descendant*;
  - **parent's sibling / sibling's child**, and **cousin** (children of siblings); more distant blood relatives are
    just *relative*;
  - by marriage: **parent-in-law / child-in-law**, **sibling-in-law** (a spouse's sibling or a sibling's spouse), and
    **step-parent / stepchild** (a spouse's child who isn't their own).
- **The words** follow the relative's *gender* field (§12.5), never a fact:
  - *female*: mother, daughter, sister, half-sister, grandmother, granddaughter, aunt, niece, mother-in-law,
    daughter-in-law, sister-in-law, stepmother, stepdaughter, wife;
  - *male*: father, son, brother, half-brother, grandfather, grandson, uncle, nephew, father-in-law, son-in-law,
    brother-in-law, stepfather, stepson, husband;
  - *nonbinary* or *not set*: the general word, one per relation: parent, child, sibling, half-sibling, grandparent,
    grandchild, parent's sibling, sibling's child, parent-in-law, child-in-law, sibling-in-law, step-parent,
    stepchild, spouse.

  *Cousin*, *relative*, *ancestor* and *descendant* are the same for everyone, and *great-* is added to any of the
  grand- words. Recorded relationships keep their own labels. Free-text facts such as *pronouns* stay for nuance;
  the tree doesn't read them.

  Two people related in two ways (cousins who marry) show both. A recorded relationship wins: if Isolde and Oswin
  have a recorded *sibling of*, the worked-out *sibling* isn't shown again.
- **As of a chapter.** The Graph page's *as of* applies: only relationships that hold at that chapter count, for
  the drawing and for the kin worked out. If Varren marries Seyla from chapter 3, as of chapter 2 she isn't in his
  family and isn't anyone's step-parent. Parenthood is read as recorded: a *parent of* with an *until* ends there.
- **On the entry page.** Under the recorded relationships, a dimmed group *Family, worked out* lists each relative
  with the path, following the page's *as of*: `cousin · Mirelle (via Varren → Oswin)`. It is read-only; to make one
  a recorded relationship, record it as any other.
- **Odd data.** More than two parents are all drawn, and any shared parent makes a sibling. Someone recorded as their
  own ancestor is drawn once, with a note above the tree naming the loop, and the Checks page lists it under
  Continuity (*their own ancestor*), as it lists a place inside itself.
- **Drawn in the browser**, from what the Graph page already loads: generations from parent links, a married couple
  on one row, and a few sweeps to keep couples together and children under their parents. Plain SVG, laid out once
  (nothing moves, as with the graph). A big family scrolls inside its card; on the phone it pans by dragging.

**Data:** none. `GET /graph` already carries every relationship with its type, standing and span; *status* as of a
chapter comes from the cards.

*Done when* the tree centred on Mirelle shows three generations, with Varren and Seyla as a couple, Varren labelled
*grandfather* and Isolde *aunt* (their gender is set to male and female); Isolde's page lists *brother: Oswin*,
*niece: Mirelle* and *stepmother: Seyla*, dimmed and with their paths, while a relative whose gender is nonbinary or
not set gets the general word (*sibling*, *parent's sibling*); none of them reads a fact; none of them adds a relationship row; and as of chapter 2 Seyla is in neither the tree nor Isolde's
list.

### 12.3 Entries across chapters

The Where-everyone-is grid (characters × chapters) becomes a grid of **any entries** × chapters. Characters stay
its default, so the grid that exists today is still one click away.

- **The page** keeps its name and place: *Where everyone is*, at `/w/<world>/where`, opening with characters as
  before.
- **Rows** are chosen at the top:
  - **kinds**: a chip per kind adds every entry of that kind named in the chapters shown (*Characters* is on by
    default), in order of first appearance, as today;
  - **entries**: *Add…* picks one entry of any kind (Varren, Isolde, the logbook, the Lamp Guild);
  - a row's `×` hides it; hidden rows are listed under the grid, to show again.

  The choice is kept in the address, so a set can be bookmarked, and the last one used is remembered per world on
  the device.
- **Columns** are the current chapters in story order, with the project filter as today. Each chapter head also
  shows its POV character, small.
- **Cells.**
  - **Characters**, as today: the place recorded with *is at*, else the place named in the same paragraph (fainter,
    with `?`), else a dot for named there. Clicking still records *is at*.
  - **Places** are filled when named, and also count the characters recorded *is at* there: the cell shows how
    many, and resting on it lists them.
  - **Everything else** is filled when the chapter names it, shaded by how often in the strip's three steps
    (§12.1), with the count on hover.
  - The *Events* line at the top stays while events aren't rows of their own.
- **Do these share a chapter?** Tick two or more rows (a box on each row head), then pick which chapters to show:
  *all*, *any of them* (hides chapters naming none of them) or *all of them* (only chapters naming every ticked
  row). With nothing ticked, the choice applies to every row.
  - A line says what it found: `Varren, Isolde and the logbook are named together in 4 of 48 chapters`.
  - With two ticked and no chapter shared, it says the nearest miss: `Never in the same chapter. Closest: Isolde in
    12, the logbook in 13.`
  - "Named in the same chapter" is all it claims. *Have they met?* stays the companion's question.
- **On the phone** the first column stays put and the grid scrolls inside its card.

**Data:** none. `GET /where` takes `kinds`, `entities` and `project`, and returns the chapters (with POV) and,
per row, each cell's count, recorded and derived place, and for places the people there. The share filter is worked
out in the browser from the cells.

*Done when* choosing Varren, Isolde, the logbook and the Lamp Guild shows four rows across the book, with places for
the two characters and shaded counts for the logbook and the guild; ticking Varren and the logbook with *all of them*
leaves only the chapters that name both, and says how many; and the *Characters* chip alone gives today's grid,
where clicking a cell still records *is at*.

### 12.4 World entries and project entries

This answers the open question "do some bible pages belong to one project only?": **yes**. Every entry lives at one
of two levels:

- **The world**: shared by every project, as every entry is today. Anything that belongs to the setting, or turns up
  in more than one book, lives here.
- **A project**: an entry that so far only matters to one book (a ferryman in one novella). Each project has its own
  part of the bible, on top of the world's.

The level says where an entry is listed and where it is expected. It doesn't fence anything in: a project's entry is
still matched, coloured, linkable and in the graph in every project. So there is no "several projects": an entry in
two books is a world entry, and its mentions strip (§12.1) shows which books name it. Names stay unique within the
world, so a name always means one entry, whichever book it is read in.

**How entries get their level**, without anything to fill in:

- **New entries made while writing** start in the project of the chapter they were made from: the strip's
  `+ Character`, the F8 pass, the companion's *Add as…*. New entries made anywhere else (the bible pages, Capture, a
  world page) start in the world.
- **A world with one project** keeps everything in the world and shows none of this. So when a second book is
  started, the first book's entries are already shared, and only the new book's new names start in its own bible.
- **Moving up.** When a project's entry is named in another project's chapter, the **Archivist** says so,
  `Mirelle is in The Salt Road's bible and is named here`, with **Share with the world** (one click moves it up) and
  *Intentional* (leave it where it is; not flagged again for that project).
- **By hand**, the entry page has the level beside the kind: *World* or one of the projects.

**Where it shows:**

- **Bible lists show everything, the current book first.** Nothing is hidden: the world's entries and every
  project's are listed in every book. With a project chosen in the switcher, each kind's table has two groups:
  - **In this book**: entries named in its current chapters, and entries in its own bible even if not named yet;
  - **Elsewhere**, dimmed below them, each with a small tag for where it is used: `only in The Salt Road`,
    `in 2 other books`, or `not named yet`.

  Within a group the table sorts as it does now (by name, or by a column clicked). A *Level* column shows *World* or
  the project. Search covers both groups. With no project chosen, or with one project in the world, there is one
  group, as today. The counts in the nav stay counts for the whole world.
- **Pickers** in a chapter (*is at*, *Link to…*, the editor's strips) list the chapter's own project's entries and
  the world's first, other projects' after them, labelled with their project.
- **Views.** When the grid (§12.3) is limited to a project, its kind rows leave out other projects' entries (entries
  added by hand stay). The graph gets the same project filter.
- **Matching is unchanged**: every entry's names are matched in every project's text. That is what lets the
  Archivist notice a crossover.
- **Export and Restore.** Each entry's frontmatter gets `project:` (the project's slug, or `null` for the world), as
  items and journal entries already do. Files stay in `Bible/<Kind>/`, so moving an entry between levels doesn't move
  its file. Restore reads `project:` back; a missing or unknown slug (an export from before phase 11) means the world.
- Projects can't be deleted today; the column is `ON DELETE SET NULL` so that, if they ever can, their entries move
  up to the world.

**Data:**

```sql
entities  + project_id NULL                   -- ON DELETE SET NULL; NULL is the world
```

The cards on the device carry it too, for the Archivist, the pickers and the editor's new entries.
`PATCH /entities/<id>` takes `project`, and the bible's list of entries gains, per entry, the projects whose current
chapters name it (from the stored mentions), for the two groups and their tags.

*Done when* Mirelle, added as a new name from a Salt Road chapter, starts in The Salt Road's bible; with The Salt
Road chosen she is listed under *In this book*, and with Ninefold chosen under *Elsewhere*, tagged
`only in The Salt Road`; naming her in a Ninefold chapter makes the Archivist offer *Share with the world*,
which moves her up in one click; a world with one project shows no levels; and exporting and restoring the world
keeps each entry's level.

### 12.5 Three small additions

- **Witnessed.** A new starting relationship type, character → event: *witnessed* / *witnessed by* (`Varren
  witnessed the Burning of the Quay`). It is not *took part in*: a witness was there and saw it, which is what "who
  knows what" turns on. Nothing is worked out from it; the companion doesn't turn it into *knows about*.
  - **New worlds** and the demo get it with the starting vocabulary.
  - **Existing worlds** get it from a data migration: it is added, at the end of the Character–event types, to every
    world that has no character–event type already reading *witnessed* (either way, any capitals).
  - **Restore** keeps the export's own vocabulary, as now: a world restored from an export made before phase 11 has
    no *witnessed* until it is added on the types page.
- **Gender**, a structured field on characters only: a dropdown of *female*, *male*, *nonbinary* and *not set*.
  - Optional, *not set* to start, edited on the entry page beside the kind. It is not time-bounded: it has no
    *from* or *until*, unlike facts.
  - The family tree reads it for its words (§12.2); *nonbinary* and *not set* give the general words.
  - On the name's card it shows only when set, as one small word after the name, so an unset field adds nothing.
  - An entry whose kind changes away from character keeps the value but doesn't show or use it.
  - **Export** writes `gender:` into a character's frontmatter when set; **Restore** reads it back (anything else, or
    nothing, means not set).
  - **Existing worlds** start with every character *not set*; nothing is inferred from facts. The demo sets it for
    some of its characters.
  - It replaces a *gender* fact suggestion. A free-text *pronouns* fact stays suggested (§12.6.5) for nuance.
- **Pronunciation.** A suggested fact for characters and places (`VAR-en`).
  - Suggested facts are a list in the code, not stored per world, so every world, old and new, offers it at once:
    no migration.
  - A fact labelled *pronunciation* (any capitals) is shown in small type after the name, on the entry page and on
    the name's card, and isn't repeated among the card's facts. Otherwise it is a fact like any other, exported as
    facts are.

**Data:**

```sql
entities  + gender text NULL CHECK (gender IN ('female', 'male', 'nonbinary'))   -- NULL is not set
```

One data migration adds the *witnessed* type to existing worlds. `PATCH /entities/<id>` takes `gender`, and the cards
carry it.

*Done when*, after upgrading, an existing world's types page lists *witnessed* under Character–event; recording
"Varren witnessed the Burning of the Quay" reads back as "witnessed by Varren" on the event; and a character's fact
picker offers *pronunciation*, which then shows beside the name on the card; and an existing world's characters show
*Gender: not set*, setting Varren to *male* shows `male` on his card (a character not set shows nothing there), and
exporting and restoring the world keeps it.

### 12.6 Labels and values

Classification stays free-form. There are no fixed lists, no required fields, no forms per kind and no category
trees: an event's type, a character's pronouns or a place's climate is a fact like any other, typed when it comes up
while writing. What builds up that way already has a shape: the same labels come back for the same kind, with the
same handful of values. These parts make that shape pay off without asking for anything up front.

Labels and values are always read **per kind**: *type* for events (festival, battle) and *type* for places (city,
fen) are different things, and mixing them would mix domains. Labels and values match **whatever the capitals**
(and with spaces trimmed), as the Continuity check already compares them. A value is shown in its most-used spelling.

#### 12.6.1 Value suggestions

Typing a fact's value on an entry page offers the values already used for that label on entries of the same kind,
so spellings stay the same.

- Today, typing a fact's **label** already offers the kind's suggested labels plus every label the world uses for
  that kind (`fact_suggestions` in `api/world.py` merges `SUGGESTED_FACTS` with the labels in use). The **value**
  works the same way: with *type* as the label on an event, the value field lists the events' types, most used
  first, each with its count: `Festival (4) · Battle (2) · Wedding (1)`.
  - Matching ignores capitals: typing `fest` offers *Festival*. Places' types aren't offered for an event.
  - Picking one fills it in. Typing something new is fine: it is a new value, offered next time.
- **Only on the entry page** (and wherever its fact form is used, such as recording a fact from a passage). Never in
  the prose, never while typing in a chapter.

**Data:** none. `GET /fact-suggestions` returns, per kind, the labels (as now) and for each label its values with
counts.

*Done when* typing `fest` as an event's type offers *Festival (4)* from the other events and nothing from the places'
types, and picking it saves *Festival* with that spelling.

#### 12.6.2 Filtering and grouping a kind's table by a value

Each kind's bible table already shows up to three fact labels that at least two of its entries have, as columns.

- **Filter.** Clicking a value in a fact column (or on an entry page, a fact's value) filters the table to entries
  with that value: clicking *Festival* in the events' *type* column shows every festival. The filter shows as a chip
  (`type: Festival ×`) and is kept in the address, so it can be bookmarked; several chips narrow further.
- **Group.** *Group by* picks any label the kind uses (not only the three shown). The table splits into one group per
  value, with counts, in order of size, and *no type* last. A group's heading filters to it when clicked.
- **Which value.** The table reads each entry's facts as they stand at the end of the story (the latest that holds,
  as *as of* the last chapter would show). A label with several values (§12.6.4) puts the entry in each of its
  values' groups, and a filter matches any of them.
- **Columns.** A fact column the filter or grouping uses is shown even if it isn't among the three.

**Data:** none; worked out in the browser from the cards (which carry every entry's facts).

*Done when* clicking *Festival* in the Events table's *type* column leaves only the festivals, with the filter in
the address, and *Group by type* splits the events into Festival, Battle and *no type* with their counts.

#### 12.6.3 The Labels page

A page for the world's fact labels, like the relationship types editor: `/w/<world>/bible/labels`, linked from the
bible pages next to *Relationship types*.

- **Per kind.** One card per kind, listing its labels by how many entries have them: `type: 6 of 9 events`. Opening a
  label lists its values with counts (`Festival 4 · Battle 2`) and the entries with each. The same label on another
  kind is its own row under that kind; a line says `also used for places (3)`, with a link.
- **Rename or merge a label** within a kind: renaming *colour of eyes* to *eye colour* changes the label on every
  character's facts. Renaming it to a label the kind already uses merges the two; an entry that had both keeps both
  facts (the Continuity check then shows where they disagree). A tick extends a rename to the other kinds that use
  the label.
- **Rename or merge a value** within a label and kind: merging *Feast* into *Festival* for events changes those facts
  and leaves any place's *Feast* alone. Values that differ only in capitals are one value here, and a rename makes
  them all the chosen spelling.
- **One step back.** Each rename or merge says what it changed (`Changed 5 facts on 5 events`) with **Undo**, which
  puts back the old label or value on each fact that hasn't changed since. Facts keep their version check, so an
  entry page open elsewhere gets the usual conflict instead of overwriting.
- The per-label switches of §12.6.4 and §12.6.5 (*several values*, *expected*) live here too.

**Data:**

```sql
fact_labels  (id, world_id, kind, label, several bool default false, expected bool default false,
              asked bool default false)    -- asked: the "expect it?" prompt of §12.6.5 has been shown
             -- unique (world_id, kind, lower(label)); a row exists only once a switch has been set or the prompt shown
```

Labels and values themselves are not stored separately: they are read from the facts. A renamed label carries its
`fact_labels` row with it. Endpoints: `GET /labels` (per kind: labels, counts, values with counts, switches),
`POST /labels/rename` and `POST /labels/values/rename` (kind, old, new; answering with the changed facts for Undo),
`PUT /labels/<kind>/<label>` for the switches. Export writes the rows into `world.md` (`fact_labels:`); Restore reads
them back, and an older export has none.

*Done when* the Labels page lists *type* under events with Festival 4 and Battle 2 and separately under places with
City 3, merging *Feast* into *Festival* for events changes only the events' facts, and Undo puts them back.

#### 12.6.4 Labels that hold several values

Some labels hold more than one value at a time: eye colour *green* and *red*, languages, titles.

- **The switch.** *Several values* per label and kind, on the Labels page (off to start, as today). Also offered
  where the conflict shows up: a *conflicting facts* finding gets **Both are true (several values)**, which sets the
  switch for that label and kind.
- **What changes when it is on.**
  - Values that hold at the same time are not a Continuity conflict: Varren's eye colour can be green and red from
    chapter 1.
  - *As of* keeps every value whose span holds, instead of letting the latest-starting one take over. A value ends
    only with its own *until*.
  - The values show as chips side by side: on the entry page, on the name's card, and in the bible table's column.
- **When it is off**, nothing changes from phase 9: a later value takes over from an open-ended earlier one, and two
  values that start in the same chapter, or overlap through an explicit *until*, are a conflict.

**Data:** `fact_labels.several` (§12.6.3). The check in `api/companion.py` skips labels with it set for the entry's
kind; `factsAsOf` in `world/time.ts` keeps all holding values for them.

*Done when*, with *several values* on for characters' *eye colour*, Varren's *green* and *red* from chapter 1 show as
two chips on his page and card and Checks lists no conflict; switched off, Checks lists the conflict as before.

#### 12.6.5 Suggestions that grow with use, and expected labels

- **New starting suggestions**: *type* for events, *pronouns* for characters (next to *pronunciation* from §12.5;
  gender is a field, not a fact), both optional like every suggestion. `SUGGESTED_FACTS` is a list in the code, not
  stored per world, so existing and new worlds offer them at once, with no migration.
- **Growing with use.** Every label in use is already offered for its kind. A label on **at least three** entries of
  a kind now counts as *common* for that kind:
  - it is listed with the starting suggestions, at the top of the label field, before labels used only once or
    twice;
  - an entry of that kind without it gets a quiet `Add: eye colour · age` line under its facts, one click to start the
    fact. It is an offer on the page, not a warning, and appears nowhere else.
- **Expected labels.** A label can be marked **expected** for a kind (*every character should have an eye colour*).
  Only then do entries without it become findings; nothing is ever inferred from use alone, since three characters
  with an eye colour would otherwise flag the other thirty-four.
  - **Asked once, at the third use.** When adding a fact on an entry page brings its label to three entries of the
    kind, a line appears under the fact just added:
    `3 characters have "eye colour" now · Expect it on every character? · Not now`.
    - It is inline, not a dialog: it takes no focus and blocks nothing, and typing on carries on as if it weren't
      there. It appears on the entry page only (and in its fact form wherever that is used), never in the editor.
    - It is asked **once per label and kind**. *Not now*, or ignoring it and moving on, means it isn't asked again
      for that pair; the Labels page stays the place to change it later.
    - *Expect it* marks the label expected for that kind, and the line says so with a link to the Labels page.
    - Not asked when the label is already expected, or for a kind's starting suggestions that are already
      expected.
  - **On the Labels page**, the switch can be set or unset at any time. The page also points out candidates
    (`31 of 37 characters have it`) for labels most entries of a kind already have, but never marks one by itself.
  - The findings are the **Archivist's**: `Varren has no eye colour (expected for characters)`. Like every finding
    they are silent while Drafting. In the editor they cover the entries named in the chapter; the entry page shows
    its own; the Labels page lists every entry missing it. They never become inbox items.
  - Each is resolved per entry: **Add it** opens the fact on the entry, with its value suggestions; **Not for this
    one** is stored as a resolution (`intentional`), so it never comes back for that entry and label.
  - Unmarking *expected* removes the findings; the resolutions stay, in case it is marked again.

**Data:** `fact_labels.expected` and `fact_labels.asked` (§12.6.3). Adding a fact answers with the prompt when it
applies, and the server marks the pair asked in the same save, so a prompt that is ignored, or shown on another
device, isn't shown again. The finding's rule is `missing_label`, keyed by entry and label, using the existing
`resolutions` table.

*Done when* an existing world's fact picker offers *type* for events and *pronouns* for characters; a label put on a
third character is listed among the common ones and offered as `Add:` on characters without it, with no finding
anywhere; adding *eye colour* to a third character shows `3 characters have "eye colour" now · Expect it on every
character? · Not now` under the new fact, without taking focus, and a fourth character's *eye colour* doesn't ask
again after *Not now* or after the line was ignored; and choosing *Expect it* (there, or on the Labels page) makes
the Archivist (while Revising) list a named character without an eye colour, where *Not for this one* silences it
for that character only and *Add it* opens the fact on the entry.

### 12.7 Data model, in one place

```sql
projects        + gap_chapters int default 5                         -- §12.1
entities        + project_id NULL                                    -- §12.4; ON DELETE SET NULL; NULL is the world
entities        + gender NULL (female | male | nonbinary)            -- §12.5; characters only; NULL is not set
relation_types  + "witnessed" / "witnessed by" (character – event)   -- §12.5; added to every existing world
fact_labels     (id, world_id, kind, label, several, expected, asked)  -- §12.6; only labels with a switch set
```

Endpoints: `GET /timeline` gains each chapter's POV and each project's gap length (§12.1); `GET /where` takes kinds,
entries and a project (§12.3); `PATCH /entities/<id>` takes `project` (§12.4); `GET /fact-suggestions` gains values,
and `/labels` lists, renames and switches labels (§12.6). The mentions strip, the family tree, kin, shared chapters,
common labels and missing-label findings are worked out when read, never stored.

**Phase 11 is done when** each part's *done when* above holds, and the demo world has a family of three
generations (with a cousin worked out, and gender set for some of them), an entry in each of its two projects'
bibles, a *witnessed* and a pronunciation, and events with a *type* (one label with several values, one marked
expected) to show.

### 12.8 Open questions for phase 11

None left. Missing labels are findings only for labels marked *expected* (Thomas: "For missing labels your instinct
is correct."), with a one-time prompt at the third use (§12.6.5). Existing entries all start in the world's bible
and need no tidying: what is there today is test worlds and the demo, which sets its own levels.

## 13. Time, history and kinds of being (phase 12)

Phases 6–11 kept one clock: the chapter, in book order ([WORLD-MODEL.md](WORLD-MODEL.md) §4). That is right for a
book told forwards and wrong for one that isn't. A tale told by a character, set centuries earlier, breaks the
Continuity checks (someone recorded dead in the present is flagged when they are alive in the tale), and there is
nowhere for the world's history to live: wars, foundings and births long before chapter 1. Phase 12 adds **in-world
time on one axis** under the chapters, a **Timeline** with a happened order and a told order, a way to **record
history from the prose**, a ninth kind for **kinds of being**, **roles** inside groups, a little more starting
vocabulary, **restructuring** (experiments that replace several chapters at once, and a review of everything tied to
chapters before they leave the book), and **the chart**, a schematic map of how the world's places nest, border and
connect.

The principles hold: nothing here writes or suggests story content; times are optional everywhere, and a world that
sets none works exactly as today; times are plain numbers with free labels, never a calendar (no months, moons or
date arithmetic: [research/README.md](research/README.md#not-building), "Not building", and research/05 §4 on how
World Anvil's calendars barely connect to its timelines); the compiled manuscript stays pure prose.

Examples use made-up names. The Lamp Guild was founded in year 0, so its people count years from the Founding. The
book is set in year 312. Varren marries Seyla in chapter 3; Seyla, a selkie, dies in chapter 9. Chapter 14, *The
Drowned Bell*, is a tale Isolde tells, set 800 years before the Founding, and Seyla is in it.

### 13.1 Story time on one axis

#### 13.1.1 An in-world time

- **A number.** A time is one sortable number: whole or with decimals, below zero for before the world's zero
  (`312`, `-800`, `312.5`). Quarry never converts it, splits it into months or works out weekdays. Two times compare
  by their numbers and nothing else.
- **The world names its unit.** On the world page: *Time is counted in* `year` / `years`, the default. A world
  counting in days, or in reigns, changes the words; numbers are left as they are.
- **A free label**, optional: `800 years before the Founding`, `the winter of the long ice`. Where a label is given it
  is shown, with the number small beside it or on hover; otherwise the number is shown with the unit:
  `year 312`, `year −800`.
- **Approximate**: a tick, *about*. Shown as `about year 312`; it sorts by its number like any other, and anything
  worked out from it (an age, a gap) says *about* too.
- **A span**, optional: a second number for where it ends, `years 300–302`. Spans sort by their start.
- **Three states.** A time is *a time* (a number, as above), *not set*, or **outside time**: for what is at no point
  on the world's axis, such as planes beyond the world, an afterlife, visions, dreams, myths and prophecies
  (§13.1.8).
- **Its era.** A time inside an era's span is shown with the era's tint and name, wherever it appears:
  `year 312 · the Lamp Years` (§13.2.1).

The same time field (number, end, label, about) is used for chapters (§13.1.2) and events (§13.2.1). Bounds on
facts and relationships use the number and the tick (§13.1.5).

#### 13.1.2 When a chapter is set

- **Set in.** Each chapter can say when it is set, with the time field. Empty to start. It is edited in place on the
  manuscript list (muted, after the summary) and in the editor's side panel. Like a summary and a status, it is
  saved without the version check and makes no new version: it is a label on the chapter, not its text.
- **Told as.** A chapter can be marked as told as a **flashback** or a **tale** (a story a character tells), or
  neither, the default. The mark shows as a small pill beside the title on the manuscript list and in the editor.
  Both marks behave the same; they differ only in the word shown.
- **A gentle hint.** On the manuscript list, a chapter whose own time is before the one of the chapter before it,
  and that has no mark, gets a quiet `set earlier` note with one click to mark it a flashback. Nothing else asks for
  it, and the note can be left there forever.
- **One time per chapter.** A tale told inside a present-day chapter (a few paragraphs in someone's mouth) is not a
  time for the chapter: it is recorded as an event from the passage (§13.2.3).
- Experiments and retired chapters keep their time and mark; an accepted experiment brings its own into the book.

#### 13.1.3 The clock: happened order

The book's chapters now have two orders: **told** (book order, as today: project order, then chapter order) and
**happened** (when they are set). Happened order is worked out, never stored:

1. **A chapter's set time** is
   - its own time, when it has one;
   - otherwise, unless it is marked as a flashback or a tale, the set time of the nearest chapter **before** it in
     book order that has its own time and no mark: an unset chapter carries on from the present it follows. With
     none before it, the first such chapter **after** it (so the chapters before the first one with a time share
     its time);
   - otherwise none.
2. **Happened order** sorts chapters by set time, then by book order. Two chapters set at the same time keep their
   book order; a span sorts by its start.
3. **A flashback or tale with no time of its own** is set *sometime before the story*: it sorts before every other
   chapter (in book order among such chapters), and the Continuity checks skip it (§13.1.7). Marking a tale is
   enough to stop false findings in it, before any time is chosen.
4. **No times and no marks**: every chapter's set time is none, and happened order is book order. Everything works
   exactly as today.
5. If only flashbacks and tales have times, the other chapters have no set time and keep book order after them.

So with chapters 1–13 set in year 312 and chapter 14 marked a tale set in year −800, happened order is 14, 1, 2, …,
13, 15, …; chapter 15, with no time, carries on from chapter 13 in year 312, not from the tale.

#### 13.1.4 What follows the clock, and what stays in book order

The rule: **told order is the reader's; happened order is the world's.**

- **Happened order** (the clock) is used by: facts and relationships and their *from*/*until* (§13.1.5), *as of*
  (§13.1.6) on entry pages, the name's card, the companion's cast, the graph and the family tree, the Continuity
  checks (§13.1.7), ages (§13.2.4), and the Timeline's *happened* view.
- **Book order** stays for: the manuscript list and chapter numbers, the mentions strip and its gaps (§12.1), first
  appearance, reading one entry's thread (§11.4), find and replace, word history and the POV tally, and the Timeline's
  *told* view. These are about what the reader meets, and when.
- **Where they meet.**
  - The mentions strip stays in book order, but *as of* now dims the chapters that are **later on the clock**: a
    flashback after the chosen chapter in the book, but set before it, isn't dimmed. With no times, the chapters after
    it, as today.
  - The Where-everyone-is grid (§12.3) keeps book order by default and gets *Order: told · happened* once any chapter
    has a time. Each chapter's head shows its set time and mark. "Is at" stays one place per character per chapter;
    its time is the chapter's set time.

#### 13.1.5 Facts and relationships

- **Bounded by chapters, read on the clock.** A fact or relationship *from* chapter A *until* chapter B holds in a
  chapter when that chapter is at or after A and at or before B in **happened** order. Book order no longer decides.
  - *Seyla: status dead from chapter 9.* In chapter 14, the tale set in year −800, she is alive: chapter 14 is before
    chapter 9 on the clock. In chapter 15 she is dead.
  - *Varren married to Seyla from chapter 3 until chapter 9*, with chapter 3 set in year 305 and chapter 9 in year
    312. A flashback in chapter 20 set in year 300, before the wedding, is outside the span though it comes after
    chapter 9 in the book; one set in year 308 is inside it.
  - A span *from* chapter 14 (the tale) *until* chapter 3 runs forwards now: the tale is earlier. A span runs
    backwards only on the clock.
  - The latest-starting fact still takes over from an open-ended earlier one (phase 7), with "latest" on the clock.
  - A bound to an experiment or a retired chapter is still ignored, as today.
- **Bounded by a time.** A *from* or *until* can be a time instead of a chapter (one or the other, never both): *born
  from year 278*, *member of the Lamp Guild until year 0*. History before the book needs this, since no chapter is
  set then. The span picker offers the book's chapters (with their times) and *A time…* (a number and *about*).
  - A time bound holds in a chapter whose set time is on the right side of it; a chapter set exactly at that time
    counts as inside. A chapter with no set time ignores time bounds (as it ignores a retired chapter), so in a world
    with no chapter times a time-bounded fact simply holds throughout.
  - Spans shown in text: `from year 278`, `year 0 – chapter 9`, `about year −800 – year 0`.
- **A chapter or a time: what each is for.** A chapter bound says *where in the book* something changes; a time bound
  says *when in the world*. A chapter bound moves with its chapter, and has to be dealt with when the chapter is
  retired (§13.6.2). A time bound outlives any reshuffle: *dead from year 312* stays true whatever happens to chapter
  9; *dead from chapter 9* does not. **Anchoring to time is what survives restructuring.** A time is only as fine as
  its number, so decimals (`312.4`) order things within a year where that matters.
- **How the two combine.** Each side of a span is one or the other, and the two sides may differ (`from chapter 3
  until year 400`). Both sit on the one clock:
  - a chapter bound at its chapter's place in happened order (its set time, then book order);
  - a time bound at its number: a *from* just before the chapters set at that time, an *until* just after them. So
    *from year 312* takes in every chapter set in year 312, while *until chapter 9* stops at chapter 9 even among
    chapters set in the same year;
  - which of two facts started latest, and whether two spans overlap, are decided on the same clock;
  - a chapter with no set time can't be placed against a time bound, so for that chapter the bound counts as no bound,
    and the Continuity checks leave out what they can't compare rather than guess.
- **Saving.** "From must come before until" is checked on the clock. Setting or changing a chapter's time can make an
  existing span run backwards; Checks lists it, as it lists one after chapters are reordered today.

#### 13.1.6 As of

- **The selector** lists the book's chapters per project in book order, as now, with each chapter's set time after
  its title and the tales and flashbacks marked: `14 · The Drowned Bell — tale, year −800`.
- **A time.** Once any chapter or bound has a time, the selector also offers *At a time…*: a number. *As of year 0*
  shows what holds at that time: chapter bounds compare by their set time, and chapters set at that time count as
  begun. The choice is kept in the address: `?asof=<chapter>` as now, or `?at=<number>`.
- Everything that follows *as of* follows either kind: the entry page, the family tree, the graph.

#### 13.1.7 The Continuity checks

All of them use the clock, and every check that compares times skips a chapter set at an unknown earlier time (a
mark without a time).

- **Named after being recorded dead**: named in a chapter that is after the death on the clock. Names inside a
  passage recorded as the telling of an event (§13.2.3) are skipped: telling of the dead is history, not an
  appearance.
- **Named before coming into the story** is split by what the label means:
  - *born* and *arrives* are about the world, so they use the clock: being named in a tale set before the birth is a
    finding; being named in a later chapter set after it isn't.
  - *introduced* and *first appears* are about the reader, so they keep book order.
- **Spans that run backwards**, **two values at once** (*fact_conflict*) and **two holders of a one-at-a-time role**
  (§13.4) compare on the clock.
- A finding's chapter is still the chapter it is about, and Checks still lists findings by that chapter in book
  order.
- **A computed age that disagrees with an *age* fact** (§13.2.4) is a finding too.

#### 13.1.8 Outside time

Some things are at no point on the world's axis: a plane beyond the world, an afterlife, a vision or a dream, a myth
that is told but never happened, a prophecy. **Outside time** is the time field's third choice, beside a time and
*not set*.

- **What can be outside time.**
  - A **chapter** (*set in: outside time*): a chapter in the Hollow Court, beyond death. It needs no tale or flashback
    mark, though it may have one.
  - An **event** (*when: outside time*): the Prophecy of the Second Lamp, the myth of the Drowned Bell.
  - A **fact** or a **relationship** (a tick, *outside time*, in place of *from* and *until*): Seyla *rules* the Hollow
    Court, outside time; *title: Queen of the Hollow Court*, outside time. It has no bounds.
- **Never on the axis.** Outside time has no number and no era, so it is never placed, never compared and never
  carried on:
  - happened order leaves outside-time chapters out of the clock; lists in happened order show them after it, under
    *Outside time*, in book order (the grid's happened order too);
  - an unset chapter after one carries on from the last chapter before it that has a time and no mark, as if the
    outside-time chapter weren't there;
  - the Continuity checks skip outside-time chapters, facts and relationships: no *named after death* in the Hollow
    Court, no *two values at once* between an outside-time title and one in time, no role clash, no age conflict;
  - no age is worked out in an outside-time chapter or for an outside-time event.
- **As of.** An outside-time fact or relationship is **always shown**, whatever chapter or time is chosen, labelled
  `outside time`. It never takes over from a value in time, and is never taken over by one; a label that holds one
  value shows both, the one in time first.
  - *As of* an outside-time chapter shows the outside-time facts and relationships and those with no bounds; those
    bounded in time are left out, and a line says so: `Outside time: what changes over time isn't shown`.
- **Shown** as `outside time`, in a neutral tint, wherever a time would be.
- **On the Timeline** it has its own strip, apart from the axis (§13.2.2).
- **Export** writes `time: outside` for a chapter or an event, and `outside_time: true` for a fact or relationship
  (with no `from`/`until`); **Restore** reads them back.

*Done when* chapter 21, *The Hollow Court*, set outside time, names Seyla (dead from chapter 9) with no finding and
no age on her card; *title: Queen of the Hollow Court*, outside time, shows on her page as of chapter 2, chapter 14
and year 0 alike, labelled `outside time`, and Checks finds no conflict with her *title: Lady of Old Harbour*; chapter
22, with no time, carries on from the last timed chapter before 21; the Prophecy of the Second Lamp, outside time,
sits in the Timeline's outside-time strip; and exporting and restoring the world keeps all three.

**Data:**

```sql
worlds        + time_unit text default 'year', time_units text default 'years'
chapters      + time_at numeric NULL, time_end numeric NULL, time_label text NULL,
                time_approx bool default false, outside_time bool default false,   -- outside: no time_at
                told_as text NULL CHECK (told_as IN ('flashback', 'tale'))
facts         + from_time numeric NULL, from_approx bool default false,
                until_time numeric NULL, until_approx bool default false,
                outside_time bool default false                                    -- outside: no bounds
relationships + from_time, from_approx, until_time, until_approx, outside_time     -- as for facts
              -- for both: CHECK (from_chapter_id IS NULL OR from_time IS NULL), and the same for until
```

`GET /timeline` gains per chapter its time, mark, set time and `clock` (its place in happened order); the browser's
`holds` and `factsAsOf` (`world/time.ts`) and the server's checks compare clock places instead of book indexes, and
time bounds against set times. `story_order` keeps book order beside a new `clock_order`. **Export** writes a
chapter's `time:` (`at`, `end`, `label`, `approx`, or `outside`) and `told_as:`, the time bounds of facts and relationships
(`from_time:`, `until_time:` and their `approx`), and the unit into `world.md`. **Restore** reads them back; an older
export has none, which is today's behaviour.

*Done when*, with chapters 1–13 set in year 312, Seyla *status: dead from chapter 9* and *married to Varren from
chapter 3*, and chapter 14 marked a tale set in year −800: Checks lists no "named after death" for Seyla in chapter
14; her page *as of* chapter 14 shows her alive and unmarried; chapter 15, with no time, shows her dead; removing
the tale's time but keeping the mark still gives no finding there; a fact *born from year 278* is offered and shown
as `from year 278`; and a world with no times and no marks gives exactly the findings and *as of* results it gave
before (the existing tests pass unchanged).

### 13.2 History and the timeline

#### 13.2.1 Events get a time

- **When.** An event's page has *When* beside the kind, with two choices:
  - **in a chapter**: the event happens on the page in that chapter, takes the chapter's set time and follows it when
    it changes. With no times in the world it still has a place: that chapter, in book order;
  - **a time**: the time field of §13.1.1 (number, end, label, about), for anything off the page, such as history;
  - **outside time** (§13.1.8), for myths, prophecies, visions.

  Or empty: *not placed yet*. The Events table gets a *When* column that sorts in happened order.
- The suggested fact *when* gives way to the field. Existing *when* facts stay, as facts (a festival's "every spring"
  is still a good one).
- **History** is what happened before the story: events, births and deaths set before the first chapter on the
  clock (chapters marked as tales or flashbacks don't count as the story's start). It is a view of the Timeline
  (§13.2.2), not a separate store.
- **Eras** are events too: an event whose *type* (§12.6) is *era*, whatever the capitals, with a span. Being events,
  they have a page, mentions and relationships for free; an era named in the prose is matched like any other entry.
  *Era* is among the starting values for an event's type (§13.5).
  - **A colour.** An era's page has a colour, picked from a palette of eight that works in both themes (each a pair
    of tokens, light and dark, like the kind colours). A new era takes the next colour not yet used.
  - **Its span.** An era with a start and no end runs on to the end of time (the era the book is in, say). An era
    inside another's span is **nested** in it.
  - **A time's era** is the innermost era whose span holds it; between two eras that overlap without nesting, the one
    that starts later.
  - **Every time shown carries its era**: its tint and its name, `year 312 · the Lamp Years`, wherever a time is
    shown: the manuscript list, the editor's side panel, the *as of* selector, an event's *When* and the Events
    table, spans (`from year 278 · the Long Ebb`), the name's card, an entry's own timeline and the Timeline. A time
    in no era is shown plain, and outside time has none. A world without eras looks as it did.
  - On the Timeline eras are background bands, nested ones thinner inside them (§13.2.2), and can be a filter or a
    lane.

#### 13.2.2 The Timeline page

One page for the world: `/w/<world>/timeline`, in the nav after *Graph*. How it looks and moves is in the design
brief (§13.2.6).

- **Two orders**, a switch at the top, as in Aeon Timeline (research/06 §7): **Happened** (the default once anything
  has a time) and **Told**. Moving something in one order never moves it in the other.
- **Happened.** Time runs left to right along one axis; lanes are rows across it.
  - **To scale, with gaps folded.** The axis is to scale, except that a long stretch with nothing in it is folded to
    a fixed width and labelled with its length (`· 512 years ·`), so 800 empty years don't push the book off the
    screen. Folds are worked out again as the zoom changes.
  - **Eras** are painted as background bands across every lane, in their colours, named along the top; an era nested
    in another is a thinner band inside it. The axis's labels carry their era's tint.
  - **Events**, the main lane: each event a mark (an event with a span, a bar), with its name beside it where there is
    room; type and the people in it on its card.
  - **The book**, a lane of its own: the chapters as ticks at their set times, and the stretch from the book's first
    to its last chapter by set time (tales and flashbacks aside) shaded *the book*. A tale or flashback is a marked
    tick at its own time: `14 · The Drowned Bell — tale`.
  - **Births and deaths**, from facts (the start of a *born* fact; the start of the *status* fact the Continuity check
    reads as dead) or from events whose type is *birth* or *death* (§13.5) and who they involve. They show in the
    characters' lanes, and in the main lane when the page is filtered to entries.
  - **Movements** from "is at", each at its chapter's set time, in the characters' lanes (and in the main lane when
    filtered to entries; otherwise there would be one mark per character per chapter).
  - **Outside time**: a strip of its own under the axis, not on it and not to scale: the outside-time events and
    chapters in book order, and each lane's own outside-time items in line with that lane (§13.1.8).
  - **Not placed yet**: a tray at the end with the events that have no time, each with *When…* to set it in place.
- **Told.** Rows are the chapters in book order, each with its set time (tinted by its era) and mark. A thin margin
  shows where each chapter sits in happened order, so a flashback is a jump to the left and a chapter outside time
  sits apart. Under each chapter: the events told in it (§13.2.3), the events happening in it, and births and deaths
  recorded from it. Events never told and not in any chapter are listed at the end, *Not in the book yet*.
- **History** is a tab: the happened view cut off where the book begins. With no chapter times it shows the events
  with a time, and says `Set a time on a chapter to place the book among them`.
- **Lanes**, optional: *Lanes…* adds a lane per character, faction or era, kept in the address (any number; they
  scroll).
  - A **character's lane**: a life line from birth to death (fading out where either is unknown), the places over
    time (each run of chapters with the same "is at" one segment, named; *lives in* spans fainter), and a mark for
    each event they are related to, with their age at it when it can be worked out (§13.2.4).
  - A **faction's lane**: its events, its members joining and leaving (*member of* spans), and who held each role
    when (§13.4).
  - An **era's lane**: the events within its span, and the eras nested in it.
  - Every lane **collapses** to a thin line with its counts (`Seyla · 12 events · 4 places`) and opens again; which
    lanes are collapsed is kept in the address.
- **Filters**, kept in the address, the last used remembered per world on the device: kinds of mark (events,
  chapters, births and deaths, movements), entries (only marks about them, with the grid's picker), an era (only its
  span), and standing (planned and rumour, as on the Graph).

#### 13.2.3 Recording from the prose

- **Record as event.** Selecting a passage in a chapter (a character telling an old tale, say) offers *Record as
  event* in the selection strip, on the desk and on the phone (next to *Cut to bin*). The strip grows into a small
  form in place, as *Another name of…* does: never a dialog, and Esc goes straight back to the text.
  1. **The event**: type a name for a new one, or pick an existing event (the events named in the selection and the
     chapter come first).
  2. **Who and where**: a chip for each entry named in the selection, found by the matcher that colours names (any
     of their names). Characters, factions and species start ticked as taking part; the first place named starts
     ticked as where it happened; other kinds start unticked. Entries already related to the event say so. Nothing is
     suggested beyond the names in the selection.
  3. **When**: the time field; it can be left empty and set later. In a tale or flashback with a time of its own, a
     chip offers it: `This chapter's time (year −800)`.
  4. **Save** (Enter). A new event is made (in the chapter's project's bible when the world has several, §12.4).
     The passage is kept as a **telling**: the chapter and the passage's text. The ticked entries are recorded with
     the world's *involved* and *happened at* types (found by label, as the family tree finds parent types; *linked
     to* when the world has neither), established in this chapter, with the passage as evidence. For an existing
     event, the telling and any new participants are added; an empty time is filled; a different time asks
     `Keep year 0 · Use year −800`.

  A toast says `Recorded "The Founding" · 3 taking part · Open · Undo`; Undo removes what this save added.
- **Tellings** show on the event's page under *Told in*: each passage quoted, with its chapter, linking into the
  editor at the passage. An event can be told several times (Varren in chapter 2, a priest in chapter 30).
- **Telling is not appearing.** The *named after death* check skips names inside a telling's passage, found in its
  chapter by its text. If the passage has been edited so that it can't be found, the names count again and the
  telling is marked *passage changed* on the event page.
- **Set born here · Set died here.** The same strip lists each character named in the selection with two chips:
  `Seyla: born here · died here`.
  - *Born here* records a *born* fact from this chapter; *died here* records *status: dead* from this chapter. Either
    keeps the passage as evidence.
  - If the fact exists already, the chip says so and offers to move it: `Seyla is recorded born in chapter 2 · Move it
    here`.
  - In a tale or flashback with no time of its own, a line says `This chapter has no time yet: Seyla will count as
    born before the story begins · Set its time…`.
- As everywhere in the editor (WORLD-MODEL.md §5), the strip opens only for a selection, never while typing.

#### 13.2.4 Ages

- **A birth time** is the start of a character's canon *born* fact (a time, or a chapter's set time), or the time of
  a canon *birth* event they are involved in. A **death time** is the start of the *status* fact the Continuity check
  reads as dead, or of a *death* event.
- **Age as of a chapter** is the chapter's set time minus the birth time, in the world's unit, rounded down, and
  *about* when either is approximate. As of a time, the same with that time.
- **Shown** on the name's card (`age 34`, as of this chapter), on the entry page beside the facts (`34 as of chapter
  9 · born year 278`), in the character's lane, and on the entry's own timeline. After the death time: `died at 61`.
  Before the birth time: `not born yet`.
- An *age* fact stays a fact, and both are shown. When they **disagree**, it is a **Continuity** finding:
  `Tamsin is 17 in "The Crossing" by her age, but born in year 390 makes her 22.`
  - The *age* fact as of the chapter is read as a number when its value starts with one (`17`, `about 60`); a value
    that doesn't (`old`, `in her thirties`) is never compared.
  - They disagree when they differ by more than one unit (a birthday later in the year isn't a clash); with *about*
    on either side, by more than one unit plus a tenth of the age.
  - Canon facts only, chapters on the clock only (not tales or flashbacks without a time, not outside time).
  - Resolved like any finding: *update the fact*, *intentional*, *later*.

#### 13.2.5 An entry's own timeline

Each entry page gets a **Timeline** section (hidden while it would be empty): the entry's own slice of the Timeline,
in happened order, each row with its time.

- A **character**: born, events they are related to, runs of "is at" (`at Old Harbour · chapters 3–7`), relationships
  starting and ending (with their roles, §13.4), died; with their age on each row when it can be worked out.
- A **place**: events that happened there, and who was there when (from "is at").
- A **faction**: its events, members joining and leaving, and who held each role.
- An **event**: its time and era, its tellings, and the ages of the people in it.
- A **species**, a culture or anything else: the events it is related to.

It follows the page's *as of*: rows after it on the clock are dimmed. *Open in the Timeline* opens the page with this
entry's lane.

#### 13.2.6 The Timeline's design (brief)

The Timeline should look good, be pleasant to move around in, and pack a lot in without clutter. Time is coloured by
its era. What it has to do:

- **Zoom and pan.** Wheel or pinch zooms around the pointer, dragging pans, `+` `−` and the arrow keys do the same,
  and *Fit* shows everything. Double-clicking a cluster or an era zooms to it.
- **Semantic zoom.** What is drawn depends on how far in you are:
  - up close, every event, birth, death and move is its own mark with its name;
  - further out, marks that would overlap merge, per lane, into a **cluster** with a count and a breakdown
    (`14 events · 3 births · 2 moves`);
  - furthest out, the eras, the book's band and the clusters' counts.
- **Collapsible lanes**, per character, faction or era (§13.2.2).
- **Hover cards.** Resting on a mark (a long-press on the phone) shows the **same card component as the editor's**
  (WORLD-MODEL.md §5): the one-liner, facts as of that time, the closest relationships. A chapter's card has its
  title, summary, set time and status; a cluster's lists what is in it. The card never takes focus.
- **Click through.** Clicking a mark opens it: an entry's page, a chapter in the editor at its passage, a fact on its
  entry.
- **Brushing.** Dragging along the axis (or in the overview) marks a span. The other lanes dim outside it, and the
  list under the Timeline, *In this span* (events, chapters, births and deaths, moves, with counts), shows only what
  is in it. The span says its length and era (`year 290–312 · 22 years · the Lamp Years`), is kept in the address,
  and is cleared with Esc or its `×`.
- **An overview strip** above the axis: the whole timeline, small, with the eras in their colours, how dense the marks
  are, and the book's band, and the part on screen as a frame that can be dragged and resized.
- **Smooth at a few thousand items.** The layout is worked out once per change of data; panning and zooming move a
  transform, and the clusters are worked out again only when the zoom crosses a step, so no more than a few hundred
  marks are drawn at any zoom. Budget, as for typing (DECISIONS, 2026-10-22): pan and zoom at 60 frames a second with
  3,000 items on the desk, no frame over 50 ms at 4× slower CPU, and the first drawing within a second.
- **Names are never cut off or drawn over one another.** A mark's name stands beside it in the lowest of a few rows
  above the lane's line where it fits (a higher row with a thin leader down to its mark), to the left of the mark near
  the right edge, and shortened with "…" only where no row holds it whole; what can't be named is read from its card.
  A cluster is named by its breakdown. Era names have a strip of their own above the axis numbers (outer eras, then
  those nested in them), and an axis number that would be cut at an edge is left out. What is outside time is listed
  under the Timeline; a lane says only how many of its own are ("1 outside time", named on hover).
- **On the phone**, the same axis: pinch to zoom, drag to pan, lanes stacked and scrolling down, the overview on top.
- **By keyboard**, arrow keys move from mark to mark, and the *In this span* list reaches everything shown.
- Drawn in the browser, plain SVG, no library, as the graph and the family tree are, from the cards, the graph's
  relationships and `GET /chronology`. It reads online, like the Graph.

*Done when*, in a world of 3,000 events (a fixture made up for the purpose, like the editor's `frontend/perf`):
zooming out from one year to the whole world merges marks into clusters with counts and zooming back in splits them
into named marks, within the budget above; eras are painted as bands in their colours, a nested era thinner inside
its parent, and a time on the manuscript list reads `year 312 · the Lamp Years` in that era's tint; collapsing
Seyla's lane leaves a line with her counts; resting on an event shows the editor's card for it and clicking opens its
page; brushing years 290–312 dims everything outside and leaves only that span in *In this span*; and dragging the
overview's frame pans the Timeline.

**Data:**

```sql
entities  + time_at numeric NULL, time_end numeric NULL, time_label text NULL,
            time_approx bool default false, outside_time bool default false,
            time_chapter_id NULL,               -- events: "in a chapter" (ON DELETE SET NULL), a time, or outside
                                                -- time, one of them; kept, unused, if the kind changes
            era_colour text NULL                -- eras: one of the palette's eight names
tellings  (id, world_id, event_id, chapter_id NULL,   -- ON DELETE SET NULL
           passage text, created_by, created_at)
```

The cards carry an event's time, and each era's span and colour, so a time's era is found on the device.
`GET /chronology` returns the world's "is at" rows and tellings for the Timeline; the rest is worked out in the
browser from the cards, `GET /timeline` and `GET /graph`. `POST /events/record` saves *Record as event* in one
transaction and answers with what it added, for Undo. **Export** writes an event's `when:` (a chapter id, the time,
or `outside`), an era's `colour:`, and `tellings:` (chapter and passage) into its frontmatter; **Restore** reads them
back and relinks the chapters by id.

*Done when* selecting the passage in chapter 2 where Varren tells how the Lamp Guild was founded and choosing *Record
as event* offers the guild, Seyla and Isolde (the names in it) as chips, and saves *The Founding* with year 0, its
participants and the passage under *Told in*; the Timeline's happened view lists the tale (year −800), the Founding
and then the book's band, with `· 800 years ·` and `· 312 years ·` between them, and its told view shows chapter 14
jumping back; History lists the tale and the Founding; with Seyla *born from year
−1000*, *Set died here* on her in chapter 9 records her death, after which her lane runs from her birth to chapter 9,
her card in chapter 5 shows `age 1312` and in chapter 14 `age 200`; and her page lists, in happened order, her birth,
the Founding, her marriage from chapter 3 and her death.

### 13.3 Species

A ninth kind, for kinds of being: peoples, beasts, spirits, ancient races. It is not Culture: Culture is what people
share (faith, customs, language); Species is what they are. The kind is called **Species** (settled with Thomas).

- **In the nav and the bible** like every kind: a page with its table, its own colour in both themes, the strip's
  `+ Species` under *More…*, and the F8 pass and the companion's *Add as…*.
- **Starting relationship types:**

  | Between | Types |
  |---|---|
  | Character – species | *is a* / *includes* (time-bounded like any relationship; several allowed: a half-selkie is a selkie and a human; someone turned is a human until chapter 9 and a wraith from it); *appears as* / *the guise of* (a disguise or outward form) |
  | Species – species | *descended from* / *ancestor of*; *related to*; *preys on* / *prey of* |
  | Species – place | *native to* / *home of* |
  | Culture – species | *culture of* / *has culture* |
  | Faction – species | *made up of* / *makes up* |

  Event, term and *linked to* types already reach every kind.
- **Describing a species** is done with suggested facts and value suggestions (§12.6), not structured fields, since
  there are more ways to qualify a species than humanoid or not:
  - *form* (humanoid, beast, aquatic, amorphous, spirit …), *sapient* (yes, no, partly), *size*, *lifespan*,
    *habitat*, *diet*, *reproduction*, plus *appearance*, *pronunciation* and *name meaning* (§13.5);
  - each offers the values used on other species, after a short starting list (§13.5), and takes anything typed;
  - each can be marked *expected* for Species on the Labels page (§12.6.5), like any label, so the Archivist asks
    for it on every species only once that is wanted;
  - a label that holds several values (§12.6.4) works here too (*habitat: reef* and *river*).

  Free text, as all facts: nothing reads them, so lifespan isn't checked against ages. A species attribute becomes a
  structured field only once something reads it, as gender did (§12.5).
- **Beside a character's name.** The species a character *is* as of the chapter (from *is a*, found by label as the
  family tree finds parent types) shows as one small word after the name on the card and the entry page, as gender
  does: `Seyla · selkie`. While an *appears as* holds, it is added: `Seyla · selkie · appears as human`. Several show
  side by side. Nothing shows when none is recorded.
- **On the characters table**, a *Species* column (at the end of the story, as the table reads facts, §12.6.2), which
  filters and groups like a fact column.
- **On the graph**, *Colour by: kind · cluster · species*: characters take their species' colour (as of the graph's
  chapter), from a fixed set in order of size, with the rest grey and a legend.
- **Existing worlds** get the kind and its starting types from a data migration: each type is added at the end of its
  pair unless the world already has a type for that pair reading the same (either way, any capitals), as *witnessed*
  was (§12.5). Suggested facts reach every world at once (they are not stored). Entries recorded as culture or other
  that are really species can be moved by changing their kind; their relationships stay, as for any change of kind.
- **Restore** keeps an export's own vocabulary, except that an export with no type touching species (every export
  made before phase 12) gets the species starting types, since the kind didn't exist when it was made.

**Data:**

```sql
entities.kind    + 'species'                        -- the CHECK constraint widens
relation_types   + the species starting types       -- for every existing world, by migration
```

The cards carry each character's *is a* and *appears as* relationships with their spans, so the word beside the name
follows *as of* offline too.

*Done when*, after upgrading, an existing world's types page lists the species types; Seyla *is a* selkie, and *appears
as* human from chapter 3 until chapter 9, shows `selkie · appears as human` on her card in chapter 5 and `selkie` in
chapter 10; the characters table has a Species column that groups by it; the graph colours characters by species; and
exporting and restoring the world keeps it all.

### 13.4 Roles in groups

A captain in a guild, a treasurer, the keeper of a temple's lamps: a role belongs on the relationship that puts
someone in the group, and changes when they are promoted, demoted or replaced.

- **Which relationships have one.** A switch per relationship type on the types page, *has a role*. It is on to start
  for *member of*, *leads*, *serves* and *works at*, and can be set on any other type. The holder is the A side, the
  group the B side: Varren *member of* the Lamp Guild; Isolde *serves* Varren.
- **The field.** Such a relationship gets *role*: free text, empty to start, with value suggestions as in §12.6.1: the
  roles used on that type across the world, most used first with counts, those already used in the same group first.
  `Captain (3) · Treasurer (1)`.
- **Time-bounded like the relationship.** The role is the role for the relationship's span. A promotion is a new
  span: *Change role from here…* on a relationship ends it just before a chosen chapter or time and starts a copy with
  the new role from there. Planned and rumoured roles are kept and shown as their standing says.
- **Shown wherever the relationship shows**: on both entry pages (`member of the Lamp Guild · Captain · from chapter
  3`, and from the guild's side `has member Varren · Captain`), on the name's card, on the graph's edge, in a faction's
  lane and on the entry's own timeline (§13.2).
- **One at a time.** A switch per role, off to start: *one at a time* (whatever the capitals, across the world). With
  it on, two holders of that role in the same group at the same time is a **Continuity** finding:
  `The Lamp Guild has two Captains in chapter 5: Varren (from chapter 1) and Isolde (from chapter 5).`
  - Canon relationships only, compared on the clock (§13.1). A handover (one ends at the chapter or time where the
    other starts) is not a clash.
  - It is resolved like any finding, plus **End Varren's before Isolde's**, which sets the earlier one's *until*.
  - The switch lives on the Labels page (§12.6.3) in a new *Roles* card, which lists roles with counts and renames or
    merges them across the world with Undo, as it does values.
- **Export** writes a relationship's `role:`, each type's `has_role:`, and the one-at-a-time roles into `world.md`
  (`roles:`); **Restore** reads them back. An older export has no roles; its types get *has a role* by the same labels
  as the migration.

**Data:**

```sql
relation_types  + has_role bool default false      -- on for member of, leads, serves, works at; by migration too
relationships   + role text NULL
roles           (id, world_id, role, one_at_a_time bool default false)
                -- unique (world_id, lower(role)); a row exists only once the switch has been set
```

*Done when* Varren *member of* the Lamp Guild with role *Captain* until chapter 4 and Isolde *Captain* from chapter
5 show their roles on both entry pages, the guild's lane shows who was Captain when, and typing `Cap` offers
*Captain (2)*; with *one at a time* on for Captain, extending Varren's until chapter 6 lists the clash at chapter 5
on Checks, and *End Varren's before Isolde's* clears it.

### 13.5 Starting vocabulary

- **Possesses / possessed by** (character – character), time-bounded as always: the Grey Tenant *possesses* Isolde
  from chapter 12 until chapter 15. While it holds as of the chapter, the possessed character's card says
  `possessed by the Grey Tenant` under the name. Nothing else reads it.
- **Ancestor of / descendant of** (character – character), for lineages across centuries where the generations
  between aren't recorded.
  - **The family tree** (§12.2) reads it by label (a label ending in `ancestor of`, a reverse ending in `descendant
    of`, or the mirror) and draws a **long dashed link**: the ancestor at least two rows above, the link labelled with
    the gap: `about 600 years` from their birth times (§13.2.4) when both are known, otherwise `generations not
    recorded`.
  - **Kin worked out** through it stops there: the descendant, and anyone descended from them through parent links,
    are the ancestor's *descendants*, and the ancestor's own ancestors theirs; no cousins, siblings or in-laws are
    worked out across it.
  - *Their own ancestor* (Continuity) follows these links too.
- **Name meaning**, a suggested fact on every kind (`name meaning: "keeper of the ford"`). A term's *meaning* stays
  the meaning of the term.
- **Starting values.** Value suggestions (§12.6.1) also offer a short list from the code after the values in use,
  without counts, so a new world has something to pick from. Like suggested facts they are not stored, so every world
  gets them at once:
  - a place's *type*: world, plane, land, region, sea, lake, river, island, mountain, forest, reef, city, town,
    village, district, building, room;
  - an event's *type*: era, war, battle, founding, treaty, betrayal, birth, death, festival, wedding, coronation
    (*era*, *birth* and *death* are read by the Timeline, §13.2);
  - a species' *form*: humanoid, beast, aquatic, amorphous, spirit, plant; *sapient*: yes, no, partly; *size*: tiny,
    small, human-sized, large, huge; *diet*: plants, meat, anything, none.
- **Existing worlds** get the new types from the same data migration as Species, by the same rule (unless the world
  has one reading the same).

**Data:** the new types in `STARTING_TYPES` and the migration; `SUGGESTED_FACTS` and a new `SUGGESTED_VALUES` in
`vocabulary.py`.

*Done when* an upgraded world's types page lists *possesses* and *ancestor of*; Isolde's card in chapter 13 says
`possessed by the Grey Tenant`; the tree centred on Mirelle draws a recorded ancestor 600 years back as a long dashed
link labelled `about 600 years` and lists her as *ancestor*, with no cousins worked out through it; and a place's
type field offers *plane* and *reef* in a world that has never used them.

### 13.6 Restructuring

A new beginning that moves characters around leaves chapters already written that may no longer happen, or not in
that order or that way, but still hold much worth keeping. Quarry already has single-chapter experiments, retiring
to Salvage with harvest notes, the cuts bin, reading an entry's thread with retired chapters included, drag
reordering and chapters that are only a summary. This part adds experiments across several chapters, and makes
sure that retiring a chapter never quietly changes what the bible says.

#### 13.6.1 Experiments across several chapters

- **One experiment, several drafts.** An experiment (*New beginning*) holds any number of draft chapters, meant to
  replace a chosen **range** of current chapters (chapters 1–5, say). A single-chapter experiment, as today, is the
  case of one draft replacing one chapter.
- **Starting.** On the manuscript list, *Start an experiment…* on a chapter, or on a range picked with Shift-click,
  asks for a title and how to begin: *from scratch* (one empty draft) or *from copies* (a draft copied from each
  chapter in the range, each with a `start` revision, §11.5). Starting from the editor, as today, is a range of one.
  The range is a run of current chapters in one project.
- **Only adding.** A range can also be **none**, placed before or after a chapter: *Add chapters here…* before
  chapter 1 starts *New prologue*. Its drafts are written alongside in the same way; accepting inserts them at that
  place and retires nothing, so there is no review; harvesting or rejecting retires the drafts as for any
  experiment.
- **Writing alongside the book.** The drafts are written beside the current book without changing it: the current
  chapters stay current, in the book, the compiled manuscript and every count. The drafts are outside the story
  order, as experiments are today.
  - In the experiment, drafts are added (*New draft*, *Copy a chapter in*: any chapter, current or retired, including
    from Salvage), reordered by dragging, renamed, given summaries, statuses, times and marks, and removed (a removed
    draft is retired like any chapter, §13.6.2).
  - A draft is read as if it stood where its range stands: in the editor, *as of*, the cards and the companion treat it
    as being at the range's place in the book, and on the clock a draft with no time of its own carries on from the
    chapter before the range.
  - Hiding the replaced chapters while writing (*from scratch*, today's "the old chapter is hidden") hides the whole
    range in the editor's chapter switcher; they are still in the book.
- **On the manuscript list** the range gets a quiet bracket, and the experiment shows under its last chapter as the
  alternative to it: `↳ New beginning · replaces 1–5 (14.2k words) · 3 drafts (9.4k)`, opening to its drafts in order,
  each with its summary and status; one that only adds shows at its place: `↳ New prologue · adds 2 drafts before
  chapter 1`. *Read as if accepted* opens the book read-only with the drafts in place of the
  range (the reading of §11.4 takes the same switch).
- **Several experiments** may cover the same chapters. When one is accepted, any other whose range has lost
  chapters says so (`2 of its chapters were replaced by "New beginning"`) and can be given a new range.
- **Accepting** (from the experiment): the dependency review (§13.6.2) for the replaced chapters, with *move* set to
  the drafts where it can be; then the drafts become current chapters in their order, at the place of the range's
  first chapter still current; the replaced chapters are retired, and one prompt asks for harvest notes, one line per
  chapter, each skippable, as today. Chapters of the range retired or moved out of it since the experiment started
  are left where they are, and the accept says so.
- **Harvesting or rejecting** retires the drafts, after the dependency review for what was recorded in them (facts
  established while writing a draft, a telling recorded from one), and asks for a harvest note, as today.
- Closing an experiment closes its item, with the optional decision line, as today.

**Data:**

```sql
experiment_ranges  (item_id, chapter_id, position)    -- the current chapters an experiment would replace, in order
items              + insert_at_chapter_id NULL, insert_side text NULL   -- an experiment that only adds:
                                                       -- 'before' or 'after' that chapter (ON DELETE SET NULL)
chapters           - replaces_id                       -- moved into experiment_ranges by the migration
                   -- a draft's position is its place among its experiment's drafts
```

The migration turns each existing experiment's `replaces_id` into a range of one. **Export** writes the experiment
item's `replaces:` (a list of chapter ids) or `insert:` (`before:` or `after:` a chapter id) and each draft's `item:`
and `position:`; **Restore** reads them back, and a
draft in an older export with `replaces: <id>` gives its experiment a range of that one chapter.

*Done when* an experiment *New beginning* for chapters 1–5 starts from copies, gets a sixth draft and a new order,
shows on the manuscript list as the alternative to 1–5 while the book, its word count and `manuscript.md` are
unchanged; *Read as if accepted* shows the drafts in place of 1–5; accepting it puts the six drafts at the start of
the book and the five old chapters in Salvage, after the review and the harvest-note prompt; *New prologue*, adding
two drafts before chapter 1, accepts with no review and leaves every chapter current; and an existing single-chapter
experiment still accepts as before.

#### 13.6.2 A review before anything is retired

Whenever chapters leave the book (retiring one, retiring several at once from the manuscript list, accepting an
experiment, or retiring its drafts), Quarry first lists everything tied to them, and nothing is changed until it has
been seen.

- **What is tied** to a chapter, grouped:
  - facts and relationships *from* or *until* it, or *established in* it, with their evidence passages;
  - "is at" records in it;
  - events that happen in it (§13.2.1) and tellings recorded from it (§13.2.3);
  - items linked to it;
  - the note for next time left in it.

  With nothing tied, there is no review and the chapter retires as today.
- **The choices**, per row or for a whole group at once, each row showing only those that apply:
  - **Keep**: the default for every row. A *from* or *until* bound becomes the chapter's set time (§13.1.3: its own,
    or the one it carries on; the row says which, `from year 312`); if it has none, that bound goes and the row holds
    throughout on that side (the row says so: `will hold from the start`). When other chapters of the book share that
    set time, the bound would take them in too, so the row says so (`chapters 1–13 are all set in year 312`) and
    starts on *move* instead. For example: Isolde *lives in* Old Harbour *from chapter 3*; chapter 3 is retired and
    has no time; *keep* makes it hold from the beginning of the story. An event in the chapter takes its time, or
    becomes *not placed yet*. Evidence, tellings, item links, "is at" and the note stay pointing at the chapter, which
    is still there, in Salvage.
  - **Move to another chapter**: pick one; the bound, evidence or link points at it instead. The pick is set for you
    where there is a likely one: when accepting an experiment, the draft where the row's passage is found (by its
    text), else the first draft for a *from* and the last for an *until*; otherwise the chapter after the retired one
    for a *from* and the one before it for an *until*, so "dead from chapter 9" moves to chapter 10 in one click.
  - **Mark as planned** (facts and relationships): kept as *keep* would, with the standing set to *planned*: true in
    your head, not on the page any more.
  - **Drop**: the fact, relationship, "is at", item link or telling is removed; an event that happened in the chapter
    is kept, unplaced.
- **One step back.** The review is applied in one transaction with the retirement, and the toast offers **Undo**
  (as find and replace does, §11.7): it puts back each row that hasn't changed since, and the chapters. Later, the
  retired chapter's page in Salvage shows what its review did (`14 kept, 3 moved, 1 dropped`), and **Reinstate**
  offers to put those rows back as they were.
- **Offline**, retiring needs the network, as it does today.
- **This replaces** the rule that a span bounded by a retired chapter simply ignores that bound (DECISIONS,
  2026-10-22). After the review nothing is bounded by a retired chapter. Spans bounded by an experiment's draft are
  still ignored while the experiment is open (the draft isn't in the book yet), and are reviewed when it closes.
- **Existing data.** Nothing is changed by the migration. Bounds that already point at retired chapters keep being
  read as today (the bound is ignored) until they are reviewed: each such chapter's page in Salvage shows `Still
  tied: 4 facts, 1 relationship · Review…`, which opens the same review, and the Archivist lists the evidence
  (§13.6.3).

**Data:**

```sql
retire_reviews  (id, world_id, chapter_ids uuid[], changes jsonb,      -- each row changed or dropped, as it was
                 created_by, created_at)                                -- for Undo and Reinstate
```

`GET /chapters/ties?ids=…` lists what is tied; retiring and closing an experiment take the review's choices. Reviews
are bookkeeping, like resolutions, and are not exported (an export never has a bound into a retired chapter that
hasn't been through one, or the old rule reads it as before).

*Done when* retiring chapter 9 lists Seyla's *status: dead from chapter 9*, Varren's *married until chapter 9*, two
"is at" records and an item linked to it; with chapter 9 the only chapter set in year 312, *keep* turns the first
into `from year 312` and her page still shows her alive in chapter 8 and dead in chapter 10, while with chapters 1–13
all set in year 312 the row warns and starts on *move*; *move* on the second preselects chapter 8; *drop* on one "is at"
removes it; nothing else changes; Undo puts everything back with the chapter; retiring three chapters at once gives
one review for all three; and a chapter retired before phase 12 shows `Still tied…` in Salvage until reviewed.

#### 13.6.3 Evidence in Salvage

- An **Archivist** finding for evidence that points into a retired chapter: a fact's or a relationship's *established
  in* and passage, or a telling. `Seyla: "status: dead" rests on a passage in a retired chapter, *The Storm*.`
- **Resolved** by:
  - **Re-anchor…**: pick a chapter; current chapters where the passage's text is found are offered first (a copy in a
    new draft is found this way). The evidence then points there.
  - **Dismiss**: stored as a resolution (`intentional`), never shown again for that row. The evidence stays as it is,
    readable in Salvage.
- Like every finding it is silent while Drafting. It shows in the editor for the entries named in the chapter, on the
  entry page, and on the retired chapter's page in Salvage. It is the same check for evidence kept by a review and for
  evidence left from before phase 12.

**Data:** none; the rule `evidence_retired`, keyed by the fact, relationship or telling, uses the existing
`resolutions` table.

*Done when* a fact whose evidence is in a retired chapter is listed by the Archivist (while Revising) on its entry's
page; *Re-anchor…* offers the draft where the passage now is and moves the evidence there; and *Dismiss* keeps it out
for good.

### 13.7 The chart

A schematic map of the world's places: not their shapes on the ground, but how they relate. Which land holds which
cities, which lands border which, which sea surrounds an island, which roads join them. It is drawn from what is
already recorded (the place tree's *inside*, *borders*, *road to*, *sea route to*, a place's *type*) plus four
direction types, and it is a view of places in its own right, beside the graph and the place tree. It doesn't need
the Timeline.

Examples use made-up names: the Iron Vale is a land holding Old Harbour and Greywick; Old Harbour holds the Quay
district and the Lamp House; the Grey Sea surrounds the Isle of Wrens; the Iron Vale borders the Salt Marches.

#### 13.7.1 What is drawn

- **Where.** Its own page, `/w/<world>/chart`, in the nav after *Graph*. A place's page gets *On the chart*, which
  opens it centred and zoomed on that place.
- **Containment is nesting.** A place *inside* another (read as the place tree reads it: `inside`, `in`, `part of`,
  `within`, or the reverse `contains`) is drawn inside its shape: lands enclose regions and cities, cities enclose
  districts and buildings, buildings enclose rooms. A place inside two others is drawn in the first recorded, as the
  place tree does, and its card names the other.
- **Borders touch.** Two places recorded as *borders* that sit in the same container are drawn sharing an edge. Across
  containers, their containers are pulled together and a short thick mark joins the two at the nearest edges.
- **Water surrounds.** A water place (§13.7.2) that contains land places is drawn as a water shape around them: the
  Grey Sea around the Isle of Wrens. A land that *borders* a sea touches it; a river is a ribbon running between or
  through the places it borders or is inside.
- **Routes are lines.** *Road to* is a solid line between two places, *sea route to* a dashed one, drawn above the
  shapes and routed around them where they can be.
- **Directions.** New starting types, place – place: *north of* / *south of* and *east of* / *west of* (each pair
  is one type and its reverse). North is up. The layout honours them where it can (§13.7.3); one it can't honour (a
  place both north and south of another) is drawn anyway and listed under the chart as `Couldn't place: …`.
- **Who and what.** Each shape has its name, coloured as a place. Places named often are a little larger, in the
  three steps of the mentions strip (§12.1); a container is as large as what is inside it.
- **Planes** (type *plane*) and everything inside them are laid out apart, each as its own island off to the side
  of the world, with its name above it.

#### 13.7.2 Shapes from the type

A place's shape comes from its *type* fact (§12.6; starting values in §13.5), whatever the capitals, as it holds at
the end of the story (or as of the chosen point, §13.7.4).

| Type | Shape |
|---|---|
| world | the outermost hexagon, framing everything not in a plane |
| land, region (and realm, kingdom, country, province) | hexagon |
| city, town, village (and port, fort, hamlet) | circle |
| district | rounded square |
| building, room | square, sharp corners |
| sea, lake (and ocean, bay) | soft blob, in a water tint |
| river | ribbon, in a water tint |
| island | soft blob, in a land tint |
| mountain | triangle |
| forest | scalloped circle |
| reef | dotted blob |
| plane | an island apart (§13.7.1) |
| no type, or one not listed | rounded rectangle when it contains places, small rounded square when it doesn't, drawn lighter; its card says `no type` |

- The list (with its synonyms) is in the code, like the starting values. A world can map its own type values to a
  shape in the chart's settings (`duchy` → hexagon), kept per world.
- A place with several types (§12.6.4) takes the first that maps to a shape.

#### 13.7.3 Layout: automatic first, then shaped by hand

- **Automatic.** Laid out from the inside out: each container's contents are packed inside it, with forces that make
  bordering places touch, keep directions (*north of* above), pull places joined by a road closer, and stop shapes
  overlapping; the container's size then follows from what it holds. It is laid out to rest before drawing, as the
  graph is (d3-force, plain SVG, no graph library; DECISIONS, 2026-10-22), and seeded, so the same data gives the same
  chart.
- **Pinning.** Dragging a place moves it and **pins** it there. A pin is kept relative to its container, so moving a
  container moves everything inside it. Pinned places stay put when the layout runs again; the rest settle around
  them.
  - **A place added** (or newly given a container) is laid out among the pinned ones, where there is room; a
    container grows to fit, and its pins keep their places relative to it.
  - **A place that moves to another container** keeps its pin for the old one (a pin belongs to a place in a
    container) and is laid out fresh in the new one until it is pinned there. So a town that changes hands as of a
    chapter (§13.7.4) sits where it was pinned in each.
  - **A place removed** from the bible, or whose container is gone, loses its pins.
  - **Reset layout** unpins everything, or everything inside one container (*Reset inside the Iron Vale*), with Undo.
- Pins are the only thing stored: shapes, sizes and everything unpinned are worked out when drawn.

#### 13.7.4 As of, and moving around

- **As of** is an optional control on the chart, sharing the selector of §13.1.6 (a chapter, or from phase 12a a
  time). With nothing chosen the chart shows the latest state: the end of the story, as the bible's tables read
  facts. With a point chosen it shows, as of then:
  - containment, borders, directions and routes as they held (relationships with *from* and *until*);
  - **who controls** each place, from the *controls* relationships (faction – place), as a shade in the faction's
    colour with a legend (factions take colours from a fixed set, in order of how much they control); a place
    controlled by two is striped;
  - **who is there**: characters recorded "is at" the place in that chapter, else those who *live in* it then, as
    small dots on its shape, named on hover.
- **Zoom and pan** as on the Timeline (§13.2.6). **Semantic zoom**: zoomed out, a container shows its name and how
  many places it holds (`Iron Vale · 14 places`); zooming in reveals its contents and their names, level by level.
  **Names** are drawn above every shape and line and never cross an outline, a route, a border mark, someone's dot or
  another name: a container's inside along its top where its outline leaves room, any other place's below it, else
  above, to the right or to the left, inside its container. Where nothing holds the whole name it is shortened, and
  where nothing at all is clear it is left to the place's card rather than drawn over another name. A place with
  nothing inside keeps a line's room between it and its container's outline for its name.
- **Hover cards** use the same component as the editor's (WORLD-MODEL.md §5): the one-liner, facts as of the chosen
  point, the closest relationships. **Click** opens the place.
- **Filters**, kept in the address: by type (show or hide each), by depth (*down to*: lands · settlements · buildings
  · rooms), and the standing switches of the graph (planned and rumoured relationships dashed or hidden).
- **On the phone**, pinch and drag; dragging a place to pin it takes a long-press first, so panning doesn't pin.
- **Smooth** at a few hundred places: the same budget as the graph's.
- **From the Timeline**: brushing a span there drives the chart's *as of* (§13.7.5).
- **Not a drawn map.** The chart doesn't replace an uploaded map image with pinned places, which stays on the later
  list (WORLD-MODEL.md §6; §21).

**Data:**

```sql
chart_pins  (world_id, place_id, container_id NULL,     -- NULL: at the top level
             x real, y real,                             -- relative to the container
             updated_by, updated_at)                     -- unique (place_id, container_id); ON DELETE CASCADE
worlds      + chart jsonb default '{}'                   -- the chart's settings: shapes for the world's own types
relation_types + north of / south of, east of / west of   -- place – place; every existing world, by migration
```

`GET /chart` returns the pins and settings; the chart is drawn in the browser from them, the cards (types, mentions)
and `GET /graph`. `PUT /chart/pins/<place>` (with its container) and `DELETE /chart/pins` (all, or a container's,
answering with them for Undo). **Export** writes `chart:` into `world.md` (the settings, and each pin with its place
and container ids); **Restore** reads it back and relinks the places by id; an older export has none, so its chart
starts laid out automatically.

*Done when*, with no *as of* chosen, the chart shows the Iron Vale as a hexagon holding Old Harbour and Greywick as
circles, Old Harbour holding the Quay as a rounded square and the Lamp House as a square, the Grey Sea as a blob
around the Isle of Wrens, the Iron Vale sharing an edge with the Salt Marches, a road as a solid line and a sea route
as a dashed one, and Greywick above Old Harbour when it is recorded *north of* it; a place with no type is a lighter
rounded square; dragging Greywick pins it, and it stays there after the page is reloaded and after a new town is
added to the Iron Vale; *Reset inside the Iron Vale* unpins it, and Undo pins it again; choosing *as of* chapter 4
shades the places the Lamp Guild controls then and shows Varren's dot where he is recorded; zooming out folds Old
Harbour to `Old Harbour · 2 places`; and exporting and restoring the world keeps the pins.

#### 13.7.5 From the Timeline

Part of 12d, built on the Timeline of 12b. Nothing else on the chart depends on it: the chart works the same without
a span brushed, and using it is up to the writer.

- **Side by side.** On the Timeline, *Chart* opens the chart in a panel beside the lanes (under them on the phone),
  and the chart page has *Follow the Timeline* when opened from there. Either way, the chart follows the Timeline's
  brushed span.
- **A span drives *as of*.** With a span brushed (§13.2.6), the chart shows the state at the span's end, and marks
  what **changed across the span**: places whose controlling faction, container or borders were different at its
  start are outlined, and a list under the chart says what changed and when, in happened order:
  `Greywick · controlled by the Lamp Guild → the River Wardens · year 300` ·
  `the Salt Marches · no longer borders the Iron Vale · chapter 12`.
- **Stepping through.** A scrubber over the span stops at each change; moving it moves *as of* to that point, and the
  chart eases between the states (shading fades, a place that changes container glides to its pin in the new one,
  §13.7.3), so a border or a hold changing hands can be watched. Arrow keys step from change to change.
- **Clearing** the span on the Timeline leaves the chart at the latest state, or at its own *as of* if one was set.
- Changes are read from the same relationships as *as of*: *controls*, the place tree's *inside* types and
  *borders*, with their *from* and *until* on the clock (§13.1). Nothing is stored.

*Done when*, with the Lamp Guild controlling Greywick until year 300 and the River Wardens from then, and the Salt
Marches bordering the Iron Vale until chapter 12: brushing years 290–312 on the Timeline (chart panel open) shows the
chart as of year 312 with Greywick in the Wardens' shade and outlined, and lists both changes with their times;
moving the scrubber to before year 300 shows Greywick in the Guild's shade and the two lands touching; clearing the
span returns the chart to the end of the story; and with no span brushed, every part of the chart's own *done when*
(§13.7.4) holds as before.

### 13.8 Data model, in one place

```sql
worlds          + time_unit, time_units                                   -- §13.1; 'year' / 'years'
chapters        + time_at, time_end, time_label, time_approx, told_as     -- §13.1; told_as: flashback | tale
chapters, entities, facts, relationships + outside_time bool              -- §13.1.8
facts           + from_time, from_approx, until_time, until_approx        -- §13.1; a bound is a chapter or a time
relationships   + from_time, from_approx, until_time, until_approx        -- §13.1
relationships   + role NULL                                               -- §13.4
relation_types  + has_role bool                                           -- §13.4
roles           (id, world_id, role, one_at_a_time)                       -- §13.4; only roles with the switch set
entities        + time_at, time_end, time_label, time_approx, time_chapter_id   -- §13.2; events
entities        + era_colour NULL                                         -- §13.2.1; eras, one of eight
entities.kind   + 'species'                                               -- §13.3
tellings        (id, world_id, event_id, chapter_id NULL, passage, created_by, created_at)   -- §13.2
relation_types  + species types, possesses, ancestor of                   -- §13.3, §13.5; every existing world
experiment_ranges (item_id, chapter_id, position)                         -- §13.6.1; replaces chapters.replaces_id
items           + insert_at_chapter_id, insert_side                       -- §13.6.1; experiments that only add
retire_reviews  (id, world_id, chapter_ids, changes, created_by, created_at)   -- §13.6.2; for Undo and Reinstate
chart_pins      (world_id, place_id, container_id NULL, x, y, updated_by, updated_at)   -- §13.7; relative to the container
worlds          + chart jsonb                                             -- §13.7; the chart's settings
relation_types  + north of / south of, east of / west of                  -- §13.7; every existing world
```

Endpoints: `GET /timeline` gains each chapter's time, mark, set time and clock place (§13.1); `GET /chronology`
(§13.2); `POST /events/record` (§13.2); `PATCH /chapters/<id>` takes the time and mark; facts and relationships take
time bounds; relationships take `role`; `/labels` gains roles (§13.4); experiments take a range and drafts; `GET
/chapters/ties` lists what is tied to chapters, and retiring and closing an experiment take the review's choices
(§13.6); `GET /chart` and its pins (§13.7). Happened order, set times, history, ages, lanes, species beside a name, kin across an ancestor link and the
ties of a chapter, a time's era, the Timeline's clusters and the chart's shapes and unpinned layout are worked out
when read, never stored.

**Phase 12 is done when** each part's *done when* above holds, and the demo world (The Ninefold Delta) shows it:
its chapters set in years (the book in year 412, Ash Season a year on), a short tale chapter set forty years before,
in which a character recorded dead in the present appears without a finding; a few events of history, one of them
recorded from a passage with its telling, two eras in their colours (one nested in the other) and a prophecy
outside time; births for some of the family, so ages show; species (human,
dog, and one made up for the delta) with an *is a*, an *appears as* and a *native to*; the Warden-Captain as a role
on the River Wardens marked one at a time, with one clash planted; an ancestor link in the family; an experiment
across two chapters of Ash Season; a retired chapter with a fact still tied to it and an evidence passage in it; and places typed, bordering and
directed enough for a chart with a land, its towns, a sea around an island and one road.

### 13.9 Four phases

Phase 12 is built as four phases, **in this order**, by one build session, one after another, as **stacked pull
requests**: 12c's off master, 12a's off 12c's branch, 12b's off 12a's, 12d's off 12b's.

1. **12c, species, roles and vocabulary** (§13.3–§13.5): one kind, one field with a switch, one small table, a
   migration of types and starting values. Small, and it needs nothing from the others.
2. **12a, time and restructuring** (§13.1, §13.6): the clock, chapter times and marks, outside time, time bounds, the
   checks on the clock, experiments across several chapters (and ones that only add), the review before retiring,
   and evidence in Salvage. This is what a new beginning needs before it is written: times to anchor facts to, and a
   review so that retiring the old chapters changes nothing quietly. It also fixes the tale chapters' findings.
3. **12b, history and the timeline** (§13.2): event times, eras and their colours, the Timeline page and its design,
   History, *Record as event*, *Set born/died here*, ages and the age check, and an entry's own timeline. It builds
   on 12a's clock.
4. **12d, the chart** (§13.7): the shapes, nesting, borders, water, routes and directions, the layout and pins, and
   *as of* on the chart. It needs 12c's place types (the starting values) and nothing from 12a or 12b: *as of* takes
   chapters until 12a adds times. Its link from the Timeline (§13.7.5) is part of 12d and needs 12b, which is in place
   by then. The rest of the chart needs only 12c, and could have followed it directly; the order above stands.

What a part needs from a later one waits quietly: until 12a the role check compares in book order; until 12b an
ancestor link says `generations not recorded` (no birth times are worked out yet), the review has no events or
tellings to list, and the Archivist no tellings. Each phase updates the demo world with its own parts, and each
pull request lists what it leaves for the next.

### 13.10 Open questions for phase 12

None left. Thomas's answers are in DECISIONS.md (2026-10-25): the kind is called Species; a tale or flashback with no
time is set before the story; *outside time* is a third kind of time; eras stay events, with a colour that tints every
time shown; one at a time per role across the world; a computed age that disagrees with an *age* fact is a finding;
*keep* without a time holds throughout; an experiment may only add; and the build order is 12c, 12a, 12b, then the
chart as 12d.

## 14. Planning before writing (phase 13)

Phases 6–12 made the world model work from the prose: names light up in chapters, facts and events are recorded
from passages, the checks read what the chapters say, and getting back in is per chapter. A world can also live
mostly in planning: years of dated notes, decisions and questions, worked out long before (or instead of) the
chapters. Then the knowledge sits in the Journal, which today is a plain text box that the world tools never see.
Phase 13 makes the planning a first-class place to work: the **editor's world tools in the Journal**, with what was
**planned in the Journal** kept beside what is **canon in the book**; a way to **read an entry's thread through the
planning**; **turning a passage into a spark or question**; a **front page** for getting back into a world after a
long gap; **"since this was written"** on old notes; **"Include planned"** on the Continuity checks; **cause arrows**
on the Timeline; **entries of more than one kind** (a world that is a place and acts); and a **focus** per world,
*Writing* or *Planning*, that decides what is up front.

The approach is *dump freely, then sweep*: write in the Journal as before, and classify afterwards with the same
gestures as in a chapter (the quick-fix strip, F8, recording from a selection). There are no questionnaires and no
prompts to fill in. The principles hold: nothing here writes or suggests story content; nothing has to be filled in
(the new fields, a premise and more kinds for an entry, are optional); everything else is worked out from links Quarry already keeps; and the
compiled manuscript stays pure prose. **Planning isn't story order**: a journal entry's date is never a place on the
clock or in the book, so nothing here changes what the Continuity checks, the mentions strip, first appearance or
the told order read. The one part that widens the checks, *Include planned* (§14.6), is a switch that starts off.

**Built after phase 12 is merged.** It is specced against §13, not against phase 12's code: *Record as event*,
tellings and the Timeline come from 12b, time bounds and *as of a time* from 12a.

Examples use made-up names. The Journal of the world has an entry dated 2 March 2019, *What the Guild wants*, that
names Varren, Isolde and the Lamp Guild; the book has only a few chapters so far.

### 14.1 The world tools in the Journal

#### 14.1.1 Journal entries in the editor

- **The list and the entry.** `/w/<world>/journal` stays the chronological list with search and the project filter.
  Each entry shows its date, title, project and its first lines with names coloured (as the inbox shows items), and
  the quiet count of §14.5. **New entry** makes an entry dated today and opens it. Opening an entry opens it in the
  editor at `/w/<world>/journal/<id>`, the way a chapter opens. The form with a text box goes.
- **The head** has the title and the date, edited in place, and the project (or *Whole world*). Changing the date
  moves the entry in the list; it is a label, saved without the version check, as a chapter's summary is.
- **Saving, as for chapters** (§4): autosave after about 1.5 s, revisions on the same rules, **Checkpoint** (Ctrl+S)
  with a label, **History** with word diffs and restore, conflict copies when another device saved first. Today a
  journal entry is saved only with a Save button and has no history.
- **Offline.** The offline copy carries journal entries as it carries chapters, each with its last 30 revisions, so
  the Journal opens, reads and edits on the phone with no network. Typed text is kept on the device until the server
  has it. A new entry made offline gets an id chosen on the device and waits in the outbox, as captures do.
- **What comes along** from the chapter editor, unchanged: names coloured by kind, cards on hover or long-press,
  likely misspellings and possible new names, the quick-fix strip, Alt+Enter, the **F8** sweep, the selection strip,
  **Drafting/Revising** (Drafting the default, as for chapters), focus mode, typewriter scrolling, search in the
  entry (Ctrl+F), the word count, and *stash a thought* (Ctrl+Shift+S), whose spark is tied to the entry.
- **What stays with chapters**: POV, summary, status, *set in* and *told as*, "is at" and *Moved…*, *Cut to bin*,
  find and replace across chapters, changes since a checkpoint, experiments and retiring, margin notes (a `%%` line in
  the Journal is ordinary text: the whole entry is a note to yourself; only a choice line for a shared name, §14.10,
  is read there), and word history (it counts the book).
- **The side panel** has the names in the entry (the cast, below), the items linked to it, History, the note for next
  time (§14.4) and *Since this was written* (§14.5).
- **The companion's tabs** in a journal entry:
  - **Proofreader**, as in a chapter.
  - **Connections**: unrecorded connections by strength, as in a chapter. *Record how* records the relationship as
    *planned*, planned in this entry (§14.1.2). No *Where are they?*: "is at" is per
    chapter.
  - **Archivist**: possible new names, entries without a one-liner, other names worth adding. A new entry made from a
    journal entry starts in its project's bible when it has a project and the world has several (§12.4), otherwise in
    the world's.
  - **Loose ends**: TK and `??` markers in the entry (§14.3.2), open items linked to it, the note for next time.
  - No **Continuity** tab: the checks are about chapters on the clock, and a journal entry has no place there.
- **Cards and the cast.** A journal entry has no chapter, so its cards read as of **the end of the story**, as the
  bible's tables do. The side panel has the *as of* selector of §13.1.6 (a chapter or a time) for planning about a
  particular point; the choice is kept per entry on the device. Cards in the Journal also show **planned** facts and
  relationships, marked `planned`, since in planning they are often all there is; a chapter's cards keep showing
  canon only. The cards on the device carry planned rows for this.
- **Performance.** The typing budget is the chapter's (DECISIONS, 2026-10-22): a 10,000-word entry with 400 entries
  in the bible, also at 4× slower CPU.

**Data:**

```sql
revisions      doc_table + 'journal'               -- the CHECK widens; REVISION_DOCS gains journal
```

Journal entries go through the same saver as chapters (`PATCH /journal/<id>` with `base_version`, a draft on the
device, snapshots), and `GET /offline` gains the journal entries changed since the given time, with their revisions
and the ids of every entry that still exists. Existing entries get their first revision the first time they are
saved after the upgrade.

*Done when* opening *What the Guild wants* shows it in the editor with Varren, Isolde and the Lamp Guild coloured by
kind; F8 steps through its possible new names and `+ Faction` adds one to the world's bible; it autosaves, has a
History with a checkpoint that can be restored, and opens and takes typing on the phone in airplane mode; Varren's
card shows a planned fact marked `planned`; and the Continuity tab isn't there.

#### 14.1.2 Planned in the Journal, canon in the book

Evidence and *established in* point at a chapter today: where something is on the page. From phase 13 a fact or
relationship can also say where it was **planned**: a journal entry and the passage it was worked out in. The two are
separate, and a fact can have both: planned in the Journal in 2019, established in chapter 9 once it was written.

- **The rule for standing** (Thomas): something is **planned** until it is in the book or is explicitly marked canon.
  - Recorded **from a chapter** (*Record a fact*, *Link to…*, *Record how*, *Record as event*, *Set born/died here*):
    *canon*, as today.
  - Recorded **anywhere else** (from a journal entry, on an entry page, in the companion outside a chapter): it starts
    as *planned*, with one click to *canon* in the form. On an entry page this changes today's default, which is
    canon. Rows that exist already keep their standing.
  - Marking it canon by hand is the standing pill, as today.
- **Record a fact** (new, in chapters and journal entries alike; WORLD-MODEL.md §2 describes it, and it was never
  built). Selecting a passage offers *Record a fact* in the selection strip, on the desk and the phone. The strip grows
  into a small form in place, as *Record as event* does (§13.2.3):
  1. **The entry**: a chip for each entry named in the selection (the first one chosen), or *Other…*.
  2. **Label and value**, with the label and value suggestions of §12.6.
  3. **When it holds**: the span picker of §13.1.5 (chapters and times). In a chapter it starts on *from this
     chapter*; in a journal entry it starts empty (holds throughout).
  4. **Standing**, by the rule above.
  5. **Save** (Enter). From a chapter, the fact is *established in* the chapter with the passage as its evidence;
     from a journal entry, it is *planned in* the entry with the passage. A toast says
     `Recorded "status: dead" on Seyla · Open · Undo`.

  The strip opens only for a selection, never while typing. It appears for any selection a passage action can use,
  as 12b's *Record as event* needs; for a selection longer than a name it offers only the passage actions (*Record a
  fact*, *Record as event*, *Spark*, *Question* and, in a chapter, *Cut to bin*).
- **Make it canon here.** In a chapter, when what is being recorded is already there as *planned* (a fact with the
  same label on the entry; a relationship of the same type between the same two; an event's planned participant),
  the form says so and offers that instead of a second row:
  `Planned: status dead (Journal, 2 March 2019) · Make it canon here`. It sets the standing to *canon*, the chapter
  as *established in* with the passage as evidence, and the span the form chose; where it was planned stays. *Record
  a new one* is still there, for when the plan changed.
- **Link to…** from a card in a journal entry records the relationship as *planned in* the entry, as *Record how*
  does.
- **Record as event** (§13.2.3) from a journal passage works as from a chapter, except that:
  - the participants are recorded as *planned*, planned in the journal entry;
  - the passage is kept as a **note** on the event, not a telling: the event's page lists it under *Noted in*, apart
    from *Told in*, each with its date and entry, linking into the Journal at the passage;
  - *When* offers a time, a chapter, or outside time; there is no "this chapter's time".
  *Set born here · died here* is not offered in the Journal: there is no "here". A *born* fact with a time does it.
- **How *planned in* is read.** It is a pointer back to where something was thought out, never a place in the story:
  - it bounds nothing, as *established in* bounds nothing; *from* and *until* stay a chapter or a time;
  - the Continuity checks read only chapters' names, so nothing named in the Journal is ever "named after being
    recorded dead" or "named before being born"; a note on an event is not a telling, so it doesn't hide names from
    that check either;
  - the Timeline's **told** view lists only tellings in chapters: an event noted only in the Journal is under *Not in
    the book yet*, and its card says `noted in the Journal 3 times`;
  - the review before retiring (§13.6.2) and evidence in Salvage (§13.6.3) are about chapters and never list it;
  - the entry page shows it beside the fact as `planned in the Journal, 2 March 2019 · What the Guild wants`, after
    the chapter's evidence when there is one, linking into the entry at the passage (found by its text; if it can't
    be found, the entry opens at the top and the line is marked `passage changed`).
- **Deleting a journal entry** that something was planned in says so first: `2 facts, 1 relationship and 1 event note
  were planned in this entry. They keep their passage, without the entry.` The link is then cleared; the passage text
  stays.
- **Export** writes `planned_in:` (the journal entry's id) and `planned_evidence:` beside `established_in:` and
  `evidence:` for a fact or relationship, and an event's notes as `notes:` (journal id and passage) beside
  `tellings:`. Journal files already carry their `id`. **Restore** relinks them by id; it keeps a map from the
  export's journal ids to the new rows, as it does for chapters (today it doesn't, since nothing points at a journal
  entry). An older export has none of this.

**Data:**

```sql
facts          + planned_in_journal_id NULL, planned_evidence text NULL    -- ON DELETE SET NULL
relationships  + planned_in_journal_id NULL, planned_evidence text NULL    -- ON DELETE SET NULL
tellings       + journal_id NULL                    -- §13.2; ON DELETE SET NULL; a note, not a telling
               -- CHECK (chapter_id IS NULL OR journal_id IS NULL)
```

A pair of columns beside the chapter's pair rather than a source table and id: each keeps its foreign key and `SET
NULL`, and a fact can have both. `POST /entities/<id>/facts` and the relationship endpoints take
`planned_in_journal_id` and `planned_evidence`, and `make_canon` (the planned row's id) for *Make it canon here*;
`POST /events/record` takes a journal entry in place of a chapter.

*Done when* selecting "the Guild has kept the Lamp lit for three hundred years" in *What the Guild wants* and
choosing *Record a fact* offers the Lamp Guild, saves *age: three hundred years* as *planned* with the passage, and
the guild's page shows `planned in the Journal, 2 March 2019 · What the Guild wants`, linking back to the passage; a
fact added on an entry page starts as *planned*; *Record as event* on a passage there makes *The Founding* with its
participants planned and the passage under *Noted in*, while the Timeline's told view lists it under *Not in the book
yet*; *Record a fact* in chapter 9 for Seyla's *status: dead*, planned in the Journal, offers *Make it canon here*,
after which the fact is canon, established in chapter 9 with that passage, and still shows where it was planned;
Checks gives no finding for a name in the Journal; and exporting and restoring the world keeps all of it.

### 14.2 Reading an entry's thread through the planning

What did the notes say about Varren over the years? §11.4 reads him through the book; this reads him through the
planning, **oldest first**.

- **Where.** The thread reading gets a switch at the top: **The book** (§11.4, as today) · **The planning**. An entry's
  page has *Read where Varren appears* and, beside it, *… in the planning*. `/w/<world>/bible/<id>/read?in=planning`.
- **What it reads**, each kind a chip at the top, all on to start:
  - **journal entries** that name him;
  - **items** (sparks, questions, tasks, experiments; open and closed) that name him or are tagged with him;
  - **decisions** that name him or are tagged with him.

  Naming is found by the same matcher as in the book (any of his names). An item or decision tagged with him but not
  naming him is shown with a small `tagged` mark.
- **In date order**, oldest first: a journal entry by its date, an item by when it was captured, a decision by its
  date; on the same day, journal entries, then items, then decisions. A heading marks each year, and between two
  sources more than a year apart a quiet `· 3 years ·` says so.
- **Two ways to read**, as in §11.4:
  - *Paragraphs* (the default): each journal paragraph that names him, under its entry's date and title, with
    `⋯ 6 paragraphs` between paragraphs that aren't next to each other. Items and decisions are short, so they are
    always shown whole: an item with its kind, status and closing note, a decision as its line.
  - *Entries*: every journal entry that names him, in full.
- A count at the top: `Varren in the planning: 48 paragraphs in 19 journal entries, 11 items, 6 decisions ·
  2014–2026`.
- **With…** works as in §11.4: only what names (or is tagged with) both.
- The **project filter** as on the Journal page: the whole world, or one project and the world's own planning.
- Names are coloured as in the editor and his own marked strongly. Each paragraph links into the journal entry at
  that place; each item opens the item; each decision its line on the Decisions page.
- **The book and the planning are never mixed** into one reading: a note's date isn't a place in the story.
- **Built on the device** from the offline journal (§14.1.1) and the matcher, like §11.4. Items and decisions are read
  online (`GET /planning?entity=<id>` returns those that name or are tagged with the entry, from the stored mentions
  and links); offline, the reading shows the journal entries and says `Items and decisions need the network`.

**Data:** none. A query parameter, and `GET /planning`.

*Done when* Varren's page opens a planning reading that lists, oldest first, a 2014 journal paragraph that names him,
a question captured in 2016 tagged with him, a decision of 2019 that names him and the 2019 entry *What the Guild
wants*, with a year heading over each and `· 2 years ·` between 2014 and 2016; *Entries* shows the journal entries
in full; *With…* Isolde leaves only what names both; and in airplane mode the journal part still shows.

### 14.3 From a passage to a spark or question

#### 14.3.1 Spark or question from a selection

Old planning holds ideas that aren't settled and may belong somewhere else; prose holds doubts noticed while
writing. Either becomes an item in one gesture, without leaving the text.

- **In the selection strip** of a chapter or a journal entry, on the desk and the phone: **Spark** · **Question**. The
  strip grows into a small form in place (Esc goes straight back to the text):
  1. **Kind**: spark, question or task, starting on the one chosen.
  2. **A line of your own**, optional: what the item is about, in your words. The item's text is that line followed
     by the passage as a quote; with no line typed, just the quote.
  3. **Entries**: a chip for each entry named in the passage, ticked, to tag the item with them.
  4. **Project**: the source's (the chapter's project, or the journal entry's project or none).
  5. **Park it**: a chip that saves the item as *deferred* instead of open, for an old idea to keep without it
     waiting in the inbox.
  6. **Save** (Enter). The toast says `Question saved · Open · Undo`.
- **The text stays where it is.** It is copied, never cut.
- **Linked back to the passage.** The item is linked to its chapter or journal entry, with the passage. In the inbox,
  Triage, on the Board and on the item: `From chapter 4, *The Quay*` or `From the Journal, 2 March 2019`, with the
  passage quoted and a link into the editor at the passage (found by its text, or the top of the text with `passage
  changed`).
- **In the editor**, the Loose ends tab lists the open items linked to the chapter or entry, each with its passage;
  resting on one marks the passage in the text. While Revising a small mark in the margin sits beside each passage
  with an open item.
- **Offline** it goes through the outbox like a capture, with its links and passage.
- **Keyboard**: Alt+Enter on a selection opens the strip with the keyboard in it, as for names.

#### 14.3.2 Loose ends in the Journal

- **`??` is a marker**, like TK: two or more question marks that don't follow a letter (`Varren's age ?? maybe 40`,
  `(??)`, a line that is just `???`), so a question in dialogue (`What??`) is not one. It is a marker in chapters too.
- **In an entry's Loose ends tab** (§14.1.1): each TK and `??` line, with **Make a question**, which opens the form of
  §14.3.1 with that line as the passage.
- **On the Journal page**, a *Loose ends* tab lists every entry with TK or `??` markers, oldest entry first, each
  marker line quoted with a link into the entry at it: `31 markers in 14 entries`. Worked out on the device from the
  offline journal.

**Data:**

```sql
item_links  target_table + 'journal'               -- the CHECK widens: entity, chapter, journal
            + passage text NULL                    -- for a chapter or journal link: the passage it came from
```

`POST /items` takes `chapter_id` or `journal_id` with a `passage`. **Export** writes an item's links to chapters and
journal entries into its frontmatter (`from:` a chapter or journal id, with `passage:`); **Restore** relinks them by
id.

*Done when* selecting a sentence in *What the Guild wants* and choosing *Question* saves an open question tagged with
the Lamp Guild, showing `From the Journal, 2 March 2019` with the passage, and its link opens the entry at the
sentence; *Park it* saves a spark as deferred; the same in a chapter links the item to the chapter and lists it in
the editor's Loose ends; a `??` in a journal entry shows in its Loose ends tab and on the Journal page's *Loose ends*,
and *Make a question* turns it into a question linked to that line; and `What??` in dialogue is not listed.

### 14.4 A front page for the world

The world page, `/w/<world>`, becomes the place to get back in after weeks or years away: a premise, and what has
been happening, worked out for you.

- **The premise.** One optional line under the world's name, edited in place, up to 300 characters: what this world
  is about, in your words. Empty, the page shows only a faint *Add a premise*.
- **Where you left off.** The latest note for next time (from a chapter or a journal entry), with where and when:
  `"Isolde has to find out before the flood" — chapter 4, The Quay · 3 weeks ago · Continue`. *Continue* opens it at
  the place where you stopped. Older notes fold under it (`2 more`).
- **The note for next time in the Journal.** Leaving a journal entry after writing 30 or more words asks once,
  skippably, for a note for next time, as leaving a chapter does (DECISIONS, 2026-10-22), with the same setting. It
  shows when the entry opens again and in the entry's Loose ends tab, and is per user and not exported, as for
  chapters.
- **Lately.** What changed recently, newest first, grouped by day: the last ten days on which anything happened,
  however long ago. Each day says how long ago it was (`14 March 2023 · three years ago`), so a long gap is plain
  without being judged.
  - Per day: words written per project (from word history, §11.5), journal entries written or changed, bible entries
    added or changed, facts and relationships recorded, items captured and closed, and decisions; each line a link.
    `14 March 2023 · 1,240 words in The Salt Road · 2 journal entries · Varren, Old Harbour changed · 3 facts recorded
    · 1 question captured`.
  - Worked out from revisions and from when rows were created or last changed. It is a rough picture: a row changed
    twice counts once, on the later day, and nothing removed is seen (nothing is logged).
- **Latest decisions**: the last five, dated, with their project, and a link to Decisions.
- **Open questions**: the open question items, newest first (five, then `12 open questions · oldest from 2015`), and
  the count of `??` markers in the Journal (§14.3.2), linking to its *Loose ends*.
- **Projects**, as today, each with its word count and when it was last written in.
- **Every section** hides while it would be empty, so a new world shows its name, *Add a premise* and its projects.
- **What moves where.** Today the page holds the projects with their order, a New project form, Rename, Export and
  Delete.
  - **Stay** on the front page: the projects list with its up and down arrows, and **Export** in the head.
  - **New project** becomes a button beside *Projects* that opens the form in place.
  - **Rename** (name and address), the world's **time unit** (§13.1.1, from 12a) and **Delete this world…** move to
    a new **World settings** page, `/w/<world>/settings`, linked from the head.
- **Getting there.** The world's name in the nav always leads to the front page, and a world whose focus is
  *Planning* opens on it (§14.9).
- **On the phone** the sections stack in the order above.
- **Export** writes `premise:` into `world.md`; **Restore** reads it back.

**Data:**

```sql
worlds         + premise text NULL                 -- up to 300 characters
session_notes  + journal_id NULL                   -- ON DELETE CASCADE; chapter_id becomes NULL-able
               -- CHECK exactly one of chapter_id, journal_id; unique per (chapter, user) and per (journal entry, user)
```

`GET /worlds/<slug>/front` returns the latest notes, *Lately*, the latest decisions and the open questions; the `??`
count is worked out on the device. `PATCH /worlds/<slug>` takes `premise`. `GET`/`PUT /journal/<id>/session-note` as
for chapters.

*Done when* the demo world's page shows a premise edited in place, the latest note for next time with *Continue*,
*Lately* with the days on which words, journal entries, facts and items were added (each dated and with how long ago),
the last decisions and the open questions with the `??` count; leaving a journal entry after writing 30 words asks for
a note that then leads *Where you left off*; Rename, the time unit and Delete are on *World settings*; and exporting
and restoring the world keeps the premise.

### 14.5 Since this was written

An old note may rest on things that have since changed. Each journal entry shows how much has happened to what it
names since its date, worked out from links Quarry already keeps. Nothing is marked by hand, and nothing is said
about whether the note is still right.

- **What it counts**, for the entries a journal entry names (its stored mentions) after the entry's date:
  - **decisions** dated after it that name or are tagged with any of them;
  - **changes**: their facts and relationships recorded or changed since, and their own pages changed since (name,
    other names, one-liner, notes);
  - **later notes**: other journal entries, dated after it, that name them.
- **In the journal entry's side panel**: `Since this was written: 4 decisions and 12 changes touch Varren, the Lamp
  Guild and 2 more · 6 later notes`. It opens to a list per named entry, newest first: the decisions (dated, quoted),
  the changes (`status: dead recorded · 2023-05-01`, `page changed · 2024-01-03`), and `6 later notes name Varren ·
  Read them`, which opens the planning reading (§14.2) from this entry's date. If the entry itself was edited later,
  the line says so: `written 2 March 2019 · last edited 2021-06-01`.
- **On the Journal list**, an entry with any decisions or changes since gets a quiet, dimmed `16 since` after its date.
  No colour, no warning, no threshold, and it can't be dismissed: it is a count, not a task.
- **Rough, like *Lately*** (§14.4): a fact changed twice counts once; something removed isn't seen.
- **Only for journal entries.** A chapter's own history is its revisions.

**Data:** none. `GET /journal` gains, per entry, its count of decisions and changes since; `GET /journal/<id>/since`
returns the list.

*Done when* *What the Guild wants* (2 March 2019), naming Varren and the Lamp Guild, says `Since this was written: 2
decisions and 3 changes` after a decision of 2021 tagged with Varren, a fact on the guild recorded in 2022 and two
relationships changed in 2024; the list names each with its date; *Read them* opens the planning reading from 2019;
the Journal list shows `5 since` dimmed beside it; and an entry written today shows nothing.

### 14.6 "Include planned" on the Continuity checks

In a world with little or no prose, much of what is recorded is honestly *planned*: true in your head, not on the page
yet. The checks read canon only, so they see nothing there. This adds the Graph's standing switch to them.

- **The switch.** *Include planned*, on the Checks page and in the editor's Continuity tab. It starts from the
  world's focus (§14.9): off under *Writing*, the default focus, and on under *Planning*; set by hand, it stays until
  the focus changes. So the default is unchanged: under *Writing* **the checks look at canon**, as today.
- **With it on**, every check that reads canon only also reads planned facts and relationships, as if they were
  canon: *named after being recorded dead*, *named before coming into the story*, *two values at once*, *a place
  inside itself*, *their own ancestor*, and phase 12's *two holders of a one-at-a-time role* and *an age that
  disagrees*, and *an effect before its cause* (§14.7). *Spans that run backwards* already reads every standing.
- **Rumour stays out**: a rumour is what someone in the story believes, and is expected to contradict the truth.
- **Findings that rest on a planned row say so**, with a small `planned` tag and the row:
  `Seyla is named in chapter 12, but is planned dead from chapter 9`. A planned row that contradicts canon is a
  finding too: the plan and the page disagree.
- **Resolutions** are kept as today, by rule and key; a finding resolved as *intentional* stays resolved whether or
  not the switch is on.
- **Without chapters** the checks that read names in chapters have nothing to read, and the rest still work: two
  values whose spans are bounded by times are compared on the clock by their numbers (§13.1.5), as are role holders;
  places inside themselves and ancestors of themselves need no time at all. Such findings are listed under *The whole
  world*, as a place inside itself is today.
- **No new standing.** There is no *undecided*: an alternative not yet chosen is a question item (§14.3), and
  choosing it is a decision.

**Data:** none. `GET /checks` takes `planned=1`.

*Done when*, with Seyla *planned* dead from chapter 9 and named in chapter 12, Checks lists nothing until *Include
planned* is on, and then lists the finding tagged `planned`; two planned values of a label bounded by overlapping
times, in a world with no chapters, are listed under *The whole world*; a rumoured death is never listed; and with
the switch off every existing test gives the findings it gave before.

### 14.7 Cause arrows on the Timeline

Events are already related by *caused* / *caused by* (event – anything) and *followed from* / *led to* (event –
event). The Timeline can draw them for one event at a time.

- **Showing them.** Resting on an event's mark (a long-press on the phone) shows its card, as in §13.2.6, and while
  the card shows, the event's direct causes and effects are drawn as arrows. Moving on hides both. Clicking still
  opens the event, as before. Nothing is stored.
- **Keeping them.** The event's card has **Keep arrows**: the card and the arrows then stay while the Timeline is
  panned, zoomed or brushed, and resting on other marks shows their cards as usual. Esc (before it clears a brushed
  span) or the card's `×` lets them go. A kept event is kept in the address, like a brushed span.
- **The arrows** run from cause to effect, curving above the main lane. They are read from event – event
  relationships by label, as the family tree reads parent types: a type reading *caused* (or its reverse *caused by*)
  or *led to* (or *followed from*), whatever the capitals, so a renamed type still counts if it reads that way. *A
  caused B* and *B followed from A* both draw A → B.
- **The whole chain.** *Whole chain* on the card (which keeps the arrows too) follows causes back and effects
  forward, each event once (a loop stops where it closes), each step further a little fainter.
- **Standing.** Planned and rumoured links are dashed, and the Timeline's standing filter hides them as it hides
  other planned and rumoured marks.
- **Edges of the view.**
  - An event off screen: the arrow runs to the edge with the event's name; clicking the name pans to it.
  - An event inside a cluster (zoomed out): the arrow ends at the cluster.
  - An event outside time: the arrow ends at the outside-time strip.
  - An event not placed yet: no arrow; the card lists it, `led to: the Second Flood (not placed yet) · When…`.
- **An effect before its cause** on the clock is drawn anyway, running left, labelled `before its cause`, and is a
  **Continuity** finding (Thomas): `The Lamp Wars (year 40) caused the Founding (year 0), which comes before it.`
  - Both events need a place on the clock: a time, or a chapter with a set time. Events not placed yet, outside time,
    or in a chapter with no set time are skipped. Spans compare by their starts; two events at the same time are not
    a finding.
  - Canon relationships, and planned ones with *Include planned* (§14.6). Rumour never.
  - Listed under the effect's chapter when it happens in one, otherwise under *The whole world*; resolved like any
    finding (*update*, *intentional*, *later*). Rule `cause_after_effect`, keyed by the relationship.
- **Happened view only.** The told view draws no arrows; events related to anything but events (*caused* to a
  character) aren't drawn.

**Data:** none; read from the graph's relationships the Timeline already loads. The finding is one more rule in the
server's checks.

*Done when*, with *The Founding caused the Lamp Wars* and *the Burning of the Quay followed from the Lamp Wars*,
resting on *The Founding* shows its card with an arrow to the Lamp Wars, and moving on hides it; *Keep arrows* keeps
them while panning; *Whole chain* adds the arrow on to the Burning of the Quay; a planned cause is dashed and
disappears with the standing filter; a caused event off screen gives an arrow to the edge with its name; a click
still opens the event; the told view draws none; and giving the Lamp Wars year −20 lists `before its cause` on
Checks.

### 14.8 An entry of more than one kind

Some entries are more than one kind: a world that is a place and, later in the planning, acts; a sun that is a place
and a being. Today an entry has one kind and names are unique, so one side has to give way. From phase 13 an entry
can **add a kind** and stay one entry (Thomas: "at first I make the world, and then it acts").

- **Adding a kind.** On the entry page, beside the kind: **Also a…** picks another kind (Character, Faction, …). The
  same is under *More…* on the name's card. Nothing is copied: it is the same entry, with one name, one page, its
  mentions, facts and relationships.
- **Its kinds, in order.** The kinds are kept in the order they were added; the first is the **main kind**. The page
  heads with them: `Place · also a character`. *Make main* on an added kind moves it first.
- **Where it shows.** In every one of its kinds' tables, with the nav counts counting it in each. In an added kind's
  table it carries a small tag, `place, also a character`, and sorts and filters as any row there. Pickers that list
  a kind list it too. It is still one entry everywhere: one page, matched once in the prose, one node on the graph.
- **The colour** is the main kind's, in the prose, on the card and on the graph; the card adds `also a character`.
- **Relationships.** The types offered are those for any of its kinds: Ashgard can *contain* Old Harbour as a place
  and *lead* the Lamp Guild as a character. The type says which side is used; relationships are stored as today.
- **Every reader of a kind reads all of its kinds.** As a place it nests in the place tree, takes a shape on the
  chart, and can be where someone "is at"; as a character it can have a gender, a species, an age and a POV chapter,
  sits in the family tree and the companion's cast, and the checks for characters (named after being recorded dead,
  and so on) apply. A kind's suggested facts are offered for each of its kinds.
- **Not in time.** An added kind isn't bounded by chapters or times: when the world starts to act in the story is
  told by its facts and relationships (*awake: yes from year 300*, *leads the Lamp Guild from chapter 12*).
- **Removing an added kind** says what uses it (`3 relationships use Ashgard as a character`); they stay, as they do
  today when an entry's kind is changed. Changing the main kind works as changing the kind does today.
- **Export** writes the main kind as `kind:` and the added ones as `also: [character]`; the file stays in the main
  kind's folder. **Restore** reads them back; an older export has none.

**Data:**

```sql
entities  + also_kinds text[] default '{}'     -- in the order added; never the main kind; each one of the kinds
```

The cards carry it, so the tables, pickers and the editor know it offline. `PATCH /entities/<id>` takes `also_kinds`.

*Done when* Ashgard, a place holding Old Harbour, gets *Also a character*; it is listed under Places and under
Characters (tagged there, and counted in both), its page heads `Place · also a character`, it can be recorded as
*leads* the Lamp Guild and still nests Old Harbour in the place tree and on the chart; its card in the prose has the
place colour and says `also a character`; *Make main* on Character colours it as a character; and exporting and
restoring the world keeps both kinds in order.

### 14.9 A focus per world

A world is worked on in stretches: months of planning, then a run of writing, then back. A **focus** says which one
it is now (Thomas: "I just choose the 'current' phase really so I can go back and forth"). Everything works under
either focus; it only changes what is up front.

- **Two focuses**: **Writing** (the default, and every existing world's) and **Planning**.
- **Switching** at any time: a small two-way switch beside the world's name in the world switcher and in the front
  page's head (`Writing · Planning`). It takes effect at once, without leaving the page. It is kept on the server, per
  person and world, so the phone and the desk agree.
- **Where the world opens.** Opening the world (from the switcher, or the app on the desk) lands:
  - under *Writing*, at the last place used in it on this device, as today;
  - under *Planning*, on the front page (§14.4).

  The world's name in the nav always leads to the front page. The phone still starts at Capture, as the installed
  app does today. There is no rule about time spent away.
- **The order of the nav.** The desk nav has three groups today: the planning links (Capture, Inbox, Triage,
  Decisions, Journal), the world (the kinds, Bible, Graph, the Timeline and the chart from phase 12, Where everyone is,
  Checks, Name check) and the projects with their manuscripts. Nothing is hidden under either focus, and no link
  moves between groups except the Timeline:
  - *Writing*: the projects first, then the planning links, then the world;
  - *Planning*: the planning links first, with the Journal at their head and the Timeline after Decisions; then the
    world; then the projects.

  The phone's bottom tab bar stays as it is; its *World* tab opens the front page.
- **Include planned** (§14.6) starts **on** under *Planning* and **off** under *Writing*. Switched by hand on the
  Checks page or in the Continuity tab, it stays as set until the focus changes, which sets it again.
- **Nothing else** follows the focus: Drafting/Revising, the editor's settings, the companion's tabs and the Graph's
  standing switches are as they were.
- Not exported, like the note for next time: it is how one person is working on the world, not part of it.

**Data:**

```sql
world_members  + focus text default 'writing' CHECK (focus IN ('writing', 'planning'))
```

`PUT /worlds/<slug>/focus`; `GET /worlds` and `GET /worlds/<slug>` carry it.

*Done when* switching the demo world to *Planning* on the front page reorders the nav at once (Journal first in the
planning links, the Timeline after Decisions, the projects last), turns *Include planned* on in Checks, and opening
the world again on the desk lands on the front page, while the phone shows *Planning* too; switching back to
*Writing* puts the projects first, turns *Include planned* off, and the world opens at the last chapter used.

### 14.10 Names shared by two entries

Two characters can share a first name: Isolde Marr and Isolde Senn. Today a first name matches only when one entry
claims it, so where the book calls her just *Isolde*, the cast, the mentions and the checks miss both. An other name
given to two entries (two characters each called *the Warden*) is worse: it silently goes to whichever entry comes
first. From phase 13 such a name is **shared**, and the writer says in the text which entry it means from that point
on. (From the analysis of Thomas's screenplay notes, where several characters share first names.)

- **What is shared.** A form that two or more entries claim: a character's first name (WORLD-MODEL.md §2) or an other
  name. An entry's own name is never shared: where a form is one entry's name and another's other name or first
  name, the name wins, as first names already give way today. Switching *first name matches* off on one of two
  characters makes the other's first name theirs alone again. Names stay unique, as today.
- **Before any choice: ambiguous.** A bare *Isolde* with no choice above it is **ambiguous**. The editor colours it
  by kind (the claimants' kind, or the plain name colour when they differ), and while Revising it also has a faint
  dotted underline, like a possible new name. Its card lists every claimant with their one-liner, then the strip
  below. An ambiguous name can stay ambiguous for good: nothing asks.
- **A choice is a margin-note line**: `%% Isolde: Isolde Marr`.
  - After the colon, one or more claimants, separated by commas, each by its full name or by any word of it that
    singles it out (`%% Isolde: Marr`, `%% Isolde: Marr, Senn`, capitals ignored). `?` makes the name ambiguous again.
  - It holds from the line to the next choice line for the same name, or to the end of the chapter. Nothing carries
    over between chapters, so every chapter starts ambiguous, and a chapter that never uses the bare name needs no
    line.
  - The name before the colon is read as names are matched (capitals per entry), and its plural and possessive forms
    follow it: *Isolde's* follows the choice for *Isolde*.
  - A `%%` line that doesn't start with a shared name and a colon is an ordinary margin note, as today. A choice line
    whose words single out no claimant does nothing, has a wavy underline while Revising, and its strip offers the
    claimants to put in instead.
  - Being margin notes, choice lines stay in the text, so they survive edits, cuts, experiments (a draft starts as a
    copy of the chapter), offline use, export and Restore. They are dimmed, and left out of the word count, the
    compiled manuscript and `manuscript.md`, like any margin note. A choice line names nobody: its names aren't
    mentions. A rename's *Replace in the text…* (§11.7) includes margin notes, so choice lines follow a renamed
    entry.
- **Making the choice.** On an ambiguous name, the quick-fix strip (pointing at it, Alt+Enter, F8, a long-press on the
  phone) offers `From here: Marr · Senn · Both` (with three claimants, each of them and *All*). One click inserts
  `%% Isolde: Isolde Marr` on its own line above the paragraph (*Both* writes every claimant), and the name is
  coloured as that entry's at once. On a shared name that a line has settled, the card is the chosen entry's and the
  strip offers the others, *Both* and *Unsure*, which insert a new line above this paragraph the same way. When the
  line right above the paragraph is already a choice for this name, the click rewrites that line instead of adding a
  second. As everywhere in the editor (WORLD-MODEL.md §5), nothing appears while typing.
- **F8** stops at ambiguous names with the other marked words. A choice holds for the rest of the chapter, so a sweep
  meets only the first ambiguous use in each stretch.
- **How each state counts**:
  - **chosen** (one entry): a mention of that entry like any other, for the cast, the mentions strip, first
    appearance, the thread readings, entries across chapters, connections and the Continuity checks;
  - **several** (*Both*): a mention of each;
  - **ambiguous**: shown faintly for each claimant, and counted for none. The mentions strip (§12.1) draws a chapter
    whose only uses are ambiguous as a faint cell, and the line above it adds `+ 6 unsettled in 3 chapters`; the
    side panel's cast lists the claimants once, as `Isolde? Marr · Senn`. Ambiguous uses drive no Continuity
    findings, no unrecorded connections, no first appearance and no gaps. The thread readings (§11.4, §14.2) leave
    them out and say so: `+ 4 paragraphs where "Isolde" isn't settled`.
- **Both matchers agree.** The server's matcher (`mentions.py`) and the browser's (`matcher.ts`) read shared names and
  choice lines the same way: the cards carry each character's first name whether or not it is shared, and each side
  works out what is shared from them. The same table of cases is run by pytest and Vitest. A likely misspelling of a
  shared name (*Isolda*) still offers *Replace*, which is the same word whoever is meant; it is stored against the
  first claimant, as before.
- **Outside chapters.** In the Journal, once its entries are in the editor (§14.1.1), choice lines are read and
  dimmed as in a chapter, while other `%%` lines stay ordinary text there. In items, decisions and an entry's notes a
  shared name is always ambiguous, except that in an entry's own notes a shared name that is one of its own means the
  entry itself (Isolde Marr's notes calling her *Isolde* aren't about Isolde Senn).
- **Changing names.** Renaming, adding or removing an other name, or switching *first name matches* can make a name
  shared or no longer shared; mentions are worked out again, as for any change of names. A choice line for a name
  that is no longer shared is an ordinary margin note.
- **Typing.** Choice lines are found per changed line, as names are; the editor keeps their places and settles each
  shared name by the nearest choice line above it, so the typing budget (DECISIONS, 2026-10-22) holds, with 400
  entries and a 10,000-word chapter, also at 4× slower CPU.

**Data:**

```sql
mentions   kind + 'ambiguous'      -- the CHECK widens: exact | alias | near_miss | ambiguous
```

Nothing else is stored: the choices are in the text. A chosen name is stored as an `alias` mention of the chosen
entry, several as one `alias` mention per chosen entry at the same place, and an ambiguous name as one `ambiguous`
mention per claimant at the same place. Everything that counts mentions today (`kind != 'near_miss'`) counts `exact`
and `alias` only; the mentions strip, the entry page and the cast read `ambiguous` as well. The upgrade widens the
CHECK and works out every world's mentions again once, so a bare first name that matched nothing before shows as
ambiguous, and an other name that went to the first of two entries becomes ambiguous until a line settles it.
Export and Restore carry the lines as part of the text; nothing changes in the files.

*Done when* a chapter that calls her *Isolde*, with no choice line, colours the name as a character, its card lists
Isolde Marr and Isolde Senn, both entry pages show it faintly as unsettled, and Checks gives no finding for it though
Isolde Senn is recorded dead from an earlier chapter; *From here: Marr* inserts `%% Isolde: Isolde Marr` above the
paragraph, after which that and every later bare *Isolde* in the chapter count for Isolde Marr only, and the next
chapter starts ambiguous again; a later `%% Isolde: Senn` switches to Isolde Senn, giving the *named after being
recorded dead* finding; *Both* counts the name for each; `%% Isolde: ?` makes it ambiguous again; the line is dimmed,
not in the word count and not in the compiled manuscript; two characters both given the other name *the Warden*
share it the same way; a choice line in a journal entry settles the name there; the server's mentions and the
editor's colours agree on every case in the shared table; and exporting and restoring the world keeps the choices.

### 14.11 Data model, in one place

```sql
revisions      doc_table + 'journal'                                        -- §14.1.1
facts          + planned_in_journal_id NULL, planned_evidence NULL          -- §14.1.2; beside established in
relationships  + planned_in_journal_id NULL, planned_evidence NULL          -- §14.1.2
tellings       + journal_id NULL                                            -- §14.1.2; a note in the Journal
item_links     target_table + 'journal'; + passage text NULL                -- §14.3
worlds         + premise text NULL                                          -- §14.4
session_notes  + journal_id NULL; chapter_id NULL-able, exactly one of them -- §14.4
entities       + also_kinds text[]                                          -- §14.8
world_members  + focus text default 'writing'                               -- §14.9; writing | planning
mentions       kind + 'ambiguous'                                           -- §14.10; one row per claimant
```

Endpoints: the journal is saved like a chapter, with revisions, and joins `GET /offline` (§14.1.1); facts and
relationships take where they were planned and *make canon*, and `POST /events/record` takes a journal entry
(§14.1.2); `GET /planning` (§14.2); `POST /items` takes a chapter or journal entry with a passage (§14.3); `GET
/worlds/<slug>/front`, `premise` on `PATCH /worlds/<slug>`, and the journal's session notes (§14.4); `GET
/journal/<id>/since` and counts on `GET /journal` (§14.5); `planned=1` on `GET /checks` (§14.6); one more check
(§14.7); `also_kinds` on `PATCH /entities/<id>` (§14.8); `PUT /worlds/<slug>/focus` (§14.9); first names on every
character's card, shared or not (§14.10). The planning reading, loose ends, *Lately*, *since this was
written* and the cause arrows are worked out when read, never stored.

**Phase 13 is done when** each part's *done when* above holds, and the demo world (The Ninefold Delta) shows it: a
premise; a few journal entries over several years (made up), one with a fact and an event recorded from it as planned
and one with `??` markers; a planned fact made canon in a chapter; a question made from a passage in a chapter and one
parked spark from the Journal; a note for next time left in a journal entry; an old entry with decisions and changes
since; a planned death that *Include planned* turns into a finding; three events joined by *caused* and *followed
from*, one of them before its cause; an entry that is a place and also a character; and a second character sharing a
first name with one already there, with a chapter that uses the bare first name before, between and after choice
lines.

### 14.12 Three build phases

Phase 13 is built **after phase 12 is merged**, as three build phases, by one build session, each a pull request
merged before the next is begun: 13a, then 13b, then 13c. These are only the order the code is written in; nothing
in the app is split by them.

1. **13a, the Journal as a workplace** (§14.1–§14.3): journal entries in the editor with revisions and the offline
   copy, planned in the Journal and canon in the book with *Record a fact* and *Make it canon here*, the planning
   reading, sparks and questions from a passage, and loose ends in the Journal. Most of the work is here, and the rest
   reads what it adds.
2. **13b, getting back in and checking** (§14.4–§14.9): the front page and World settings, the Journal's note for next
   time, *since this was written*, *Include planned*, cause arrows and their check, entries of more than one kind, and
   the focus.
   Each is small and works from existing links.
3. **13c, names shared by two entries** (§14.10): the shared names in both matchers, choice lines, the strip's
   *From here*, and how each state counts. Added after the spec of 13a and 13b, and built last because it reads
   the Journal's editor from 13a.

Each phase updates the demo world with its own parts, and each pull request lists what it leaves for the next.

### 14.13 Open questions for phase 13

None left. Thomas's answers are in DECISIONS.md (2026-10-25): something is planned until it is in the book or marked
canon, with *Make it canon here* (§14.1.2); cause arrows show on hover and can be kept, and a click still opens
(§14.7); an effect before its cause is a Continuity finding (§14.7); an entry can add a kind and stay one entry
(§14.8); a focus per world, *Writing* or *Planning*, decides where the world opens, the nav's order and where
*Include planned* starts (§14.9); two build phases (§14.12), with shared names added after them as a third (§14.10,
§14.12); and a shared name is settled by a visible margin-note line in the text (§14.10).

## 15. The Guide: learning Quarry by watching, then doing

Quarry grew fast, and much of it is only found by someone who already knows it is there. The Guide shows it the way
Thomas learns: seeing a feature used on a real story, then doing it himself. It is a page of short walkthroughs, each a
few minutes, each played on the real app against a copy of the demo world, with a caption saying what is happening
and why a writer would want it.

The Guide is opt-in and stays out of the way. Nothing runs, pops up or is suggested unless a walkthrough is started
from the Guide page. A walkthrough never takes focus from what is being typed, never covers the prose with its caption,
and its captions are written by hand: no AI writes, reads or judges anything (§1).

### 15.1 Watch, then try

The Guide page (`/guide`, linked from the nav's foot and from Settings on the phone) lists the walkthroughs in the
order a writer would meet the features, each with its length, what it covers, when it was last seen on this device,
and two buttons:

- **Watch.** The steps do themselves. A pointer moves to what the step is about and presses it, typing goes a letter
  at a time, and a ring shows what the caption is about. **Pause**, **Next** and a speed of
  0.5×, 0.75×, 1×, 1.5× or 2× (kept per device) are on the caption.
- **Try it yourself.** The same steps, each waiting for the writer. The ring shows where; the caption says what to
  do ("Shift-click the highlighted button", "Select the highlighted paragraph"); the walkthrough moves on when it sees
  it done, by the click itself or by what appears after. **Do it for me** does the step instead.

Before a step shows, what it points at is brought into view: if it isn't comfortably on screen (between about an
eighth and three quarters of the window's height), it is scrolled to the middle, through any scrolling box it sits in,
smoothly (at once for a writer who asks for reduced motion, and at the tests' instant pace), and the ring and caption
appear once it has stopped moving.

The caption sits next to what it points at: below it if it fits, else above, right or left, shifted along to stay on
screen. It never covers the target, what the next step will use, or the nav, and of the places that fit it takes the
first that covers no text, else the one covering least. When nothing beside the target will do (a target nearly as
big as the window) it keeps to a corner clear of it. It moves with the page as it scrolls or the window changes size,
and a faint dashed line runs from it to the ring when the two are apart. On a phone it stays docked above the tab bar,
with the line pointing up to what the step is about.

The page around the ring can be dimmed a little, a soft spotlight that clicks still pass through. The Guide page sets
when: while watching (the default, so a writer trying it sees the page as it is), always, or never. The caption can be
folded to its title line. Its buttons never take focus, so a field the walkthrough is typing in stays open. **End**
stops a walkthrough at any step.

A walkthrough runs with the default writing settings (the panel open, Focus mode off, Drafting, asking for a note
for next time), so its steps find what they point at whatever this device is set to. The writer's own settings are
kept aside, untouched, and come back when it stops, or at the next load if the tab was closed in the middle. A reload in the middle of one offers
**Carry on** on the Guide page, from the step it had reached, in the same sandbox.

### 15.2 The sandbox

A walkthrough changes things: it records an event, accepts an experiment, closes an item. It never does so in the
writer's own worlds, or in a demo world loaded to explore.

- Starting a walkthrough makes a **sandbox**: a fresh copy of the demo world, made by the same code as *Load the demo
  world* (the Restore path, about three seconds), named "The Ninefold Delta (guide sandbox)" at `/w/guide-sandbox`.
  Every walkthrough starts from that known state, so its steps can rely on what the demo plants.
- There is **at most one** sandbox. The next walkthrough replaces it, with everything done in it.
- When a walkthrough ends, the sandbox **stays**, as it was left, to look around in. The Guide page and a quiet notice
  on the sandbox's own pages offer **Delete it**.
- It is a world like any other, listed in the switcher by its name, but Quarry never reopens in it: the last world
  used, which "/" and the installed app's Capture open, stays the writer's own. It gets no offline copy.
- Deleting or replacing it also takes out what it left on the device: its keys in local storage and its entries in
  the per-world ones (the capture choice, the Timeline's filters, the last place used).

### 15.3 Steps, and keeping them true

A walkthrough is a list of steps, written once, that both buttons play. A step says one or two sentences, may open an
address in the sandbox, points at an element on the page (the same data-testids and labels the end-to-end tests use,
narrowed by its text), may do one thing to it (click, shift-click, rest the pointer on it, type into a field, choose
from a list by its value or the words it shows, press a key with Ctrl (Cmd on a Mac), Shift or Alt, or in the editor select a passage, put the cursor after some words
or type at it), and may wait for what that brings up. Nothing in the views knows about the Guide.

The app changes; a walkthrough must not quietly drift from it. A step that can't find what it points at, or what it
waits for, is skipped and named on the walkthrough's last card. The end-to-end run watches every walkthrough at an
*instant* pace (no reading pauses, no pointer travel, typing at once, but every step done and everything it expects
waited for; a step can ask for the time the app itself needs, such as a count that catches up after typing) and fails
if any step was skipped, so a renamed button or a moved panel breaks the build, not the lesson. That pace is set only
by the tests, on the device; *Try it yourself* and Carry on are checked once more on their own. The walkthroughs are
split over two shards of their own.

### 15.4 The phone in a frame

Some features are about the phone and the desk together: a spark captured on the bus and sorted at the desk. A step
can open the phone: a phone-shaped frame beside the page holding Quarry itself at phone width (the same address, the
phone's layout and tab bar), and point at and act on what is inside it as on the page. The caption moves beside it.
Quarry may therefore be framed by its own pages (`frame-ancestors 'self'`, `X-Frame-Options: SAMEORIGIN`); no other site
can frame it. On a real phone the frame fills the screen.

### 15.5 Videos

The same run can record each walkthrough, watched at 1×, as a video: a workflow started by hand (*guide videos*)
squeezes them (about 1.5 MB a minute, some 35 MB in all) and keeps them as a download on the run for 30 days. Nothing is committed, so they take no room in the repository; the
Guide itself doesn't need them.

### 15.6 The walkthroughs

Fourteen walkthroughs (the fourteenth from phase 16, §18.6), about 27 minutes in all when watched at 1×, in the order the Guide lists them. Each names what it does in the
sandbox, and what it only points at (a download, a file picker, a confirmation, a drag), where doing it would leave the
app or the sandbox.

| # | Walkthrough | Min | What it does |
|---|---|---|---|
| 1 | Getting back in | 2 | The front page: the premise, *Where you left off* (with the Journal's note under "1 more"), *Lately*, the latest decisions, open questions and the ?? count. *Continue* into chapter 3 at "Tamsin opens the compass…"; a paragraph written and left, so the note for next time is asked and the front page shows it first; the *Writing* and *Planning* focus reordering the nav. |
| 2 | A spark on the phone, sorted at the desk | 1 | In the phone frame, a spark captured for The Ferryman's Daughter; at the desk the inbox, closing it with a decision, Triage's keys, and the Decisions log. |
| 3 | Writing a chapter with the companion | 2 | Chapter 2's names coloured by kind; the Proofreader: Alt+Enter removes "the the", F8 steps to "Oscar" and replaces it with Oskar Vey; Continuity's Mountain Fires before the Flood. Chapter 3's margin note, Connections (Pell and Brother Cade), the Archivist ("Rook" twice, added as a character), Loose ends, and a thought stashed with Ctrl+Shift+S. Points at Drafting and Revising. |
| 4 | The bible | 2 | The characters table and Tamsin Vey's page (pronunciation, other names, the mentions strip, first appearance); Corin Dray, only in Ash Season's bible; Moss the dog not matched in "Moss grew"; the name check (Tamsen, Oscar); Pell renamed, the old name kept; the Labels page's expected *type* missing on the Mountain Fires, and a label holding several values. |
| 5 | Facts and relationships from the prose | 2 | A fact recorded from a passage of The Crossing, with its evidence on Tamsin's page; her two occupations; *As of* year 411, before Saltreach; the family tree with Corin worked out as her cousin and Wenna the ancestor; Where everyone is. |
| 6 | Species and roles | 2 | The species (human, dog, marsh-wight, native to the delta); the characters table by species; Brother Cade, a marsh-wight who appears human; the Warden-Captain held one at a time; Harl Brenner's roles; the clash in Checks, settled with *End … before …*. |
| 7 | Story time and the Timeline | 2 | When chapters are set; "The compass argument begins" recorded from a passage of chapter 3 in year 392 and its *Told in*; the Timeline's eras, folds and the book; the Lock Years and the Ash Summers chosen; the Mountain Fires' backwards cause arrow; *Told* and *History*; Checks reading the clock. |
| 8 | Revising | 2 | Summaries and status pills; word history; find and replace, Oscar to Oskar, previewed, replaced and undone; a checkpoint "before the cuts" (Ctrl+S) and the changes since it while Revising; a line cut with Ctrl+Shift+X, in the chapter's cuts and Salvage, and put back; the Brass Compass read in story order. Points at unticking a hit. |
| 9 | Restructuring with experiments | 2 | Ash Season's experiment and *Read as if accepted*; a new one over chapters 3–4 from copies; *Accept*, the review and a harvest note; *Undo* on the note; the old chapters in Salvage. |
| 10 | Planning in the Journal | 2 | Loose ends (Hesper's age ??), the entries and their *since* counts; "What the Wardens want" in the editor with the world tools and the Wardens' planned age on their card; a fact recorded as planned; a question from a passage; Hesper's trade planned in "The first map" (2014) and canon in "The Cartographer", and her planning reading; *Include planned* turning Brother Cade's planned death into a finding. |
| 11 | The chart | 2 | The delta as a land holding Carrow Ferry, Greywater and Marrow Locks, the Outer Sound and the Salt Flats; shapes from types; Greywater pinned and Carrow Ferry placed automatically; the dyke road and the sea route; control shades; Marrow Locks' card; *As of* The Crossing and What the River Kept moving Tamsin's dot; from the Timeline with 412–413 brushed, the scrubber. Points at pins (pinning is a drag). |
| 12 | Names shared by two entries | 2 | "The Cartographer"'s bare "Linnet", its shared card, the same on the phone; *Sorrel* writing a choice line; the Dray and "?" lines; the chapter's unsettled names; Linnet Sorrel's *Not settled*; the Ninefold Delta, a place that is also a character. |
| 13 | Keeping it safe | 2 | Autosave and History, an older revision restored and the one before it kept; the delete section of World settings, which needs the name typed (opened, then cancelled). Points at Export and Restore (a download, a file picker), the offline copy, passkeys and recovery codes (new codes ask to confirm). |

The demo world (backend/src/quarry/demo.py) is the walkthroughs' material: a walkthrough uses what it plants and adds
what it shows being made (an event from a passage, a cut, a checkpoint, a rename) itself, so the demo needs nothing
new for them.

### 15.7 Data model, in one place

- `worlds.sandbox` (boolean, default false; migration 0017): the Guide's copy of the demo world. Deleting the world
  deletes everything in it, as for any world.
- `POST /api/guide/sandbox` deletes the writer's sandbox and makes a fresh one; `DELETE /api/guide/sandbox` deletes it.
  A world's answer says whether it is a sandbox.
- On the device: which walkthroughs were seen and when, the speed, the spotlight, and the writer's own writing settings while a
  walkthrough runs (local storage, `quarry.guide*`); the step a walkthrough had reached (session storage, for *Carry
  on*).

### 15.8 Decisions

Thomas's answers (DECISIONS.md, 2026-10-25): the Guide's pages may frame each other (§15.4); the sandbox stays after a
walkthrough until the next one or *Delete it* (§15.2); watching has speed controls down to 0.5× (§15.1); videos are
made by hand into a short-lived download, not kept in the repository (§15.5); and every walkthrough below is written
and built at once.

## 16. Decisions with follow-ups (phase 14)

A decision is a dated one-line verdict (§2): `Varren dies at the end of chapter 9`. Today nothing follows from it. It
sits in the log, and whether chapter 9 ever got written that way is something only memory knows (Thomas: "with a
decision like that, how do I know it was carried out?"). Phase 14 lets a decision have **follow-ups**: the planned
changes and tasks that carry it out. Its state (*settled*, *1 of 2 to do*, *done*) is **worked out** from them, never
ticked by hand, and a chapter that is written but still lacks a planned change from a decision says so in its **Loose
ends**.

It builds on what phase 13 made: facts and relationships with a standing, *planned* until they are in the book and
*Make it canon here* when the text shows them (§14.1.2); tasks linked to chapters and listed in their Loose ends
(§14.3); the planning reading (§14.2); the front page (§14.4); and *Include planned* on Checks (§14.6).

The principles hold. Nothing here writes, suggests or reads story content: whether chapter 9 *shows* Varren's death is
for the writer to say, by making the planned change canon there. Follow-ups are optional and the step that offers
them is skipped with Enter. The state is worked out from links Quarry keeps, and no list asks for attention: there are
no reminders, no badges and nothing while typing. The compiled manuscript stays pure prose.

Examples use made-up names. On 12 October 2026 the writer closes the question *When does Varren die?* in Triage with
the decision `Varren dies at the end of chapter 9`, tagged with Varren and Isolde, in the project *The Salt Road*,
whose ninth chapter is *The Drowned Bell*.

### 16.1 Follow-ups

A decision can have **any number of follow-ups, none to start with**. A follow-up is one of three things, each a row
Quarry already has:

- **A planned fact** (*status: dead* on Varren, from chapter 9).
- **A planned relationship** (*Isolde knows about Varren*, from chapter 11).
- **A task** item (*Plant the bell's crack in chapter 4*), linked to the chapters and entries it is about, so it shows
  in those chapters' Loose ends (§14.3.1) like any task linked to a chapter.

The follow-up is only the link from the decision to that row. The fact, relationship or task is an ordinary one:
edited, made canon, closed or deleted wherever it is, and read by everything that reads its kind.

**Making one from the decision.** One gesture makes the row and links it (where the gesture is offered: §16.3). The
small form is filled from the decision, and everything it takes from the decision is shown as a chip to keep or
remove, so nothing is guessed silently:

- **Planned fact**: the form of *Record a fact* (§14.1.2) in one row.
  1. **The entry**: a chip for each entry the decision is tagged with, then each it names (its stored mentions), the
     first tagged one chosen; *Other…*.
  2. **Label and value**, empty, with the suggestions of §12.6. Nothing is read from the decision's words.
  3. **When it holds**: the span picker of §13.1.5, starting empty. When the decision names a chapter (below), the
     picker offers it: `Named in the decision: chapter 9, The Drowned Bell · From · Until`. One click (or Tab and
     Enter) uses it; otherwise it isn't used.
  4. **Standing**: *planned*, as for anything recorded outside a chapter (§14.1.2). The one-click switch to *canon* is
     there, but a follow-up made canon at once is done at once.
  5. **Save** (Enter). The toast says `Planned "status: dead" on Varren · follows the decision · Undo`.
- **Planned relationship**: the relationship form in one row. *A* and *B* start on the first two tagged entries (each a
  chip with the others and *Other…*), the types are those for their kinds, a role where the type has one, the span
  with the same chapter offer, and *planned*.
- **Task**: a line of your own (required, since a task needs words; it starts empty), then chips:
  - the decision's tagged entries, **ticked** (they are the writer's own tags);
  - a chapter the decision names, **offered unticked**: `chapter 9, The Drowned Bell · named in the decision`;
  - *Chapter…* to pick any other.

  The project is the decision's. It saves an **open task** linked to the ticked entries and chapters (`item_links`, no
  passage), and the toast says `Task added · follows the decision · Undo`.

**A chapter the decision names.** Read from the decision's text, only to offer it:

- `chapter 9`, `ch 9`, `ch. 9` or `chapter nine` (one to twenty in words) is the ninth current chapter by position in
  the decision's project. For a decision with no project, in a world with several projects, it is offered once per
  project that has that many chapters, each with its project's name.
- A current chapter's **full title**, matched as a whole phrase, any capitals (`The Drowned Bell`). Titles of one word
  shorter than five letters are not matched.
- At most three chapters are offered, in the order they appear in the decision.

A wrong offer costs a glance; it is never applied without a click.

**Attaching what already exists.** *Attach…* in the same row opens a picker (type to filter) of:

- planned facts and relationships, those on the decision's tagged entries first, each shown as on the entry page
  (`Varren · status: dead · from chapter 9 · planned`);
- open and deferred tasks, newest first.

Canon rows and closed tasks aren't offered: they would be done before they were attached. A row can follow more than
one decision; it is attached to a decision once. From the other side, a planned fact or relationship on an entry page
and a task on its item page have *Follows a decision…* under *More…*, which picks from the decisions tagged with the
entry (or the task's entries) first, then all of them, newest first.

**Where a follow-up shows its decision.** On the entry page, beside a fact or relationship that follows one:
`follows the decision of 12 Oct 2026` (the decision's text on hover), linking to its line on the Decisions page. On a
task's item page, in Triage, on the Board and in the inbox: `Follows: "Varren dies at the end of chapter 9" · 12 Oct
2026`.

**Letting one go.**

- **Drop** (on a follow-up that is still to do): the change or task won't happen. The follow-up stays on the decision
  as *dropped*, with the date; the planned row or task is left as it is, and can be deleted or closed separately.
- **Deleting** a planned fact or relationship that follows a decision says so first (`This follows the decision "Varren
  dies at the end of chapter 9". It will be listed there as dropped.`) and drops the follow-up. Its words are kept on
  the decision, since the row is gone.
- **Detach** removes the follow-up altogether, for one made or attached by mistake; the row stays, and the decision no
  longer counts it.

Each has *Undo* in its toast.

**Deleting a decision** with follow-ups says so first (`1 planned fact and 1 task follow this decision. They stay,
without the decision.`) and removes only the links.

**Undoing the close.** Undo on the toast of a close in Triage or the inbox deletes the decision, as today, and also
deletes the planned rows and tasks that were *made* in its follow-up step; ones that were *attached* stay, unlinked.

*Done when* the decision `Varren dies at the end of chapter 9`, tagged with Varren and Isolde, makes a planned fact
with Varren chosen, the span offering `chapter 9, The Drowned Bell` as *From* (used only after a click), saved as
*planned* and shown on Varren's page with `follows the decision of 12 Oct 2026`; makes a task with Varren and Isolde
ticked and chapter 9 offered unticked, which, once ticked, lists the task in chapter 9's Loose ends; attaches an
existing planned relationship from the picker; *Drop* keeps the follow-up as dropped; deleting a planned fact that
follows it warns first and leaves it dropped with its words; *Detach* removes it; a decision with no project in a
world with two projects offers chapter 9 once per project; and `Chapter Nine` is offered as chapter 9.

### 16.2 The worked-out state

A decision's state is **worked out** from its follow-ups each time it is read. There is no checkbox, and nothing to
keep up to date.

- **Settled**: no follow-ups. Every decision today, and any decision that needs nothing further.
- **To do** (`1 of 2 to do`): some follow-ups are still to do.
- **Done**: it has follow-ups, and none is to do.

A follow-up is **to do** while:

- a fact or relationship is *planned* or *rumour*: a change set to rumour stays to do until it is made canon or dropped
  (Thomas);
- a task is *open* or *deferred*.

It is **done** when:

- a fact or relationship is *canon* (by *Make it canon here*, the standing pill, or anywhere else);
- a task is *accepted* or *harvested*.

It is **dropped** when:

- it was dropped by *Drop*, or by deleting its row;
- a task was closed as *rejected*. It counts toward the decision being done, but is listed as *dropped*, dated its
  close, so the list shows it wasn't carried out (Thomas).

Done and dropped both count as not to do; the follow-up list tells them apart. Reopening a task or setting a canon row
back to planned makes the follow-up to do again, and the decision's state follows.

**Where it shows.** The same quiet pill wherever a decision's line is:

- on the **Decisions** page;
- in the **Decisions** section of an entry page;
- in the **planning reading** (§14.2), on each decision;
- in **Latest decisions** on the front page (§14.4).

A settled decision shows **no pill**: it is a decision, as today. `1 of 2 to do` is a plain pill and `done` a dimmed one
with a tick. No colour says late or overdue, since nothing is.

**The follow-up list.** Clicking the pill (or `+ follow-up` on a settled decision, §16.3) opens the decision's
follow-ups under its line, to do first, then done, then dropped:

```
Varren dies at the end of chapter 9 · The Salt Road · 12 Oct 2026          1 of 3 to do
  to do    Varren · status: dead · from chapter 9, The Drowned Bell · planned · chapter 9 is written
  done     Plant the bell's crack in chapter 4 · task · accepted 20 Oct
  dropped  Isolde knows about Varren · from chapter 11 · 22 Oct                    (the row was deleted)
```

Each line links to its row (the entry page at the fact, or the item). A to-do line has *Drop* and *Detach*; a line
whose chapter is written adds the quiet `chapter 9 is written`, the same test as §16.4.

**Data:** none beyond §16.6; the state is worked out when read. `GET /decisions` gains, per decision, `followups:
{todo, done, dropped}` counts, and `GET /decisions/<id>/followups` returns the list.

*Done when* a decision with no follow-ups shows no pill; adding a planned fact makes it `1 of 1 to do` on the
Decisions page, on Varren's page, in his planning reading and on the front page; *Make it canon here* on that fact
turns it to `done` everywhere; adding a task makes it `1 of 2 to do` again; deferring the task leaves it to do,
rejecting it makes the decision done, with the task listed as dropped; reopening the task makes it `1 of 2 to do`
again; changing a planned relationship that follows it to *rumour* leaves it to do; and there is nowhere to tick a
decision done.

### 16.3 Where follow-ups are added

The gesture is the same everywhere: **one row, keyboard first**, under the decision's line.

```
Decision logged · + follow-up:  f fact · w relationship · t task · x attach existing · Enter skip
```

- **f** opens the planned fact form in the row, **w** the relationship form (*with*), **t** the task form, **x** the
  picker of existing rows (§16.1). On the phone they are four chips and *Skip*.
- In a form, Enter saves, and the row comes back as `+ another · Enter done`, so a decision can take several follow-ups
  in a row. Esc in a form goes back to the choice row without saving.
- Enter or Esc on the choice row ends the step.

**After closing an item with a decision line**, in Triage and in the phone Inbox:

- The step is offered only when a decision was written (not for an empty line, a harvest note or *defer*), and only
  online: offline the close goes on as today and nothing is asked.
- **Triage**: the row appears above the next item, with the keyboard in it. f, w, t and x are not Triage keys, so they
  can't be pressed by habit for something else. **Any Triage key** (a, r, h, d, l, p, e, 1–3, j, k, u) skips the step
  and does what it does, so the step never holds up a run through the inbox. The close's toast stays beside it.
- **Inbox** (phone and desk): the row appears in the list where the closed item was, as chips. Tapping anywhere else,
  or scrolling away, skips it.
- **Closing an experiment** with a decision line (§13.6.1) offers the same step under the close form.
- There is no setting to turn it off: it is one row, and Enter skips it.

**On a decision's line, anywhere.** On the Decisions page, an entry page's Decisions, the planning reading and the front
page's Latest decisions, a quiet `+ follow-up` sits at the end of each line (shown on hover or focus on the desk, always
on the phone). It opens the same row under the line. A new decision written on the Decisions page itself gets the step
too, as after a close.

**Nothing while typing.** The step appears only after the decision line is saved; the forms open only on a key or a
click, and the chapter offer is worked out once, when the step opens.

*Done when* closing a question in Triage with `Varren dies at the end of chapter 9` shows the row above the next item;
Enter skips it, and so does `a`, which accepts the next item; `f` opens the fact form, Enter saves it, and the row comes
back as `+ another`; `t` then adds a task, and Enter ends the step; Esc in a form returns to the row; closing with no
decision line, or harvesting, offers nothing; on the phone the step is four chips and *Skip*, and isn't offered in
airplane mode; `+ follow-up` on a line on Varren's page opens the same row; and typing in the decision line never opens
anything.

### 16.4 Catching the gap in a chapter

The point of following through: when the writer reaches the chapter, the plan should be there to meet them. Quarry
doesn't read the prose to see whether chapter 9 kills Varren. It only says that chapter 9 has text, and a planned change
from a decision is tied to it.

**The rule.** For a current chapter C, a **gap line** is shown for each follow-up of any decision that is:

- a fact or relationship that is still to do (§16.2);
- tied to C, in either of two ways:
  - its *from* chapter, its *until* chapter or its *established in* chapter is C;
  - its *from* or *until* is a time (§13.1.5), and C is set at that time (§13.1.2): C's time, or the span from it to
    its end, includes it (Thomas). A chapter with no set time is tied by chapter bounds only, and a change *outside
    time* is tied to no chapter;
- and C **has text**: at least one word of prose, margin notes not counted.

A change bounded by a time can so be tied to several chapters, each with its own line and its own *Not yet*.

Experiment drafts and retired chapters have no gap lines.

**In Loose ends**, under the items tied to the chapter (§14.3.1), as their own small group:

```
Decided 12 Oct 2026: Varren · status: dead, from this chapter · not in the book yet
    "Varren dies at the end of chapter 9"
    Make it canon here · Not yet
```

The change is shown as on the entry page, *this chapter* for C; the decision's text is quoted under it and links to its
line on the Decisions page.

- **Make it canon here** works as in §14.1.2: the standing becomes *canon* and C its *established in*. The span is
  left as it is. If a passage is selected in the editor, it becomes the evidence, and the button says `Make it canon
  here, with the selection`; with nothing selected there is no evidence, which can be added later on the entry page.
  The toast says `Canon in chapter 9 · Undo`, and, if it was the decision's last follow-up, `· the decision is done`.
  *Record a fact* in C offering *Make it canon here* for the same planned row (§14.1.2) completes the follow-up the
  same way.
- **Not yet** hides the line from C's Loose ends: the writer knows, and will get to it. It is remembered as a
  **resolution** (the table the Continuity findings use): rule `followup_gap`, key `<follow-up id>:<chapter id>`,
  outcome `later`. The line folds under `Not yet · 1` at the foot of the group, where *Show again* deletes the
  resolution. Because the key names the chapter, moving the planned change to another chapter shows it again there. The
  follow-up stays to do: the decision's pill, the Decisions page and the front page are unchanged by *Not yet*.
- **No count while typing.** The gap lines are fetched with the items tied to the chapter, when the chapter opens and
  when Loose ends is shown, never per keystroke. Writing the first words of an empty chapter doesn't make a line appear
  until the chapter is next opened. Offline they are not shown, as the tied items aren't.

**With *Include planned*** (§14.6):

- The gap line is not a Continuity finding and isn't on Checks. It is about planned rows whatever the switch says, so
  the switch neither shows nor hides it.
- With the switch on, a finding that rests on a planned row that follows a decision adds `· decided 12 Oct 2026`, linking
  to the decision: `Varren is named in chapter 12, but is planned dead from chapter 9 · decided 12 Oct 2026`.
- The two are kept apart. Resolving that finding (*intentional*, *later*) doesn't touch the follow-up, and *Not yet*
  resolves no finding. Checks' list of resolutions leaves the `followup_gap` rule out.
- Making it canon here can bring the finding up with the switch off, since the checks now read the row as canon. That is
  the checks working.

**Data:** none beyond §16.6 and one more rule name in `resolutions`. Loose ends reads the gap lines from `GET
/chapters/<id>/gaps`, fetched beside `GET /chapters/<id>/items` as it is today; the facts and relationship endpoints'
`make_canon` takes a chapter with no passage.

*Done when*, with Varren's *status: dead* planned from chapter 9 as a follow-up and chapter 9 empty, chapter 9's Loose
ends shows no gap line; after a paragraph is written and the chapter reopened, it shows `Decided 12 Oct 2026: Varren ·
status: dead, from this chapter · not in the book yet`; *Not yet* hides the line, folds it under `Not yet · 1` and
leaves the decision `1 of 1 to do`, and *Show again* brings it back; moving the fact's span to chapter 10 (which has
text) shows the line there, and moving it back shows it in chapter 9 again only after *Show again*; *Make it canon here*
with a sentence selected makes the fact canon, established in chapter 9 with that sentence, and the decision `done`;
a fact planned from year 412 shows the line in each chapter set in 412 that has text, and in none set in 413 or with
no set time; the line is the same with *Include planned* on or off; with it on, Checks' finding for Varren named in chapter 12 adds
`decided 12 Oct 2026`; and nothing appears or changes while typing.

### 16.5 Surfacing

Where an open follow-up can be found, other than on its decision and in its chapter. All of it is lists to read when
wanted; nothing comes to the writer.

- **On the Decisions page**, a filter beside the project filter: **All · With open follow-ups**, kept in the address
  (`?followups=open`). It lists the decisions with something to do, oldest first, since those have waited longest, each
  with its follow-up list open. `4 decisions with 6 open follow-ups`.
- **On the front page** (§14.4), a section **To follow through**, after *Latest decisions*: the decisions with open
  follow-ups, oldest first, five, then `4 more · Decisions` (linking to the filter). Each line has its text, date,
  project and pill, and, when one of its planned changes is tied to a written chapter (§16.4), `chapter 9 is written`,
  linking into the chapter's Loose ends. Like every section there, it hides while empty.
- **Nowhere else**: no count in the nav, no badge on the Decisions link, no notification, no line in the editor outside
  Loose ends, nothing while typing. A to-do follow-up is never shown as late.

**Data:** none. `GET /decisions` takes `followups=open`; `GET /worlds/<slug>/front` gains `follow_through`.

*Done when* the filter on the Decisions page lists only the decisions with open follow-ups, oldest first, and survives a
reload; the front page's *To follow through* lists them with `chapter 9 is written` beside Varren's and hides once both
are done; and the nav shows no count.

### 16.6 Data model, export and Restore

```sql
decision_followups (
  id               uuid primary key,
  decision_id      → decisions      ON DELETE CASCADE,
  fact_id          → facts          ON DELETE SET NULL,  NULL
  relationship_id  → relationships  ON DELETE SET NULL,  NULL
  item_id          → items          ON DELETE SET NULL,  NULL
  what             text NOT NULL,   -- the row in words, kept for when it is gone
  dropped_on       date NULL,       -- by Drop, or by deleting its row
  created_by, created_at
)
-- CHECK num_nonnulls(fact_id, relationship_id, item_id) <= 1
-- UNIQUE (decision_id, fact_id), (decision_id, relationship_id), (decision_id, item_id)
-- a row with none of the three is dropped
```

**Why a table of its own**, and not a `decision_id` on facts, relationships and items:

- A follow-up has to outlive its row: a deleted planned fact still counts as *dropped* on the decision, with its words.
- Real foreign keys with `SET NULL` keep it whole, unlike a polymorphic `target_table, target_id` (as in `item_links`),
  which nothing cleans up.
- One row can follow two decisions.
- The three busy tables and their forms don't change.

`Decision.item_id`, the item a decision closed, stays as it is and is not a follow-up.

**Keeping it right:**

- `what` is written when the follow-up is made, and again whenever its row is saved through the facts, relationships or
  items endpoints, so it reads right when the row is later gone (`Varren · status: dead · from chapter 9`, `task: Plant
  the bell's crack in chapter 4`).
- Deleting a fact, relationship or item through the API sets `dropped_on` on its follow-ups in the same transaction.
  A task closed as rejected is worked out as dropped from its status, not stored. A row lost by a cascade (its entry
  deleted) leaves a follow-up with no row and no date, shown as `dropped`.
- An entry's delete warning (`3 relationships use…`) adds `2 of its facts follow decisions`.
- Done and to do are never stored (§16.2).

**Endpoints:**

- `POST /decisions/<id>/followups` takes either `{fact | relationship | item: <new row as its own endpoint takes it>}`,
  which makes the row and the link in one transaction, or `{attach: {table, id}}`.
- `POST /decisions/<id>/followups/<fid>/drop`, its undo, and `DELETE` (detach).
- `GET /decisions/<id>/followups`.
- `GET /decisions/<id>/chapters` returns the chapters the decision names (§16.1), so the server and the phone read
  numbers and titles alike.

**Export** keeps the links and makes them readable in plain text:

- A fact or relationship in an entry's frontmatter, and an item's frontmatter, carry `follows: [<decision id>, …]`.
  Decision ids are already in `Decisions.md`.
- `Decisions.md` lists each decision's follow-ups as indented lines under it, worked out for the reader:
  ```
  - 2026-10-12 · [the-salt-road] Varren dies at the end of chapter 9 <!-- id=… item=… entities=… -->
    - to do: Varren · status: dead · from chapter 9 (planned fact)
    - done: Plant the bell's crack in chapter 4 (task, accepted)
    - dropped 2026-10-22: Isolde knows about Varren · from chapter 11
  ```
  The decision line's form is unchanged, so `DECISION_RE` still reads it.

**Restore:**

- It makes the decisions as today, keeping a map from the export's decision ids to the new rows.
- After that it links each fact, relationship and item that has `follows:` (facts and relationships are made before the
  decisions today, so their `follows:` is kept aside until then).
- From `Decisions.md` it reads only the `dropped` lines, as follow-ups with no row, with their date and words. The to-do
  and done lines are worked out again from the rows.
- An older export has none of this, and its decisions come back settled.

*Done when* the table and endpoints above exist with their migration; deleting Varren's planned fact leaves the
follow-up dropped with `Varren · status: dead · from chapter 9`; deleting Varren himself leaves it dropped with no date;
and exporting and restoring a world keeps every follow-up, to do, done and dropped, with its decision, and
`Decisions.md` reads as above.

### 16.7 The demo world and the Guide

**The demo world** (backend/src/quarry/demo.py) gains two decisions with follow-ups, planted through the export layout
like the rest (`follows:` and `Decisions.md`). The decision *Oskar dies in chapter 2, not chapter 1* stays settled, so
all three states show.

- **Done**: `2026-10-06 · Ash Season · Hesper is a cartographer, and Ash Season shows her at her maps`, tagged with
  Hesper Quill. Its follow-up is her *trade: cartographer* fact, planned in the Journal in 2014 and already canon in
  *The Cartographer*. It shows `done`.
- **Not done**: `2026-10-08 · The Ferryman's Daughter · Brother Cade dies at Saltreach, in What the River Kept`, tagged
  with Brother Cade. Two follow-ups:
  - his *status: dead* fact, planned from chapter 3 (*What the River Kept*, which has text), so chapter 3's Loose ends
    shows the gap line, and *Include planned* still turns it into Ash Season's finding (§14.6);
  - a task, *Let Pell ask about the bells before Cade dies*, linked to chapter 3 and Brother Cade, accepted.

  It shows `1 of 2 to do`, and the front page lists it under *To follow through* with `chapter 3 is written`.

**The Guide** (§15) gains two steps rather than a walkthrough of its own, since the follow-up step belongs to closing an
item and the gap belongs to planning:

- **Walkthrough 2** (*A spark on the phone, sorted at the desk*): after the spark about the Wardens' toll is accepted
  with the decision `The toll is paid in lanterns, from The Crossing on`, the `+ follow-up` row shows. `t` makes the
  task *Show a lantern paid at the lock*, the River Wardens ticked and *The Crossing* offered and clicked. The Decisions
  log then shows the decision `1 of 1 to do`. About 20 seconds more.
- **Walkthrough 10** (*Planning in the Journal*): before *Include planned*, the front page's *To follow through* and
  Brother Cade's decision, its follow-up list, and chapter 3's Loose ends with the gap line. *Not yet* folds it.
  *Make it canon here* is only pointed at, since the walkthrough then needs his death planned for *Include planned*.
  About 30 seconds more.

The Guide's total becomes about 26 minutes. The end-to-end run plays both, as it plays every walkthrough (§15.3).

*Done when* loading the demo world shows the three decisions as settled, `done` and `1 of 2 to do`, chapter 3's gap
line and the front page's *To follow through*; and both walkthroughs play with no skipped step in the end-to-end run.

### 16.8 Not building

- **Mandatory follow-ups**, or any prompt that has to be answered: the step is skipped with Enter, and most decisions
  stay settled.
- **A manual done checkbox** on a decision: done is worked out from the rows, so it can't drift from them.
- **Reading the prose** to see whether a chapter shows the change: the writer says so with *Make it canon here*.
- **Reminders, nags, badges, due dates or "overdue"**: open follow-ups are found on the Decisions filter, the front page
  and a written chapter's Loose ends, when the writer looks.
- **Follow-ups of other kinds**: an event, a chapter status, a summary. A task covers anything else.
- **Decisions that follow decisions** (a decision superseding another): a new decision is written, and the old one's
  follow-ups are dropped or detached.

### 16.9 Open questions for phase 14

None left. Thomas's answers are in DECISIONS.md (2026-10-25):

- a task closed as rejected counts toward done but is listed as dropped (§16.2);
- a change set to rumour stays to do until it is canon or dropped (§16.2);
- a decision with no follow-ups shows no pill (§16.2);
- a change bounded by a time gives the gap line in the chapters set at that time that have text (§16.4);
- closing an experiment with a decision offers the follow-up step too (§16.3);
- the keys are `f`, `w`, `t` and `x` (§16.3);
- and phase 14 is built as one pull request: the table and endpoints, the forms and the step, the state and its pills,
  the gap line, the filter and the front page section, export and Restore, the demo and the two Guide steps.

## 17. Pictures (phase 15)

Thomas asked for "images of people, objects, places etc etc just like in a wiki". Today a world holds only text, so
a portrait of a character, a sketch of an object or a view of a place lives somewhere else. Moving the novel in (§8)
makes it urgent: one chapter opens with a picture, and Restore can only bring Markdown.

Phase 15 adds **pictures**. A picture is uploaded once into a world and placed where it is wanted: in a bible entry's
**gallery**, whose first picture is the entry's **main picture** (shown at the top of its page and on its cards, like
a wiki's infobox), or on a **line of its own** in a chapter, a journal entry or an entry's notes. The export carries
the picture files, and Restore links them up again.

The principles hold. Quarry stores and shows the pictures it is given. It never makes, changes, describes or tags
one: nothing reads what is in a picture (§1). A picture line is a note, as a margin note is: it is not counted, not
matched for names, and the compiled manuscript stays pure prose (Thomas). Pictures are never required anywhere.

Examples use made-up names. The world has the place *Greywick* and the character *Isolde*; *The Salt Road*'s ninth
chapter is *The Drowned Bell*.

### 17.1 A picture in a world

A picture belongs to **one world**. It has:

- a **name**, taken from its file name (`harbour-at-dusk.jpg` is *harbour-at-dusk*), which can be changed;
- its **size** in pixels, and three **files** made when it is uploaded (§17.4): the *full* picture, a *view* copy for
  pages and a *thumb* for galleries and cards.

It is placed in two ways, and one picture can be placed in any number of places:

- in an entry's **gallery** (§17.2);
- on a **picture line** in a text (§17.3).

A **caption** belongs to the place, not to the picture: the same view of Greywick can be *The harbour at dusk* on
Greywick's page and *Where Isolde lands* in chapter 9. A picture's files never change once it is uploaded: a better
picture of Greywick is a new picture, put in the old one's place.

**Adding a picture** needs the network: *Add pictures…* on an entry (§17.2), pasting or dropping a picture into a text
or *Picture…* in the editor (§17.3), and *Upload…* on the Pictures page. Offline, these say `Pictures need the
network` and do nothing else.

**The Pictures page**, a section of World settings, lists every picture in the world, newest first: its thumb, name,
size and where it is used. The count and size are at the top: `48 pictures · 61 MB`.

- **Where it is used** is the entries whose gallery has it and the texts that have a picture line for it: chapters
  (current, experiments and salvage), journal entries, entries' notes and the cuts bin. Old revisions don't count.
- **Rename** changes the name (`Undo` on the toast).
- **Delete** is offered only for a picture used nowhere, and asks first (`Delete harbour-at-dusk? This can't be
  undone.`). An old revision restored after its picture was deleted shows the placeholder `Picture deleted` on that
  line, and the line stays as written.

*Done when* a picture uploaded on the Pictures page lists as used nowhere and can be renamed and deleted; once it is
placed on Greywick's page and in chapter 9, it lists both and offers no Delete; and offline, *Upload…* says `Pictures
need the network`.

### 17.2 Pictures on an entry

Any entry, of any kind, can have a **gallery**: any number of pictures in an order, none to start with, each with an
optional caption. The **first** is the entry's **main picture**.

**On the entry page:**

- **The main picture** sits at the top right of the page head, beside the name, other names and one-liner, at most
  280 px wide, with its caption under it. On the phone it is full width under the name, at most 40% of the screen
  high. An entry with no pictures has no space for one.
- **A Pictures section**, after the notes, shows the whole gallery as thumbs in order, each with its caption.
  - *Add pictures…* opens the file picker for one or more files (on the phone it offers the camera or the gallery).
    Dropping files on the section does the same. Each file gets its own progress line, and the pictures join the
    end of the gallery.
  - *From the world…* opens a picker of the world's pictures (type to filter by name or by any of their captions).
  - Each thumb has a *More…* menu with *Make main*, *Caption…* and *Remove from this entry*. On the desk the thumbs can
    be dragged into a new order, and on the phone moved with arrows.
  - *Remove from this entry* takes the picture out of the gallery only. The picture stays in the world, on the
    Pictures page (`Undo` on the toast).
  - With no pictures, the section is one line: `Pictures · Add…`.
- **Clicking a picture** opens the **full view**: the view copy as large as the window allows, its caption and name,
  *Open full size* (the full file, in a new tab) and, for a gallery, ‹ › (or the arrow keys, or a swipe on the phone)
  through the entry's pictures. Esc closes it.

**On its cards.** The main picture's thumb, a small square cropped to its middle, sits in the corner of the entry's
card: the name card in the editor (resting on a name), the cards in a journal entry's side panel, and the card shown on
hover wherever a name links to its page. An entry with no picture shows its card as today.

Changes to a gallery are saved at once and aren't revisions; each has `Undo` on its toast. Deleting an entry removes
its gallery, and its pictures stay in the world.

*Done when* two pictures added to Greywick show as a gallery; *Make main* on the second puts it at the top of the page
and on Greywick's card when resting on the name in chapter 9; a caption shows under the main picture and in the gallery;
the full view steps through both with the arrow keys; *Remove from this entry* leaves the picture on the Pictures page
as used nowhere; an existing picture is added from *From the world…*; and on the phone the main picture is full width
under the name.

### 17.3 Pictures in the text

**A picture line** is a line with an image link to a picture, and nothing else:

```
![The harbour at dusk](picture:3f2a9c1e-8b4d-4c1a-9e57-2d6f0b8a41c3)
```

The caption may be empty (`![](picture:…)`), and spaces around the link are allowed. The full id is used, so the line
can't be mistaken for anything else. An image link inside a sentence, a link to a web address, or a line starting with
`%%` is not a picture line, and it is shown as written.

Picture lines work in **chapters** (in every state), **journal entries** and **entries' notes**. In items, decisions,
summaries and captions, an image link is only text.

**What a picture line is.** A picture line is treated as a margin note is (WORLD-MODEL.md §7):

- it is not counted in the word count, the word history or "has text" (§16.4);
- names in its caption are not matched as mentions, and the companion doesn't read it;
- it is left out of the compiled manuscript (Thomas).

It stays in the chapter, in its revisions and in its exported file (§17.6). Cutting it to the cuts bin, copying it into
an experiment and putting it back all work on the line, as on any text.

**In the editor** (chapters and journal entries), the line stays text that can be typed in, and the picture is drawn
under it:

- With the cursor elsewhere, the `(picture:…)` part is **folded** into a small chip, so the line reads `![The harbour
  at dusk] ▣`. The fold is one unit: the cursor steps over it, and Backspace just after it deletes the whole link
  (`Undo` brings it back). With the cursor on the line, the line shows in full.
- **Under the line**, the picture is drawn as a block: the view copy, at most the measure wide and 60% of the window
  high, with the caption under it in the interface's font. The block isn't text. The cursor moves from the line to
  the next line past it, and a click on it opens the full view (§17.2).
- **Smooth typing.** The block's height is reserved from the picture's stored size, so nothing jumps when it loads.
  Pictures are loaded only when their line is drawn, and typing in other lines never redraws them. The 10k-word
  chapter on a mid-range phone (§6) stays smooth with a dozen pictures in it.
- **Adding a picture.** Pasting a picture, or dropping a file onto the text, uploads it (`Uploading harbour.jpg…` at
  the foot). When it is done, a picture line `![](picture:…)` is put on its own line after the paragraph the cursor is
  in, with the cursor between the brackets for a caption. *Picture…* (in the command palette, and *More…* in the
  toolbar) offers *Upload…* or the world's pictures, filtered by typing, with the pictures of entries named in the
  text first.
- **A picture that can't be shown** leaves a box of its shape (or a short one when its size isn't known) with its
  caption and a word on why: `Not on this device` offline (§17.5), `Picture deleted`, or `Not a picture of this world`
  for a line copied from another world.

**Read-only.** Wherever these texts are shown read-only, a picture line shows as the picture with its caption under
it: an entry's notes on its page, *Read as if accepted* (§13.6.1) and a chapter opened read-only on the phone. While an
entry's notes are edited, the line shows as written, and pasting a picture into them puts a picture line at the cursor.

*Done when* pasting a picture into chapter 9 uploads it and puts `![](picture:…)` after the current paragraph with the
cursor in the caption; the picture shows under the line, and the link folds to a chip once the cursor leaves; Backspace
after the chip deletes the link and `Undo` brings it back; the word count, the mentions and the compiled manuscript are
the same with and without the line, whatever its caption says; `Isolde ![x](picture:…) waits` in a sentence stays text;
a picture line in Greywick's notes shows as the picture on the page; and typing in chapter 9 with six pictures stays as
fast as without them.

### 17.4 Upload, sizes and storage

**What is taken.** JPEG, PNG and WebP, recognised by opening the file, not by its name. Anything else (HEIC, GIF, TIFF,
PDF, SVG) is refused with `Quarry takes JPEG, PNG or WebP pictures`. SVG is never taken, since it can carry script. An
animated WebP keeps its first frame. A file may be up to **25 MB**, and a picture up to 50 megapixels. Several files
are sent one after another, one per request.

**What is kept.** On upload, the server (with Pillow, a new backend dependency) does this once:

1. It turns the picture the way its camera says it was held, and drops its metadata (location, camera, date).
2. A picture larger than **2400 px** on its longest side is scaled down to it (Thomas), and kept as the **full** file
   in its own format: JPEG at quality 90, PNG, or WebP at quality 90. Transparency is kept.
3. It makes two WebP copies: **view**, at most 1600 px, and **thumb**, at most 400 px. A smaller picture isn't scaled
   up: its copies are its own size.

So the full file is about 1–2 MB for a phone photo, the view copy about 300 KB and the thumb about 30 KB.

**Memory.** The container has 256 MB of memory (§9). JPEGs are decoded at a reduced scale (Pillow's draft mode), so a
phone photo never needs its whole size in memory. A PNG or WebP over 30 megapixels is refused, and one picture is
worked on at a time, with an upload waiting its turn.

**Where the bytes live: in Postgres** (Thomas), in a table of their own (§17.7), beside everything else. The managed
cluster's daily backups cover them, and restoring the database restores the pictures. There's no volume and no new
service. The files are stored without Postgres trying to compress them again (`STORAGE EXTERNAL`). At 2 MB a picture
with its copies, 200 pictures take about 0.5 GB.

**Serving.** `GET /api/pictures/<id>/full`, `/view` and `/thumb` check that the user is a member of the picture's world
and send the file with:

- its own type, and `X-Content-Type-Options: nosniff`;
- `Cache-Control: private, max-age=31536000, immutable`, since a picture's files never change;
- `Content-Disposition: inline` with its name.

The gzip middleware leaves pictures alone, since they are compressed already. Lists, entry pages and texts never carry
picture bytes, only ids with each picture's width and height.

*Done when* a JPEG of 4000 × 3000 px with a location in its metadata is kept as 2400 × 1800 px without it, with a
1600 px view copy and a 400 px thumb; a photo taken sideways shows upright; a PNG with transparency keeps it; an SVG, a
HEIC and a text file renamed `.jpg` are refused; a 30 MB file is refused; uploading a 50-megapixel JPEG keeps the app
inside its memory limit; and a picture of a world the user isn't a member of answers 404.

### 17.5 On the phone, and offline

The phone loads thumbs in galleries and on cards, and view copies in texts and the full view. It loads the full file
only on *Open full size*.

**In the offline copy.** When the device syncs a world (§4), after the chapters and journal entries, it fetches the
**view copy** of every picture used in them that it doesn't have yet:

- They go into a cache of their own, kept with the rest by `navigator.storage.persist()`. One picture is fetched at a
  time, so a sync is never held up by its pictures.
- A picture no longer used in any text on the device is dropped at the next sync.
- The offline copy also keeps each picture's name, width and height, so the box for a missing picture has its shape.
- Settings' *Offline copy* section adds `Pictures: 34 · 12 MB`.

**Everything else** (entry pages' galleries, thumbs on cards) is kept when first shown, in a second cache of at most
300 pictures, the oldest dropped first. Entry pages are read online anyway (§4).

**Offline, a picture that isn't on the device** shows as a box of its shape with its caption and `Not on this device`.
Text around it is untouched and can be typed in as usual.

*Done when* after a sync, chapter 9's picture shows on the phone in airplane mode; a picture on Greywick's page that was
never opened shows `Not on this device` in a text that uses it, at the right shape; removing the picture line from
chapter 9 drops its picture from the device at the next sync; and Settings shows the pictures' count and size.

### 17.6 Export and Restore

**Export** (§8):

- **`<world>/Pictures/<name>-<id8>.<ext>`**: each picture's full file as kept, with its name lower-cased and hyphened
  so paths need no escaping (`Pictures/harbour-at-dusk-3f2a9c1e.jpg`). The files are stored in the zip without being
  compressed again.
- **`world.md`** gains `pictures:`, one line per picture in the world (used or not) with its file and name:
  `- {file: Pictures/harbour-at-dusk-3f2a9c1e.jpg, name: harbour-at-dusk}`.
- **In every `.md` file**, `picture:<id>` becomes the picture's path **relative to that file**, so the export shows its
  pictures in any Markdown reader. In `Projects/The Salt Road/Manuscript/09 The Drowned Bell.md` the line becomes
  `![The harbour at dusk](../../../Pictures/harbour-at-dusk-3f2a9c1e.jpg)`.
- **An entry's frontmatter** gains `pictures:`, its gallery in order (the main picture first), with paths relative to
  the world folder: `- {file: Pictures/harbour-at-dusk-3f2a9c1e.jpg, caption: The harbour at dusk}`.
- **`manuscript.md`** leaves picture lines out, as it leaves out margin notes.

**Restore:**

- Every `.jpg`, `.jpeg`, `.png` and `.webp` file under `<world>/Pictures/` (at any depth) becomes a picture, made as an
  upload is (§17.4): opened, scaled down when larger than 2400 px, and given its copies. Its name comes from
  `world.md`, or else from its file name. A file Quarry doesn't take is skipped and named in the result.
- In every `.md` file, an image link on a line of its own whose path, read relative to that file (or else to the world
  folder), is one of those files becomes `picture:<new id>`. Paths written with `%20` or in `<…>` are read too.
  Links to web addresses, or to files that aren't in the zip, stay as written.
- Galleries come back from the entries' `pictures:`.
- A picture in the zip that nothing uses comes back as used nowhere. An export from before phase 15 has no
  `Pictures/` folder, and comes back as before.

So a zip made by hand, such as the one that moves the novel in (§8), only needs its image files under `Pictures/` and a
`![caption](relative path)` line where each belongs.

**Sizes.** Today the whole zip is read into memory, with a cap of 50 MB (`MAX_UPLOAD`) and 200 MB unpacked
(`MAX_UNPACKED`). Pictures would break both, so:

- **Restore** takes a zip of up to **1 GB**. The upload is kept on disk (as FastAPI's `UploadFile` already does), and
  the zip's files are read one at a time. The `.md` files together stay capped at 200 MB unpacked, and each picture at
  25 MB, with reading stopped at the cap whatever the zip claims. Pictures are made one at a time and flushed as they
  go.
- **Export** writes the zip to a temporary file on disk, reading each picture from the database in turn, and sends
  that file. It is never held in memory whole.
- **nginx**: the export and restore location gets `client_max_body_size 1g` and `proxy_read_timeout 600s`
  (`deploy/nginx-quarry.conf`, docs/deploy.md).
- Restore's result says `Restored, with 48 pictures` and lists any files it skipped.

*Done when* exporting a world with a gallery on Greywick, a picture line in chapter 9, one in a journal entry and an
unused picture gives a `Pictures/` folder of four files, links that open in a Markdown reader, and Greywick's
`pictures:`; restoring that zip gives back all four pictures, the gallery in order with its captions and both
picture lines showing; a hand-made zip with `![](<../../../Pictures/old map.png>)` restores with the picture linked; a
link to a missing file stays as written; and a 600 MB export restores without the app going over its memory limit.

### 17.7 Data model, in one place

```sql
pictures (
  id          uuid primary key,
  world_id    → worlds ON DELETE CASCADE,
  name        text NOT NULL,          -- from the file name; changed on the Pictures page
  format      text NOT NULL,          -- jpeg | png | webp: the full file's
  width       int NOT NULL,           -- the full file's, to reserve room before it loads
  height      int NOT NULL,
  size        int NOT NULL,           -- bytes of the full file
  created_by, created_at
)
picture_files (
  picture_id  → pictures ON DELETE CASCADE,
  kind        text NOT NULL,          -- full | view | thumb
  data        bytea NOT NULL,         -- STORAGE EXTERNAL: already compressed
  PRIMARY KEY (picture_id, kind)
)
entity_pictures (
  entity_id   → entities ON DELETE CASCADE,
  picture_id  → pictures ON DELETE RESTRICT,
  position    int NOT NULL,           -- 0 is the main picture
  caption     text NOT NULL DEFAULT '',
  PRIMARY KEY (entity_id, picture_id)
)
```

- **Why the bytes have a table of their own:** lists, entry pages and the Pictures page read pictures without loading
  any files.
- **Texts point at pictures by id in their Markdown**, with no foreign key, like names. That is why a picture is
  deleted only when nothing uses it (§17.1), and why a line whose picture is gone shows a placeholder instead of
  failing.
- **The picture line** is recognised by one pattern, kept beside the margin-note pattern in `margin.py` and its twin
  in the frontend: `^[ \t]*!\[([^\]\n]*)\]\(picture:([0-9a-f-]{36})\)[ \t]*$`.

**Endpoints:**

- `POST /api/worlds/<slug>/pictures` takes one file and returns the picture.
- `GET /api/worlds/<slug>/pictures` returns every picture with where it is used.
- `PATCH /api/pictures/<id>` changes the name. `DELETE /api/pictures/<id>` answers 409, with the uses, when the picture
  is used.
- `GET /api/pictures/<id>/{full,view,thumb}` returns the files (§17.4).
- `PUT /api/entities/<id>/pictures` takes the gallery in order (`[{picture, caption}]`).
- An entry's detail gains `pictures` (id, caption, width, height), and the cards gain `picture`, the main picture's id
  or null.
- The offline sync's answer (§4) gains `pictures`: the id, name, width and height of each picture used in the texts it
  sends.

### 17.8 The demo world and the Guide

**The demo world** (backend/src/quarry/demo.py) gains three made-up pictures, **drawn in code** with Pillow when the
demo is loaded, so no image files are added to the repository:

- Marrow Locks gets two: a lock gate in flat shapes, *The upper gate*, as its main picture, and a plan of the locks,
  *The locks from above*.
- The Brass Compass gets a compass rose, *The compass, closed*.
- Chapter 3 of The Ferryman's Daughter (*What the River Kept*) opens with a picture line of the compass, captioned
  *The brass compass*.

They go in through the export layout like the rest of the demo: files under `Pictures/`, `pictures:` in frontmatter,
and a link in the chapter.

**The Guide** (§15) gains one step. In **walkthrough 4** (*The bible*), after Tamsin Vey's page comes Marrow Locks' page,
with its main picture at the top. The step opens the full view and steps to the plan, then uses *Make main* on the plan.
It only points at *Add pictures…*, since that is a file picker. About 20 seconds more, so the Guide's total is about 26
minutes. Walkthrough 3 needs nothing new: chapter 3's picture is simply there.

**Tests** use made-up pictures drawn in the tests (Pillow), never photos or drawings of anything real, and no story
content (§1).

*Done when* loading the demo world shows Marrow Locks with its main picture on its page and card, the compass at the
top of chapter 3 (also on the phone in airplane mode after a sync), and three pictures on the Pictures page; and
walkthrough 4 plays the new step with no skipped step in the end-to-end run.

### 17.9 Not building

- **Editing pictures**: no cropping, rotating (beyond turning the picture the way its camera held it), filters,
  drawing or marking up. A picture is changed by uploading another.
- **AI of any kind**: no generated pictures, no captions, descriptions or tags made by a model, no recognising faces or
  places, and no "similar pictures". Captions are the writer's own words (§1).
- **Pictures in the compiled manuscript** (Thomas). They are in the chapter files of the export.
- **Albums, folders or tags** for pictures: the Pictures page and where each is used are enough.
- **Pictures on captures, items and decisions**, and **sharing a picture to Quarry** from the phone's gallery: a
  picture is added where it belongs, on an entry or in a text.
- **Pictures from a web address**: a picture is uploaded, so the export holds it.
- **Video and sound.**
- **Thumbs in the bible tables**: the main picture is on the entry page and its cards.

### 17.10 Toward a drawn map

The drawn map (an uploaded map image with places pinned on it, WORLD-MODEL.md §6) stays on the later list (§21), and
isn't specified here. This work makes it smaller: the map image is a picture, uploaded, kept, copied for the phone,
cached offline and carried by the export and Restore as above. What is left for it is the pins (a picture, a place
entry, and where on the picture it sits, as fractions of its width and height), the view that draws them with *as of*,
and perhaps a larger size limit for maps than 2400 px, which is for that spec to decide.

### 17.11 Decisions for phase 15

Thomas's answers are in DECISIONS.md (2026-10-26):

- the bytes live in Postgres, in a table of their own, rather than on a volume or in object storage (§17.4);
- a picture is scaled down to 2400 px on upload and its metadata dropped, rather than kept as uploaded (§17.4);
- picture lines are left out of the compiled manuscript (§17.3);
- the demo world gets three made-up pictures drawn in code, and walkthrough 4 one step (§17.8).

## 18. A chapter's plan (phase 16)

Thomas plans a chapter by writing a planning session first (what has to happen, who is there, what it is for, loose
ideas), then writes the chapter with that plan open beside it, half the screen each. He goes back to the plan while
writing, adds to it, and some plans exist before their chapter does; a chapter can have more than one (a first plan,
and a second after the first didn't hold). Today a plan can live in the Journal, but nothing ties it to its chapter, and
the editor shows one text at a time.

Phase 16 keeps that flow and builds it from what exists. **A plan is a journal entry** marked as a plan and **linked to
its chapters**, and the chapter page can **open it beside the chapter**, in the same editor the Journal already has
(§14.1.1): names coloured, cards, *Record a fact* as planned, sparks and questions from a passage, `??` loose ends,
autosave, History and the offline copy. Nothing new is written, only a link and a second pane.

Considered and not chosen (Thomas): a new kind of plan document owned by one chapter, which would repeat the Journal's
tools and couldn't cover several chapters; and a plan assembled only from structures (planned facts, tasks, decisions
tied to the chapter), which loses the free planning session that comes first.

The principles hold. Nothing here writes, suggests or judges story content: the plan is the writer's own text, shown as
written. Nothing has to be filled in: a chapter needs no plan, a plan needs no chapter, and the split opens only when
asked. Nothing appears while typing. The compiled manuscript stays pure prose: the plan is never part of the chapter's
text.

Examples use made-up names. In *The Salt Road*, chapter 4 is *The Quay*. The Journal has *Plan: The Quay* (3 October
2026) and a second, *The Quay again* (14 October 2026), written after the first draft stalled, and *After the flood*
(20 October 2026), a plan for a chapter not written yet.

### 18.1 A plan is a journal entry

- **The mark.** A journal entry's head gains a small **Plan** switch beside its project. A plan is an ordinary journal
  entry in every other way: dated, in the Journal list, read by the planning reading (§14.2) and *since this was
  written* (§14.5), exported in `Journal/`.
- **Linked to chapters.** A plan's head shows what it is for: `Plan for: chapter 4, The Quay · + chapter`. *+ chapter*
  picks from the current chapters and experiment drafts of the plan's project (of every project, for a plan with no
  project), type to filter. Each chapter is a chip with `×` to unlink, and *Undo* in its toast. Linking an entry that
  isn't marked as a plan marks it.
- **Several of each.** One plan can be for several chapters (a plan for chapters 4 to 6 opens beside each of them), and
  a chapter can have several plans (*Plan: The Quay* and *The Quay again*).
- **From the chapter.** The chapter's side panel has a **Plans** section listing its plans, newest first, each with its
  date and *Open beside*; under them **New plan**, which makes a journal entry dated today in the chapter's project,
  titled `Plan: The Quay`, marked and linked, and opens it beside the chapter; and **Link a plan…**, a picker of journal
  entries (plans with no chapter yet first, then other plans, then other entries, newest first, type to filter).
- **Unmarking.** Switching *Plan* off on an entry linked to chapters says so first (`This is the plan for chapter 4, The
  Quay. Unlink it and unmark it?`) and removes the links, with *Undo*.
- **In the Journal list**, a plan carries a quiet tag after its date, `plan · chapter 4, The Quay` (`plan · 3
  chapters`, `plan · no chapter yet`), and the list gets a filter **All · Plans**, kept in the address (`?plans=1`).
- **Deleting** a plan says so in the journal entry's delete warning (`It is the plan for chapter 4, The Quay.`); the
  links go with it. Deleting a chapter (only an empty one with no history can be) removes its links; the plan stays.
- **Linking, unlinking and the mark need the network**, as a journal entry's date and project do (DECISIONS,
  2026-10-25). Reading and editing a plan works offline (§18.2).

*Done when* *Plan: The Quay* switched to *Plan* and linked to chapter 4 shows `Plan for: chapter 4, The Quay` in its
head and `plan · chapter 4, The Quay` in the Journal list, where *Plans* lists it; *New plan* in chapter 4's side panel
makes *Plan: The Quay* dated today, linked and open beside the chapter; *Link a plan…* adds *The Quay again* as a second
plan; a plan linked to chapters 4 and 5 is listed in both chapters' Plans; and unmarking a linked plan asks first and
unlinks it, with *Undo*.

### 18.2 The plan beside the chapter

**On the desk.**

- **Opening it.** **Plan** in the chapter's toolbar, beside *Panel* and *History*, splits the page: the chapter on the
  left, the plan on the right. **Ctrl+Shift+P** opens the split and puts the cursor in the plan; pressed again it moves
  the cursor back to the chapter, and so on between the two. *Plan* again, or the plan pane's `×`, closes the split. A
  chapter with no plan opens the split on an empty pane with *New plan* and *Link a plan…*.
- **Half each, to start.** The two panes share the page's whole width (the editor's width, DECISIONS 2026-10-25), half
  each, with a divider between them that drags from 30% to 70%; a double-click puts it back to half. The divider's place
  is kept per device. Each pane centres its text at up to the editor's measure (about 70ch) and wraps it to the pane when
  the pane is narrower. While the split is open the companion panel folds away; *Panel* opens it again, over the chapter's
  side, and it is the chapter's companion.
- **Several plans** show as tabs at the top of the plan pane, newest first (`Plan: The Quay · 3 Oct` · `The Quay again ·
  14 Oct`), with *Open in the Journal* beside them. The tab last chosen is kept per chapter on the device.
- **The plan pane is the journal editor**, editable, so planning goes on while writing: names coloured, cards, the
  quick-fix strip, the selection strip (*Record a fact*, *Record as event*, *Spark*, *Question*), F8 within the plan,
  search in it (Ctrl+F while the cursor is there), its own save status, word count, autosave, revisions and conflict
  copies, as for any journal entry. Each pane has its own undo. The journal entry's side panel isn't shown; *Open in the
  Journal* has it.
- **Cards in the plan pane** read as of the chapter beside it, not the end of the story, since the plan is about that
  point: planned rows show, marked `planned`, as in the Journal (§14.1.1).
- **Drafting and Revising** is one switch for the page; focus mode and typewriter scrolling apply to the pane the cursor
  is in.
- **What stays the chapter's.** The page is the chapter's: its title, toolbar, Checkpoint (Ctrl+S checkpoints the pane
  the cursor is in), History button (the chapter's; the plan's History is in the Journal), word history, and the note for
  next time asked on leaving (words typed in the plan don't count toward its 30). Leaving from the split doesn't ask for
  the plan's own note.
- **Remembered.** Whether the split was open, and on which plan, is kept per chapter on the device, so a chapter opened
  again comes back as it was left. A chapter never opens its plan by itself the first time. `?plan=<journal id>` in the
  address opens the split on that plan, which is how links into it work (§18.3).
- **Narrow windows.** Where the window is too narrow for two readable panes (under 1,000 px), *Plan* toggles as on the
  phone.

**On the phone**, and in narrow windows:

- **Plan** in the chapter's toolbar flips the screen between the chapter and the plan, full screen each; a tab at the
  top says which is shown (`The Quay · Plan`) and flips back. Each keeps its own scroll and cursor, so flipping back and
  forth costs nothing. Several plans are chosen with the same tabs, above the plan.

**Offline.** Plans are journal entries, so they are in the offline copy (§14.1.1), and the offline copy carries each
entry's mark and its chapters, so the split opens, reads and takes typing with no network.

**Performance.** Typing in one pane does no work in the other: the other pane only updates when its own text changes.
The typing budget (DECISIONS, 2026-10-22) holds in either pane with a 10,000-word chapter beside a 10,000-word plan and
400 entries, also at 4× slower CPU.

*Done when* *Plan* on chapter 4 opens *Plan: The Quay* on the right half with its names coloured; Ctrl+Shift+P moves the
cursor between the two and typing in the plan autosaves it as a journal revision; the divider drags and keeps its place
after a reload; the tabs switch to *The Quay again*; a card in the plan shows a fact planned from chapter 6 as not yet
holding at chapter 4; closing and reopening chapter 4 brings the split back on the same plan; on the phone *Plan* flips
to the plan and back with the cursor where it was in each; in airplane mode the split opens and takes typing; and the
typing budget holds in both panes.

### 18.3 A plan before its chapter

A plan can be written long before its chapter exists, and needn't know where the chapter will go.

- **On the project page**, under the manuscript list, a section **Plans with no chapter yet**: the project's plans
  linked to no chapter, oldest first, each with its date, title, first line and **Start a chapter from it** · *Open*.
  It hides while empty.
- **Start a chapter from it** asks where, in one row: *at the end* (the default) or *after chapter …* (a picker of the
  project's chapters). It makes an empty current chapter there, titled as the plan is (and editable as any title), links
  the plan to it, and opens the chapter with the plan beside it (`?plan=`). The toast says `Chapter 7, After the flood ·
  from its plan · Undo`; *Undo* deletes the chapter while it is still empty and has no history, as deleting a chapter
  allows, and the plan is back under *Plans with no chapter yet*.
- **A plan with no project** (for the whole world) is found under the Journal's *Plans* filter; *Start a chapter from
  it* there asks for the project first.
- **On the manuscript list**, a chapter with plans shows a small quiet `plan` (`2 plans`), which opens the chapter with
  its plan beside it.
- Nothing else counts or lists plans: no plan count in the nav, nothing that asks for a plan.

*Done when* *After the flood*, a plan in *The Salt Road* linked to no chapter, is listed under *Plans with no chapter
yet*; *Start a chapter from it* after chapter 6 makes an empty chapter 7, *After the flood*, opens it with the plan
beside it and drops the plan from that list; *Undo* deletes the chapter and lists the plan again; a whole-world plan
asks for a project first; and chapter 4 shows `2 plans` on the manuscript list.

### 18.4 From the plan to the chapter

A plan is reference: it isn't ticked off, and Quarry doesn't say whether the chapter follows it. What is worth keeping
track of goes through the structures that already have a state, and the link makes them reach the chapter in one step.

- **Record a fact** (§14.1.2) in the plan pane records the fact as *planned*, planned in the plan with the passage, as in
  any journal entry. Its span picker offers the chapter beside it, as a decision's named chapter is offered (§16.1):
  `The chapter beside: chapter 4, The Quay · From · Until`, used only after a click. In the chapter, *Make it canon here*
  then works as it does today.
- **A spark, question or task from a passage** of a plan (§14.3.1) gets a chapter chip: in the split, the chapter beside
  it, **ticked**; in the Journal, each of the plan's chapters, ticked when there is just one. The item is linked to the
  plan with the passage, as today, and to each ticked chapter, so it shows in that chapter's Loose ends.
- **Decisions** made while planning a chapter take follow-ups as in §16; nothing new.
- **No links from a plan line to a paragraph** (Thomas). A position kept for a line drifts as the chapter is rewritten,
  and an anchor in the chapter's text would put the plan into the prose. The link is the chapter.
- **Nothing is ticked.** A plan has no *followed* or *done*; the writer can strike a line out or write `done` in it, which
  is just text.
- **Experiments.** Starting an experiment links each draft to the plans of the chapters it replaces: a draft from a copy
  gets its own chapter's plans, a draft from scratch the plans of every chapter in the range (an experiment that only adds
  chapters links none). Accepting or rejecting changes no links: a retired chapter keeps its plans, and the plan's chip
  for it says `in Salvage`. Plans aren't part of the review before retiring (§13.6.2); nothing about them can break.

*Done when* *Record a fact* in *Plan: The Quay* beside chapter 4 offers `The chapter beside: chapter 4, The Quay`, and the
fact is planned in the plan from chapter 4 after a click; *Question* on a passage of the plan in the split ticks chapter 4,
and the question shows in chapter 4's Loose ends; an experiment on chapter 4 from a copy has both plans beside its draft;
after accepting it, *Plan: The Quay* is for the new chapter 4 and shows the old one `in Salvage`; and there is nowhere to
tick a plan done.

### 18.5 Data model, export and Restore

```sql
journal        + is_plan boolean NOT NULL default false
chapter_plans (
  chapter_id   → chapters  ON DELETE CASCADE,
  journal_id   → journal   ON DELETE CASCADE,
  created_by, created_at,
  PRIMARY KEY (chapter_id, journal_id)
)
```

A table of its own because the link runs many to many both ways. Linking an entry sets `is_plan`; the mark is kept on its
own so a plan with no chapter yet is still a plan.

**Endpoints:**

- `PATCH /journal/<id>` takes `is_plan`, saved without the version check, as a journal entry's date and project are;
  `false` removes its links.
- `PUT` and `DELETE /journal/<id>/chapters/<chapter id>` link and unlink.
- `POST /journal/<id>/start-chapter` takes the project and `after` (a chapter id, or none for the end), and returns the
  new chapter.
- `GET /chapters/<id>` carries its plans (id, title, date); `GET /journal` carries each entry's `is_plan` and chapters,
  and takes `plans=1` and `plans=unlinked` with a project; `GET /offline` carries the same for the journal entries it
  sends.
- `POST /items` already takes a journal entry with a passage; with it, it takes `chapter_ids` to link as well.
- Starting an experiment links its drafts in the same transaction (§18.4).

**Export** writes, in a journal entry's frontmatter, `plan: true` and `chapters: [<chapter id>, …]` (current,
experiment or retired). **Restore** reads the Journal after the chapters, so it relinks them through its map of the
export's chapter ids; a chapter id it can't find is skipped, and the entry stays a plan. An older export has neither key.

**For the move from the Google Doc** (§8), a plan is a file in `Journal/` like any other, with `plan: true`, `project:`,
and `chapters:` naming the `id`s of the chapter files it is for; a plan for a chapter not written yet has no `chapters:`
and is listed under *Plans with no chapter yet*.

*Done when* the table and endpoints exist with their migration; deleting a plan or an empty chapter removes their links;
and exporting and restoring a world keeps every plan with its chapters, including one for a retired chapter and one with
no chapter.

### 18.6 The demo world and the Guide

**The demo world** (backend/src/quarry/demo.py) gains three plans, planted through the export layout like the rest:

- *What the River Kept, first plan* (2026-09-20) and *What the River Kept, again* (2026-10-04), both for chapter 3 of
  The Ferryman's Daughter, so it shows two tabs. The second has a fact on Brother Cade recorded from it as planned and a
  `??` line.
- *After the Locks* (2026-10-18), a plan in The Ferryman's Daughter with no chapter yet, under *Plans with no chapter yet*.

**The Guide** (§15) gains a fourteenth walkthrough:

| # | Walkthrough | Min | What it does |
|---|---|---|---|
| 14 | Planning a chapter | 1 | Chapter 3 with *Plan* open beside it; the two plans' tabs; a line typed in the plan and Ctrl+Shift+P back to the chapter; a card in the plan as of chapter 3; a question from a plan passage, ticked for chapter 3 and in its Loose ends; *After the Locks* on the project page and *Start a chapter from it*; the same chapter on the phone, flipping to the plan and back. Points at dragging the divider. |

The Guide's total becomes about 27 minutes, and the end-to-end run plays it with the others (§15.3).

*Done when* loading the demo world shows chapter 3 with `2 plans`, both in its split, and *After the Locks* under *Plans
with no chapter yet*; and the walkthrough plays with no skipped step in the end-to-end run.

### 18.7 Not building

- **A plan template**, beats, scene cards or an outline structure: a plan is written freely, as the Journal is (§14).
- **Links from a plan line to a paragraph**, stored positions or anchors in the prose (§18.4).
- **A followed or done state** on a plan or its lines; facts, tasks and decisions carry state where it is wanted.
- **Opening the plan by itself**, or any prompt to write one.
- **Scrolling the plan with the chapter**: the two panes scroll on their own.
- **Other things beside the chapter** (another chapter, an entry page): cards, the thread reading and History cover
  those; the split is for the chapter's plan.

### 18.8 Open questions for phase 16

None left. Thomas's answers are in DECISIONS.md (2026-10-26):

- a plan is a journal entry, marked as a plan and linked to its chapters, opened beside the chapter (§18.1, §18.2);
- a plan for a chapter not written yet waits on the project page until *Start a chapter from it* (§18.3);
- no links from plan lines to paragraphs; the link is the chapter (§18.4);
- and on the phone, *Plan* flips between the chapter and the plan (§18.2).

## 19. A byline (phase 17)

Thomas: "I'd like to have byline as a thing." A book can carry a line under its title, as a cover does: *A Salt Road
Tale*, *As told by the ferryman's daughter*, or a pen name. Today a project has only its name.

Phase 17 adds a **byline**: one optional line of text on a project. It is the writer's own words, shown as written;
nothing is made from it.

- **Where it is set.** The project's *Edit* form gains *Byline*, under *Name*: one line, up to 200 characters, empty
  for none (the hint says `Shown under the title, as on a cover`).
- **Where it shows.** Under the title on the project page and on the Read page (§13.6.1), in italics, and in the
  compiled `manuscript.md` of the export as an italic line under `# <name>`. Nowhere else: not in the nav, the
  chapter pages or the bible.
- **Export and Restore.** `project.md` gains `byline:` (left out when empty). Restore reads it; an export from before
  phase 17 has none, and the project has no byline.

```sql
projects + byline text NULL   -- at most 200 characters, NULL for none
```

`PATCH /projects/<slug>` takes `byline` (an empty string clears it); the project carries it wherever projects are sent.

*Done when* a byline set in *The Salt Road*'s Edit form shows under its title on the project page and the Read page and
under `# The Salt Road` in the exported `manuscript.md`; clearing it removes it everywhere; and exporting and restoring
keeps it, while an older export restores with none.

## 20. Dated earlier versions in the export (phase 18)

Today an export carries each chapter's text as it is now, and Restore starts its history over: a chapter's text comes
in as a `start` revision dated the day of the restore, which counts as no words (§11.5). Moving the novel in (§8)
brings years of writing whose history is known day by day, and Thomas wants it kept: History should go back to when
it was written, and the word chart (§11.5) should show the days it was written on.

Phase 18 lets the export carry **dated earlier versions** of chapters and journal entries, and Restore read them back
as revisions on their dates. Revisions are still kept in the database, and the database's backups stay the way to
restore everything (§8); the export carries the history that matters for moving a world.

**In the zip.** One file per revision, under `<world>/History/` at any depth. Folder and file names are for people;
Restore reads the frontmatter:

```
<world>/History/The Salt Road/04 The Quay (3f2a9c1e)/2026-03-05 2210.md
---
chapter: 3f2a9c1e-8b4d-4c1a-9e57-2d6f0b8a41c3   # the chapter's id in the export (or journal: <id> for an entry)
at: 2026-03-05T22:10:00+01:00                  # when; a bare date (2026-03-05) means 12:00 UTC that day
reason: checkpoint                              # optional: autosnap (the default), checkpoint or start
label: first draft done                         # optional, with a checkpoint
title: The Quay                                 # optional: its title then (the chapter's own when left out)
---

The whole text at that moment, as in the chapter's own file.
```

**Restore** reads them after the chapters and the Journal, a file at a time:

- Each chapter's (and journal entry's) revisions are made in the order of `at`, dated `at`. A file whose id matches no
  chapter or entry in the zip is skipped.
- **The word history counts them on their days.** The first one counts its words as written on its day (from an empty
  chapter), unless it says `reason: start`, which counts none (for text that came from elsewhere); each later one counts
  what changed since the one before, on its own day. A journal entry's revisions fill its History only: the Journal
  never counts (§14.1.1).
- **The chapter's own file is its current text.** When it is the same as the last dated revision, nothing more is
  added; when it differs, it comes in as a `start` revision dated the restore, which counts none, as today.
- A chapter or entry with no History files, and an export from before phase 18, restore as before.
- History files are read one at a time, each at most 10 MB, and don't count toward the 200 MB of the other `.md`
  files (§17.6).

**Export** writes them too, so exporting and restoring keeps History and the word chart: for each chapter (in every
state) and journal entry, its **last revision of every day** it has revisions on (days in UTC), and **every labelled
checkpoint**, each with its `at`, `reason` and `label`. Conflict copies are left out. A world written over two years is
some thousands of small files: a few tens of MB before compression.

So the history of a book brought in from elsewhere needs one file per day it changed, the last one the same as the
chapter's file.

*Done when* a hand-made zip with three dated versions of a chapter (the last one its current text) restores with those
three revisions in History on their dates, and the project's word chart shows the words written on each of those days;
one marked `reason: start` counts none; a chapter whose file differs from its last version gets a `start` of today; a
journal entry's versions fill its History; exporting a world and restoring it keeps each chapter's last version of each
day and its labelled checkpoints, and the word chart shows the same days of writing (each day's words as what
changed over the day, a rough picture as ever); and an export without `History/` restores as before.

## 21. Out of scope (for now)

- AI features of any kind in the story path
- Co-writing features: inviting people, permissions beyond owner, comments, presence (the data model is ready for them; see §7)
- Rich text beyond Markdown
- Real-time collaborative editing or CRDTs
- Native apps (the PWA is enough on Android)
- A git mirror of the content (§8)
- A drawn map: uploaded map images with pinned places stay on the later list (WORLD-MODEL.md §6). The chart (§13.7)
  is schematic and doesn't replace them. Pictures (§17) carry the image, so what is left is the pins (§17.10).
- From the plan-first comparison (phase 13, §14), deliberately not built:
  - questionnaires, templates or prompts for worldbuilding: the Journal is written freely and swept afterwards
    (§14.1);
  - a rules engine for magic or other forces: a system is a Term entry with facts, and Quarry doesn't evaluate it;
  - a motif tracker: a motif can be a Term entry, and its mentions strip and both thread readings (§11.4, §14.2)
    show where it recurs;
  - forking a world for versions: alternatives are question items, choosing one is a decision, and the Journal keeps
    the dated thinking; experiments stay for chapters;
  - calendars, or packs of real history: time stays a sortable number (§13.1.1);
  - a soundtrack feature: the share target already records where a link came from.

## 22. Open questions

- Should experiments also be allowed for entities ("what if this character were…") or only for chapters?
- Should journal entries be lockable after a period to keep them truly append-only, or stay freely editable?
- Is a light theme needed at all, or dark only?
- The domain (likely `quarry.daevil1.com`), which fixes the passkey Relying Party ID.
