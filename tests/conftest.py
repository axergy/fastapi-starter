import asyncio
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from src.app.core import db
from src.app.core.config import get_settings
from src.app.core.migrations import run_migrations_sync
from src.app.main import create_app


@pytest.fixture(scope="function")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine per test to avoid connection sharing issues."""
    # Reset the global engine to ensure tests use fresh connections
    await db.dispose_engine()

    settings = get_settings()
    # Use NullPool to avoid connection sharing across async contexts
    test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def test_tenant(engine: AsyncEngine) -> AsyncGenerator[str, None]:
    """
    Create isolated tenant schema for each test using Alembic migrations.
    This ensures tests use the exact same schema as production.
    """
    tenant_slug = f"test_{uuid4().hex[:8]}"
    schema_name = f"tenant_{tenant_slug}"

    # Register tenant in public schema first
    async with engine.connect() as conn:
        await conn.execute(
            text("""
                INSERT INTO tenants (id, name, slug, is_active, created_at)
                VALUES (gen_random_uuid(), :name, :slug, true, now())
                ON CONFLICT (slug) DO NOTHING
            """),
            {"name": f"Test {tenant_slug}", "slug": tenant_slug},
        )
        await conn.commit()

    # Run migrations for tenant schema (creates schema + tables)
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, run_migrations_sync, schema_name)

    yield tenant_slug

    # Cleanup: drop schema (CASCADE removes all tables + alembic_version)
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        await conn.execute(
            text("DELETE FROM public.tenants WHERE slug = :slug"),
            {"slug": tenant_slug},
        )
        await conn.commit()


@pytest.fixture
async def client(test_tenant: str) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with isolated tenant schema."""
    # Reset global engine before creating app to ensure clean state
    await db.dispose_engine()

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": test_tenant},
    ) as client:
        yield client

    # Dispose engine after test
    await db.dispose_engine()
