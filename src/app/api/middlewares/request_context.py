"""Unified request context middleware.

Consolidates all request-scoped context initialization:
- AuditContext: IP address, user agent, request ID
- AssumedIdentityContext: Operator info from assumed identity tokens
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from asgi_correlation_id import correlation_id
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.app.api.context import (
    clear_assumed_identity_context,
    clear_audit_context,
    get_client_ip,
    set_assumed_identity_context,
    set_audit_context,
)
from src.app.core.security import decode_token


def _extract_assumed_identity_from_token(request: Request) -> dict[str, Any] | None:
    """Extract assumed identity claims from JWT if present.

    Returns dict with operator_user_id, assumed_user_id, tenant_id, reason, started_at
    or None if not an assumed identity token.

    Note: This only extracts claims - full validation (operator is superuser)
    happens in auth dependency.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    payload = decode_token(token)
    if not payload:
        return None

    assumed_identity = payload.get("assumed_identity")
    if not assumed_identity:
        return None

    # Extract and validate required fields
    operator_user_id = assumed_identity.get("operator_user_id")
    if not operator_user_id:
        return None

    try:
        started_at = None
        if assumed_identity.get("started_at"):
            started_at = datetime.fromisoformat(assumed_identity["started_at"])

        return {
            "operator_user_id": UUID(operator_user_id),
            "assumed_user_id": UUID(payload.get("sub", "")),
            "tenant_id": UUID(payload.get("tenant_id", "")),
            "reason": assumed_identity.get("reason"),
            "started_at": started_at,
        }
    except (ValueError, KeyError):
        return None


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware that initializes all request-scoped context.

    Sets up:
    - AuditContext: Captures IP address, user agent, and request ID for audit logging
    - AssumedIdentityContext: Extracts assumed identity info from JWT if present

    Context is automatically cleared after request processing.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Clear any stale context
        clear_audit_context()
        clear_assumed_identity_context()

        try:
            # Set audit context
            forwarded_for = request.headers.get("x-forwarded-for")
            client_host = request.client.host if request.client else None
            ip_address = get_client_ip(forwarded_for, client_host)

            set_audit_context(
                ip_address=ip_address,
                user_agent=request.headers.get("user-agent"),
                request_id=correlation_id.get(),
            )

            # Set assumed identity context if token contains it
            assumed_identity = _extract_assumed_identity_from_token(request)
            if assumed_identity:
                set_assumed_identity_context(
                    operator_user_id=assumed_identity["operator_user_id"],
                    assumed_user_id=assumed_identity["assumed_user_id"],
                    tenant_id=assumed_identity["tenant_id"],
                    reason=assumed_identity["reason"],
                    started_at=assumed_identity["started_at"],
                )

            return await call_next(request)
        finally:
            # Always clean up context
            clear_audit_context()
            clear_assumed_identity_context()
