"""
Database engine and session factory.

Environment variables:
    DATABASE_URL: SQLAlchemy connection string (default: sqlite:///gym_coach.sqlite)
    MODEL_DIR: Directory for PyTorch model weights (default: ./models/)
"""
import os

from sqlalchemy import create_engine as _create_engine, event
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///gym_coach.sqlite")
MODEL_DIR = os.getenv("MODEL_DIR", "./models/")


def get_engine(url: str = DATABASE_URL):
    """Create SQLAlchemy engine. Use url param to override DATABASE_URL."""
    engine = _create_engine(url)

    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


# Module-level default engine — created once per process
_engine = None


def get_default_engine():
    """Get or create the default engine (lazy initialization)."""
    global _engine
    if _engine is None:
        _engine = get_engine()
    return _engine


def get_session(engine=None) -> Session:
    """Create a new session. Caller is responsible for context management.

    Usage:
        with get_session() as session:
            session.add(...)
            session.commit()
    """
    if engine is None:
        engine = get_default_engine()
    return Session(engine)
