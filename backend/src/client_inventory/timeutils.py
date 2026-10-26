"""Keeping every timestamp in UTC, including the ones that come back from SQLite.

SQLite has no timestamp type and no notion of a time zone, so a value written as
timezone-aware comes back naive. PostgreSQL returns it aware. Without a single place that
normalises this, the same code would compute one age in development and another in
production, and the difference would show up as an off-by-one-hour bug twice a year.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC value."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Return the value as timezone-aware UTC.

    A naive value is assumed to be UTC, because that is the only thing this application
    ever writes to the database. An aware value is converted.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def age_in_days(value: datetime, now: datetime) -> float:
    """Return how many days lie between value and now, both normalised to UTC."""
    delta = ensure_utc(now) - ensure_utc(value)
    return delta.total_seconds() / 86400.0
