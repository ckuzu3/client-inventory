"""Engine construction, the unhealthy case, and the seeding command line."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from client_inventory.database import (
    _is_in_memory_sqlite,
    _is_sqlite,
    create_db_engine,
)
from client_inventory.main import create_app
from client_inventory.seed import main
from tests.conftest import build_settings


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite+pysqlite:///:memory:", True),
        ("sqlite+pysqlite:///file:x?mode=memory&cache=shared", True),
        ("sqlite+pysqlite:///./client-inventory.sqlite3", False),
        ("postgresql+psycopg://user:pass@localhost:5432/inventory", False),
    ],
)
def test_in_memory_sqlite_is_recognised(url: str, expected: bool) -> None:
    """An in-memory database needs a pool that hands out one shared connection."""
    assert _is_in_memory_sqlite(url) is expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite+pysqlite:///:memory:", True),
        ("postgresql+psycopg://user:pass@localhost:5432/inventory", False),
    ],
)
def test_sqlite_urls_are_recognised(url: str, expected: bool) -> None:
    assert _is_sqlite(url) is expected


def test_foreign_keys_are_enforced_on_a_sqlite_connection(tmp_path: Path) -> None:
    """SQLite accepts foreign keys but ignores them unless the pragma is set."""
    engine = create_db_engine(f"sqlite+pysqlite:///{tmp_path / 'pragma.sqlite3'}")
    try:
        with engine.connect() as connection:
            enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()

        assert enabled == 1
    finally:
        engine.dispose()


def test_healthz_reports_a_degraded_database_instead_of_failing(tmp_path: Path) -> None:
    """The endpoint has to answer when the database does not, which is the point of it."""
    unreachable = tmp_path / "missing-directory" / "inventory.sqlite3"
    settings = build_settings(
        database_url=f"sqlite+pysqlite:///{unreachable}",
        cors_origins=[],
    )

    app = create_app(settings)
    try:
        with TestClient(app) as client:
            response = client.get("/healthz")
    finally:
        app.state.engine.dispose()

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "database": "unreachable"}


def test_the_seed_command_fills_a_fresh_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "seeded.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setattr(
        "sys.argv",
        [
            "client-inventory-seed",
            "--count",
            "5",
            "--seed",
            "11",
            "--database-url",
            database_url,
            "--create-schema",
        ],
    )

    main()

    assert "Wrote 5 synthetic client reports." in capsys.readouterr().out

    engine = create_db_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) == {"client", "client_report"}
    finally:
        engine.dispose()
