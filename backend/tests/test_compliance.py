"""The baseline rules, tested as plain functions against a stub client."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

import pytest

from client_inventory.compliance import (
    FindingCode,
    Severity,
    evaluate,
    free_disk_percent,
)
from client_inventory.config import Baseline
from tests.conftest import FIXED_NOW


@dataclass
class FactsStub:
    """A client's facts without a database behind them."""

    os_name: str = "Windows"
    os_version: str = "10.0.26100.1742"
    encryption_enabled: bool = True
    disk_total_gb: float = 512.0
    disk_free_gb: float = 256.0
    last_patched_at: datetime | None = FIXED_NOW - timedelta(days=3)
    last_seen_at: datetime = FIXED_NOW - timedelta(hours=2)


def codes(facts: FactsStub, baseline: Baseline, now: datetime = FIXED_NOW) -> list[FindingCode]:
    """Evaluate the stub and return only the finding codes."""
    return [finding.code for finding in evaluate(facts, baseline, now)]


def test_a_client_that_meets_every_rule_has_no_findings(baseline: Baseline) -> None:
    assert evaluate(FactsStub(), baseline, FIXED_NOW) == []


def test_an_old_build_is_a_high_severity_finding(baseline: Baseline) -> None:
    facts = replace(FactsStub(), os_version="10.0.19045.4529")

    findings = evaluate(facts, baseline, FIXED_NOW)

    assert [finding.code for finding in findings] == [FindingCode.OS_VERSION_BELOW_BASELINE]
    assert findings[0].severity is Severity.HIGH
    assert "10.0.26100" in findings[0].detail


def test_the_os_rule_is_skipped_for_an_operating_system_it_was_not_written_for(
    baseline: Baseline,
) -> None:
    """A macOS version compared against a Windows build would flag every Mac."""
    facts = replace(FactsStub(), os_name="macOS", os_version="15.1")

    assert codes(facts, baseline) == []


def test_an_unreadable_version_is_reported_rather_than_raised(baseline: Baseline) -> None:
    facts = replace(FactsStub(), os_version="Windows 11 23H2")

    findings = evaluate(facts, baseline, FIXED_NOW)

    assert [finding.code for finding in findings] == [FindingCode.OS_VERSION_UNREADABLE]
    assert findings[0].severity is Severity.MEDIUM


def test_encryption_off_is_a_finding_when_the_baseline_requires_it(baseline: Baseline) -> None:
    facts = replace(FactsStub(), encryption_enabled=False)

    assert codes(facts, baseline) == [FindingCode.ENCRYPTION_DISABLED]


def test_encryption_off_is_accepted_when_the_baseline_does_not_require_it() -> None:
    relaxed = Baseline(require_encryption=False)
    facts = replace(FactsStub(), encryption_enabled=False)

    assert codes(facts, relaxed) == []


def test_a_missing_patch_date_outranks_a_late_one(baseline: Baseline) -> None:
    """An unknown patch state cannot be planned, so it is rated higher than a late one."""
    never_patched = evaluate(replace(FactsStub(), last_patched_at=None), baseline, FIXED_NOW)
    late = evaluate(
        replace(FactsStub(), last_patched_at=FIXED_NOW - timedelta(days=60)),
        baseline,
        FIXED_NOW,
    )

    assert never_patched[0].code is FindingCode.PATCH_LEVEL_UNKNOWN
    assert never_patched[0].severity is Severity.HIGH
    assert late[0].code is FindingCode.PATCH_LEVEL_OUTDATED
    assert late[0].severity is Severity.MEDIUM


@pytest.mark.parametrize(
    ("patch_age_days", "expected_finding"),
    [(34, False), (35, False), (36, True)],
)
def test_the_patch_age_boundary_is_inclusive(
    baseline: Baseline, patch_age_days: int, expected_finding: bool
) -> None:
    facts = replace(FactsStub(), last_patched_at=FIXED_NOW - timedelta(days=patch_age_days))

    assert (FindingCode.PATCH_LEVEL_OUTDATED in codes(facts, baseline)) is expected_finding


def test_a_client_that_stopped_reporting_is_flagged(baseline: Baseline) -> None:
    facts = replace(FactsStub(), last_seen_at=FIXED_NOW - timedelta(days=30))

    assert FindingCode.NOT_SEEN_RECENTLY in codes(facts, baseline)


def test_low_disk_space_is_a_low_severity_finding(baseline: Baseline) -> None:
    facts = replace(FactsStub(), disk_total_gb=512.0, disk_free_gb=20.0)

    findings = evaluate(facts, baseline, FIXED_NOW)

    assert [finding.code for finding in findings] == [FindingCode.DISK_SPACE_LOW]
    assert findings[0].severity is Severity.LOW
    assert "3.9 percent" in findings[0].detail


def test_a_client_reporting_a_zero_sized_disk_is_not_divided_by_zero(baseline: Baseline) -> None:
    facts = replace(FactsStub(), disk_total_gb=0.0, disk_free_gb=0.0)

    assert free_disk_percent(facts) is None
    assert codes(facts, baseline) == []


def test_findings_come_back_worst_first(baseline: Baseline) -> None:
    facts = replace(
        FactsStub(),
        os_version="10.0.19045.4529",
        encryption_enabled=False,
        last_patched_at=FIXED_NOW - timedelta(days=90),
        last_seen_at=FIXED_NOW - timedelta(days=40),
        disk_free_gb=10.0,
    )

    findings = evaluate(facts, baseline, FIXED_NOW)
    severities = [finding.severity for finding in findings]

    assert len(findings) == 5
    assert severities == sorted(
        severities, key=lambda severity: ["high", "medium", "low"].index(severity.value)
    )
    assert findings[-1].code is FindingCode.DISK_SPACE_LOW
