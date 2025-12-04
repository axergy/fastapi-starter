"""
Temporal Workflows - Deterministic orchestration.

Workflows MUST be:
1. Deterministic - Same input = same execution path
2. Side-effect free - All external calls through activities
3. Short-running code - Long operations go in activities
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.app.temporal.activities import (
        CreateStripeCustomerInput,
        CreateStripeCustomerOutput,
        CreateTenantInput,
        CreateTenantOutput,
        RunMigrationsInput,
        SendEmailInput,
        create_stripe_customer,
        create_tenant_record,
        run_tenant_migrations,
        send_welcome_email,
    )


@workflow.defn
class UserOnboardingWorkflow:
    """
    Onboard new user:
    1. Create Stripe customer
    2. Send welcome email

    If step 1 succeeds but step 2 fails, Temporal only retries step 2.
    """

    @workflow.run
    async def run(self, user_email: str, user_name: str, tenant_id: str) -> str:
        stripe_result: CreateStripeCustomerOutput = await workflow.execute_activity(
            create_stripe_customer,
            CreateStripeCustomerInput(
                email=user_email,
                name=user_name,
                tenant_id=tenant_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )

        workflow.logger.info(f"Created Stripe customer: {stripe_result.stripe_customer_id}")

        await workflow.execute_activity(
            send_welcome_email,
            SendEmailInput(
                to=user_email,
                subject="Welcome!",
                body=f"Hello {user_name}, welcome to our platform!",
            ),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                maximum_attempts=5,
                initial_interval=timedelta(seconds=2),
            ),
        )

        return stripe_result.stripe_customer_id


@workflow.defn
class TenantProvisioningWorkflow:
    """
    Provision a new tenant:
    1. Create tenant record in public schema
    2. Run Alembic migrations to create tenant schema + tables

    Idempotent: Safe to retry - activities handle existing tenants.
    """

    @workflow.run
    async def run(self, name: str, slug: str) -> str:
        """
        Run tenant provisioning workflow.

        Args:
            name: Display name for the tenant
            slug: URL-safe identifier for the tenant

        Returns:
            tenant_id: UUID of the created/existing tenant
        """
        # Step 1: Create tenant record
        result: CreateTenantOutput = await workflow.execute_activity(
            create_tenant_record,
            CreateTenantInput(name=name, slug=slug),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )

        workflow.logger.info(
            f"Tenant record created: {result.tenant_id}, schema: {result.schema_name}"
        )

        # Step 2: Run migrations for tenant schema
        await workflow.execute_activity(
            run_tenant_migrations,
            RunMigrationsInput(schema_name=result.schema_name),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
            ),
        )

        workflow.logger.info(f"Tenant provisioning complete: {result.tenant_id}")

        return result.tenant_id
