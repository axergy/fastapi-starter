"""Rate limiting configuration with optional Redis backend.

Uses Redis for distributed rate limiting when REDIS_URL is configured.
Falls back to in-memory storage (per-process) when Redis is unavailable.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from src.app.core.config import get_settings
from src.app.core.logging import get_logger

logger = get_logger(__name__)


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
