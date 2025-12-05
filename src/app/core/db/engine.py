"""Database engine management."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.app.core.config import get_settings

_engine: AsyncEngine | None = None


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
        )
    return _engine


async def dispose_engine() -> None:
    """Dispose the database engine. Call during shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
