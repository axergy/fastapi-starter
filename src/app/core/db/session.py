"""Database session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.app.core.db.engine import get_engine
from src.app.core.security.validators import validate_schema_name


@asynccontextmanager
async def get_session(
    tenant_schema: str | None = None,
    engine: AsyncEngine | None = None,
) -> AsyncGenerator[AsyncSession]:
    """Create a database session, optionally scoped to a tenant schema.

    Args:
        tenant_schema: If provided, session is scoped to this tenant schema.
                      If None, session uses the public schema.
        engine: Optional engine override for testing.

    Yields:
        AsyncSession bound to the appropriate schema.

    Note:
        When using tenant schema, search_path is set to ONLY that schema
        for strict isolation. Public schema tables must be explicitly
        qualified (public.users, etc.).
    """
    if engine is None:
        engine = get_engine()

    async with engine.connect() as connection:
        try:
            if tenant_schema is not None:
                # Validate schema name before any SQL execution
                validate_schema_name(tenant_schema)
                # Use quote_ident to properly quote the schema name
                quoted_schema = await connection.scalar(
                    text("SELECT quote_ident(:schema)").bindparams(schema=tenant_schema)
                )
                # Set search_path to ONLY the tenant schema for strict isolation
                await connection.execute(text(f"SET search_path TO {quoted_schema}"))
            else:
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
        finally:
            # CRITICAL: Always reset before returning to pool
            if tenant_schema is not None and not connection.closed:
                await connection.execute(text("SET search_path TO public"))
                await connection.commit()
