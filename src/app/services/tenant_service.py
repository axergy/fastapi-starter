"""Tenant provisioning service."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.config import get_settings
from src.app.models.base import utc_now
from src.app.models.public import Tenant, TenantStatus, WorkflowExecution
from src.app.repositories.tenant_repository import TenantRepository
from src.app.repositories.workflow_execution_repository import WorkflowExecutionRepository
from src.app.temporal.client import get_temporal_client
from src.app.temporal.workflows import TenantProvisioningWorkflow


class TenantService:
    """Tenant provisioning service - business logic only."""

    def __init__(
        self,
        tenant_repo: TenantRepository,
        workflow_exec_repo: WorkflowExecutionRepository,
        session: AsyncSession,
    ):
        self.tenant_repo = tenant_repo
        self.workflow_exec_repo = workflow_exec_repo
        self.session = session

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
        # Create tenant record FIRST (unique constraint on slug handles races)
        try:
            tenant = Tenant(name=name, slug=slug, status=TenantStatus.PROVISIONING.value)
            self.tenant_repo.add(tenant)
            await self.session.commit()
            await self.session.refresh(tenant)
        except IntegrityError as e:
            await self.session.rollback()
            raise ValueError(f"Tenant with slug '{slug}' already exists") from e

        # Create workflow execution record before starting workflow
        workflow_id = self.get_workflow_id(slug)
        workflow_exec = WorkflowExecution(
            workflow_id=workflow_id,
            workflow_type="TenantProvisioningWorkflow",
            entity_type="tenant",
            entity_id=tenant.id,
            status="pending",
        )
        self.workflow_exec_repo.add(workflow_exec)
        await self.session.commit()
        await self.session.refresh(workflow_exec)

        # Start workflow with tenant_id
        settings = get_settings()
        client = await get_temporal_client()

        await client.start_workflow(
            TenantProvisioningWorkflow.run,
            args=[str(tenant.id)],
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )

        # Update workflow execution status to running
        workflow_exec.status = "running"
        workflow_exec.started_at = utc_now()
        await self.session.commit()

        return workflow_id

    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Get tenant by slug."""
        return await self.tenant_repo.get_by_slug(slug)

    async def list_tenants(self, active_only: bool = True) -> list[Tenant]:
        """List all tenants."""
        return await self.tenant_repo.list_all(active_only)

    async def list_user_tenants(self, user_id: UUID) -> list[Tenant]:
        """List tenants where user has active membership."""
        return await self.tenant_repo.list_by_user_membership(user_id)

    async def deactivate_tenant(self, tenant: Tenant) -> Tenant:
        """Deactivate a tenant."""
        try:
            tenant.is_active = False
            await self.session.commit()
            await self.session.refresh(tenant)
            return tenant
        except Exception:
            await self.session.rollback()
            raise
