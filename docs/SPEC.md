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
| **Entity** | A bible page in a world: character, place, term, faction, object or other. Has a name, aliases and a body. Lives at world level (shared by every project) or in one project's part of the bible (§12.4); either way it is matched in every project. |
| **Item** | Anything that needs attention: `spark`, `question`, `task` or `experiment`. Status is `open`, `accepted`, `rejected`, `harvested` or `deferred`. Belongs to a world and optionally to one project (an idea about the world in general has no project). Can link to entities and chapters. |
| **Journal entry** | Dated thinking-on-paper (the "What now?" kind of writing). World-level or project-level. Editable, but conceptually append-only. |
| **Decision** | A dated one-line verdict ("chapter 3 is now told by the sister"), optionally tied to the item it closes. World-level or project-level. |
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
3. It flags a **near miss** when a capitalised word of at least 5 letters is no known name but is one edit away from a word of an entity's name or alias (two edits for words of 7 letters or more; a swapped pair of letters counts as one edit), and is not in `name_ignores`. A word that is part of any name, or differs from one only in capitals, is never flagged. A typo such as "Varen" for Varren would be flagged.

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
- **Bootstrap.** With zero users, `/setup` accepts a one-time `QUARRY_SETUP_TOKEN` from the environment, creates the first user and registers the first passkey, shows the recovery codes, then asks for the first world. After that, setup is disabled.
- **More devices.** From a signed-in session, choose "Add passkey" (desktop and the Android phone via Google Password Manager).
- **Recovery.** Ten one-time recovery codes are generated at setup and stored hashed. A CLI command `quarry passkey reset <user>` recovers from the server shell.
- Sessions use an httpOnly, Secure, SameSite=Strict cookie with a 30-day sliding expiry. CSRF is covered by SameSite plus an Origin check. Login is rate-limited.

## 8. Export, backups and import

- **Backups.** The Postgres server's own backups are the disaster-recovery path. Every revision lives in the database, so restoring the database restores the full history.
- **Export now.** Downloads a zip with one folder per world: `world.md`, `Bible/<Kind>/<Name>.md`, `Journal/`, `Decisions.md`, `Planning/<status>/` (items for the whole world), and per project `Projects/<Name>/` with `Manuscript/` (numbered in order), `Experiments/`, `Salvage/`, `Planning/` and a compiled `manuscript.md`. YAML frontmatter carries ids, state, POV, tags and aliases; the layout is documented in `backend/src/quarry/api/transfer.py`.
  From phase 10, chapters also carry their summary and status, `project.md` the project's statuses, and each project has a `Cuts/` folder (§11).
  From phase 11, bible entries also carry the project they belong to (`project:`, §12.4).
- **Restore.** Imports an export zip as a new world (with new ids; every link between files is kept), recreating projects, chapters (current, experiments, salvage with harvest notes), entities, items with their tags, journal, decisions and "not a typo" words from the files and their frontmatter. It is the only import path: there is no importer for other tools' formats. Revision history stays in the database and is not part of an export.
- **Moving the existing material in.** Quarry starts empty. Once the editor is usable (after phase 4), Thomas provides the current Google Doc and Claude converts it by hand into the export layout: chapters, bible entries, planning notes as items or journal entries, and old chapters as retired chapters, with anything uncertain listed for Thomas to decide. The result is loaded with Restore and merged with whatever was captured in Quarry in the meantime. This is a one-time migration, done outside the repo.
- **Later, if wanted.** A scheduled export into a git repo (a local repo on the server, or a remote one) can be added as an optional setting. It is not part of the plan.

## 9. Tech stack, deploy and repo

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, py_webauthn, rapidfuzz (near misses) |
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
11. **More views of the bible**: a mentions strip on each entry page, a family tree with kin worked out, a grid of any entries across chapters, world entries and project entries, the *witnessed* type and *pronunciation* and *gender* facts, and labels and values (value suggestions, filtering by a value, a Labels page, labels with several values, expected labels). Designed in §12, with a *done when* per part.

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
stores: mentions, relationships, "is at" and the story order. Nothing new has to be filled in: the two new fields
have defaults (a project's gap length, §12.1, and an entry's level, §12.4, which is set for you), §12.5 adds one
relationship type and two suggested facts, and §12.6 makes the facts typed so far easier to keep consistent, with
one small table of per-label switches.
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
  - **aunt or uncle / niece or nephew**, and **cousin** (children of siblings); more distant blood relatives are
    just *relative*;
  - by marriage: **parent-in-law / child-in-law**, **sibling-in-law** (a spouse's sibling or a sibling's spouse), and
    **step-parent / stepchild** (a spouse's child who isn't their own).
