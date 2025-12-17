"""Shared database utilities for activities."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.app.core.config import get_settings

_sync_engine: Engine | None = None


def get_sync_engine() -> Engine:
    """Get or create synchronous database engine (singleton)."""
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        # Convert async URL to sync (asyncpg -> psycopg2)
        sync_url = settings.database_url.replace("+asyncpg", "")
        _sync_engine = create_engine(sync_url, pool_pre_ping=True)
    return _sync_engine


def dispose_sync_engine() -> None:
    """Dispose of the sync engine (call on worker shutdown)."""
    global _sync_engine
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
