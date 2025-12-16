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
        UpdateWorkflowExecutionStatusInput,
        cleanup_email_verification_tokens,
        cleanup_expired_invites,
        cleanup_refresh_tokens,
        create_admin_membership,
        create_stripe_customer,
        drop_tenant_schema,
        run_tenant_migrations,
        send_welcome_email,
        soft_delete_tenant,
        update_tenant_status,
        update_workflow_execution_status,
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

            # Step 5: Update workflow execution status to completed
            await workflow.execute_activity(
                update_workflow_execution_status,
                UpdateWorkflowExecutionStatusInput(
                    workflow_id=workflow.info().workflow_id,
                    status="completed",
                ),
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

            # Update workflow execution status to failed
            await workflow.execute_activity(
                update_workflow_execution_status,
                UpdateWorkflowExecutionStatusInput(
                    workflow_id=workflow.info().workflow_id,
                    status="failed",
                    error_message=str(e),
                ),
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
    Delete a tenant: soft-delete record first, then drop schema.

    Steps:
    1. Soft-delete tenant record (set deleted_at, is_active=False) - stops API requests immediately
    2. Get tenant info (schema_name)
    3. Drop tenant schema (CASCADE removes all data) - now safe, tenant already marked deleted

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

        # Step 1: Soft-delete tenant record FIRST (stops API requests immediately)
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

        # Step 2: Get tenant info (schema_name)
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

        # Step 3: Drop tenant schema (now safe, tenant already marked deleted)
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

        return {"deleted": True, "tenant_id": tenant_id}


@workflow.defn
class TokenCleanupWorkflow:
    """
    Clean up expired tokens and invites.

    Runs cleanup activities for:
    1. Refresh tokens (expired or revoked)
    2. Email verification tokens (expired or used)
    3. Tenant invites (expired, cancelled, or accepted)

    Designed to be run on a schedule (e.g., daily at 3am UTC via Temporal cron).

    Idempotent: All cleanup activities use DELETE which is idempotent - safe
    to run multiple times without side effects.
    """

    @workflow.run
    async def run(self, retention_days: int = 30) -> dict[str, int]:
        """
        Run all token cleanup activities.

        Args:
            retention_days: Number of days to retain expired/revoked/used tokens
                           (default: 30 days from config)

        Returns:
            dict with counts of deleted tokens by type:
            {
                "refresh_tokens": int,
                "email_verification_tokens": int,
                "invites": int,
                "total": int
            }
        """
        workflow.logger.info(f"Starting token cleanup (retention: {retention_days} days)")

        # Run all cleanup activities in parallel for efficiency
        # Each activity is independent and idempotent
        refresh_count_task = workflow.execute_activity(
            cleanup_refresh_tokens,
            retention_days,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
            ),
        )

        email_count_task = workflow.execute_activity(
            cleanup_email_verification_tokens,
            retention_days,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
            ),
        )

        invite_count_task = workflow.execute_activity(
            cleanup_expired_invites,
            retention_days,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
            ),
        )

        # Wait for all activities to complete
        refresh_count = await refresh_count_task
        email_count = await email_count_task
        invite_count = await invite_count_task

        total = refresh_count + email_count + invite_count

        result = {
            "refresh_tokens": refresh_count,
            "email_verification_tokens": email_count,
            "invites": invite_count,
            "total": total,
        }

        workflow.logger.info(
            f"Token cleanup complete: {result['refresh_tokens']} refresh, "
            f"{result['email_verification_tokens']} email, "
            f"{result['invites']} invites (total: {result['total']})"
        )

        return result
