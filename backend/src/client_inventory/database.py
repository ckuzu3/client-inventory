"""Engine and session construction.

The engine is built from a URL instead of being a module-level global, so a test can get
its own database without monkeypatching anything.
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import StaticPool

IN_MEMORY_SQLITE_MARKERS = (":memory:", "mode=memory")


class DbApiCursor(Protocol):
    """The part of a DBAPI cursor this module uses."""

    def execute(self, statement: str) -> object:
        """Run one statement."""

    def close(self) -> None:
        """Release the cursor."""


class DbApiConnection(Protocol):
    """The part of a raw DBAPI connection this module uses.

    A narrow protocol rather than Any: the pragma listener receives the driver's own
    connection object, and this says exactly what is expected of it.
    """

    def cursor(self) -> DbApiCursor:
        """Open a cursor."""


def _is_sqlite(database_url: str) -> bool:
    """Tell whether the URL points at SQLite."""
    return database_url.startswith("sqlite")


def _is_in_memory_sqlite(database_url: str) -> bool:
    """Tell whether the URL points at an in-memory SQLite database."""
    return _is_sqlite(database_url) and any(
        marker in database_url for marker in IN_MEMORY_SQLITE_MARKERS
    )


def _enforce_sqlite_foreign_keys(engine: Engine) -> None:
    """Switch on foreign key enforcement for every new SQLite connection.

    SQLite accepts foreign keys but ignores them unless this pragma is set, per
    connection. Without it the cascade from client to client_report silently does
    nothing, and a test suite running on SQLite would happily pass while the same code
    fails against PostgreSQL.
    """

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection: DbApiConnection, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def create_db_engine(database_url: str) -> Engine:
    """Create an engine for the given URL, with the quirks of each backend handled.

    SQLite needs `check_same_thread` switched off because the API serves requests from a
    thread pool, and an in-memory database needs a pool that hands out the same single
    connection, or every session would see an empty database of its own.
    """
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}

    if _is_sqlite(database_url):
        connect_args["check_same_thread"] = False

    if _is_in_memory_sqlite(database_url):
        engine_kwargs["poolclass"] = StaticPool

    engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)

    if _is_sqlite(database_url):
        _enforce_sqlite_foreign_keys(engine)

    return engine
