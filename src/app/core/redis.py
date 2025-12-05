"""Redis client with connection pooling and graceful fallback.

This module provides an optional Redis connection. If Redis is not configured
or unavailable, functions that depend on it should gracefully degrade.
"""

from redis.asyncio import ConnectionPool, Redis

from src.app.core.config import get_settings
from src.app.core.logging import get_logger

logger = get_logger(__name__)

_pool: ConnectionPool | None = None
_redis: Redis | None = None
_connection_attempted: bool = False


async def get_redis() -> Redis | None:
    """Get Redis client. Returns None if unavailable (graceful degradation).

    The connection is lazily initialized on first call and reused thereafter.
    If Redis is not configured or connection fails, returns None.
    """
    global _pool, _redis, _connection_attempted

    # If already connected, return existing client
    if _redis is not None:
        return _redis

    # If we already tried and failed, don't retry (until close_redis is called)
    if _connection_attempted:
        return None

    _connection_attempted = True
    settings = get_settings()

    # No Redis URL configured
    if not settings.redis_url:
        logger.info("Redis not configured (REDIS_URL not set)")
        return None

    try:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_pool_size,
            decode_responses=True,  # Return strings instead of bytes
        )
        _redis = Redis(connection_pool=_pool)

        # Test connection
        await _redis.ping()  # type: ignore[misc]
        logger.info("Redis connected successfully")
        return _redis

    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Falling back to non-Redis mode.")
        # Clean up partial initialization
        if _redis:
            await _redis.aclose()
            _redis = None
        if _pool:
            await _pool.disconnect()
            _pool = None
        return None


async def close_redis() -> None:
    """Close Redis connection pool.

    Should be called during application shutdown.
    """
    global _pool, _redis, _connection_attempted

    if _redis:
        await _redis.aclose()
        logger.info("Redis connection closed")
    if _pool:
        await _pool.disconnect()

    _redis = None
    _pool = None
    _connection_attempted = False


def reset_redis_state() -> None:
    """Reset Redis state for testing purposes.

    This allows tests to reinitialize the Redis connection.
    """
    global _pool, _redis, _connection_attempted
    _redis = None
    _pool = None
    _connection_attempted = False
