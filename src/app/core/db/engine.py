"""Database engine management."""

import ssl
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.app.core.config import get_settings

_engine: AsyncEngine | None = None
_sync_engine: Engine | None = None


def _get_connect_args() -> dict[str, Any]:
    """Get connection arguments including SSL configuration."""
    settings = get_settings()
    connect_args: dict[str, Any] = {
        "statement_cache_size": settings.database_statement_cache_size,
    }

    ssl_mode = settings.database_ssl_mode
    if ssl_mode != "disable":
        ssl_context = ssl.create_default_context()
        if ssl_mode == "prefer" or ssl_mode == "require":
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        elif ssl_mode in ("verify-ca", "verify-full"):
            ssl_context.check_hostname = ssl_mode == "verify-full"
            ssl_context.verify_mode = ssl.CERT_REQUIRED
        connect_args["ssl"] = ssl_context

    return connect_args


def get_engine() -> AsyncEngine:
    """Get or create the database engine singleton."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            connect_args=_get_connect_args(),
        )
    return _engine


async def dispose_engine() -> None:
    """Dispose the database engine. Call during shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def get_sync_engine() -> Engine:
    """Get or create synchronous database engine singleton.

    Used by Temporal activities which run in thread pools and need sync DB access.
    Converts asyncpg URL to psycopg2 (sync driver).
    """
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        # Convert async URL to sync (asyncpg -> psycopg2)
        sync_url = settings.database_url.replace("+asyncpg", "")
        _sync_engine = create_engine(sync_url, pool_pre_ping=True)
    return _sync_engine


def dispose_sync_engine() -> None:
    """Dispose of the sync engine. Call on Temporal worker shutdown."""
    global _sync_engine
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
