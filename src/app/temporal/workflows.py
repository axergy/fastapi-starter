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
    from src.app.models.public import TenantStatus
    from src.app.temporal.activities import (
        CreateMembershipInput,
        CreateStripeCustomerInput,
        CreateStripeCustomerOutput,
        DropSchemaInput,
        RunMigrationsInput,
        SendEmailInput,
        SoftDeleteTenantInput,
        UpdateTenantStatusInput,
        create_admin_membership,
        create_stripe_customer,
        drop_tenant_schema,
        run_tenant_migrations,
        send_welcome_email,
        soft_delete_tenant,
        update_tenant_status,
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
    Provision a new tenant with Saga-pattern compensation (Lobby Pattern).

    Steps (with compensations):
    1. Get tenant info - No compensation needed (read-only)
    2. Run migrations - Compensate: drop_tenant_schema
    3. Create membership - No compensation (FK cascades on tenant delete)
    4. Update status to ready - No compensation (overwritten to failed)

    On failure: Runs compensations in reverse order, then marks tenant as failed.
    Idempotent: Safe to retry - activities handle existing records.
    """

    @workflow.run
    async def run(self, tenant_id: str, user_id: str | None = None) -> str:
        """
        Run tenant provisioning workflow.

        Args:
            tenant_id: UUID of the existing tenant (created by service layer)
            user_id: Optional user ID to create admin membership for

        Returns:
            tenant_id: UUID of the tenant
        """
        schema_name: str | None = None
        completed_steps: list[str] = []

        try:
            # Step 1: Get tenant info (schema_name) for migrations
            # No compensation needed - read-only operation
            from src.app.temporal.activities import (
                GetTenantInput,
                GetTenantOutput,
                get_tenant_info,
            )

            tenant_info: GetTenantOutput = await workflow.execute_activity(
                get_tenant_info,
                GetTenantInput(tenant_id=tenant_id),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                ),
            )

            schema_name = tenant_info.schema_name
            workflow.logger.info(f"Processing tenant: {tenant_id}, schema: {schema_name}")

            # Step 2: Run migrations for tenant schema (creates empty schema)
            # Compensation: drop_tenant_schema
            await workflow.execute_activity(
                run_tenant_migrations,
                RunMigrationsInput(schema_name=schema_name),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=2),
                ),
            )
            completed_steps.append("migrations")
            workflow.logger.info("Migrations completed, schema created")

            # Step 3: Create admin membership if user_id provided
            # No compensation needed - membership will be orphaned but harmless,
            # and will be cleaned up when tenant is deleted (FK cascade)
            if user_id:
                await workflow.execute_activity(
                    create_admin_membership,
                    CreateMembershipInput(user_id=user_id, tenant_id=tenant_id),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        maximum_attempts=3,
                        initial_interval=timedelta(seconds=1),
                    ),
                )
                completed_steps.append("membership")
                workflow.logger.info(f"Admin membership created for user {user_id}")

            # Step 4: Mark tenant as ready
            await workflow.execute_activity(
                update_tenant_status,
                UpdateTenantStatusInput(tenant_id=tenant_id, status=TenantStatus.READY.value),
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                ),
            )

            workflow.logger.info(f"Tenant provisioning complete: {tenant_id}")
            return tenant_id

        except Exception as e:
            workflow.logger.error(f"Provisioning failed: {e}")

            # Run compensations in reverse order (Saga pattern)
            await self._run_compensations(completed_steps, schema_name, tenant_id)

            # Mark tenant as failed after cleanup
            await workflow.execute_activity(
                update_tenant_status,
                UpdateTenantStatusInput(tenant_id=tenant_id, status=TenantStatus.FAILED.value),
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                ),
            )
            raise

    async def _run_compensations(
        self,
        completed_steps: list[str],
        schema_name: str | None,
        tenant_id: str,
    ) -> None:
        """Run compensating actions in reverse order (Saga pattern)."""
        for step in reversed(completed_steps):
            try:
                if step == "migrations" and schema_name:
                    workflow.logger.info(f"Compensating: dropping schema {schema_name}")
                    await workflow.execute_activity(
                        drop_tenant_schema,
                        DropSchemaInput(schema_name=schema_name),
                        start_to_close_timeout=timedelta(seconds=60),
                        retry_policy=RetryPolicy(
                            maximum_attempts=3,
                            initial_interval=timedelta(seconds=1),
                        ),
                    )
                elif step == "membership":
                    # Membership will be orphaned but harmless - tenant FK cascade handles cleanup
                    workflow.logger.info("Skipping membership compensation (tenant FK cascade)")
            except Exception as comp_error:
                # Log but don't fail - best effort cleanup
                workflow.logger.warning(f"Compensation for '{step}' failed: {comp_error}")


@workflow.defn
class TenantDeletionWorkflow:
    """
    Delete a tenant: drop schema, then soft-delete record.

    Steps:
    1. Get tenant info (schema_name)
    2. Drop tenant schema (CASCADE removes all data)
    3. Soft-delete tenant record (set deleted_at, is_active=False)

    Idempotent: Safe to retry - each step handles already-completed state.
    """

    @workflow.run
    async def run(self, tenant_id: str) -> dict[str, bool | str]:
        """
        Run tenant deletion workflow.

        Args:
            tenant_id: UUID of the tenant to delete

        Returns:
            dict with deleted status and tenant_id
        """
        from src.app.temporal.activities import (
            GetTenantInput,
            GetTenantOutput,
            get_tenant_info,
        )

        # Step 1: Get tenant info (schema_name)
        tenant_info: GetTenantOutput = await workflow.execute_activity(
            get_tenant_info,
            GetTenantInput(tenant_id=tenant_id),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )

        workflow.logger.info(f"Deleting tenant: {tenant_id}, schema: {tenant_info.schema_name}")

        # Step 2: Drop tenant schema
        await workflow.execute_activity(
            drop_tenant_schema,
            DropSchemaInput(schema_name=tenant_info.schema_name),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )
        workflow.logger.info(f"Schema {tenant_info.schema_name} dropped")

        # Step 3: Soft-delete tenant record
        await workflow.execute_activity(
            soft_delete_tenant,
            SoftDeleteTenantInput(tenant_id=tenant_id),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )
        workflow.logger.info(f"Tenant {tenant_id} soft-deleted")

        return {"deleted": True, "tenant_id": tenant_id}
