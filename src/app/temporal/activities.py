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
from src.app.core.db import run_migrations_sync
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


@activity.defn
async def send_welcome_email(input: SendEmailInput) -> bool:
    """
    Send welcome email to new user.

    In production, integrate with email service (SendGrid, SES, etc.)
    """
    activity.logger.info(f"Sending welcome email to {input.to}")
    # TODO: Integrate with actual email service
    # await email_client.send(to=input.to, subject=input.subject, body=input.body)
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

    IMPORTANT: Must be idempotent. Use Stripe's idempotency keys.
    """
    activity.logger.info(f"Creating Stripe customer for {input.email}")
    # TODO: Integrate with Stripe
    # customer = await stripe.Customer.create(
    #     email=input.email,
    #     name=input.name,
    #     metadata={"tenant_id": input.tenant_id},
    #     idempotency_key=f"customer_{input.tenant_id}_{input.email}",
    # )
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

    Idempotent: Safe to retry - just retrieves tenant data.
    """
    activity.logger.info(f"Getting tenant info for: {input.tenant_id}")
    result = await asyncio.to_thread(_sync_get_tenant_info, input.tenant_id)
    activity.logger.info(f"Tenant info retrieved: {result.tenant_id}, schema: {result.schema_name}")
    return result


def _sync_run_tenant_migrations(schema_name: str) -> bool:
    """Synchronous migration logic."""
    # Validate schema name to prevent injection
    if not schema_name.replace("_", "").isalnum():
        raise ValueError(f"Invalid schema name: {schema_name}")

    run_migrations_sync(schema_name)
    return True


@activity.defn
async def run_tenant_migrations(input: RunMigrationsInput) -> bool:
    """
    Run Alembic migrations for tenant schema.

    Idempotent: Alembic tracks migration state per-schema.
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

    Idempotent: Safe to retry - just sets the status value.
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

    Idempotent: Safe to retry - skips if membership exists.
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

    Idempotent: Safe to call multiple times - uses IF EXISTS.
    Security: Validates schema name before execution.

    Args:
        input: DropSchemaInput with schema_name

    Returns:
        DropSchemaOutput indicating success and whether schema existed
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


def _sync_soft_delete_tenant(tenant_id: str) -> bool:
    """Synchronous soft-delete logic."""
    engine = get_sync_engine()
    with Session(engine) as session:
        tenant_uuid = UUID(tenant_id)
        stmt = select(Tenant).where(Tenant.id == tenant_uuid)
        tenant = session.scalars(stmt).first()

        if not tenant:
            return False

        if tenant.deleted_at is not None:
            return True  # Already deleted (idempotent)

        tenant.deleted_at = utc_now()
        tenant.is_active = False
        session.commit()
        return True


@activity.defn
async def soft_delete_tenant(input: SoftDeleteTenantInput) -> bool:
    """
    Soft-delete a tenant by setting deleted_at timestamp.

    Idempotent: Safe to retry - skips if already deleted.

    Args:
        input: SoftDeleteTenantInput with tenant_id

    Returns:
        True if tenant was deleted (or already was), False if tenant not found
    """
    activity.logger.info(f"Soft-deleting tenant: {input.tenant_id}")
    result = await asyncio.to_thread(_sync_soft_delete_tenant, input.tenant_id)

    if result:
        activity.logger.info(f"Tenant {input.tenant_id} soft-deleted")
    else:
        activity.logger.warning(f"Tenant {input.tenant_id} not found")

    return result
