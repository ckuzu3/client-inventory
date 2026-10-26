"""The HTTP surface, exercised through the real application."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from client_inventory.timeutils import utc_now

NOW = utc_now()


def payload(**overrides: Any) -> dict[str, Any]:  # noqa: ANN401 - a JSON body is heterogeneous
    """Build a valid report body with individual fields replaced."""
    body: dict[str, Any] = {
        "hostname": "ws-0001",
        "os_name": "Windows",
        "os_version": "10.0.26100.1742",
        "agent_version": "1.4.2",
        "encryption_enabled": True,
        "disk_total_gb": 512.0,
        "disk_free_gb": 256.0,
        "last_patched_at": (NOW - timedelta(days=3)).isoformat(),
        "reported_at": NOW.isoformat(),
    }
    body.update(overrides)

    return body


def test_submitting_a_report_returns_the_evaluated_client(client: TestClient) -> None:
    response = client.post("/api/v1/reports", json=payload())

    assert response.status_code == 201
    body = response.json()
    assert body["hostname"] == "ws-0001"
    assert body["compliant"] is True
    assert body["findings"] == []
    assert body["free_disk_percent"] == 50.0


def test_a_noncompliant_client_comes_back_with_its_findings(client: TestClient) -> None:
    response = client.post(
        "/api/v1/reports",
        json=payload(encryption_enabled=False, os_version="10.0.19045.4529"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["compliant"] is False
    assert [finding["code"] for finding in body["findings"]] == [
        "encryption_disabled",
        "os_version_below_baseline",
    ]


def test_an_invalid_report_is_rejected_with_an_explanation(client: TestClient) -> None:
    response = client.post("/api/v1/reports", json=payload(disk_free_gb=9999.0))

    assert response.status_code == 422
    assert "disk_free_gb cannot be larger" in response.text


def test_an_unknown_field_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/reports", json=payload(encryption_enbaled=True))

    assert response.status_code == 422


def test_listing_is_paginated_and_reports_the_total(client: TestClient) -> None:
    for index in range(5):
        client.post("/api/v1/reports", json=payload(hostname=f"ws-{index:04d}"))

    response = client.get("/api/v1/clients", params={"limit": 2, "offset": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0


def test_listing_can_be_filtered_by_operating_system(client: TestClient) -> None:
    client.post("/api/v1/reports", json=payload(hostname="ws-0001"))
    client.post(
        "/api/v1/reports",
        json=payload(hostname="mac-0001", os_name="macOS", os_version="15.1"),
    )

    response = client.get("/api/v1/clients", params={"os_name": "macOS"})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["hostname"] == "mac-0001"


def test_listing_can_be_reduced_to_clients_with_findings(client: TestClient) -> None:
    client.post("/api/v1/reports", json=payload(hostname="ws-good"))
    client.post("/api/v1/reports", json=payload(hostname="ws-bad", encryption_enabled=False))

    response = client.get("/api/v1/clients", params={"only_with_findings": True})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["hostname"] == "ws-bad"


def test_a_rejected_page_size_does_not_reach_the_database(client: TestClient) -> None:
    response = client.get("/api/v1/clients", params={"limit": 500})

    assert response.status_code == 422


def test_the_detail_endpoint_carries_the_report_history(client: TestClient) -> None:
    client.post("/api/v1/reports", json=payload())
    client.post(
        "/api/v1/reports",
        json=payload(
            encryption_enabled=False,
            reported_at=(NOW + timedelta(hours=1)).isoformat(),
        ),
    )

    response = client.get("/api/v1/clients/ws-0001")

    assert response.status_code == 200
    body = response.json()
    assert len(body["recent_reports"]) == 2
    assert body["recent_reports"][0]["encryption_enabled"] is False
    assert body["compliant"] is False


def test_the_detail_endpoint_is_case_insensitive(client: TestClient) -> None:
    client.post("/api/v1/reports", json=payload(hostname="ws-0042"))

    assert client.get("/api/v1/clients/WS-0042").status_code == 200


def test_an_unknown_hostname_is_a_404_that_says_so(client: TestClient) -> None:
    response = client.get("/api/v1/clients/ws-nothing")

    assert response.status_code == 404
    assert "ws-nothing" in response.json()["detail"]


def test_the_summary_counts_clients_and_findings(client: TestClient) -> None:
    client.post("/api/v1/reports", json=payload(hostname="ws-good"))
    client.post("/api/v1/reports", json=payload(hostname="ws-bad", encryption_enabled=False))
    client.post(
        "/api/v1/reports",
        json=payload(hostname="ws-older", os_version="10.0.22631.4169", last_patched_at=None),
    )

    body = client.get("/api/v1/compliance/summary").json()

    assert body["total_clients"] == 3
    assert body["compliant_clients"] == 1
    assert body["noncompliant_clients"] == 2
    assert body["findings_by_code"]["encryption_disabled"] == 1
    assert body["findings_by_code"]["os_version_below_baseline"] == 1
    assert body["findings_by_code"]["patch_level_unknown"] == 1
    assert body["findings_by_severity"]["high"] == 3


def test_the_summary_of_an_empty_fleet_is_all_zeros(client: TestClient) -> None:
    body = client.get("/api/v1/compliance/summary").json()

    assert body["total_clients"] == 0
    assert body["findings_by_code"] == {}


def test_the_baseline_endpoint_states_what_is_measured(client: TestClient) -> None:
    body = client.get("/api/v1/baseline").json()

    assert body["minimum_os_version"] == "10.0.26100"
    assert body["require_encryption"] is True
    assert body["os_version_applies_to"] == "Windows"


def test_healthz_reports_a_reachable_database(client: TestClient) -> None:
    body = client.get("/healthz").json()

    assert body == {"status": "ok", "database": "reachable"}


def test_the_openapi_document_is_served(client: TestClient) -> None:
    """A documented API is part of the deliverable, so it is worth a test."""
    document = client.get("/openapi.json").json()

    assert "/api/v1/reports" in document["paths"]
    assert document["info"]["title"] == "Client Inventory"
