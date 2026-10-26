"""The sample data generator: deterministic, and varied enough to be useful."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from client_inventory.models import Client
from client_inventory.seed import build_reports, seed_session
from tests.conftest import FIXED_NOW


def test_the_same_seed_produces_the_same_fleet() -> None:
    """Reproducible sample data means a screenshot and a test can rely on it."""
    first = build_reports(count=20, seed=42, now=FIXED_NOW)
    second = build_reports(count=20, seed=42, now=FIXED_NOW)

    assert [report.model_dump() for report in first] == [report.model_dump() for report in second]


def test_a_different_seed_produces_a_different_fleet() -> None:
    first = build_reports(count=20, seed=1, now=FIXED_NOW)
    second = build_reports(count=20, seed=2, now=FIXED_NOW)

    assert [report.os_version for report in first] != [report.os_version for report in second]


def test_every_generated_report_is_valid() -> None:
    """build_reports returns validated models, so a broken generator fails here."""
    reports = build_reports(count=60, seed=7, now=FIXED_NOW)

    assert len(reports) == 60
    assert all(report.disk_free_gb <= report.disk_total_gb for report in reports)
    assert all(report.hostname == report.hostname.lower() for report in reports)


def test_the_fleet_is_mixed_so_the_os_specific_rule_is_visible() -> None:
    reports = build_reports(count=60, seed=7, now=FIXED_NOW)
    operating_systems = {report.os_name for report in reports}

    assert operating_systems == {"Windows", "macOS"}


def test_the_fleet_contains_both_compliant_and_failing_clients() -> None:
    """A sample fleet where everything passes would make the dashboard pointless."""
    reports = build_reports(count=60, seed=7, now=FIXED_NOW)

    assert any(report.encryption_enabled is False for report in reports)
    assert any(report.last_patched_at is None for report in reports)
    assert any(report.os_version == "10.0.19045.4529" for report in reports)


def test_seeding_writes_through_the_same_path_the_api_uses(session: Session) -> None:
    reports = build_reports(count=12, seed=3, now=FIXED_NOW)

    written = seed_session(session, reports)

    assert written == 12
    assert session.scalars(select(func.count()).select_from(Client)).one() == 12
