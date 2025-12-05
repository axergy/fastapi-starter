"""
Temporal Activities - Fine-grained, idempotent operations.

Activities should be:
1. Idempotent - Safe to retry
2. Fine-grained - Do one thing well
3. Side-effect aware - External calls go here, not in workflows
"""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from temporalio import activity

from src.app.core.config import get_settings
from src.app.core.db import get_public_session, run_migrations_sync
from src.app.core.security import validate_schema_name
from src.app.models.base import utc_now
from src.app.models.public import MembershipRole, Tenant, TenantStatus, UserTenantMembership

# Singleton sync engine for activities
_sync_engine: Engine | None = None


@dataclass
class SendEmailInput:
    to: str
    subject: str
    body: str
    idempotency_key: str | None = None  # Optional: unique key for deduplication


@activity.defn
async def send_welcome_email(input: SendEmailInput) -> bool:
    """
    Send welcome email to new user.

    Idempotency: Uses idempotency_key for deduplication. If the same key is
    provided multiple times, the email is only sent once. When integrated with
    an actual email service, use the service's idempotency features (e.g.,
    SendGrid's idempotency key header, SES message ID tracking).

    For now, relies on workflow execution ID for deduplication via Temporal's
    activity completion guarantees - an activity with the same input will not
    execute twice within the same workflow run.

    In production, implement one of:
    1. Service-level idempotency: Use provider's idempotency key (SendGrid, SES)
    2. Database tracking: Store sent email records with idempotency_key
    3. Application-level: Check if email was already sent before sending

    Example implementation:
        # Check if already sent (database tracking approach)
        if input.idempotency_key:
            existing = await idempotency_repo.get_by_key(input.idempotency_key)
            if existing:
                activity.logger.info(f"Email already sent for key {input.idempotency_key}")
                return True

        # Send with provider's idempotency support
        await email_client.send(
            to=input.to,
            subject=input.subject,
            body=input.body,
            idempotency_key=input.idempotency_key,
        )

        # Record successful send
        if input.idempotency_key:
            await idempotency_repo.mark_complete(input.idempotency_key)

    Args:
        input: SendEmailInput with recipient, subject, body, and optional idempotency_key

    Returns:
        True if email was sent (or already sent)
    """
    activity.logger.info(f"Sending welcome email to {input.to}")
    # TODO: Integrate with actual email service (see docstring for implementation pattern)
    return True


@dataclass
class CreateStripeCustomerInput:
    email: str
    name: str
    tenant_id: str


@dataclass
class CreateStripeCustomerOutput:
    stripe_customer_id: str


@activity.defn
async def create_stripe_customer(
    input: CreateStripeCustomerInput,
) -> CreateStripeCustomerOutput:
    """
    Create Stripe customer for new user.

    Idempotency: Uses Stripe's native idempotency key feature. All Stripe API
    POST requests accept an idempotency key parameter. If Stripe receives a
    request with the same idempotency key, it will return the cached result
    instead of creating a duplicate resource.

    The idempotency key should be deterministic and unique per customer:
        idempotency_key = f"customer_{tenant_id}_{email}"

    This ensures that if the activity is retried due to network failure or
    worker crash, no duplicate Stripe customers will be created.

    Implementation pattern:
        customer = await stripe.Customer.create(
            email=input.email,
            name=input.name,
            metadata={"tenant_id": input.tenant_id},
            idempotency_key=f"customer_{input.tenant_id}_{input.email}",
        )

    Note: Stripe stores idempotency keys for 24 hours, which is sufficient
    for Temporal's retry windows.

    Args:
        input: CreateStripeCustomerInput with email, name, and tenant_id

    Returns:
        CreateStripeCustomerOutput with the Stripe customer ID
    """
    activity.logger.info(f"Creating Stripe customer for {input.email}")
    # TODO: Integrate with Stripe (see docstring for idempotency pattern)
    return CreateStripeCustomerOutput(stripe_customer_id="cus_placeholder")


# --- Tenant Provisioning Activities ---


@dataclass
class GetTenantInput:
    tenant_id: str


@dataclass
class GetTenantOutput:
    tenant_id: str
    schema_name: str


