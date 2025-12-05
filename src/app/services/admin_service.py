"""Admin service - platform-level operations (superuser only)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.config import get_settings
from src.app.models.public import Tenant
from src.app.repositories import TenantRepository
from src.app.temporal.client import get_temporal_client
from src.app.temporal.workflows import TenantDeletionWorkflow


class AdminService:
    """Service for platform-wide admin operations.

    These operations are superuser-only and cross-tenant.
    """

    def __init__(
        self,
        tenant_repo: TenantRepository,
        session: AsyncSession,
    ):
        self.tenant_repo = tenant_repo
        self.session = session

    async def delete_tenant(self, tenant_id: UUID) -> str:
        """Start tenant deletion workflow (drop schema + soft-delete).

        Args:
            tenant_id: UUID of the tenant to delete

        Returns:
            workflow_id: The Temporal workflow ID for tracking

        Raises:
            ValueError: If tenant not found or already deleted
        """
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        if tenant.deleted_at is not None:
            raise ValueError("Tenant already deleted")

        settings = get_settings()
        client = await get_temporal_client()
        workflow_id = f"tenant-deletion-{tenant_id}"

        await client.start_workflow(
            TenantDeletionWorkflow.run,
            args=[str(tenant_id)],
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )

        return workflow_id

    async def bulk_delete_tenants(self, status_filter: str | None = None) -> list[str]:
        """Start deletion workflows for multiple tenants.

        Args:
            status_filter: Optional status to filter by (e.g., 'failed')

        Returns:
            List of workflow IDs started
        """
        tenants = await self.tenant_repo.list_for_deletion(status_filter)
        workflow_ids = []

        for tenant in tenants:
            try:
                wf_id = await self.delete_tenant(tenant.id)
                workflow_ids.append(wf_id)
            except ValueError:
                # Skip tenants that are already deleted
                continue

        return workflow_ids

    async def get_tenant_by_id(self, tenant_id: UUID) -> Tenant | None:
        """Get tenant by ID (admin access, includes deleted)."""
        return await self.tenant_repo.get_by_id(tenant_id)
