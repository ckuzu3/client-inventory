"""Database tables.

Two tables, on purpose. `client` holds the current state of a machine and is updated in
place, which is what every screen and every query needs. `client_report` keeps each
submission, which is what makes "when did this device lose encryption" answerable at all.
Keeping only the current state would have been less code and a worse tool.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all tables."""


class Client(Base):
    """The current state of one managed client."""

    __tablename__ = "client"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String(253), unique=True, index=True)
    os_name: Mapped[str] = mapped_column(String(64), index=True)
    os_version: Mapped[str] = mapped_column(String(64))
    agent_version: Mapped[str] = mapped_column(String(32))
    encryption_enabled: Mapped[bool] = mapped_column()
    disk_total_gb: Mapped[float] = mapped_column(Float())
    disk_free_gb: Mapped[float] = mapped_column(Float())
    last_patched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    reports: Mapped[list[ClientReport]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="ClientReport.reported_at.desc()",
        lazy="selectin",
    )


class ClientReport(Base):
    """One submission from one client, kept as history."""

    __tablename__ = "client_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id", ondelete="CASCADE"), index=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    os_version: Mapped[str] = mapped_column(String(64))
    agent_version: Mapped[str] = mapped_column(String(32))
    encryption_enabled: Mapped[bool] = mapped_column()
    disk_total_gb: Mapped[float] = mapped_column(Float())
    disk_free_gb: Mapped[float] = mapped_column(Float())
    last_patched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    client: Mapped[Client] = relationship(back_populates="reports")