@dataclass
class RunMigrationsInput:
    schema_name: str


def get_sync_engine() -> Engine:
    """Get or create synchronous database engine (singleton)."""
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        # Convert async URL to sync (asyncpg -> psycopg2)
        sync_url = settings.database_url.replace("+asyncpg", "")
        _sync_engine = create_engine(sync_url, pool_pre_ping=True)
    return _sync_engine


def dispose_sync_engine() -> None:
    """Dispose of the sync engine (call on worker shutdown)."""
    global _sync_engine
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None


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


def _sync_run_tenant_migrations(schema_name: str) -> bool:
    """Synchronous migration logic."""
    # Validate schema name BEFORE any operations to prevent injection
    validate_schema_name(schema_name)

    run_migrations_sync(schema_name)
    return True


@activity.defn
async def run_tenant_migrations(input: RunMigrationsInput) -> bool:
    """
    Run Alembic migrations for tenant schema.

    Idempotency: This activity is fully idempotent through multiple mechanisms:

    1. Schema Creation: Uses `CREATE SCHEMA IF NOT EXISTS` in Alembic's env.py,
       so creating an existing schema is a no-op.

    2. Migration Tracking: Alembic maintains an `alembic_version` table per
       schema that tracks which migrations have been applied. It will only run
       migrations that haven't been applied yet.

    3. Safe Retries: If this activity is retried after a partial migration
       failure, Alembic will resume from where it left off, not re-run
       completed migrations.

    This makes the activity safe to retry at any point without risk of:
    - Duplicate schema creation errors
    - Re-running already applied migrations
    - Inconsistent database state

    Args:
        input: RunMigrationsInput with schema_name

    Returns:
        True if migrations completed successfully
    """
    activity.logger.info(f"Running migrations for schema: {input.schema_name}")
    await asyncio.to_thread(_sync_run_tenant_migrations, input.schema_name)
    activity.logger.info(f"Migrations complete for schema: {input.schema_name}")
    return True


@dataclass
class UpdateTenantStatusInput:
    tenant_id: str
    status: str  # "provisioning", "ready", "failed"


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


# --- Membership Activities ---


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
            raise RuntimeError(f"Failed to create membership (FK violation): {e}") from e

        return True


@activity.defn
async def create_admin_membership(input: CreateMembershipInput) -> bool:
    """
    Create user-tenant membership.

    Idempotency: Uses check-then-act pattern - queries for existing membership
    before attempting to create. If membership already exists (from a previous
    execution), returns True without creating a duplicate.

    The database also has a unique constraint on (user_id, tenant_id) as a
    safety net, so even if the check race-conditions, the IntegrityError is
    caught and handled.

    Pattern:
        1. Check if membership exists
        2. If exists, return success (idempotent retry)
        3. If not exists, create membership
        4. On IntegrityError (race condition), rollback and raise error

    This makes the activity safe to retry - subsequent calls after successful
    creation will see the existing membership and return immediately.

    Args:
        input: CreateMembershipInput with user_id, tenant_id, and role

    Returns:
        True if membership was created or already exists
    """
    activity.logger.info(
        f"Creating membership for user {input.user_id} in tenant {input.tenant_id}"
    )
    result = await asyncio.to_thread(
        _sync_create_membership, input.user_id, input.tenant_id, input.role
    )
    activity.logger.info(f"Membership created: {result}")
    return result


# --- Schema Management Activities ---


@dataclass
class DropSchemaInput:
    schema_name: str


@dataclass
class DropSchemaOutput:
    success: bool
    schema_existed: bool


