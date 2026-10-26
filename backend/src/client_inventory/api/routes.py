"""The HTTP surface.

Handlers stay thin: validate, call the repository, evaluate the baseline, return a
schema. Any rule that needs a decision lives in compliance.py, and any query lives in
repository.py.
"""

from __future__ import annotations

from collections import Counter
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from client_inventory import repository
from client_inventory.api.deps import BaselineDep, SessionDep, SettingsDep
from client_inventory.compliance import evaluate
from client_inventory.schemas import (
    BaselineOut,
    ClientDetailOut,
    ClientListOut,
    ClientOut,
    ClientReportIn,
    ComplianceSummaryOut,
    HealthOut,
)
from client_inventory.timeutils import utc_now

router = APIRouter(prefix="/api/v1")


@router.post(
    "/reports",
    response_model=ClientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an inventory report",
)
def submit_report(
    report: ClientReportIn,
    session: SessionDep,
    baseline: BaselineDep,
) -> ClientOut:
    """Record one submission and return the client's state as it now stands."""
    client = repository.record_report(session, report)

    return ClientOut.from_client(client, baseline, utc_now())


@router.get("/clients", response_model=ClientListOut, summary="List clients")
def list_clients(
    session: SessionDep,
    baseline: BaselineDep,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    os_name: Annotated[str | None, Query(max_length=64)] = None,
    only_with_findings: Annotated[bool, Query()] = False,
) -> ClientListOut:
    """Return a page of clients, the longest-silent first.

    `only_with_findings` is evaluated in the application rather than in SQL, because
    compliance is derived from the baseline and no column holds it. That pass is bounded
    by the configured scan limit.
    """
    now = utc_now()

    if only_with_findings:
        candidates = repository.list_clients_for_evaluation(
            session, settings.compliance_filter_scan_limit
        )
        matching = [client for client in candidates if evaluate(client, baseline, now)]
        page = matching[offset : offset + limit]

        return ClientListOut(
            items=[ClientOut.from_client(client, baseline, now) for client in page],
            total=len(matching),
            limit=limit,
            offset=offset,
        )

    clients = repository.list_clients(session, limit=limit, offset=offset, os_name=os_name)

    return ClientListOut(
        items=[ClientOut.from_client(client, baseline, now) for client in clients],
        total=repository.count_clients(session, os_name=os_name),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/clients/{hostname}",
    response_model=ClientDetailOut,
    summary="Get one client with its recent reports",
)
def get_client(
    hostname: str,
    session: SessionDep,
    baseline: BaselineDep,
    settings: SettingsDep,
) -> ClientDetailOut:
    """Return one client, its findings and its most recent submissions."""
    client = repository.get_client_by_hostname(session, hostname)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No client named '{hostname}' has reported in.",
        )

    return ClientDetailOut.from_client_with_history(
        client, baseline, utc_now(), settings.recent_reports_limit
    )


@router.get(
    "/compliance/summary",
    response_model=ComplianceSummaryOut,
    summary="Fleet-wide compliance counts",
)
def compliance_summary(
    session: SessionDep,
    baseline: BaselineDep,
    settings: SettingsDep,
) -> ComplianceSummaryOut:
    """Return how many clients are compliant and which rules are failing most."""
    now = utc_now()
    clients = repository.list_clients_for_evaluation(session, settings.compliance_filter_scan_limit)

    code_counter: Counter[str] = Counter()
    severity_counter: Counter[str] = Counter()
    compliant = 0

    for client in clients:
        findings = evaluate(client, baseline, now)
        if not findings:
            compliant += 1
            continue

        for finding in findings:
            code_counter[finding.code.value] += 1
            severity_counter[finding.severity.value] += 1

    return ComplianceSummaryOut(
        evaluated_at=now,
        total_clients=len(clients),
        compliant_clients=compliant,
        noncompliant_clients=len(clients) - compliant,
        findings_by_code=dict(sorted(code_counter.items())),
        findings_by_severity=dict(sorted(severity_counter.items())),
    )


@router.get("/baseline", response_model=BaselineOut, summary="The active baseline")
def get_baseline_endpoint(baseline: BaselineDep) -> BaselineOut:
    """Return the rules clients are measured against."""
    return BaselineOut(**baseline.model_dump())


health_router = APIRouter()


@health_router.get("/healthz", response_model=HealthOut, summary="Liveness and database check")
def healthz(request: Request) -> HealthOut:
    """Report whether the process is up and the database answers.

    This handler takes the engine rather than a session on purpose. A session dependency
    would fail before the handler ran when the database is down, and the endpoint would
    answer 500 instead of saying which part is unhealthy.
    """
    engine: Engine = request.app.state.engine

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return HealthOut(status="degraded", database="unreachable")

    return HealthOut(status="ok", database="reachable")
