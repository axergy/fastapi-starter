"""Test fixtures for Lobby Pattern multi-tenant architecture."""

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
from src.app.core.security import hash_password
from src.app.main import create_app


@pytest.fixture(scope="function")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine per test to avoid connection sharing issues."""
    await db.dispose_engine()

    settings = get_settings()
    test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def test_tenant(engine: AsyncEngine) -> AsyncGenerator[str, None]:
    """Create isolated tenant for each test (Lobby Pattern).

    Creates:
    1. Tenant record in public.tenants (status=ready)
    2. Empty tenant schema (via migrations)
    """
    tenant_slug = f"test_{uuid4().hex[:8]}"
    schema_name = f"tenant_{tenant_slug}"

    # Create tenant record in public schema
    async with engine.connect() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, slug, status, is_active, created_at)
                VALUES (gen_random_uuid(), :name, :slug, 'ready', true, now())
                """
            ),
            {"name": f"Test {tenant_slug}", "slug": tenant_slug},
        )
        await conn.commit()

    # Run migrations for tenant schema (creates empty schema)
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, run_migrations_sync, schema_name)

    yield tenant_slug

    # Cleanup
    async with engine.connect() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        # Clean up membership, tokens, then users, then tenant
        await conn.execute(
            text(
                """
                DELETE FROM public.user_tenant_membership
                WHERE tenant_id = (SELECT id FROM public.tenants WHERE slug = :slug)
                """
            ),
            {"slug": tenant_slug},
        )
        await conn.execute(
            text(
                """
                DELETE FROM public.refresh_tokens
                WHERE tenant_id = (SELECT id FROM public.tenants WHERE slug = :slug)
                """
            ),
            {"slug": tenant_slug},
        )
        await conn.execute(
            text("DELETE FROM public.tenants WHERE slug = :slug"),
            {"slug": tenant_slug},
        )
        await conn.commit()


@pytest.fixture
async def test_user(engine: AsyncEngine, test_tenant: str) -> AsyncGenerator[dict, None]:
    """Create a test user with membership in test_tenant."""
    user_id = uuid4()
    email = f"testuser_{uuid4().hex[:8]}@example.com"
    password = "testpassword123"
    hashed = hash_password(password)

    async with engine.connect() as conn:
        # Create user in public.users
        await conn.execute(
            text(
                """
                INSERT INTO public.users
                (id, email, hashed_password, full_name, is_active, is_superuser,
                 created_at, updated_at)
                VALUES (:id, :email, :hashed_password, :full_name, true, false, now(), now())
                """
            ),
            {
                "id": user_id,
                "email": email,
                "hashed_password": hashed,
                "full_name": "Test User",
            },
        )

        # Get tenant_id
        result = await conn.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": test_tenant},
        )
        tenant_id = result.scalar_one()

        # Create membership
        await conn.execute(
            text(
                """
                INSERT INTO public.user_tenant_membership
                (user_id, tenant_id, role, is_active, created_at)
                VALUES (:user_id, :tenant_id, 'admin', true, now())
                """
            ),
            {"user_id": user_id, "tenant_id": tenant_id},
        )
        await conn.commit()

    yield {
        "id": str(user_id),
        "email": email,
        "password": password,
        "tenant_slug": test_tenant,
    }

    # Cleanup - explicitly delete user (membership is cleaned by test_tenant fixture)
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM public.users WHERE id = :id"),
            {"id": user_id},
        )
        await conn.commit()


@pytest.fixture
async def client(test_tenant: str) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with tenant header."""
    await db.dispose_engine()

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": test_tenant},
    ) as client:
        yield client

    await db.dispose_engine()


@pytest.fixture
async def client_no_tenant(engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """Create test client WITHOUT tenant header (for registration).

    Only cleans up data created by registration tests (non-test_ prefixed slugs).
    """
    await db.dispose_engine()

    # Pre-test cleanup - only clean non-test data (registration creates slugs without test_ prefix)
    async with engine.connect() as conn:
        # Delete memberships for non-test tenants
        await conn.execute(
            text(
                """
                DELETE FROM public.user_tenant_membership
                WHERE tenant_id IN (
                    SELECT id FROM public.tenants WHERE slug NOT LIKE 'test_%'
                )
                """
            )
        )
        # Delete tokens for non-test tenants
        await conn.execute(
            text(
                """
                DELETE FROM public.refresh_tokens
                WHERE tenant_id IN (
                    SELECT id FROM public.tenants WHERE slug NOT LIKE 'test_%'
                )
                """
            )
        )
        # Delete users not associated with test tenants
        await conn.execute(
            text(
                """
                DELETE FROM public.users
                WHERE id NOT IN (
                    SELECT user_id FROM public.user_tenant_membership
                )
                """
            )
        )
        # Delete non-test tenants
        await conn.execute(text("DELETE FROM public.tenants WHERE slug NOT LIKE 'test_%'"))
        await conn.commit()

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    await db.dispose_engine()

    # Post-test cleanup - same targeted cleanup
    async with engine.connect() as conn:
        await conn.execute(
            text(
                """
                DELETE FROM public.user_tenant_membership
                WHERE tenant_id IN (
                    SELECT id FROM public.tenants WHERE slug NOT LIKE 'test_%'
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                DELETE FROM public.refresh_tokens
                WHERE tenant_id IN (
                    SELECT id FROM public.tenants WHERE slug NOT LIKE 'test_%'
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                DELETE FROM public.users
                WHERE id NOT IN (
                    SELECT user_id FROM public.user_tenant_membership
                )
                """
            )
        )
        await conn.execute(text("DELETE FROM public.tenants WHERE slug NOT LIKE 'test_%'"))
        await conn.commit()