- **The words** follow the relative's *gender* fact as of the chosen chapter, where there is one: *sister*,
  *grandfather*, *aunt*, *nephew*, *mother-in-law*, *stepdaughter*. Quarry has no gender field, so this reads a fact
  labelled *gender* or *pronouns* (any capitals): *woman*, *female*, *f*, *she* … give the female word, *man*,
  *male*, *m*, *he* … the male one. Anything else, or no such fact, gives the plain word (*sibling*, *parent's
  sibling*, *sibling's child*). *Cousin* is the same for everyone. Recorded relationships keep their own labels.

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
*grandfather* and Isolde *aunt* (their *gender* facts say so); Isolde's page lists *brother: Oswin*, *niece:
Mirelle* and *stepmother: Seyla*, dimmed and with their paths, while a relative without a *gender* fact gets the
plain word; none of them adds a relationship row; and as of chapter 2 Seyla is in neither the tree nor Isolde's
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

### 12.5 Two small additions

- **Witnessed.** A new starting relationship type, character → event: *witnessed* / *witnessed by* (`Varren
  witnessed the Burning of the Quay`). It is not *took part in*: a witness was there and saw it, which is what "who
  knows what" turns on. Nothing is worked out from it; the companion doesn't turn it into *knows about*.
  - **New worlds** and the demo get it with the starting vocabulary.
  - **Existing worlds** get it from a data migration: it is added, at the end of the Character–event types, to every
    world that has no character–event type already reading *witnessed* (either way, any capitals).
  - **Restore** keeps the export's own vocabulary, as now: a world restored from an export made before phase 11 has
    no *witnessed* until it is added on the types page.
- **Pronunciation** and **gender.** *Pronunciation* is a suggested fact for characters and places (`VAR-en`), and
  *gender* one for characters, which the family tree reads for its words (§12.2).
  - Suggested facts are a list in the code, not stored per world, so every world, old and new, offers it at once:
    no migration.
  - A fact labelled *pronunciation* (any capitals) is shown in small type after the name, on the entry page and on
    the name's card, and isn't repeated among the card's facts. Otherwise it is a fact like any other, exported as
    facts are.

**Data:** no tables. One data migration adds the *witnessed* type to existing worlds.

*Done when*, after upgrading, an existing world's types page lists *witnessed* under Character–event; recording
"Varren witnessed the Burning of the Quay" reads back as "witnessed by Varren" on the event; and a character's fact
picker offers *pronunciation* and *gender*, and a pronunciation then shows beside the name on the card.

### 12.6 Labels and values

Classification stays free-form. There are no fixed lists, no required fields, no forms per kind and no category
trees: an event's type, a character's gender or a place's climate is a fact like any other, typed when it comes up
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

- **New starting suggestions**: *type* for events, *pronouns* for characters (next to *gender* and *pronunciation*
  from §12.5), both optional like every suggestion. `SUGGESTED_FACTS` is a list in the code, not stored per world, so
  existing and new worlds offer them at once, with no migration.
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
relation_types  + "witnessed" / "witnessed by" (character – event)   -- §12.5; added to every existing world
fact_labels     (id, world_id, kind, label, several, expected, asked)  -- §12.6; only labels with a switch set
```

Endpoints: `GET /timeline` gains each chapter's POV and each project's gap length (§12.1); `GET /where` takes kinds,
entries and a project (§12.3); `PATCH /entities/<id>` takes `project` (§12.4); `GET /fact-suggestions` gains values,
and `/labels` lists, renames and switches labels (§12.6). The mentions strip, the family tree, kin, shared chapters,
common labels and missing-label findings are worked out when read, never stored.

**Phase 11 is done when** each part's *done when* above holds, and the demo world has a family of three
generations (with a cousin worked out, and *gender* facts for the words), an entry in each of its two projects'
bibles, a *witnessed* and a pronunciation, and events with a *type* (one label with several values, one marked
expected) to show.

### 12.8 Open questions for phase 11

None left. Missing labels are findings only for labels marked *expected* (Thomas: "For missing labels your instinct
is correct."), with a one-time prompt at the third use (§12.6.5). Existing entries all start in the world's bible
and need no tidying: what is there today is test worlds and the demo, which sets its own levels.

## 13. Out of scope (for now)

- AI features of any kind in the story path
- Co-writing features: inviting people, permissions beyond owner, comments, presence (the data model is ready for them; see §7)
- Rich text beyond Markdown
- Real-time collaborative editing or CRDTs
- Native apps (the PWA is enough on Android)
- A git mirror of the content (§8)

## 14. Open questions

- Should experiments also be allowed for entities ("what if this character were…") or only for chapters?
- Should journal entries be lockable after a period to keep them truly append-only, or stay freely editable?
- Is a light theme needed at all, or dark only?
- The domain (likely `quarry.daevil1.com`), which fixes the passkey Relying Party ID.
