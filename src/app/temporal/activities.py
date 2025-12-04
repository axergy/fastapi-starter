"""
Temporal Activities - Fine-grained, idempotent operations.

Activities should be:
1. Idempotent - Safe to retry
2. Fine-grained - Do one thing well
3. Side-effect aware - External calls go here, not in workflows
"""

from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlmodel import Session, select
from temporalio import activity

from src.app.core.config import get_settings
from src.app.core.migrations import run_migrations_sync
from src.app.models.public import Tenant


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
class CreateTenantInput:
    name: str
    slug: str


@dataclass
class CreateTenantOutput:
    tenant_id: str
    schema_name: str


@dataclass
class RunMigrationsInput:
    schema_name: str


def _get_sync_engine():
    """Get synchronous database engine for activities."""
    settings = get_settings()
    # Convert async URL to sync (asyncpg -> psycopg2)
    sync_url = settings.database_url.replace("+asyncpg", "")
    return create_engine(sync_url)


@activity.defn
async def create_tenant_record(input: CreateTenantInput) -> CreateTenantOutput:
    """
    Create tenant record in public schema.

    Idempotent: Returns existing tenant if slug already exists.
    """
    activity.logger.info(f"Creating tenant record for slug: {input.slug}")

    engine = _get_sync_engine()
    with Session(engine) as session:
        # Check if tenant already exists (idempotency)
        stmt = select(Tenant).where(Tenant.slug == input.slug)
        existing = session.scalars(stmt).first()

        if existing:
            activity.logger.info(f"Tenant {input.slug} already exists, returning existing")
            return CreateTenantOutput(
                tenant_id=str(existing.id),
                schema_name=existing.schema_name,
            )

        # Create new tenant
        tenant = Tenant(name=input.name, slug=input.slug)
        session.add(tenant)
        session.commit()
        session.refresh(tenant)

        activity.logger.info(f"Created tenant {tenant.id} with schema {tenant.schema_name}")
        return CreateTenantOutput(
            tenant_id=str(tenant.id),
            schema_name=tenant.schema_name,
        )


@activity.defn
async def run_tenant_migrations(input: RunMigrationsInput) -> bool:
    """
    Run Alembic migrations for tenant schema.

    Idempotent: Alembic tracks migration state per-schema.
    """
    activity.logger.info(f"Running migrations for schema: {input.schema_name}")

    # Validate schema name to prevent injection
    if not input.schema_name.replace("_", "").isalnum():
        raise ValueError(f"Invalid schema name: {input.schema_name}")

    run_migrations_sync(input.schema_name)

    activity.logger.info(f"Migrations complete for schema: {input.schema_name}")
    return True
