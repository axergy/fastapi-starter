"""Tenant provisioning service."""

from src.app.core.config import get_settings
from src.app.models.public import Tenant
from src.app.repositories.tenant_repository import TenantRepository
from src.app.temporal.client import get_temporal_client
from src.app.temporal.workflows import TenantProvisioningWorkflow


class TenantService:
    """Tenant provisioning service - business logic only."""

    def __init__(self, tenant_repo: TenantRepository):
        self.tenant_repo = tenant_repo

    @staticmethod
    def get_workflow_id(slug: str) -> str:
        """Generate deterministic workflow ID for a tenant slug."""
        return f"tenant-provision-{slug}"

    async def create_tenant(self, name: str, slug: str) -> str:
        """
        Start tenant provisioning via Temporal workflow.

        Returns the workflow_id. The workflow will:
        1. Create tenant record in public schema (status="provisioning")
        2. Run migrations to create the tenant schema and tables
        3. Update tenant status to "ready" (or "failed" on error)

        Args:
            name: Display name for the tenant
            slug: URL-safe identifier for the tenant

        Returns:
            workflow_id: The Temporal workflow ID for tracking
        """
        if await self.tenant_repo.exists_by_slug(slug):
            raise ValueError(f"Tenant with slug '{slug}' already exists")

        settings = get_settings()
        client = await get_temporal_client()
        workflow_id = self.get_workflow_id(slug)

        await client.start_workflow(
            TenantProvisioningWorkflow.run,
            args=[name, slug],
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )

        return workflow_id

    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Get tenant by slug."""
        return await self.tenant_repo.get_by_slug(slug)

    async def list_tenants(self, active_only: bool = True) -> list[Tenant]:
        """List all tenants."""
        return await self.tenant_repo.list_all(active_only)

    async def deactivate_tenant(self, tenant: Tenant) -> Tenant:
        """Deactivate a tenant."""
        tenant.is_active = False
        await self.tenant_repo.commit()
        return await self.tenant_repo.refresh(tenant)
