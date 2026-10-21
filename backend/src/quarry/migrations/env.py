"""Alembic environment: the URL comes from QUARRY_DATABASE_URL (or the caller), the schema from models.py."""

from alembic import context
from sqlalchemy import create_engine, pool

from quarry.config import get_settings
from quarry.models import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return config.attributes.get("connection_url") or get_settings().database_url


def run_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    conn = config.attributes.get("connection")
    if conn is not None:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