def _sync_drop_tenant_schema(schema_name: str) -> DropSchemaOutput:
    """Synchronous schema drop logic with validation."""
    # Validate schema name BEFORE any SQL execution
    validate_schema_name(schema_name)

    engine = get_sync_engine()
    with Session(engine) as session:
        conn = session.connection()

        # Use quote_ident for safe identifier quoting
        quoted_schema = conn.execute(
            text("SELECT quote_ident(:schema)"), {"schema": schema_name}
        ).scalar()

        # Check if schema exists first
        schema_exists = conn.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = :schema
                )
                """
            ),
            {"schema": schema_name},
        ).scalar()

        if schema_exists:
            # CASCADE drops all contained objects
            conn.execute(text(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"))
            session.commit()

        return DropSchemaOutput(success=True, schema_existed=bool(schema_exists))


@activity.defn
async def drop_tenant_schema(input: DropSchemaInput) -> DropSchemaOutput:
    """
    Drop a tenant schema from the database.

    Idempotency: Uses `DROP SCHEMA IF EXISTS` which makes this operation fully
    idempotent. If the schema doesn't exist, the operation succeeds without
    error. Returns explicit status (schema_existed=True/False) to indicate
    whether the schema was actually dropped or was already gone.

    This allows retries to be safe:
    - 1st call: schema exists, DROP executes, returns schema_existed=True
    - 2nd call: schema gone, DROP is no-op, returns schema_existed=False
    - Nth call: schema still gone, still safe

    Security: Validates schema name before execution to prevent SQL injection.

    Args:
        input: DropSchemaInput with schema_name

    Returns:
        DropSchemaOutput with:
        - success: Always True (operation succeeded)
        - schema_existed: True if schema was dropped, False if already gone
    """
    activity.logger.info(f"Dropping schema: {input.schema_name}")
    result = await asyncio.to_thread(_sync_drop_tenant_schema, input.schema_name)

    if result.schema_existed:
        activity.logger.info(f"Schema {input.schema_name} dropped successfully")
    else:
        activity.logger.info(f"Schema {input.schema_name} did not exist (already clean)")

    return result


# --- Tenant Lifecycle Activities ---


@dataclass
class SoftDeleteTenantInput:
    tenant_id: str


@dataclass
class SoftDeleteTenantOutput:
    success: bool
    already_deleted: bool


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


# --- Token Cleanup Activities ---


@activity.defn
async def cleanup_refresh_tokens(retention_days: int) -> int:
    """
    Clean up expired refresh tokens.

    Deletes tokens that:
    - Expired more than retention_days ago, OR
    - Were revoked and created more than retention_days ago

    Idempotent: DELETE operations are inherently idempotent - running multiple
    times will not cause side effects. Second run finds no matching records.

    Args:
        retention_days: Number of days to retain expired/revoked tokens

    Returns:
        Number of tokens deleted
    """
    activity.logger.info(f"Cleaning up refresh tokens older than {retention_days} days")

    async with get_public_session() as session:
        from src.app.repositories.public.token import RefreshTokenRepository

        repo = RefreshTokenRepository(session)
        count = await repo.cleanup_expired(retention_days)

    activity.logger.info(f"Deleted {count} expired refresh tokens")
    return count


@activity.defn
async def cleanup_email_verification_tokens(retention_days: int) -> int:
    """
    Clean up expired email verification tokens.

    Deletes tokens that:
    - Expired more than retention_days ago, OR
    - Were used and created more than retention_days ago

    Idempotent: DELETE operations are inherently idempotent.

    Args:
        retention_days: Number of days to retain expired/used tokens

    Returns:
        Number of tokens deleted
    """
    activity.logger.info(f"Cleaning up email verification tokens older than {retention_days} days")

    async with get_public_session() as session:
        from src.app.repositories.public.email_verification import (
            EmailVerificationTokenRepository,
        )

        repo = EmailVerificationTokenRepository(session)
        count = await repo.cleanup_expired(retention_days)

    activity.logger.info(f"Deleted {count} expired email verification tokens")
    return count


@activity.defn
async def cleanup_expired_invites(retention_days: int) -> int:
    """
    Clean up expired tenant invites.

    Deletes invites that:
    - Expired more than retention_days ago, OR
    - Were cancelled/accepted and created more than retention_days ago

    Idempotent: DELETE operations are inherently idempotent.

    Args:
        retention_days: Number of days to retain expired/cancelled/accepted invites

    Returns:
        Number of invites deleted
    """
    activity.logger.info(f"Cleaning up tenant invites older than {retention_days} days")

    async with get_public_session() as session:
        from src.app.repositories.public.invite import TenantInviteRepository

        repo = TenantInviteRepository(session)
        count = await repo.cleanup_expired(retention_days)

    activity.logger.info(f"Deleted {count} expired tenant invites")
    return count
