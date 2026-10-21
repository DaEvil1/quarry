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

## Story content stays out

This repository is public. Never commit manuscripts, bible text, exports or real names from a story; tests and
examples use made-up material. `.gitignore` blocks the usual export formats, but it cannot catch text pasted
into a test.
