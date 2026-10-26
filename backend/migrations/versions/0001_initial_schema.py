"""Initial schema: client and client_report.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create both tables and their indexes."""
    op.create_table(
        "client",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column("os_name", sa.String(length=64), nullable=False),
        sa.Column("os_version", sa.String(length=64), nullable=False),
        sa.Column("agent_version", sa.String(length=32), nullable=False),
        sa.Column("encryption_enabled", sa.Boolean(), nullable=False),
        sa.Column("disk_total_gb", sa.Float(), nullable=False),
        sa.Column("disk_free_gb", sa.Float(), nullable=False),
        sa.Column("last_patched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_client_hostname"), "client", ["hostname"], unique=True)
    op.create_index(op.f("ix_client_os_name"), "client", ["os_name"], unique=False)
    op.create_index(op.f("ix_client_last_seen_at"), "client", ["last_seen_at"], unique=False)

    op.create_table(
        "client_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("os_version", sa.String(length=64), nullable=False),
        sa.Column("agent_version", sa.String(length=32), nullable=False),
        sa.Column("encryption_enabled", sa.Boolean(), nullable=False),
        sa.Column("disk_total_gb", sa.Float(), nullable=False),
        sa.Column("disk_free_gb", sa.Float(), nullable=False),
        sa.Column("last_patched_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["client.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_client_report_client_id"), "client_report", ["client_id"])
    op.create_index(op.f("ix_client_report_reported_at"), "client_report", ["reported_at"])


def downgrade() -> None:
    """Drop both tables."""
    op.drop_index(op.f("ix_client_report_reported_at"), table_name="client_report")
    op.drop_index(op.f("ix_client_report_client_id"), table_name="client_report")
    op.drop_table("client_report")

    op.drop_index(op.f("ix_client_last_seen_at"), table_name="client")
    op.drop_index(op.f("ix_client_os_name"), table_name="client")
    op.drop_index(op.f("ix_client_hostname"), table_name="client")
    op.drop_table("client")
