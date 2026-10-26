"""Settings and the compliance baseline, read from the environment.

Everything configurable lives here so that a deployment can be described by environment
variables alone, and so the baseline is one object that can be handed to the evaluator
instead of a handful of loose constants.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Baseline(BaseModel):
    """The rules a reported client is measured against.

    The defaults describe a managed Windows fleet: a current Windows 11 build, encryption
    on, patched within the last month, seen within the last two weeks, and some disk left.
    """

    minimum_os_version: str = "10.0.26100"
    os_version_applies_to: str = "Windows"
    require_encryption: bool = True
    maximum_patch_age_days: int = Field(default=35, ge=1)
    maximum_last_seen_age_days: int = Field(default=14, ge=1)
    minimum_disk_free_percent: float = Field(default=10.0, ge=0.0, le=100.0)


class Settings(BaseSettings):
    """Application settings.

    Nested values use a double underscore, so the baseline's encryption rule is
    CLIENT_INVENTORY_BASELINE__REQUIRE_ENCRYPTION.
    """

    model_config = SettingsConfigDict(
        env_prefix="CLIENT_INVENTORY_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite+pysqlite:///./client-inventory.sqlite3"
    baseline: Baseline = Field(default_factory=Baseline)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4200"])

    # How many historical reports a client detail response carries.
    recent_reports_limit: int = Field(default=10, ge=1, le=100)

    # Upper bound for the in-memory compliance filter on the list endpoint. See the
    # walkthrough: compliance is derived rather than stored, which is fine at this scale
    # and is the first thing I would change if the fleet grew.
    compliance_filter_scan_limit: int = Field(default=5000, ge=1)


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read once per process."""
    return Settings()
