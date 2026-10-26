"""The migration has to produce the schema the models describe.

Without this test the two drift apart quietly: the test suite creates tables from the
models and passes, while a deployment runs the migration and gets a different schema.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from client_inventory.models import Base

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def alembic_config(database_url: str) -> Config:
    """Build an Alembic config that migrates the given database."""
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.attributes["configure_logger"] = False
    config.set_main_option("sqlalchemy.url", database_url)

    return config


def test_upgrade_head_creates_the_schema_the_models_describe(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migrated.sqlite3'}"

    command.upgrade(alembic_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        migrated_tables = {
            name for name in inspector.get_table_names() if name != "alembic_version"
        }

        assert migrated_tables == set(Base.metadata.tables)

        for table_name, table in Base.metadata.tables.items():
            migrated_columns = {column["name"] for column in inspector.get_columns(table_name)}
            assert migrated_columns == {column.name for column in table.columns}, table_name
    finally:
        engine.dispose()


def test_downgrade_removes_everything_again(tmp_path: Path) -> None:
    """A migration that cannot be rolled back is a one-way door, so this is checked too."""
    database_url = f"sqlite+pysqlite:///{tmp_path / 'roundtrip.sqlite3'}"
    config = alembic_config(database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(database_url)
    try:
        remaining = {
            name for name in inspect(engine).get_table_names() if name != "alembic_version"
        }

        assert remaining == set()
    finally:
        engine.dispose()
