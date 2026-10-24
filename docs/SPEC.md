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
| **Entity** | A bible page in a world: character, place, term, faction, object or other. Has a name, aliases and a body. Shared by every project in the world. |
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
- **Built on the device**, from the offline copy of the chapters and the same matcher that colours names (other
  names, first names and *not in this sense* included), so it works on the phone with no network.

**Data:** none. A route, `/w/<world>/bible/<id>/read`.

*Done when* Varren's page opens a reading of every paragraph that names him (by any of his names), in story order
across the world's projects, with the margin notes beside them shown, on the phone in airplane mode too.

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

## 12. Out of scope (for now)

- AI features of any kind in the story path
- Co-writing features: inviting people, permissions beyond owner, comments, presence (the data model is ready for them; see §7)
- Rich text beyond Markdown
- Real-time collaborative editing or CRDTs
- Native apps (the PWA is enough on Android)
- A git mirror of the content (§8)

## 13. Open questions

- Should experiments also be allowed for entities ("what if this character were…") or only for chapters?
- Should journal entries be lockable after a period to keep them truly append-only, or stay freely editable?
- Is a light theme needed at all, or dark only?
- Do some bible pages belong to one project only (a character who exists in one novella), or is "world-level, mentioned in project X" always enough?
- The domain (likely `quarry.daevil1.com`), which fixes the passkey Relying Party ID.
- Phase 10: should cuts ever be thrown away, or stay forever as specced?
- Phase 10: statuses per project (as specced) or one set for the whole world?
- Phase 10: should reading one entry's thread also take a second entry ("where Varren and Isolde both appear")?
