"""The write path: upsert in place, history append-only, and out-of-order reports."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from client_inventory import repository
from client_inventory.models import Client, ClientReport
from client_inventory.schemas import ClientReportIn
from client_inventory.timeutils import ensure_utc
from tests.conftest import FIXED_NOW


def report(**overrides: object) -> ClientReportIn:
    """Build a valid report with individual fields replaced."""
    payload: dict[str, object] = {
        "hostname": "ws-0001",
        "os_name": "Windows",
        "os_version": "10.0.26100.1742",
        "agent_version": "1.4.2",
        "encryption_enabled": True,
        "disk_total_gb": 512.0,
        "disk_free_gb": 256.0,
        "last_patched_at": FIXED_NOW - timedelta(days=3),
        "reported_at": FIXED_NOW,
    }
    payload.update(overrides)

    return ClientReportIn.model_validate(payload)


def test_a_new_hostname_creates_a_client(session: Session) -> None:
    """A collector deployment needs no registration step."""
    client = repository.record_report(session, report())

    assert client.id is not None
    assert client.hostname == "ws-0001"
    assert ensure_utc(client.first_seen_at) == FIXED_NOW
    assert ensure_utc(client.last_seen_at) == FIXED_NOW


def test_a_second_report_updates_the_client_in_place(session: Session) -> None:
    repository.record_report(session, report())
    repository.record_report(
        session,
        report(os_version="10.0.26100.2000", reported_at=FIXED_NOW + timedelta(days=1)),
    )

    assert session.scalars(select(func.count()).select_from(Client)).one() == 1

    client = repository.get_client_by_hostname(session, "ws-0001")
    assert client is not None
    assert client.os_version == "10.0.26100.2000"
    assert ensure_utc(client.last_seen_at) == FIXED_NOW + timedelta(days=1)


def test_every_report_is_kept_as_history(session: Session) -> None:
    """Without history, "when did this device lose encryption" is unanswerable."""
    repository.record_report(session, report())
    repository.record_report(
        session,
        report(encryption_enabled=False, reported_at=FIXED_NOW + timedelta(days=1)),
    )

    # The relationship declares newest first, but that ordering comes from the database.
    # In a session that still holds the freshly appended objects the collection is in
    # insertion order, so this commits and expires to read it back the way a request does.
    session.commit()
    session.expire_all()

    client = repository.get_client_by_hostname(session, "ws-0001")
    assert client is not None
    assert len(client.reports) == 2
    assert [entry.encryption_enabled for entry in client.reports] == [False, True]


def test_a_late_report_does_not_overwrite_newer_facts(session: Session) -> None:
    """A submission delayed by an offline laptop must not undo this morning's state."""
    repository.record_report(session, report(os_version="10.0.26100.2000"))
    repository.record_report(
        session,
        report(os_version="10.0.19045.4529", reported_at=FIXED_NOW - timedelta(days=7)),
    )

    client = repository.get_client_by_hostname(session, "ws-0001")
    assert client is not None
    assert client.os_version == "10.0.26100.2000"
    assert ensure_utc(client.last_seen_at) == FIXED_NOW
    assert len(client.reports) == 2


def test_a_late_report_can_move_the_first_sighting_backwards(session: Session) -> None:
    repository.record_report(session, report())
    repository.record_report(session, report(reported_at=FIXED_NOW - timedelta(days=30)))

    client = repository.get_client_by_hostname(session, "ws-0001")
    assert client is not None
    assert ensure_utc(client.first_seen_at) == FIXED_NOW - timedelta(days=30)


def test_a_hostname_lookup_is_case_insensitive(session: Session) -> None:
    repository.record_report(session, report(hostname="WS-0009"))

    assert repository.get_client_by_hostname(session, "ws-0009") is not None
    assert repository.get_client_by_hostname(session, "WS-0009") is not None


def test_deleting_a_client_removes_its_reports(session: Session) -> None:
    """Proves that foreign keys are actually enforced, which SQLite does not do by default."""
    client = repository.record_report(session, report())
    session.commit()

    session.delete(client)
    session.commit()

    assert session.scalars(select(func.count()).select_from(ClientReport)).one() == 0


def test_clients_are_listed_with_the_longest_silent_first(session: Session) -> None:
    repository.record_report(session, report(hostname="ws-recent", reported_at=FIXED_NOW))
    repository.record_report(
        session, report(hostname="ws-stale", reported_at=FIXED_NOW - timedelta(days=40))
    )

    listed = repository.list_clients(session, limit=10, offset=0)

    assert [entry.hostname for entry in listed] == ["ws-stale", "ws-recent"]


def test_listing_can_be_restricted_to_one_operating_system(session: Session) -> None:
    repository.record_report(session, report(hostname="ws-0001", os_name="Windows"))
    repository.record_report(
        session, report(hostname="mac-0001", os_name="macOS", os_version="15.1")
    )

    assert repository.count_clients(session, os_name="macOS") == 1
    assert [
        entry.hostname for entry in repository.list_clients(session, 10, 0, os_name="macOS")
    ] == ["mac-0001"]


def test_pagination_returns_disjoint_pages(session: Session) -> None:
    for index in range(5):
        repository.record_report(
            session,
            report(hostname=f"ws-{index:04d}", reported_at=FIXED_NOW - timedelta(days=index)),
        )

    first = repository.list_clients(session, limit=2, offset=0)
    second = repository.list_clients(session, limit=2, offset=2)

    assert len(first) == 2
    assert len(second) == 2
    assert {entry.hostname for entry in first}.isdisjoint(entry.hostname for entry in second)


def test_latest_report_time_is_none_on_an_empty_database(session: Session) -> None:
    assert repository.latest_report_time(session) is None


def test_latest_report_time_follows_the_newest_submission(session: Session) -> None:
    repository.record_report(session, report(reported_at=FIXED_NOW - timedelta(days=2)))
    repository.record_report(session, report(reported_at=FIXED_NOW))

    assert repository.latest_report_time(session) == FIXED_NOW
