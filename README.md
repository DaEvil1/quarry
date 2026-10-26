# Quarry

**A quiet writing environment for long fiction set in shared worlds.**

Catch an idea on your phone, sort it at your desk, keep a living bible of your world, and write the book in a fast,
dark editor that knows every name in it, without ever writing a word for you.

> Quarry does bookkeeping only. It never generates, suggests or critiques story content.

---

## Why Quarry

Long fiction in a shared world means hundreds of names, years of notes, and a story that is rewritten many times.
Quarry is built around one loop, **spark → inbox → triage → canon and manuscript**, and keeps the bookkeeping out of
your way while you write:

- **Writing never waits for the tool.** Nothing pops up or takes the keyboard while you type. Names are coloured
  quietly; everything else waits in a side panel until a natural break.
- **No AI in the story.** Every check is a plain rule over your own text and notes.
- **Nothing has to be filled in.** An entry can be just a name, forever. Structure grows from what you write.
- **Nothing is lost.** Every save is versioned, chapters are retired rather than deleted, and a world exports to plain
  Markdown at any time.
- **Prose stays pure.** No markup in the manuscript; links live beside the text, never in it.

## What it does

### Capture and triage
- **Capture anywhere.** A phone screen that opens straight to a text box, works offline, and takes text shared from
  any app.
- **Triage at the desk.** One item at a time, by keyboard: accept, reject, harvest, defer, with an optional one-line
  decision.
- **A journal and a decisions log** for the thinking around the book.

### The bible and the world model
- **Entries for every kind of thing:** characters, places, factions, cultures, species, events, objects and terms.
- **Facts and relationships that read both ways,** with when they hold, how sure you are (canon, planned or rumour),
  and the passage that established them.
- **Names found automatically.** Every mention of every name, including other spellings, is found in all your texts.
  Likely misspellings are caught and fixed in one click.
- **Pictures, as in a wiki:** a gallery on any entry, its main picture at the top of its page and on its cards, and
  a picture on a line of its own in a chapter or journal entry, never part of the compiled manuscript.
- **Views:** a relationship graph, a family tree with relatives worked out, a place tree, *where everyone is* per
  chapter, a mentions strip for each entry, and labels you can filter, group and tidy.

### Writing
- **A CodeMirror editor** with autosave, history with diffs, focus mode and typewriter scrolling.
- **Live names:** coloured by kind as you type, with a card when you rest on one (never while typing), and a one-row
  quick-fix strip for new names and misspellings.
- **A writing companion** with five rule-based editors (Proofreader, Continuity, Connections, Archivist, Loose ends),
  silent while Drafting and marked in the text while Revising.
- **Getting back in:** where you stopped, a note for next time, and margin notes that never reach the manuscript.

### Time, history and places
- **One clock for the story:** chapters, facts and relationships can be set in in-world time, before the story, or
  outside time, so flashbacks and tales are checked against when they happen, not where they're told.
- **A Timeline** with coloured eras, lanes per character or faction, births, deaths and movements, a *told* order
  beside the *happened* one, and history recorded straight from a passage.
- **A chart:** a schematic map drawn from what's recorded (lands holding their towns, borders, seas, roads), with
  pins you can drag and who controls what as of any point in the story.

### Revising and restructuring
- **Experiments:** alternate drafts of a chapter, or of a whole run of chapters, written beside the book and swapped
  in when you're ready.
- **Salvage and a cuts bin,** so nothing that leaves the book is lost.
- **Find and replace across chapters** with a preview and Undo, word history per day, and changes since a checkpoint.

### Planning
- **A front page** for coming back after a break: the premise, where you left off, recent decisions and open
  questions.
- **The Journal in the full editor,** so planning notes get the same name tools as chapters.
- **A chapter's plan beside it:** a journal entry marked as the plan for a chapter, opened half and half beside it
  while writing (flipped to on the phone), and a plan written before its chapter waiting until the chapter starts.
- **Planned facts** that become canon when the text shows them, and checks that can include them.

### Safe and portable
- **Passkey sign-in**, no passwords.
- **An installable PWA** whose chapters and recent history work offline on the phone.
- **Export and Restore:** a whole world as Markdown with frontmatter, with each day's version of every chapter, read
  back losslessly.

## Try it

- **The demo world.** Load *The Ninefold Delta* from **New world**: a small made-up story with something of every
  feature planted in it.
- **The Guide.** Fourteen short walkthroughs, at the foot of the nav or under Settings on a phone. Watch one play
  itself, or try it step by step, always on a throwaway copy of the demo world.

## Run it locally

The quickest way is the whole stack in Docker:

```bash
docker compose up -d --build
```

Open <http://localhost:8766> (use `localhost`, not `127.0.0.1`, for passkeys) and enter the setup token
`local-setup-token` on first run.

For development with hot reload and the tests, see [docs/development.md](docs/development.md).

## Built with

| Layer | |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, py_webauthn |
| Database | PostgreSQL 16+ |
| Frontend | Vue 3, TypeScript, Vite, Pinia, CodeMirror 6, Dexie, d3-force; an installable PWA |
| Tests | pytest, Vitest, Playwright, run in parallel in GitHub Actions |
| Shipping | one Docker image (`ghcr.io/daevil1/quarry`) serving the API and the app |

## Documentation

| Document | What's in it |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) | The design: principles, data model, screens, and every phase with its *done when* |
| [docs/WORLD-MODEL.md](docs/WORLD-MODEL.md) | The bible as data: kinds, facts, relationships, story time and the companion |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Dated one-line decisions, and the reasons for them |
| [docs/research/](docs/research/README.md) | How writers work, and what other writing and worldbuilding tools do |
| [docs/development.md](docs/development.md) | Running it locally, the tests and the performance checks |
| [docs/deploy.md](docs/deploy.md) | Deploying to a server behind nginx |

## Status

Phases 1–18 and the Guide are built and in use. Quarry is a personal tool for a single writer, with the data model ready for co-writing
later. The code is public; no story content is ever committed, and every example and test uses made-up names.
