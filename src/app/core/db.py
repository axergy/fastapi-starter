from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.app.core.config import get_settings
from src.app.core.validators import validate_schema_name

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


@asynccontextmanager
async def get_tenant_session(
    tenant_schema: str,
    engine: AsyncEngine | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a session scoped to a specific tenant schema.

    Uses connection-level search_path to ensure isolation even with connection pooling.
    """
    # Validate schema name before any SQL execution
    validate_schema_name(tenant_schema)

    if engine is None:
        engine = get_engine()

    async with engine.connect() as connection:
        # Use quote_ident to properly quote the schema name
        quoted_schema = await connection.scalar(
            text("SELECT quote_ident(:schema)").bindparams(schema=tenant_schema)
        )
        await connection.execute(text(f"SET search_path TO {quoted_schema}, public"))
        await connection.commit()

        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        async with session_factory() as session:
            try:
                yield session
            finally:
                await connection.execute(text("SET search_path TO public"))
                await connection.commit()


@asynccontextmanager
async def get_public_session(
    engine: AsyncEngine | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Create a session for the public schema."""
    if engine is None:
        engine = get_engine()

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        yield session
