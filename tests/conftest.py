"""Test fixtures for Lobby Pattern multi-tenant architecture."""

import asyncio
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid7

import pytest
from fakeredis import aioredis as fakeredis_aio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from src.app.core import db
from src.app.core import redis as redis_module
from src.app.core.config import get_settings
from src.app.core.db import run_migrations_sync
from src.app.core.security import hash_password
from src.app.main import create_app


@pytest.fixture(scope="function")
async def engine() -> AsyncGenerator[AsyncEngine]:
    """Create test database engine and ensure public schema migrations are applied."""
    await db.dispose_engine()

    settings = get_settings()
    test_engine = create_async_engine(settings.database_url, poolclass=NullPool)

    # Run public schema migrations to ensure tables exist
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, run_migrations_sync, None)

    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def test_tenant(engine: AsyncEngine) -> AsyncGenerator[str]:
    """Create isolated tenant for each test (Lobby Pattern).

    Creates:
    1. Tenant record in public.tenants (status=ready)
    2. Empty tenant schema (via migrations)
    """
    # Use last 8 chars of UUID7 (random part) to ensure uniqueness in parallel tests
    tenant_slug = f"test_{uuid7().hex[-8:]}"
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
        # Clean up invites, membership, tokens, then users, then tenant
        await conn.execute(
            text(
                """
                DELETE FROM public.tenant_invites
                WHERE tenant_id = (SELECT id FROM public.tenants WHERE slug = :slug)
                """
            ),
            {"slug": tenant_slug},
        )
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
async def test_user(engine: AsyncEngine, test_tenant: str) -> AsyncGenerator[dict]:
    """Create a test user with membership in test_tenant."""
    user_id = uuid7()
    email = f"testuser_{uuid7().hex[-8:]}@example.com"
    password = "testpassword123"
    hashed = hash_password(password)

    async with engine.connect() as conn:
        # Create user in public.users (with email_verified=true for testing)
        await conn.execute(
            text(
                """
                INSERT INTO public.users
                (id, email, hashed_password, full_name, is_active, is_superuser,
                 email_verified, email_verified_at, created_at, updated_at)
                VALUES (:id, :email, :hashed_password, :full_name, true, false,
                 true, now(), now(), now())
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
async def client(test_tenant: str) -> AsyncGenerator[AsyncClient]:
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
async def test_superuser(engine: AsyncEngine) -> AsyncGenerator[dict]:
    """Create a test superuser (no tenant context needed)."""
    user_id = uuid7()
    email = f"superuser_{uuid7().hex[-8:]}@example.com"
    password = "superpassword123"
    hashed = hash_password(password)

    async with engine.connect() as conn:
        # Create superuser in public.users (with email_verified=true and is_superuser=true)
        await conn.execute(
            text(
                """
                INSERT INTO public.users
                (id, email, hashed_password, full_name, is_active, is_superuser,
                 email_verified, email_verified_at, created_at, updated_at)
                VALUES (:id, :email, :hashed_password, :full_name, true, true,
                 true, now(), now(), now())
                """
            ),
            {
                "id": user_id,
                "email": email,
                "hashed_password": hashed,
                "full_name": "Super User",
            },
        )
        await conn.commit()

    yield {
        "id": str(user_id),
        "email": email,
        "password": password,
    }

    # Cleanup
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM public.users WHERE id = :id"),
            {"id": user_id},
        )
        await conn.commit()


@pytest.fixture
async def test_superuser_with_tenant(engine: AsyncEngine, test_tenant: str) -> AsyncGenerator[dict]:
    """Create a test superuser WITH membership in test_tenant."""
    user_id = uuid7()
    email = f"superuser_{uuid7().hex[-8:]}@example.com"
    password = "superpassword123"
    hashed = hash_password(password)

    async with engine.connect() as conn:
        # Create superuser in public.users
        await conn.execute(
            text(
                """
                INSERT INTO public.users
                (id, email, hashed_password, full_name, is_active, is_superuser,
                 email_verified, email_verified_at, created_at, updated_at)
                VALUES (:id, :email, :hashed_password, :full_name, true, true,
                 true, now(), now(), now())
                """
            ),
            {
                "id": user_id,
                "email": email,
                "hashed_password": hashed,
                "full_name": "Super User",
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

    # Cleanup - delete membership first, then user
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM public.user_tenant_membership WHERE user_id = :id"),
            {"id": user_id},
        )
        await conn.execute(
            text("DELETE FROM public.users WHERE id = :id"),
            {"id": user_id},
        )
        await conn.commit()


@pytest.fixture
async def client_no_tenant(engine: AsyncEngine) -> AsyncGenerator[AsyncClient]:
    """Create test client WITHOUT tenant header (for registration).

    IMPORTANT: Does NOT do aggressive cleanup to avoid interfering with parallel tests.
    Cleanup is scoped to avoid affecting other workers' data.
    """
    await db.dispose_engine()

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    await db.dispose_engine()


# --- Redis Test Fixtures ---


@pytest.fixture
async def fake_redis() -> AsyncGenerator[Redis]:
    """Provides a fakeredis client for testing.

    Returns an in-memory Redis implementation that behaves like
    a real Redis server but doesn't require external dependencies.
    """
    client = fakeredis_aio.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def mock_redis(fake_redis: Redis, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Redis]:
    """Patches get_redis() to return fakeredis client.

    Use this fixture when testing code that depends on Redis
    being available and working.

    Patches both src.app.core.redis and src.app.core.cache modules
    to ensure the fake redis is used everywhere.
    """
    redis_module.reset_redis_state()

    async def _get_fake_redis() -> Redis:
        return fake_redis

    # Patch in both modules that import get_redis
    monkeypatch.setattr("src.app.core.redis.get_redis", _get_fake_redis)
    monkeypatch.setattr("src.app.core.cache.get_redis", _get_fake_redis)
    yield fake_redis
    redis_module.reset_redis_state()


@pytest.fixture
async def mock_redis_unavailable(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    """Patches get_redis() to return None (simulates Redis unavailable).

    Use this fixture when testing graceful degradation when
    Redis is not available.

    Patches both src.app.core.redis and src.app.core.cache modules
    to ensure Redis appears unavailable everywhere.
    """
    redis_module.reset_redis_state()

    async def _get_none() -> None:
        return None

    # Patch in both modules that import get_redis
    monkeypatch.setattr("src.app.core.redis.get_redis", _get_none)
    monkeypatch.setattr("src.app.core.cache.get_redis", _get_none)
    yield
    redis_module.reset_redis_state()
