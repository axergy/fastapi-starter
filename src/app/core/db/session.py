"""Database session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.app.core.db.engine import get_engine
from src.app.core.security.validators import validate_schema_name


@asynccontextmanager
async def get_tenant_session(
    tenant_schema: str,
    engine: AsyncEngine | None = None,
) -> AsyncGenerator[AsyncSession]:
    """
    Create a session scoped to a specific tenant schema.

    Uses connection-level search_path to ensure isolation even with connection pooling.
    """
    # Validate schema name before any SQL execution
    validate_schema_name(tenant_schema)

    if engine is None:
        engine = get_engine()

    async with engine.connect() as connection:
        try:
            # Use quote_ident to properly quote the schema name
            quoted_schema = await connection.scalar(
                text("SELECT quote_ident(:schema)").bindparams(schema=tenant_schema)
            )
            # Set search_path to ONLY the tenant schema for strict isolation
            # Public schema tables must be explicitly qualified (public.users, etc.)
            # This prevents accidental data leakage if tenant tables are missing
            await connection.execute(text(f"SET search_path TO {quoted_schema}"))
            await connection.commit()

            session_factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )

            async with session_factory() as session:
                yield session
        finally:
            # CRITICAL: Always reset before returning to pool
            if not connection.closed:
                await connection.execute(text("SET search_path TO public"))
                await connection.commit()


@asynccontextmanager
async def get_public_session(
    engine: AsyncEngine | None = None,
) -> AsyncGenerator[AsyncSession]:
    """Create a session for the public schema."""
    if engine is None:
        engine = get_engine()

    async with engine.connect() as connection:
        await connection.execute(text("SET search_path TO public"))
        await connection.commit()

        session_factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        async with session_factory() as session:
            yield session
