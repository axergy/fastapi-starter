"""Tests for Redis client module (src/app/core/redis.py)."""

import pytest

from src.app.core import redis as redis_module
from src.app.core.redis import close_redis, get_redis, reset_redis_state


class TestGetRedis:
    """Tests for get_redis() function."""

    async def test_get_redis_returns_none_when_not_configured(self) -> None:
        """When REDIS_URL is not set, get_redis() should return None."""
        # Reset state to ensure clean test
        reset_redis_state()

        # Without REDIS_URL configured, should return None
        result = await get_redis()
        assert result is None

    async def test_get_redis_does_not_retry_after_initial_attempt(self) -> None:
        """After initial connection attempt fails, subsequent calls return None without retry."""
        reset_redis_state()

        # First call - marks _connection_attempted = True
        result1 = await get_redis()
        assert result1 is None

        # Second call - should return None immediately without retrying
        result2 = await get_redis()
        assert result2 is None

        # Verify the module state
        assert redis_module._connection_attempted is True
        assert redis_module._redis is None

    async def test_reset_redis_state_clears_connection(self) -> None:
        """reset_redis_state() should clear all module-level state."""
        # Set up some state
        redis_module._connection_attempted = True
        redis_module._redis = "dummy"  # type: ignore[assignment]
        redis_module._pool = "dummy"  # type: ignore[assignment]

        # Reset
        reset_redis_state()

        # Verify all state is cleared
        assert redis_module._connection_attempted is False
        assert redis_module._redis is None
        assert redis_module._pool is None


class TestCloseRedis:
    """Tests for close_redis() function."""

    async def test_close_redis_when_not_connected(self) -> None:
        """close_redis() should not error when nothing is connected."""
        reset_redis_state()

        # Should not raise any exceptions
        await close_redis()

        # State should remain cleared
        assert redis_module._redis is None
        assert redis_module._pool is None
        assert redis_module._connection_attempted is False

    async def test_close_redis_resets_connection_attempted(self) -> None:
        """close_redis() should reset _connection_attempted flag."""
        # Simulate a failed connection attempt
        reset_redis_state()
        await get_redis()  # Sets _connection_attempted = True

        assert redis_module._connection_attempted is True

        # Close should reset the flag
        await close_redis()

        assert redis_module._connection_attempted is False


class TestRedisWithFakeredis:
    """Tests using fakeredis for realistic Redis operations."""

    async def test_mock_redis_fixture_works(self, mock_redis: pytest.fixture) -> None:
        """Verify the mock_redis fixture provides working Redis client."""
        # Should be able to perform basic operations
        await mock_redis.set("test_key", "test_value")
        result = await mock_redis.get("test_key")
        assert result == "test_value"

    async def test_mock_redis_setex_with_ttl(self, mock_redis: pytest.fixture) -> None:
        """Verify setex works with TTL."""
        await mock_redis.setex("ttl_key", 3600, "value")
        result = await mock_redis.get("ttl_key")
        assert result == "value"

        # Verify TTL is set
        ttl = await mock_redis.ttl("ttl_key")
        assert ttl > 0
        assert ttl <= 3600

    async def test_mock_redis_pipeline(self, mock_redis: pytest.fixture) -> None:
        """Verify pipeline operations work."""
        pipe = mock_redis.pipeline()
        pipe.set("key1", "value1")
        pipe.set("key2", "value2")
        pipe.set("key3", "value3")
        await pipe.execute()

        # Verify all keys were set
        assert await mock_redis.get("key1") == "value1"
        assert await mock_redis.get("key2") == "value2"
        assert await mock_redis.get("key3") == "value3"

    async def test_mock_redis_unavailable_returns_none(
        self, mock_redis_unavailable: pytest.fixture
    ) -> None:
        """Verify mock_redis_unavailable fixture makes get_redis() return None."""
        result = await get_redis()
        assert result is None
