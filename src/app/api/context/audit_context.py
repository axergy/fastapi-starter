"""Audit context management using contextvars.

Stores request metadata (IP address, user agent) for use by AuditService.
"""

from contextvars import ContextVar
from dataclasses import dataclass

# Context variable for audit metadata
_audit_context: ContextVar["AuditContext | None"] = ContextVar("audit_context", default=None)


@dataclass(frozen=True)
class AuditContext:
    """Immutable audit context for the current request."""

    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


def set_audit_context(
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> None:
    """Set audit context for the current request."""
    ctx = AuditContext(
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent and len(user_agent) > 500 else user_agent,
        request_id=request_id,
    )
    _audit_context.set(ctx)


def get_audit_context() -> AuditContext | None:
    """Get the current audit context."""
    return _audit_context.get()


def clear_audit_context() -> None:
    """Clear the audit context."""
    _audit_context.set(None)


def get_client_ip(forwarded_for: str | None, client_host: str | None) -> str | None:
    """Extract client IP from X-Forwarded-For header or client host.

    Args:
        forwarded_for: Value of X-Forwarded-For header (may contain multiple IPs)
        client_host: Direct client host from the connection

    Returns:
        The client IP address (first IP from X-Forwarded-For, or client host)
    """
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: client, proxy1, proxy2...
        # First IP is the original client
        return forwarded_for.split(",")[0].strip()
    return client_host
