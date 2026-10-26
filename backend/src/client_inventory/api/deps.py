"""Dependencies the route handlers ask for.

The session factory and the settings live on the application object rather than in module
globals, so a test builds its own application against its own database and nothing has to
be monkeypatched.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from client_inventory.config import Baseline, Settings


def get_settings_from_app(request: Request) -> Settings:
    """Return the settings this application was built with."""
    settings: Settings = request.app.state.settings

    return settings


def get_baseline(settings: Annotated[Settings, Depends(get_settings_from_app)]) -> Baseline:
    """Return the active baseline."""
    return settings.baseline


def get_session(request: Request) -> Iterator[Session]:
    """Yield a session and commit it when the handler returned without raising.

    Committing here rather than in each handler means a handler cannot forget it, and a
    raised exception rolls the whole request back instead of leaving half of a submission
    behind.
    """
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_from_app)]
BaselineDep = Annotated[Baseline, Depends(get_baseline)]
