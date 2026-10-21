# Quarry

A writing environment for long fiction set in shared worlds: capture sparks on the phone, triage them at the desk, keep a living bible of the world, and write the manuscript in a fast, dark editor.

Quarry does bookkeeping only. It never generates, suggests or critiques story content.

**Status:** phase 1 of 5 (the skeleton). You can sign in with a passkey, keep recovery codes, and create worlds and the projects set in them, on desktop and phone. See [docs/SPEC.md](docs/SPEC.md) for the design and the phases, and [docs/DECISIONS.md](docs/DECISIONS.md) for the decisions behind it.

- [docs/development.md](docs/development.md): running it locally and the tests
- [docs/deploy.md](docs/deploy.md): putting it on the droplet

Python (FastAPI, SQLAlchemy, Alembic, py_webauthn) and PostgreSQL behind a Vue 3 + TypeScript PWA, shipped as one Docker image.
