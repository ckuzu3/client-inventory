"""Timestamp normalisation, which is where the SQLite and PostgreSQL difference bites."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from client_inventory.timeutils import age_in_days, ensure_utc, utc_now


def test_utc_now_is_timezone_aware() -> None:
    assert utc_now().tzinfo is not None


def test_a_naive_value_is_treated_as_utc() -> None:
    """This is the value SQLite hands back for a column declared with a time zone."""
    naive = datetime(2026, 10, 27, 12, 0, 0)  # noqa: DTZ001 - exactly what we are testing

    normalised = ensure_utc(naive)

    assert normalised.tzinfo is UTC
    assert normalised.hour == 12


def test_an_aware_value_is_converted_rather_than_relabelled() -> None:
    zurich_winter = timezone(timedelta(hours=1))
    aware = datetime(2026, 10, 27, 12, 0, 0, tzinfo=zurich_winter)

    normalised = ensure_utc(aware)

    assert normalised.hour == 11
    assert normalised.tzinfo is UTC


def test_age_in_days_works_across_a_mixed_pair() -> None:
    """One naive value from the database, one aware value from the clock."""
    stored = datetime(2026, 10, 17, 12, 0, 0)  # noqa: DTZ001 - as SQLite returns it
    now = datetime(2026, 10, 27, 12, 0, 0, tzinfo=UTC)

    assert age_in_days(stored, now) == 10.0


def test_age_in_days_is_fractional() -> None:
    now = datetime(2026, 10, 27, 12, 0, 0, tzinfo=UTC)
    stored = now - timedelta(hours=36)

    assert age_in_days(stored, now) == 1.5
