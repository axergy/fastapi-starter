"""Integration test fixtures for database and HTTP client operations.

These fixtures require external resources (PostgreSQL database).
Uses polyfactory for type-safe test data generation.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from src.app.core import db
from src.app.core import redis as redis_core
from src.app.core.config import get_settings
from src.app.core.db import run_migrations_sync
from src.app.main import create_app
from src.app.models.enums import MembershipRole
from tests.factories import (
    DEFAULT_TEST_PASSWORD,
    TenantFactory,
    UserFactory,
    UserTenantMembershipFactory,
)
from tests.utils.cleanup import (
    cleanup_tenant_cascade,
    cleanup_user_cascade,
    drop_tenant_schema,
)


@pytest.fixture(autouse=True)
async def _reset_redis_between_tests() -> AsyncGenerator[None]:
    """Reset Redis state between tests to prevent event loop issues.

    Redis clients hold references to their event loop. When pytest creates
    a new event loop for each test, stale Redis clients cause
    'Event loop is closed' errors. This fixture ensures Redis is properly
    closed after each test.
    """
    # Reset before test
    redis_core.reset_redis_state()
    yield
    # Close and reset after test
    await redis_core.close_redis()


@pytest.fixture(scope="function")
async def engine() -> AsyncGenerator[AsyncEngine]:
    """Create test database engine and ensure public schema migrations are applied."""
    await db.dispose_engine()

    settings = get_settings()
    test_engine = create_async_engine(settings.database_url, poolclass=NullPool)

    # Run public schema migrations to ensure tables exist
    await asyncio.to_thread(run_migrations_sync, None)

    yield test_engine
    await test_engine.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Provide an async session for database operations.

    IMPORTANT: The AsyncSession context manager only closes the session on exit;
    it does NOT auto-commit. Tests must explicitly call `await session.commit()`
    to persist changes to the database. Alternatively, use fixtures like
    `test_tenant` or `test_user` which handle commit/rollback internally.
    """
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
async def test_tenant(engine: AsyncEngine, db_session: AsyncSession) -> AsyncGenerator[str]:
    """Create isolated tenant for each test (Lobby Pattern).

    Creates:
    1. Tenant record in public.tenants (status=ready)
    2. Empty tenant schema (via migrations)
    """
    # Create tenant using factory
    tenant = TenantFactory.build()
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    schema_name = tenant.schema_name

    # Run migrations for tenant schema (creates empty schema)
    await asyncio.to_thread(run_migrations_sync, schema_name)

    yield tenant.slug

    # Cleanup using utilities
    async with engine.connect() as conn:
        await drop_tenant_schema(conn, schema_name)
        await cleanup_tenant_cascade(conn, tenant.id)
        await conn.commit()


@pytest.fixture
async def test_tenant_obj(engine: AsyncEngine, db_session: AsyncSession) -> AsyncGenerator:
    """Create isolated tenant and return the Tenant object (not just slug).

    Useful for tests that need direct access to tenant.id.
    """
    # Create tenant using factory
    tenant = TenantFactory.build()
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)

    schema_name = tenant.schema_name

    # Run migrations for tenant schema (creates empty schema)
    await asyncio.to_thread(run_migrations_sync, schema_name)

    yield tenant

    # Cleanup using utilities
    async with engine.connect() as conn:
        await drop_tenant_schema(conn, schema_name)
        await cleanup_tenant_cascade(conn, tenant.id)
        await conn.commit()


@pytest.fixture
async def test_user(
    engine: AsyncEngine, db_session: AsyncSession, test_tenant: str
) -> AsyncGenerator[dict]:
    """Create a test user with admin membership in test_tenant."""
    # Get tenant_id
    result = await db_session.execute(
        text("SELECT id FROM public.tenants WHERE slug = :slug"),
        {"slug": test_tenant},
    )
    tenant_id = result.scalar_one()

    # Create user using factory
    user = UserFactory.build()
    db_session.add(user)
    await db_session.flush()

    # Create membership
    membership = UserTenantMembershipFactory.build(
        user_id=user.id,
        tenant_id=tenant_id,
        role=MembershipRole.ADMIN.value,
    )
    db_session.add(membership)
    await db_session.commit()

    yield {
        "id": str(user.id),
        "email": user.email,
        "password": DEFAULT_TEST_PASSWORD,
        "tenant_slug": test_tenant,
    }

    # Cleanup using utilities
    async with engine.connect() as conn:
        await cleanup_user_cascade(conn, user.id)
        await conn.commit()


@pytest.fixture
async def client(test_tenant: str) -> AsyncGenerator[AsyncClient]:
    """Create test client with tenant header."""
    await db.dispose_engine()

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-Slug": test_tenant},
    ) as client:
        yield client

    await db.dispose_engine()


@pytest.fixture
async def test_superuser(engine: AsyncEngine, db_session: AsyncSession) -> AsyncGenerator[dict]:
    """Create a test superuser (no tenant context needed)."""
    # Create superuser using factory
    user = UserFactory.superuser()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    yield {
        "id": str(user.id),
        "email": user.email,
        "password": DEFAULT_TEST_PASSWORD,
    }

    # Cleanup
    async with engine.connect() as conn:
        await conn.execute(
            text("DELETE FROM public.users WHERE id = :id"),
            {"id": user.id},
        )
        await conn.commit()


@pytest.fixture
async def test_superuser_with_tenant(
    engine: AsyncEngine, db_session: AsyncSession, test_tenant: str
) -> AsyncGenerator[dict]:
    """Create a test superuser WITH membership in test_tenant."""
    # Get tenant_id
    result = await db_session.execute(
        text("SELECT id FROM public.tenants WHERE slug = :slug"),
        {"slug": test_tenant},
    )
    tenant_id = result.scalar_one()

    # Create superuser using factory
    user = UserFactory.superuser()
    db_session.add(user)
    await db_session.flush()

    # Create membership
    membership = UserTenantMembershipFactory.build(
        user_id=user.id,
        tenant_id=tenant_id,
        role=MembershipRole.ADMIN.value,
    )
    db_session.add(membership)
    await db_session.commit()

    yield {
        "id": str(user.id),
        "email": user.email,
        "password": DEFAULT_TEST_PASSWORD,
        "tenant_slug": test_tenant,
    }

    # Cleanup using utilities
    async with engine.connect() as conn:
        await cleanup_user_cascade(conn, user.id)
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
