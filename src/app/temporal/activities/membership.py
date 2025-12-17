"""Membership creation activities."""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from psycopg2.errors import UniqueViolation  # type: ignore[import-untyped]
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from temporalio import activity

from src.app.models.base import utc_now
from src.app.models.public import MembershipRole, UserTenantMembership

from ._db import get_sync_engine


@dataclass
class CreateMembershipInput:
    user_id: str
    tenant_id: str
    role: str = MembershipRole.ADMIN.value


def _sync_create_membership(user_id: str, tenant_id: str, role: str) -> bool:
    """Synchronous membership creation logic."""
    # Validate UUID format upfront
    try:
        user_uuid = UUID(user_id)
        tenant_uuid = UUID(tenant_id)
    except ValueError as e:
        raise ValueError(f"Invalid UUID format: {e}") from e

    engine = get_sync_engine()
    with Session(engine) as session:
        # Check if membership already exists (idempotency)
        stmt = select(UserTenantMembership).where(
            UserTenantMembership.user_id == user_uuid,
            UserTenantMembership.tenant_id == tenant_uuid,
        )
        existing = session.scalars(stmt).first()

        if existing:
            return True  # Already exists

        membership = UserTenantMembership(
            user_id=user_uuid,
            tenant_id=tenant_uuid,
            role=role,
            created_at=utc_now(),
        )
        try:
            session.add(membership)
            session.commit()
        except IntegrityError as e:
            session.rollback()
            # Unique violation means membership already exists - idempotent success
            if isinstance(e.orig, UniqueViolation):
                return True
            # FK violation or other error - real failure
            raise RuntimeError(f"Failed to create membership: {e}") from e

        return True


@activity.defn
async def create_admin_membership(input: CreateMembershipInput) -> bool:
    """
    Create user-tenant membership.

    Idempotency: Uses check-then-act pattern with race condition handling.
    First queries for existing membership before attempting to create. If
    membership already exists (from a previous execution), returns True
    without creating a duplicate.

    The database has a unique constraint on (user_id, tenant_id) as a safety
    net for race conditions. If two concurrent executions both pass the check,
    one will succeed with the INSERT and the other will get a UniqueViolation.
    The UniqueViolation is caught and treated as success (membership exists),
    making the operation fully idempotent.

    Pattern:
        1. Check if membership exists
        2. If exists, return success (idempotent retry)
        3. If not exists, create membership
        4. On UniqueViolation (race condition), return success (idempotent)
        5. On ForeignKeyViolation or other error, raise RuntimeError

    This makes the activity safe to retry - subsequent calls after successful
    creation will see the existing membership and return immediately. Concurrent
    calls are also handled correctly through unique constraint violation
    detection.

    Args:
        input: CreateMembershipInput with user_id, tenant_id, and role

    Returns:
        True if membership was created or already exists

    Raises:
        RuntimeError: If foreign key constraint fails (user/tenant doesn't exist)
            or other database errors occur
    """
    activity.logger.info(
        f"Creating membership for user {input.user_id} in tenant {input.tenant_id}"
    )
    result = await asyncio.to_thread(
        _sync_create_membership, input.user_id, input.tenant_id, input.role
    )
    activity.logger.info(f"Membership created: {result}")
    return result
