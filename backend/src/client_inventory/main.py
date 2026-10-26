"""Application factory.

`create_app` takes its settings as an argument instead of reading a global, which is what
lets the test suite build an application against an in-memory database and the seeding
command reuse the same wiring.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from client_inventory.api.routes import health_router, router
from client_inventory.config import Settings, get_settings
from client_inventory.database import create_db_engine

API_DESCRIPTION = """
Collects inventory reports from managed clients and measures each one against a
configurable baseline: operating system build, disk encryption, patch age, last check-in
and free disk space.

All data in the development setup is synthetic. Nothing here is taken from a real
environment.
""".strip()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    Tables are not created here. Schema changes go through Alembic, so a process start
    cannot silently alter a production database.
    """
    active_settings = settings or get_settings()
    engine = create_db_engine(active_settings.database_url)

    app = FastAPI(
        title="Client Inventory",
        description=API_DESCRIPTION,
        version="0.1.0",
    )

    app.state.settings = active_settings
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    if active_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=active_settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    app.include_router(health_router)
    app.include_router(router)

    return app


app = create_app()
