# Quarry

A writing environment for long fiction set in shared worlds: capture sparks on the phone, triage them at the desk, keep a living bible of the world, and write the manuscript in a fast, dark editor.

Quarry does bookkeeping only. It never generates, suggests or critiques story content.

**Status:** v1: all five phases built. Sign in with a passkey; create worlds and their projects; capture sparks, questions and tasks on the phone (also offline, and by sharing from other apps); triage them at the desk with the keyboard; keep a decisions log and a journal; keep a bible of the world, see where every name is mentioned, and fix misspelled names in one click; write chapters in a distraction-free editor with history, experiments and salvage; export a world as Markdown and restore it; and on the phone, open and write chapters and browse and restore their history with no network. Phases 6–8 of the world model ([docs/WORLD-MODEL.md](docs/WORLD-MODEL.md)) are in: bible entries carry a one-liner, facts and relationships that read both ways; each kind has its own table; and the editor colours names by kind as they are typed, shows a name's card when you rest on it (never while typing), and turns a selection into a new entry or links names from their card. Chapters are the story's clock: facts and relationships hold from/until a chapter, entry pages and cards read *as of* a chapter, and a grid shows where everyone is per chapter, recorded or derived from the text. A relationship graph (filters, as of a chapter, centred on someone with their first- and second-order links, clusters) and a place tree show the world at a glance, and the manuscript lists each chapter's cast. See [docs/SPEC.md](docs/SPEC.md) for the design and the phases, and [docs/DECISIONS.md](docs/DECISIONS.md) for the decisions behind it.

- [docs/development.md](docs/development.md): running it locally and the tests
- [docs/deploy.md](docs/deploy.md): putting it on the droplet

Python (FastAPI, SQLAlchemy, Alembic, py_webauthn) and PostgreSQL behind a Vue 3 + TypeScript PWA, shipped as one Docker image.
