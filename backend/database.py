"""Database engine, session factory and schema initialisation."""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def _sqlite_path(url: str) -> str | None:
    """Return the filesystem path of a SQLite URL, or ``None`` for non-file DBs."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    path = url[len(prefix):].split("?", 1)[0]
    if not path or path == ":memory:":
        return None
    return path


def make_engine(url: str) -> Engine:
    """Create an engine for ``url`` with sensible SQLite defaults."""
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        path = _sqlite_path(url)
        if path is None:
            # In-memory database: share one connection so every session sees the same data.
            kwargs["poolclass"] = StaticPool
        else:
            Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, **kwargs)


engine: Engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    # Import models so they register on Base.metadata before create_all.
    import backend.models  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import

    Base.metadata.create_all(bind=engine)
    logger.debug("Database initialised at %s", settings.database_url)
