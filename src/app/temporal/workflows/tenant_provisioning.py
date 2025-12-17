"""
Tenant Provisioning Workflow.

Provision a new tenant with Saga-pattern compensation (Lobby Pattern).

Steps (with compensations):
1. Get tenant info - No compensation needed (read-only)
2. Run migrations - Compensate: drop_tenant_schema
3. Create membership - No compensation (FK cascades on tenant delete)
4. Update status to ready - No compensation (overwritten to failed)

On failure: Runs compensations in reverse order, then marks tenant as failed.
Idempotent: Safe to retry - activities handle existing records.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.app.models.public import TenantStatus
    from src.app.temporal.activities import (
        CreateMembershipInput,
        DropSchemaInput,
        GetTenantInput,
        GetTenantOutput,
        RunMigrationsInput,
        TenantCtx,
        UpdateTenantStatusInput,
        UpdateWorkflowExecutionStatusInput,
        create_admin_membership,
        drop_tenant_schema,
        get_tenant_info,
        run_tenant_migrations,
        update_tenant_status,
        update_workflow_execution_status,
    )


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
        ctx: TenantCtx | None = None
        completed_steps: list[str] = []

        try:
            # Step 1: Get tenant info (schema_name) for migrations
            # No compensation needed - read-only operation
            tenant_info: GetTenantOutput = await workflow.execute_activity(
                get_tenant_info,
                GetTenantInput(tenant_id=tenant_id),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                ),
            )

            # Build TenantCtx for all subsequent activities
            ctx = TenantCtx(tenant_id=tenant_id, schema_name=tenant_info.schema_name)
            workflow.logger.info(f"Processing tenant: {tenant_id}, schema: {ctx.schema_name}")

            # Step 2: Run migrations for tenant schema (creates empty schema)
            # Compensation: drop_tenant_schema
            await workflow.execute_activity(
                run_tenant_migrations,
                RunMigrationsInput(ctx=ctx),
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
                    CreateMembershipInput(ctx=ctx, user_id=user_id),
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
                UpdateTenantStatusInput(ctx=ctx, status=TenantStatus.READY.value),
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
            await self._run_compensations(completed_steps, ctx)

            # Build minimal ctx for failure status update (may not have schema_name)
            failure_ctx = ctx if ctx else TenantCtx(tenant_id=tenant_id)

            # Mark tenant as failed after cleanup
            await workflow.execute_activity(
                update_tenant_status,
                UpdateTenantStatusInput(ctx=failure_ctx, status=TenantStatus.FAILED.value),
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
        ctx: TenantCtx | None,
    ) -> None:
        """Run compensating actions in reverse order (Saga pattern)."""
        for step in reversed(completed_steps):
            try:
                if step == "migrations" and ctx and ctx.schema_name:
                    workflow.logger.info(f"Compensating: dropping schema {ctx.schema_name}")
                    await workflow.execute_activity(
                        drop_tenant_schema,
                        DropSchemaInput(ctx=ctx),
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
