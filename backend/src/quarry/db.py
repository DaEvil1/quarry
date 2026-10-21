"""Engine and sessions. One small pool: the app runs as a single worker next to other services."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        s = get_settings()
        _engine = create_engine(
            s.database_url,
            pool_size=s.pool_size,
            max_overflow=2,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def set_engine(e: Engine) -> None:
    """Tests point the app at their own database."""
    global _engine, _factory
    _engine = e
    _factory = sessionmaker(bind=e, expire_on_commit=False)


def session_factory() -> sessionmaker[Session]:
    engine()
    assert _factory is not None
    return _factory


def get_db() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = session_factory()()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
