"""Measuring a client against the baseline.

This module is deliberately free of database and HTTP concerns: it takes the facts about
a client, a baseline and a point in time, and returns findings. That makes every rule
testable as a plain function call, and it means the API layer has no policy in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from client_inventory.config import Baseline
from client_inventory.timeutils import age_in_days
from client_inventory.versioning import InvalidVersionError, is_at_least


class Severity(StrEnum):
    """How much attention a finding deserves."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingCode(StrEnum):
    """The stable identifier of a rule.

    Codes are part of the API: a dashboard groups by them and an alert rule matches on
    them, so they are renamed only with a version bump.
    """

    OS_VERSION_BELOW_BASELINE = "os_version_below_baseline"
    OS_VERSION_UNREADABLE = "os_version_unreadable"
    ENCRYPTION_DISABLED = "encryption_disabled"
    PATCH_LEVEL_UNKNOWN = "patch_level_unknown"
    PATCH_LEVEL_OUTDATED = "patch_level_outdated"
    NOT_SEEN_RECENTLY = "not_seen_recently"
    DISK_SPACE_LOW = "disk_space_low"


@dataclass(frozen=True)
class Finding:
    """One rule that a client does not satisfy."""

    code: FindingCode
    severity: Severity
    detail: str


class ClientFacts(Protocol):
    """What the evaluator needs to know about a client.

    A protocol rather than the ORM model, so the rules can be tested with a small stub
    and never depend on a database session being open.
    """

    os_name: str
    os_version: str
    encryption_enabled: bool
    disk_total_gb: float
    disk_free_gb: float
    last_patched_at: datetime | None
    last_seen_at: datetime


def free_disk_percent(facts: ClientFacts) -> float | None:
    """Return the free disk space as a percentage, or None if the size is unusable."""
    if facts.disk_total_gb <= 0:
        return None

    return facts.disk_free_gb / facts.disk_total_gb * 100.0


def _check_os_version(facts: ClientFacts, baseline: Baseline) -> Finding | None:
    """Check the build number, but only for the operating system the rule is written for.

    The baseline carries a Windows build number. Measuring a macOS version against it
    would report every Mac as hopelessly out of date, which is noise rather than
    information, so a client running another operating system is skipped here.
    """
    if facts.os_name.casefold() != baseline.os_version_applies_to.casefold():
        return None

    try:
        if is_at_least(facts.os_version, baseline.minimum_os_version):
            return None
    except InvalidVersionError:
        return Finding(
            code=FindingCode.OS_VERSION_UNREADABLE,
            severity=Severity.MEDIUM,
            detail=f"Reported version '{facts.os_version}' could not be compared.",
        )

    return Finding(
        code=FindingCode.OS_VERSION_BELOW_BASELINE,
        severity=Severity.HIGH,
        detail=(
            f"Build {facts.os_version} is below the baseline of {baseline.minimum_os_version}."
        ),
    )


def _check_encryption(facts: ClientFacts, baseline: Baseline) -> Finding | None:
    """Check disk encryption against the baseline."""
    if not baseline.require_encryption or facts.encryption_enabled:
        return None

    return Finding(
        code=FindingCode.ENCRYPTION_DISABLED,
        severity=Severity.HIGH,
        detail="Disk encryption is off while the baseline requires it.",
    )


def _check_patch_level(facts: ClientFacts, baseline: Baseline, now: datetime) -> Finding | None:
    """Check how long ago the client was patched.

    An unknown patch date is rated higher than a late one. A late patch is a date in the
    plan; an unknown patch state cannot be planned at all, and in practice it means the
    client stopped reporting that fact for a reason nobody has looked at yet.
    """
    if facts.last_patched_at is None:
        return Finding(
            code=FindingCode.PATCH_LEVEL_UNKNOWN,
            severity=Severity.HIGH,
            detail="The client has never reported a patch date.",
        )

    age = age_in_days(facts.last_patched_at, now)
    if age <= baseline.maximum_patch_age_days:
        return None

    return Finding(
        code=FindingCode.PATCH_LEVEL_OUTDATED,
        severity=Severity.MEDIUM,
        detail=(
            f"Last patched {age:.0f} days ago, the baseline allows "
            f"{baseline.maximum_patch_age_days}."
        ),
    )


def _check_last_seen(facts: ClientFacts, baseline: Baseline, now: datetime) -> Finding | None:
    """Check when the client last reported in."""
    age = age_in_days(facts.last_seen_at, now)
    if age <= baseline.maximum_last_seen_age_days:
        return None

    return Finding(
        code=FindingCode.NOT_SEEN_RECENTLY,
        severity=Severity.MEDIUM,
        detail=(
            f"Last seen {age:.0f} days ago, the baseline allows "
            f"{baseline.maximum_last_seen_age_days}."
        ),
    )


def _check_disk_space(facts: ClientFacts, baseline: Baseline) -> Finding | None:
    """Check free disk space as a percentage of the total."""
    percent = free_disk_percent(facts)
    if percent is None or percent >= baseline.minimum_disk_free_percent:
        return None

    return Finding(
        code=FindingCode.DISK_SPACE_LOW,
        severity=Severity.LOW,
        detail=(
            f"{percent:.1f} percent free, the baseline wants at least "
            f"{baseline.minimum_disk_free_percent:.1f} percent."
        ),
    )


def evaluate(facts: ClientFacts, baseline: Baseline, now: datetime) -> list[Finding]:
    """Return every baseline rule the client does not satisfy.

    An empty list means compliant. `now` is a parameter rather than a call to the clock
    inside the function, so the ages in the tests are fixed numbers.
    """
    candidates = (
        _check_os_version(facts, baseline),
        _check_encryption(facts, baseline),
        _check_patch_level(facts, baseline, now),
        _check_last_seen(facts, baseline, now),
        _check_disk_space(facts, baseline),
    )

    findings = [finding for finding in candidates if finding is not None]
    severity_order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}

    return sorted(findings, key=lambda finding: (severity_order[finding.severity], finding.code))
