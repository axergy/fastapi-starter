"""Request context management for API layer.

Provides context variables for tracking request-scoped state:
- AuditContext: IP, user-agent, request_id for audit logging
- AssumedIdentityContext: Operator info when superuser assumes identity
"""

from src.app.api.context.assumed_identity_context import (
    AssumedIdentityContext,
    clear_assumed_identity_context,
    get_assumed_identity_context,
    is_assuming_identity,
    set_assumed_identity_context,
)
from src.app.api.context.audit_context import (
    AuditContext,
    clear_audit_context,
    get_audit_context,
    get_client_ip,
    set_audit_context,
)

__all__ = [
    # Assumed identity context
    "AssumedIdentityContext",
    "clear_assumed_identity_context",
    "get_assumed_identity_context",
    "is_assuming_identity",
    "set_assumed_identity_context",
    # Audit context
    "AuditContext",
    "clear_audit_context",
    "get_audit_context",
    "get_client_ip",
    "set_audit_context",
]
