"""Generate synthetic inventory data.

A reviewer should be able to clone this repository and see a populated dashboard in one
command, without a real fleet and without me shipping anyone's real data.

The generator is seeded, so the same seed produces the same fleet. That makes the sample
data reproducible for screenshots and lets the tests assert on it.
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from client_inventory import repository
from client_inventory.config import get_settings
from client_inventory.database import create_db_engine
from client_inventory.models import Base
from client_inventory.schemas import ClientReportIn
from client_inventory.timeutils import utc_now

# A spread of builds around the default baseline of 10.0.26100, so a generated fleet has
# both current and outdated machines in it.
WINDOWS_BUILDS = (
    "10.0.26100.1742",
    "10.0.26100.1000",
    "10.0.22631.4169",
    "10.0.19045.4529",
)
MACOS_VERSIONS = ("15.1", "14.7")
AGENT_VERSIONS = ("1.4.2", "1.4.0", "1.3.8")


def build_reports(count: int, seed: int, now: datetime) -> list[ClientReportIn]:
    """Build `count` synthetic reports without touching a database.

    Roughly one client in six is a Mac, which is what makes the "the OS baseline only
    applies to Windows" rule visible in the sample data.
    """
    rng = random.Random(seed)
    reports: list[ClientReportIn] = []

    for index in range(1, count + 1):
        is_mac = index % 6 == 0
        last_seen_days = rng.choice((0, 1, 2, 3, 5, 9, 20, 45))
        patch_age_days = rng.choice((2, 8, 15, 30, 48, 90))
        has_patch_date = rng.random() > 0.08
        disk_total = float(rng.choice((256, 512, 1024)))
        disk_free_ratio = rng.choice((0.04, 0.09, 0.18, 0.35, 0.6))

        reports.append(
            ClientReportIn(
                hostname=f"mac-{index:04d}" if is_mac else f"ws-{index:04d}",
                os_name="macOS" if is_mac else "Windows",
                os_version=rng.choice(MACOS_VERSIONS if is_mac else WINDOWS_BUILDS),
                agent_version=rng.choice(AGENT_VERSIONS),
                encryption_enabled=rng.random() > 0.12,
                disk_total_gb=disk_total,
                disk_free_gb=round(disk_total * disk_free_ratio, 1),
                last_patched_at=(now - timedelta(days=patch_age_days) if has_patch_date else None),
                reported_at=now - timedelta(days=last_seen_days, hours=rng.randrange(0, 24)),
            )
        )

    return reports


def seed_session(session: Session, reports: list[ClientReportIn]) -> int:
    """Write the reports through the same path the API uses and return how many landed."""
    for report in reports:
        repository.record_report(session, report)

    session.commit()

    return len(reports)


def main() -> None:
    """Command line entry point: client-inventory-seed."""
    parser = argparse.ArgumentParser(description="Fill the database with synthetic clients.")
    parser.add_argument("--count", type=int, default=40, help="How many clients to generate.")
    parser.add_argument("--seed", type=int, default=20261027, help="Random seed.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override the configured database URL.",
    )
    parser.add_argument(
        "--create-schema",
        action="store_true",
        help=(
            "Create the tables first. Convenient for a throwaway SQLite file; "
            "use Alembic for anything else."
        ),
    )
    arguments = parser.parse_args()

    settings = get_settings()
    engine = create_db_engine(arguments.database_url or settings.database_url)

    try:
        if arguments.create_schema:
            Base.metadata.create_all(engine)

        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        with session_factory() as session:
            written = seed_session(
                session, build_reports(arguments.count, arguments.seed, utc_now())
            )
    finally:
        engine.dispose()

    print(f"Wrote {written} synthetic client reports.")


if __name__ == "__main__":
    main()
