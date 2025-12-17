"""Tenant lifecycle activities."""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlmodel import Session, select
from temporalio import activity

from src.app.models.base import utc_now
from src.app.models.public import Tenant, TenantStatus

from ._db import get_sync_engine


@dataclass
class GetTenantInput:
    tenant_id: str


@dataclass
class GetTenantOutput:
    tenant_id: str
    schema_name: str


@dataclass
class UpdateTenantStatusInput:
    tenant_id: str
    status: str  # "provisioning", "ready", "failed"


@dataclass
class SoftDeleteTenantInput:
    tenant_id: str


@dataclass
class SoftDeleteTenantOutput:
    success: bool
    already_deleted: bool


def _sync_get_tenant_info(tenant_id: str) -> GetTenantOutput:
    """Synchronous tenant info retrieval logic."""
    engine = get_sync_engine()
    with Session(engine) as session:
        tenant_uuid = UUID(tenant_id)
        stmt = select(Tenant).where(Tenant.id == tenant_uuid)
        tenant = session.scalars(stmt).first()

        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        return GetTenantOutput(
            tenant_id=str(tenant.id),
            schema_name=tenant.schema_name,
        )


@activity.defn
async def get_tenant_info(input: GetTenantInput) -> GetTenantOutput:
    """
    Get tenant information (schema_name) for an existing tenant.

    Idempotency: Fully idempotent - read-only operation with no side effects.
    Can be retried unlimited times and will always return the same result
    (or fail consistently if tenant doesn't exist).

    This is the safest type of activity for retries since it doesn't modify
    any state. No special idempotency handling is needed.

    Args:
        input: GetTenantInput with tenant_id

    Returns:
        GetTenantOutput with tenant_id and schema_name

    Raises:
        ValueError: If tenant is not found
    """
    activity.logger.info(f"Getting tenant info for: {input.tenant_id}")
    result = await asyncio.to_thread(_sync_get_tenant_info, input.tenant_id)
    activity.logger.info(f"Tenant info retrieved: {result.tenant_id}, schema: {result.schema_name}")
    return result


def _sync_update_tenant_status(tenant_id: str, status: str) -> bool:
    """Synchronous tenant status update logic."""
    # Validate status is a valid enum value
    try:
        TenantStatus(status)
    except ValueError as e:
        raise ValueError(f"Invalid tenant status: {status}") from e

    engine = get_sync_engine()
    with Session(engine) as session:
        tenant_uuid = UUID(tenant_id)
        stmt = select(Tenant).where(Tenant.id == tenant_uuid)
        tenant = session.scalars(stmt).first()

        if not tenant:
            return False

        tenant.status = status
        # Update is_active based on terminal status
        if status == "ready":
            tenant.is_active = True
        elif status in ("failed", "deleted"):
            tenant.is_active = False
        session.commit()
        return True


@activity.defn
async def update_tenant_status(input: UpdateTenantStatusInput) -> bool:
    """
    Update tenant status in database.

    Idempotency: Setting a field to a specific value is naturally idempotent.
    If retried, the status will simply be set to the same value again, which
    is a safe no-op. The database will have the correct final state regardless
    of how many times this activity executes.

    Pattern: "Set to value" operations are inherently idempotent:
        - 1st call: status = "ready" (changes from "provisioning")
        - 2nd call: status = "ready" (no change, already "ready")
        - Nth call: status = "ready" (still no change)

    This is different from "increment by N" operations which are NOT idempotent
    without additional tracking.

    Args:
        input: UpdateTenantStatusInput with tenant_id and status

    Returns:
        True if status was updated, False if tenant not found
    """
    activity.logger.info(f"Updating tenant {input.tenant_id} status to: {input.status}")
    result = await asyncio.to_thread(_sync_update_tenant_status, input.tenant_id, input.status)

    if not result:
        activity.logger.error(f"Tenant {input.tenant_id} not found")
    else:
        activity.logger.info(f"Tenant {input.tenant_id} status updated to {input.status}")

    return result


def _sync_soft_delete_tenant(tenant_id: str) -> SoftDeleteTenantOutput:
    """Synchronous soft-delete logic with idempotency tracking."""
    engine = get_sync_engine()
    with Session(engine) as session:
        tenant_uuid = UUID(tenant_id)
        stmt = select(Tenant).where(Tenant.id == tenant_uuid)
        tenant = session.scalars(stmt).first()

        if not tenant:
            # Tenant doesn't exist - treat as already deleted for idempotency
            return SoftDeleteTenantOutput(success=True, already_deleted=True)

        if tenant.deleted_at is not None:
            # Already soft-deleted (idempotent)
            return SoftDeleteTenantOutput(success=True, already_deleted=True)

        # Perform soft delete
        tenant.deleted_at = utc_now()
        tenant.is_active = False
        session.commit()
        return SoftDeleteTenantOutput(success=True, already_deleted=False)


@activity.defn
async def soft_delete_tenant(input: SoftDeleteTenantInput) -> SoftDeleteTenantOutput:
    """
    Soft-delete a tenant by setting deleted_at timestamp.

    Idempotency: Uses check-then-act with guard - only updates if not already
    deleted. Safe to retry multiple times - returns already_deleted=True if
    the tenant was previously soft-deleted or doesn't exist.

    This follows the idempotency pattern recommended for Temporal activities:
    - Check current state before acting
    - Skip if already in desired state
    - Return explicit status about whether action was taken

    Args:
        input: SoftDeleteTenantInput with tenant_id

    Returns:
        SoftDeleteTenantOutput with:
        - success: True if operation succeeded (including idempotent retries)
        - already_deleted: True if tenant was already deleted or didn't exist
    """
    activity.logger.info(f"Soft-deleting tenant: {input.tenant_id}")
    result = await asyncio.to_thread(_sync_soft_delete_tenant, input.tenant_id)

    if result.already_deleted:
        activity.logger.info(f"Tenant {input.tenant_id} already soft-deleted (idempotent retry)")
    else:
        activity.logger.info(f"Tenant {input.tenant_id} soft-deleted successfully")

    return result
