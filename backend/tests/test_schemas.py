"""Validation of what a collector is allowed to send."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from client_inventory.schemas import ClientReportIn
from client_inventory.timeutils import utc_now


def valid_payload(**overrides: object) -> dict[str, object]:
    """Build a report that passes validation, with individual fields replaced."""
    payload: dict[str, object] = {
        "hostname": "ws-0001",
        "os_name": "Windows",
        "os_version": "10.0.26100.1742",
        "agent_version": "1.4.2",
        "encryption_enabled": True,
        "disk_total_gb": 512.0,
        "disk_free_gb": 256.0,
    }
    payload.update(overrides)

    return payload


def test_a_hostname_is_stored_in_lower_case() -> None:
    """WS-0001 and ws-0001 are one machine, so they must not become two rows."""
    report = ClientReportIn.model_validate(valid_payload(hostname="WS-0001"))

    assert report.hostname == "ws-0001"


def test_surrounding_whitespace_is_stripped() -> None:
    report = ClientReportIn.model_validate(valid_payload(hostname="  ws-0002  "))

    assert report.hostname == "ws-0002"


def test_free_space_larger_than_the_disk_is_rejected() -> None:
    with pytest.raises(ValidationError, match="disk_free_gb cannot be larger"):
        ClientReportIn.model_validate(valid_payload(disk_free_gb=600.0))


def test_a_disk_of_zero_size_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClientReportIn.model_validate(valid_payload(disk_total_gb=0.0))


def test_a_report_dated_far_in_the_future_is_rejected() -> None:
    """A broken clock would otherwise keep the device out of every staleness report."""
    with pytest.raises(ValidationError, match="reported_at is too far in the future"):
        ClientReportIn.model_validate(
            valid_payload(reported_at=(utc_now() + timedelta(days=400)).isoformat())
        )


def test_a_patch_date_in_the_future_is_rejected() -> None:
    with pytest.raises(ValidationError, match="last_patched_at is too far in the future"):
        ClientReportIn.model_validate(
            valid_payload(last_patched_at=(utc_now() + timedelta(days=10)).isoformat())
        )


def test_a_small_clock_skew_is_tolerated() -> None:
    """Managed clients drift by minutes; rejecting that would lose real reports."""
    report = ClientReportIn.model_validate(
        valid_payload(reported_at=(utc_now() + timedelta(minutes=5)).isoformat())
    )

    assert report.reported_at is not None


def test_an_unknown_field_is_rejected() -> None:
    """A misspelled field should fail loudly instead of being dropped in silence."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ClientReportIn.model_validate(valid_payload(encryption_enbaled=True))


def test_an_empty_hostname_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClientReportIn.model_validate(valid_payload(hostname="   "))
