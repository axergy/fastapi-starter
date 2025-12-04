from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from src.app.core import db
from src.app.core.config import get_settings
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
    Create isolated tenant schema for each test.
    Automatically cleaned up after test.
    """
    tenant_slug = f"test_{uuid4().hex[:8]}"
    schema_name = f"tenant_{tenant_slug}"

    # Create schema and tables
    async with engine.connect() as conn:
        await conn.execute(text(f"CREATE SCHEMA {schema_name}"))
        await conn.execute(text(f"SET search_path TO {schema_name}"))
        await conn.execute(
            text("""
            CREATE TABLE users (
                id UUID PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
        )
        await conn.execute(
            text("""
            CREATE TABLE refresh_tokens (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id),
                token_hash VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL,
                revoked BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
        )
        await conn.execute(text("SET search_path TO public"))
        await conn.execute(
            text("""
            INSERT INTO tenants (id, name, slug, is_active, created_at)
            VALUES (gen_random_uuid(), :name, :slug, true, now())
            ON CONFLICT (slug) DO NOTHING
        """),
            {"name": f"Test Tenant {tenant_slug}", "slug": tenant_slug},
        )
        await conn.commit()

    yield tenant_slug

    # Cleanup
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
