"""Tests run against a real PostgreSQL (the same engine as production).

QUARRY_TEST_DATABASE_URL points at a server where the test user may create databases; a fresh database
``quarry_test`` is created per run, migrated with Alembic, and emptied between tests. Without it the database
tests are skipped. Under pytest-xdist (``-n auto``) each worker is a process of its own with its own database,
``quarry_test_gw0`` and so on.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from .softauth import SoftPasskey

TEST_URL = os.environ.get("QUARRY_TEST_DATABASE_URL", "")
SETUP_TOKEN = "test-setup-token"

os.environ["QUARRY_BASE_URL"] = "http://testserver"
os.environ["QUARRY_SETUP_TOKEN"] = SETUP_TOKEN
os.environ.setdefault("QUARRY_MIGRATE", "0")


@pytest.fixture(scope="session")
def db_url() -> Iterator[str]:
    if not TEST_URL:
        pytest.skip("set QUARRY_TEST_DATABASE_URL to run database tests")
    from quarry.config import normalize_db_url

    base = make_url(normalize_db_url(TEST_URL))
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    name = f"quarry_test_{worker}" if worker else "quarry_test"
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    os.environ["QUARRY_DATABASE_URL"] = url
    from quarry.config import get_settings

    get_settings.cache_clear()
    from quarry.app import run_migrations

    run_migrations()
    yield url
    admin.dispose()


@pytest.fixture
def engine(db_url: str):
    from quarry import db as dbmod
    from quarry.models import Base
    from quarry.security import auth_limiter

    e = create_engine(db_url, pool_size=2)
    dbmod.set_engine(e)
    names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with e.begin() as c:
        c.execute(text(f"TRUNCATE {names} CASCADE"))
    auth_limiter.clear()
    yield e
    e.dispose()


@pytest.fixture
def db(engine):
    from quarry.db import session_factory

    s = session_factory()()
    yield s
    s.close()


class Client:
    """TestClient wrapper: sends a same-origin header with every request (the app refuses cross-site writes)."""

    def __init__(self, app) -> None:
        from fastapi.testclient import TestClient

        self.c = TestClient(app, base_url="http://testserver", follow_redirects=False)
        self.c.headers["Origin"] = "http://testserver"

    def __getattr__(self, name):
        return getattr(self.c, name)

    def setup(self, passkey: SoftPasskey, name: str = "Writer", label: str = "Laptop") -> list[str]:
        r = self.c.post("/api/setup/begin", json={"token": SETUP_TOKEN, "display_name": name})
        assert r.status_code == 200, r.text
        begin = r.json()
        r = self.c.post("/api/setup/finish", json={"challenge_id": begin["challenge_id"], "label": label,
                                                   "credential": passkey.register(begin["options"])})
        assert r.status_code == 200, r.text
        return r.json()["recovery_codes"]

    def sign_in(self, passkey: SoftPasskey):
        begin = self.c.post("/api/auth/login/begin").json()
        return self.c.post("/api/auth/login/finish", json={"challenge_id": begin["challenge_id"],
                                                           "credential": passkey.sign_in(begin["options"])})


@pytest.fixture
def app(engine):
    from quarry.app import create_app

    return create_app(run_bootstrap=False)


@pytest.fixture
def client(app) -> Client:
    return Client(app)


@pytest.fixture
def passkey() -> SoftPasskey:
    return SoftPasskey()


@pytest.fixture
def signed_in(client: Client, passkey: SoftPasskey) -> Client:
    """A client that went through first-run setup and is signed in."""
    client.setup(passkey)
    return client
