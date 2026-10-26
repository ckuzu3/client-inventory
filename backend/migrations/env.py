"""Alembic environment.

The URL comes from the application settings rather than alembic.ini, so one environment
variable configures both the service and its migrations and the two cannot drift apart.
A URL can still be passed explicitly with `-x url=...`, which is what the test suite does
when it migrates a throwaway database.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy.engine import Connection

from client_inventory.config import get_settings
from client_inventory.database import create_db_engine
from client_inventory.models import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    """Return the URL to migrate.

    In order of precedence: `-x url=...` from the command line, then an explicit
    sqlalchemy.url in the Alembic config, then the application settings. The middle one
    is what lets a test migrate a throwaway database without touching the environment.
    """
    override = context.get_x_argument(as_dictionary=True).get("url")
    if override:
        return str(override)

    configured = config.get_main_option("sqlalchemy.url", default=None)
    if configured:
        return configured

    return get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it, for review or for a DBA to apply."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite cannot alter a column in place, so Alembic has to rebuild the table.
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    """Run the migrations against an open connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run the migrations against the configured database."""
    engine = create_db_engine(_database_url())
    try:
        with engine.connect() as connection:
            _run_migrations(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
