"""Root test fixtures shared across all test types.

This conftest contains fixtures that can be used by both unit and integration tests.
Database-specific fixtures are in tests/integration/conftest.py.
"""

import os

# Set APP_ENV to testing before any app imports to disable rate limiting
os.environ.setdefault("APP_ENV", "testing")
# Disable SSL for local test database (PostgreSQL without SSL support)
os.environ.setdefault("DATABASE_SSL_MODE", "disable")

# ruff: noqa: E402 - Imports must be after env var setup
from collections.abc import AsyncGenerator

import pytest
from fakeredis import aioredis as fakeredis_aio
from redis.asyncio import Redis

from src.app.core import rate_limit
from src.app.core import redis as redis_core
from src.app.core.config import get_settings

# Clear settings cache to ensure test environment variables are picked up
get_settings.cache_clear()

# --- Rate Limit Fixtures ---


@pytest.fixture
def reset_rate_limit_buckets() -> None:
    """Reset rate limit in-memory state.

    Use this fixture when you need to ensure rate limit state is clean.
    """
    rate_limit._rate_limit_buckets.clear()
    rate_limit._script_sha = None
    yield
    rate_limit._rate_limit_buckets.clear()
    rate_limit._script_sha = None


# --- Redis Test Fixtures (shared) ---


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
    redis_core.reset_redis_state()

    async def _get_fake_redis() -> Redis:
        return fake_redis

    # Patch in both modules that import get_redis
    monkeypatch.setattr("src.app.core.redis.get_redis", _get_fake_redis)
    monkeypatch.setattr("src.app.core.cache.get_redis", _get_fake_redis)
    yield fake_redis
    redis_core.reset_redis_state()


@pytest.fixture
async def mock_redis_unavailable(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[None]:
    """Patches get_redis() to return None (simulates Redis unavailable).

    Use this fixture when testing graceful degradation when
    Redis is not available.

    Patches both src.app.core.redis and src.app.core.cache modules
    to ensure Redis appears unavailable everywhere.
    """
    redis_core.reset_redis_state()

    async def _get_none() -> None:
        return None

    # Patch in both modules that import get_redis
    monkeypatch.setattr("src.app.core.redis.get_redis", _get_none)
    monkeypatch.setattr("src.app.core.cache.get_redis", _get_none)
    yield
    redis_core.reset_redis_state()
