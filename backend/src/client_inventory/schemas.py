"""Request and response models.

These are the API contract, kept separate from the ORM models on purpose: the table can
gain a column without that column appearing in a response, and a response can carry a
derived value like the compliance findings that no table holds.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from client_inventory.compliance import Finding, FindingCode, Severity, evaluate, free_disk_percent
from client_inventory.config import Baseline
from client_inventory.models import Client, ClientReport
from client_inventory.timeutils import ensure_utc, utc_now

# A report dated further into the future than this is rejected rather than stored. Some
# clock skew is normal on managed clients; a year is not skew, it is a broken clock, and
# storing it would push the device out of every "not seen recently" report forever.
MAXIMUM_CLOCK_SKEW = timedelta(days=1)

Hostname = Annotated[str, StringConstraints(min_length=1, max_length=253, strip_whitespace=True)]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=64, strip_whitespace=True)]
VersionText = Annotated[str, StringConstraints(min_length=1, max_length=32, strip_whitespace=True)]


class ClientReportIn(BaseModel):
    """What a collector sends.

    Unknown fields are rejected. A collector that misspells a field name should find out
    at once instead of having the value silently dropped, which is the failure mode that
    makes an inventory quietly wrong.
    """

    model_config = ConfigDict(extra="forbid")

    hostname: Hostname
    os_name: ShortText
    os_version: ShortText
    agent_version: VersionText
    encryption_enabled: bool
    disk_total_gb: Annotated[float, Field(gt=0)]
    disk_free_gb: Annotated[float, Field(ge=0)]
    last_patched_at: datetime | None = None
    reported_at: datetime | None = None

    @field_validator("hostname")
    @classmethod
    def normalise_hostname(cls, value: str) -> str:
        """Lowercase the hostname.

        Hostnames are case-insensitive, so WS-0001 and ws-0001 are one machine. Without
        this, a collector that changes its mind about capitalisation creates a second
        row and the fleet appears to grow.
        """
        return value.lower()

    @model_validator(mode="after")
    def check_consistency(self) -> Self:
        """Reject reports that contradict themselves."""
        if self.disk_free_gb > self.disk_total_gb:
            raise ValueError("disk_free_gb cannot be larger than disk_total_gb")

        now = utc_now()
        if self.reported_at is not None and ensure_utc(self.reported_at) > now + MAXIMUM_CLOCK_SKEW:
            raise ValueError("reported_at is too far in the future")

        if (
            self.last_patched_at is not None
            and ensure_utc(self.last_patched_at) > now + MAXIMUM_CLOCK_SKEW
        ):
            raise ValueError("last_patched_at is too far in the future")

        return self


class FindingOut(BaseModel):
    """One unmet baseline rule."""

    code: FindingCode
    severity: Severity
    detail: str

    @classmethod
    def from_finding(cls, finding: Finding) -> FindingOut:
        """Build the response model from an evaluated finding."""
        return cls(code=finding.code, severity=finding.severity, detail=finding.detail)


class ClientOut(BaseModel):
    """The current state of a client, with its compliance findings."""

    hostname: str
    os_name: str
    os_version: str
    agent_version: str
    encryption_enabled: bool
    disk_total_gb: float
    disk_free_gb: float
    free_disk_percent: float | None
    last_patched_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    compliant: bool
    findings: list[FindingOut]

    @classmethod
    def from_client(cls, client: Client, baseline: Baseline, now: datetime) -> ClientOut:
        """Build the response model, evaluating the baseline as part of it."""
        findings = evaluate(client, baseline, now)
        percent = free_disk_percent(client)

        return cls(
            hostname=client.hostname,
            os_name=client.os_name,
            os_version=client.os_version,
            agent_version=client.agent_version,
            encryption_enabled=client.encryption_enabled,
            disk_total_gb=client.disk_total_gb,
            disk_free_gb=client.disk_free_gb,
            free_disk_percent=None if percent is None else round(percent, 1),
            last_patched_at=(
                None if client.last_patched_at is None else ensure_utc(client.last_patched_at)
            ),
            first_seen_at=ensure_utc(client.first_seen_at),
            last_seen_at=ensure_utc(client.last_seen_at),
            compliant=not findings,
            findings=[FindingOut.from_finding(finding) for finding in findings],
        )


class ReportOut(BaseModel):
    """One historical submission."""

    reported_at: datetime
    os_version: str
    agent_version: str
    encryption_enabled: bool
    disk_total_gb: float
    disk_free_gb: float
    last_patched_at: datetime | None

    @classmethod
    def from_report(cls, report: ClientReport) -> ReportOut:
        """Build the response model from a stored report."""
        return cls(
            reported_at=ensure_utc(report.reported_at),
            os_version=report.os_version,
            agent_version=report.agent_version,
            encryption_enabled=report.encryption_enabled,
            disk_total_gb=report.disk_total_gb,
            disk_free_gb=report.disk_free_gb,
            last_patched_at=(
                None if report.last_patched_at is None else ensure_utc(report.last_patched_at)
            ),
        )


class ClientDetailOut(ClientOut):
    """A client plus its most recent submissions."""

    recent_reports: list[ReportOut]

    @classmethod
    def from_client_with_history(
        cls, client: Client, baseline: Baseline, now: datetime, limit: int
    ) -> ClientDetailOut:
        """Build the detail response, including at most `limit` historical reports."""
        current = ClientOut.from_client(client, baseline, now)

        return cls(
            **current.model_dump(),
            recent_reports=[ReportOut.from_report(report) for report in client.reports[:limit]],
        )


class ClientListOut(BaseModel):
    """A page of clients."""

    items: list[ClientOut]
    total: int
    limit: int
    offset: int


class ComplianceSummaryOut(BaseModel):
    """Fleet-wide counts, which is what a dashboard opens with."""

    evaluated_at: datetime
    total_clients: int
    compliant_clients: int
    noncompliant_clients: int
    findings_by_code: dict[str, int]
    findings_by_severity: dict[str, int]


class BaselineOut(BaseModel):
    """The active baseline.

    Exposed so a frontend can state what is being measured instead of hard-coding the
    thresholds a second time.
    """

    minimum_os_version: str
    os_version_applies_to: str
    require_encryption: bool
    maximum_patch_age_days: int
    maximum_last_seen_age_days: int
    minimum_disk_free_percent: float


class HealthOut(BaseModel):
    """Liveness and database reachability."""

    status: str
    database: str
