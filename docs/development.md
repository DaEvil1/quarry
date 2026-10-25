# Developing Quarry

The backend is Python (FastAPI, SQLAlchemy, Alembic) in `backend/`. The frontend is Vue 3 + TypeScript (Vite) in
`frontend/`. In production one image serves both: the backend serves `/api` and the built frontend.

## A database

Any PostgreSQL 16+ works. A throwaway container:

```bash
docker run -d --name quarry-pg -e POSTGRES_USER=quarry -e POSTGRES_PASSWORD=quarry -e POSTGRES_DB=quarry -p 127.0.0.1:55433:5432 postgres:17-alpine
```

## Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # .venv/bin/... on Linux and macOS
```

Run it for the Vite dev server (passkeys are bound to the address the browser shows, so `QUARRY_BASE_URL` is
the Vite address, not the backend's):

```bash
QUARRY_DATABASE_URL=postgresql://quarry:quarry@127.0.0.1:55433/quarry QUARRY_BASE_URL=http://localhost:5173 QUARRY_SETUP_TOKEN=dev .venv/Scripts/quarry serve --reload
```

Migrations run at startup. After changing `models.py`, add a migration in `src/quarry/migrations/versions/`;
`tests/test_migrations.py` fails until the migrations match the models.

Tests need a server where the user may create databases; they create and migrate `quarry_test` themselves:

```bash
QUARRY_TEST_DATABASE_URL=postgresql://quarry:quarry@127.0.0.1:55433/quarry .venv/Scripts/python -m pytest
```

The passkey tests use a software authenticator (`tests/softauth.py`) that signs real WebAuthn answers, so the
server's verification runs unmocked.

## Frontend

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173, proxies /api to the backend on port 8000
npm test           # unit tests (Vitest)
npm run build      # typecheck and build into dist/
```

Open the app at `http://localhost:5173` (not `127.0.0.1`): browsers allow passkeys over plain HTTP only on
`localhost`. On first run it asks for the setup token (`dev` above).

## End-to-end tests

Playwright drives the built app served by the backend, with Chrome's virtual authenticator standing in for a
phone or laptop. The database must be empty, because the test starts with first-run setup (empty it between runs:
`TRUNCATE users, worlds, auth_challenges CASCADE`).

```bash
cd frontend
npm run build
npx playwright install --only-shell chromium
# in another terminal, from backend/:
QUARRY_DATABASE_URL=postgresql://quarry:quarry@127.0.0.1:55433/quarry_e2e QUARRY_BASE_URL=http://localhost:8767 QUARRY_SETUP_TOKEN=e2e-setup-token QUARRY_AUTH_RATE_LIMIT=1000 QUARRY_WEB_DIR=../frontend/dist QUARRY_PORT=8767 .venv/Scripts/quarry serve
# back in frontend/:
npm run e2e
```

## The whole stack in Docker

```bash
docker compose up -d --build       # http://localhost:8766, setup token local-setup-token
```

## Performance

`frontend/perf/` seeds a large made-up world into a Quarry with an empty database (400 bible entries with other
names, facts and relationships, and a 10,000-word chapter full of their names) and measures what a writer feels:
opening the chapter, each keystroke from press to paint (Chrome's Event Timing, the basis of the INP metric) at
desk speed and with the CPU slowed 4× like a phone, scrolling, saving, and the bible pages. It prints a table and
writes `perf-results.json`.

```bash
docker compose up -d --build                       # or the e2e server above, with PERF_BASE_URL and PERF_SETUP_TOKEN
cd frontend
npx playwright test -c playwright.perf.config.ts
```

`perf/timeline.perf.ts` does the same for the Timeline (docs/SPEC.md §13.2.6): a made-up world of 3,000 events, eight
eras and a book, then the first drawing, zooming from the whole world to a year and back, and panning, at desk speed
and with the CPU slowed 4×, writing `perf-timeline.json`. Each file sets up its own Quarry, so run one at a time
(`npx playwright test -c playwright.perf.config.ts timeline`) and empty the database before each.

Options: `PERF_ENTRIES` and `PERF_WORDS` (the size), `PERF_EVENTS` (the Timeline's events), `PERF_PROFILE=1` (the functions that took the time while
typing; build with `npx vite build --minify false` first for readable names), `PERF_SHOTS=<folder>` (screenshots
of the main pages at desk and phone width). Empty the database before each run.

## Story content stays out

This repository is public. Never commit manuscripts, bible text, exports or real names from a story; tests and
examples use made-up material. `.gitignore` blocks the usual export formats, but it cannot catch text pasted
into a test.
