"""
Tenant Deletion Workflow.

Delete a tenant: soft-delete record first, then drop schema.

Steps:
1. Soft-delete tenant record (set deleted_at, is_active=False) - stops API requests immediately
2. Get tenant info (schema_name)
3. Drop tenant schema (CASCADE removes all data) - now safe, tenant already marked deleted

Idempotent: Safe to retry - each step handles already-completed state.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.app.temporal.activities import (
        DropSchemaInput,
        GetTenantInput,
        GetTenantOutput,
        SoftDeleteTenantInput,
        TenantCtx,
        drop_tenant_schema,
        get_tenant_info,
        soft_delete_tenant,
    )


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
        # Step 1: Soft-delete tenant record FIRST (stops API requests immediately)
        # Minimal ctx - we don't have schema_name yet
        await workflow.execute_activity(
            soft_delete_tenant,
            SoftDeleteTenantInput(ctx=TenantCtx(tenant_id=tenant_id)),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )
        workflow.logger.info(f"Tenant {tenant_id} soft-deleted")

        # Step 2: Get tenant info (schema_name) - needed for schema drop
        tenant_info: GetTenantOutput = await workflow.execute_activity(
            get_tenant_info,
            GetTenantInput(tenant_id=tenant_id),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )

        # Build full TenantCtx with schema_name for remaining activities
        ctx = TenantCtx(tenant_id=tenant_id, schema_name=tenant_info.schema_name)
        workflow.logger.info(f"Deleting tenant: {tenant_id}, schema: {ctx.schema_name}")

        # Step 3: Drop tenant schema (now safe, tenant already marked deleted)
        await workflow.execute_activity(
            drop_tenant_schema,
            DropSchemaInput(ctx=ctx),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            ),
        )
        workflow.logger.info(f"Schema {ctx.schema_name} dropped")

        return {"deleted": True, "tenant_id": tenant_id}
