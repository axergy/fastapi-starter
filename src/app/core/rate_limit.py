"""Rate limiting configuration."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


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


limiter = Limiter(key_func=get_rate_limit_key)
