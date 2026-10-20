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
