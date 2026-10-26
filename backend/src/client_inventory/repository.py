"""Database queries, kept out of the route handlers.

Every function takes a session and returns ORM objects. No HTTP types appear here, which
is what lets the seeding command reuse the same write path as the API.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from client_inventory.models import Client, ClientReport
from client_inventory.schemas import ClientReportIn
from client_inventory.timeutils import ensure_utc, utc_now


def get_client_by_hostname(session: Session, hostname: str) -> Client | None:
    """Return one client by hostname, or None."""
    statement = select(Client).where(Client.hostname == hostname.lower())

    return session.scalars(statement).one_or_none()


def _apply_current_state(
    client: Client, report: ClientReportIn, last_patched_at: datetime | None
) -> None:
    """Copy the reported facts onto the client's current state."""
    client.os_name = report.os_name
    client.os_version = report.os_version
    client.agent_version = report.agent_version
    client.encryption_enabled = report.encryption_enabled
    client.disk_total_gb = report.disk_total_gb
    client.disk_free_gb = report.disk_free_gb
    client.last_patched_at = last_patched_at


def record_report(session: Session, report: ClientReportIn) -> Client:
    """Store a submission and update the client's current state.

    The current state is updated in place and the submission is appended, so the history
    stays complete while the list views remain a single cheap query. A hostname that has
    not been seen before creates the client, which is what makes a collector deployment
    need no registration step.

    A report that is older than what the client already reported updates the history but
    not the current state. A submission delayed by a queue or an offline laptop must not
    overwrite this morning's facts with last week's, and it must not move the device's
    last check-in backwards and make it look stale.
    """
    reported_at = ensure_utc(report.reported_at) if report.reported_at else utc_now()
    last_patched_at = ensure_utc(report.last_patched_at) if report.last_patched_at else None

    client = get_client_by_hostname(session, report.hostname)
    if client is None:
        client = Client(
            hostname=report.hostname, first_seen_at=reported_at, last_seen_at=reported_at
        )
        _apply_current_state(client, report, last_patched_at)
        session.add(client)
    else:
        if reported_at < ensure_utc(client.first_seen_at):
            client.first_seen_at = reported_at

        if reported_at >= ensure_utc(client.last_seen_at):
            client.last_seen_at = reported_at
            _apply_current_state(client, report, last_patched_at)

    client.reports.append(
        ClientReport(
            reported_at=reported_at,
            os_version=report.os_version,
            agent_version=report.agent_version,
            encryption_enabled=report.encryption_enabled,
            disk_total_gb=report.disk_total_gb,
            disk_free_gb=report.disk_free_gb,
            last_patched_at=last_patched_at,
        )
    )

    session.flush()

    return client


def count_clients(session: Session, os_name: str | None = None) -> int:
    """Count clients, optionally restricted to one operating system."""
    statement = select(func.count()).select_from(Client)
    if os_name is not None:
        statement = statement.where(Client.os_name == os_name)

    return session.scalars(statement).one()


def list_clients(
    session: Session,
    limit: int,
    offset: int,
    os_name: str | None = None,
) -> list[Client]:
    """Return a page of clients, oldest check-in first so the stale ones lead."""
    statement = select(Client).order_by(Client.last_seen_at.asc(), Client.hostname.asc())
    if os_name is not None:
        statement = statement.where(Client.os_name == os_name)

    return list(session.scalars(statement.limit(limit).offset(offset)))


def list_clients_for_evaluation(session: Session, scan_limit: int) -> list[Client]:
    """Return clients for an in-memory compliance pass.

    Compliance is derived from the baseline rather than stored, so filtering or
    summarising by it cannot be pushed into SQL. The scan limit keeps that honest: the
    endpoint is bounded instead of degrading silently as the fleet grows.
    """
    statement = select(Client).order_by(Client.last_seen_at.asc(), Client.hostname.asc())

    return list(session.scalars(statement.limit(scan_limit)))


def latest_report_time(session: Session) -> datetime | None:
    """Return when the most recent submission arrived, or None if there is none."""
    statement = select(func.max(ClientReport.reported_at))
    value = session.scalars(statement).one()

    return ensure_utc(value) if value is not None else None
