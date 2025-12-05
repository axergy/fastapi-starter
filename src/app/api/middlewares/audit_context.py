"""Audit context middleware - captures request metadata for audit logging."""

from asgi_correlation_id import correlation_id
from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from src.app.core.audit_context import clear_audit_context, get_client_ip, set_audit_context


async def audit_context_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Capture request metadata for audit logging.

    Extracts:
    - Client IP (from X-Forwarded-For or direct connection)
    - User-Agent header
    - Request ID (correlation ID)
    """
    clear_audit_context()

    # Extract client IP
    forwarded_for = request.headers.get("x-forwarded-for")
    client_host = request.client.host if request.client else None
    ip_address = get_client_ip(forwarded_for, client_host)

    # Extract user agent
    user_agent = request.headers.get("user-agent")

    # Get correlation ID (set by CorrelationIdMiddleware)
    request_id = correlation_id.get()

    set_audit_context(
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )

    try:
        return await call_next(request)
    finally:
        clear_audit_context()
