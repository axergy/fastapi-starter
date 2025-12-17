"""Rate limiting configuration with optional Redis backend.

Uses Redis for distributed rate limiting when REDIS_URL is configured.
Falls back to in-memory storage (per-process) when Redis is unavailable.

Provides two layers of rate limiting:
1. Global middleware: Applies to ALL requests before tenant validation (DoS protection)
2. Endpoint decorators: Fine-grained limits after tenant validation (abuse prevention)
"""

import asyncio
import time
from collections import defaultdict

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.app.core.config import get_settings
from src.app.core.logging import get_logger
from src.app.core.redis import get_redis

logger = get_logger(__name__)

# In-memory fallback storage for global rate limiting
_rate_limit_buckets: dict[str, dict[str, float]] = defaultdict(dict)
_rate_limit_lock = asyncio.Lock()

# Lua script for atomic Redis token bucket operation
# This runs atomically on Redis server - no race conditions
_REDIS_TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local burst = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
local tokens = tonumber(bucket[1]) or burst
local last_update = tonumber(bucket[2]) or now

local elapsed = now - last_update
tokens = math.min(burst, tokens + elapsed * rate)

if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
    redis.call('EXPIRE', key, ttl)
    return 1
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
    redis.call('EXPIRE', key, ttl)
    return 0
end
"""

# Cache for registered Lua script SHA
_script_sha: str | None = None


def get_rate_limit_key(request: Request) -> str:
    """Generate rate limit key from client IP only.

    SECURITY WARNING: Do NOT include user-controlled headers (like X-Tenant-Slug)
    in the rate limit key. Attackers can trivially bypass rate limiting by
    rotating header values to create unlimited new buckets, enabling:
    - DoS attacks (rate limiting becomes ineffective)
    - Memory exhaustion (unbounded growth of rate limit buckets)
    - Resource abuse (unlimited requests)

    For authenticated users, consider using IP + authenticated user_id instead,
    but never use unauthenticated headers.
    """
    ip = get_remote_address(request) or "unknown"
    return ip


def _get_storage_uri() -> str | None:
    """Get Redis storage URI for slowapi rate limiting.

    Returns:
        Redis URI for slowapi (sync), or None for in-memory.

    Note:
        slowapi uses sync Redis internally, so we don't use the async+ prefix here.
        The async+ prefix is only for the limits library's async storage.
    """
    settings = get_settings()
    return settings.redis_url


def create_limiter() -> Limiter:
    """Create rate limiter with appropriate storage backend.

    Uses Redis if configured, otherwise falls back to in-memory storage.
    Disabled in testing environment.
    """
    settings = get_settings()

    # Disable rate limiting in testing environment
    if settings.app_env == "testing":
        logger.info("Rate limiter disabled (testing environment)")
        return Limiter(key_func=get_rate_limit_key, enabled=False)

    storage_uri = _get_storage_uri()
    if storage_uri:
        logger.info("Rate limiter using Redis backend")
        return Limiter(key_func=get_rate_limit_key, storage_uri=storage_uri)
    else:
        logger.info("Rate limiter using in-memory backend (not distributed)")
        return Limiter(key_func=get_rate_limit_key)


# Create limiter at module load time
# Note: This reads settings at import time. For dynamic reconfiguration,
# the app would need to be restarted.
limiter = create_limiter()


async def _check_in_memory_rate_limit(client_ip: str) -> bool:
    """Check rate limit using in-memory token bucket (fallback).

    Returns True if request is allowed, False if rate limited.
    Async-safe for ASGI servers using asyncio.Lock.
    """
    settings = get_settings()
    rate = settings.global_rate_limit_per_second
    burst = settings.global_rate_limit_burst
    now = time.time()

    async with _rate_limit_lock:
        if client_ip not in _rate_limit_buckets:
            _rate_limit_buckets[client_ip] = {
                "tokens": float(burst),
                "last_update": now,
            }

        bucket = _rate_limit_buckets[client_ip]
        elapsed = now - bucket["last_update"]

        # Replenish tokens based on time elapsed
        bucket["tokens"] = min(burst, bucket["tokens"] + elapsed * rate)
        bucket["last_update"] = now

        # Check if we have tokens available
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False


async def _get_or_register_script(redis: object) -> str:
    """Get cached script SHA or register the Lua script with Redis.

    Uses SCRIPT LOAD to register the script once, then EVALSHA for execution.
    This is more efficient than sending the full script on every request.
    """
    global _script_sha
    if _script_sha is None:
        _script_sha = await redis.script_load(_REDIS_TOKEN_BUCKET_SCRIPT)  # type: ignore[attr-defined]
    return _script_sha


async def _check_redis_rate_limit(
    redis: object,  # Redis client (typed as object to avoid import complexity)
    client_ip: str,
) -> bool:
    """Check rate limit using Redis token bucket (distributed).

    Uses Lua script for atomic check-and-decrement operation.
    Returns True if request is allowed, False if rate limited.
    """
    settings = get_settings()
    rate = settings.global_rate_limit_per_second
    burst = settings.global_rate_limit_burst
    now = time.time()

    key = f"global_ratelimit:{client_ip}"
    # TTL: enough time to replenish full bucket + buffer
    ttl = int(burst / rate) + 60

    # Get or register script, then execute via EVALSHA
    script_sha = await _get_or_register_script(redis)
    result = await redis.evalsha(  # type: ignore[attr-defined]
        script_sha,
        1,  # number of keys
        key,
        str(rate),
        str(burst),
        str(now),
        str(ttl),
    )
    return bool(result == 1)


async def _check_global_rate_limit(client_ip: str) -> bool:
    """Check global rate limit, using Redis if available.

    Falls back to in-memory token bucket if Redis is unavailable or fails.
    Skips rate limiting entirely in test environment.
    """
    settings = get_settings()
    if settings.app_env == "testing":
        return True  # Skip rate limiting in test environment

    redis = await get_redis()

    if redis:
        try:
            return await _check_redis_rate_limit(redis, client_ip)
        except Exception as e:
            logger.warning(
                "Redis rate limit check failed, falling back to in-memory",
                error=str(e),
                client_ip=client_ip,
            )
            # Reset script SHA in case Redis restarted
            global _script_sha
            _script_sha = None
            return await _check_in_memory_rate_limit(client_ip)

    return await _check_in_memory_rate_limit(client_ip)


async def global_rate_limit_middleware(
    request: Request,
    call_next: object,  # type: ignore[type-arg]
) -> JSONResponse:
    """Global rate limiting middleware - applies BEFORE tenant validation.

    This provides DoS protection at the IP level, independent of tenant context.
    Uses a token bucket algorithm with configurable rate and burst limits.

    Exempt paths: /health, /metrics (monitoring endpoints)
    """
    # Skip rate limiting for monitoring endpoints
    if request.url.path in ("/health", "/metrics", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)  # type: ignore[misc, operator, no-any-return]

    client_ip = get_remote_address(request) or "unknown"

    if not await _check_global_rate_limit(client_ip):
        logger.warning(
            "Global rate limit exceeded",
            client_ip=client_ip,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please slow down.",
                "retry_after": 1,
            },
            headers={"Retry-After": "1"},
        )

    return await call_next(request)  # type: ignore[misc, operator, no-any-return]
