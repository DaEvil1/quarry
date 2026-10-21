"""Settings from the environment (QUARRY_*), read once at startup.

Everything that differs between a laptop and the server lives here, so the image is the same everywhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def normalize_db_url(url: str) -> str:
    """Accept the URLs hosting providers hand out (postgres://, postgresql://) and use the psycopg 3 driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str
    # where people open the app; passkeys are bound to its host name (the WebAuthn relying party)
    base_url: str
    # accepted once, while no user exists, to create the first user and passkey
    setup_token: str = ""
    migrate_on_start: bool = True
    pool_size: int = 3
    docs: bool = False
    # the built frontend; empty means the package's own web/ folder
    web_dir: str = ""
    # sign-in attempts per address in ten minutes (the end-to-end tests raise it)
    auth_rate_limit: int = 20

    @property
    def origin(self) -> str:
        p = urlsplit(self.base_url)
        return f"{p.scheme}://{p.netloc}"

    @property
    def rp_id(self) -> str:
        return urlsplit(self.base_url).hostname or "localhost"

    @property
    def cookie_secure(self) -> bool:
        return self.base_url.startswith("https://")

    @property
    def web_path(self) -> Path:
        return Path(self.web_dir) if self.web_dir else Path(__file__).parent / "web"


PG_VARS = ("PGHOST", "PGHOSTADDR", "PGDATABASE", "PGUSER", "PGSERVICE")


@lru_cache
def get_settings() -> Settings:
    db = os.environ.get("QUARRY_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if not db and any(os.environ.get(k) for k in PG_VARS):
        # no URL but the standard PGHOST / PGUSER / PGPASSWORD / PGSSLMODE settings: an empty URL lets libpq
        # read them itself (so passwords need no URL encoding)
        db = "postgresql+psycopg://"
    if not db:
        db = "postgresql://quarry:quarry@localhost:5432/quarry"
    return Settings(
        database_url=normalize_db_url(db),
        base_url=(os.environ.get("QUARRY_BASE_URL", "").strip() or "http://localhost:8000").rstrip("/"),
        setup_token=os.environ.get("QUARRY_SETUP_TOKEN", "").strip(),
        migrate_on_start=_bool("QUARRY_MIGRATE", True),
        pool_size=int(os.environ.get("QUARRY_DB_POOL", "3")),
        docs=_bool("QUARRY_DOCS", False),
        web_dir=os.environ.get("QUARRY_WEB_DIR", "").strip(),
        auth_rate_limit=int(os.environ.get("QUARRY_AUTH_RATE_LIMIT", "20")),
    )
