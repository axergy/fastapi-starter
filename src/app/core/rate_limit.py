"""Rate limiting configuration with optional Redis backend.

Uses Redis for distributed rate limiting when REDIS_URL is configured.
Falls back to in-memory storage (per-process) when Redis is unavailable.

Provides two layers of rate limiting:
1. Global middleware: Applies to ALL requests before tenant validation (DoS protection)
2. Endpoint decorators: Fine-grained limits after tenant validation (abuse prevention)
"""

import time
from collections import defaultdict
from threading import Lock

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.app.core.config import get_settings
from src.app.core.logging import get_logger

logger = get_logger(__name__)

# Global rate limit: requests per IP per second (before tenant validation)
# These are conservative defaults for API protection; adjust based on load testing
GLOBAL_RATE_LIMIT_PER_SECOND = 10  # Max 10 requests/second per IP
GLOBAL_RATE_LIMIT_BURST = 20  # Allow burst of 20 requests

# Simple in-memory token bucket for global rate limiting
# Note: For distributed deployments, use Redis-based limiter
_rate_limit_buckets: dict[str, dict[str, float]] = defaultdict(
    lambda: {"tokens": float(GLOBAL_RATE_LIMIT_BURST), "last_update": time.time()}
)
_rate_limit_lock = Lock()


def get_rate_limit_key(request: Request) -> str:
    """Generate rate limit key from IP + tenant slug (if present).

    This prevents a single IP from exhausting rate limits across all tenants
    while still allowing per-tenant rate limiting when X-Tenant-ID is provided.
    """
    ip = get_remote_address(request) or "unknown"
    tenant_id = request.headers.get("X-Tenant-ID", "")
    if tenant_id:
        return f"{ip}:{tenant_id}"
    return ip


def _get_storage_uri() -> str | None:
    """Get Redis storage URI for rate limiting.

    Returns:
        Redis URI with async+ prefix for async operations, or None for in-memory.
    """
    settings = get_settings()
    if settings.redis_url:
        # Use async+ prefix for asyncio-compatible Redis
        # e.g., "redis://localhost:6379" -> "async+redis://localhost:6379"
        redis_url = settings.redis_url
        if not redis_url.startswith("async+"):
            redis_url = f"async+{redis_url}"
        return redis_url
    return None


def create_limiter() -> Limiter:
    """Create rate limiter with appropriate storage backend.

    Uses Redis if configured, otherwise falls back to in-memory storage.
    """
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


def _check_global_rate_limit(client_ip: str) -> bool:
    """Check if request is within global rate limit using token bucket algorithm.

    Returns True if request is allowed, False if rate limited.
    Thread-safe for multi-threaded ASGI servers.
    """
    now = time.time()

    with _rate_limit_lock:
        bucket = _rate_limit_buckets[client_ip]
        elapsed = now - bucket["last_update"]

        # Replenish tokens based on time elapsed
        bucket["tokens"] = min(
            GLOBAL_RATE_LIMIT_BURST,
            bucket["tokens"] + elapsed * GLOBAL_RATE_LIMIT_PER_SECOND,
        )
        bucket["last_update"] = now

        # Check if we have tokens available
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False


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

    if not _check_global_rate_limit(client_ip):
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
