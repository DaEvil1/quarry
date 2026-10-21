"""The Alembic migrations produce exactly the schema models.py describes (no forgotten migration)."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from quarry.models import Base


def test_models_match_migrations(db_url):
    e = create_engine(db_url)
    with e.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c, opts={"compare_type": True}), Base.metadata)
    e.dispose()
    assert diff == [], f"models changed without a migration: {diff}"
