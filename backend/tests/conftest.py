"""Shared fixtures.

Every test gets its own in-memory database and its own application instance. Nothing is
monkeypatched, because `create_app` takes its settings as an argument, and nothing leaks
between tests, because the database disappears with the engine.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from client_inventory.config import Baseline, Settings
from client_inventory.main import create_app
from client_inventory.models import Base

IN_MEMORY_DATABASE_URL = "sqlite+pysqlite:///:memory:"

# The suite runs on in-memory SQLite by default, which needs nothing installed. Point
# this variable at a PostgreSQL instance and the same tests run against it instead, which
# is what the second CI job does. Without that, "it also works on PostgreSQL" would be a
# claim rather than something anyone checked.
TEST_DATABASE_URL_ENV = "CLIENT_INVENTORY_TEST_DATABASE_URL"

# Every age assertion in the suite is measured against this instant, so the expected
# numbers are literals instead of something that changes overnight. It sits in the past
# so that a test can add a day to it without tripping the clock-skew validation that
# rejects reports dated in the future.
FIXED_NOW = datetime(2026, 10, 20, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def baseline() -> Baseline:
    """Return the default baseline."""
    return Baseline()


def build_settings(**overrides: Any) -> Settings:  # noqa: ANN401 - settings fields differ in type
    """Build settings without reading a developer's local .env file.

    pydantic-settings accepts `_env_file` at runtime but does not advertise it in its
    signature, so the single type: ignore the suite needs lives here rather than being
    repeated in every test that builds settings.
    """
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


@pytest.fixture
def settings(baseline: Baseline) -> Settings:
    """Return settings pointing at an in-memory database."""
    return build_settings(
        database_url=test_database_url(),
        baseline=baseline,
        cors_origins=[],
    )


def test_database_url() -> str:
    """Return the database the suite should run against."""
    return os.environ.get(TEST_DATABASE_URL_ENV, IN_MEMORY_DATABASE_URL)


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    """Build an application with an empty schema in place.

    The schema is dropped as well as created, because a shared PostgreSQL database keeps
    whatever the previous test left behind, while an in-memory SQLite one does not.
    """
    application = create_app(settings)
    engine = application.state.engine

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    yield application

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Open an HTTP client bound to the test application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session(app: FastAPI) -> Iterator[Session]:
    """Open a session on the same database the test application uses."""
    session_factory: sessionmaker[Session] = app.state.session_factory
    with session_factory() as open_session:
        yield open_session
