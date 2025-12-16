"""Assumed identity context management using contextvars.

Tracks when a superuser is operating as another user (identity assumption).
Used by AuditService to record both the operator and assumed user in audit logs.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Context variable for assumed identity state
_assumed_identity_context: ContextVar["AssumedIdentityContext | None"] = ContextVar(
    "assumed_identity_context", default=None
)


@dataclass(frozen=True)
class AssumedIdentityContext:
    """Immutable context for an assumed identity session.

    Attributes:
        operator_user_id: The superuser who is assuming the identity
        assumed_user_id: The user whose identity is being assumed
        tenant_id: The tenant context for the assumed session
        reason: Optional reason provided for the assumption
        started_at: When the assumption session started
    """

    operator_user_id: UUID
    assumed_user_id: UUID
    tenant_id: UUID
    reason: str | None = None
    started_at: datetime | None = None


def set_assumed_identity_context(
    operator_user_id: UUID,
    assumed_user_id: UUID,
    tenant_id: UUID,
    reason: str | None = None,
    started_at: datetime | None = None,
) -> None:
    """Set assumed identity context for the current request.

    Args:
        operator_user_id: The superuser performing the assumption
        assumed_user_id: The user whose identity is assumed
        tenant_id: The tenant context
        reason: Optional reason for the assumption
        started_at: When the assumption started (from token)
    """
    ctx = AssumedIdentityContext(
        operator_user_id=operator_user_id,
        assumed_user_id=assumed_user_id,
        tenant_id=tenant_id,
        reason=reason[:500] if reason and len(reason) > 500 else reason,
        started_at=started_at,
    )
    _assumed_identity_context.set(ctx)


def get_assumed_identity_context() -> AssumedIdentityContext | None:
    """Get the current assumed identity context.

    Returns:
        The AssumedIdentityContext if an identity assumption is active, None otherwise.
    """
    return _assumed_identity_context.get()


def clear_assumed_identity_context() -> None:
    """Clear the assumed identity context."""
    _assumed_identity_context.set(None)


def is_assuming_identity() -> bool:
    """Check if the current request is from an assumed identity session.

    Returns:
        True if identity assumption is active, False otherwise.
    """
    return _assumed_identity_context.get() is not None
