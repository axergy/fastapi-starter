"""Tenant provisioning service."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.config import get_settings
from src.app.models.base import utc_now
from src.app.models.public import Tenant, TenantStatus, WorkflowExecution
from src.app.repositories import TenantRepository, WorkflowExecutionRepository
from src.app.temporal.client import get_temporal_client
from src.app.temporal.routing import QueueKind, route_for_tenant
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

        Raises:
            ValueError: If slug already exists or would collide with existing tenant
        """
        # Check for collisions (acme-corp and acme_corp both map to tenant_acme_corp)
        if await self.tenant_repo.exists_by_slug(slug):
            raise ValueError(f"Tenant with slug '{slug}' already exists")

        # Create tenant record (unique constraint on slug handles remaining races)
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

        # Route to tenant-specific task queue with fairness
        route = route_for_tenant(
            tenant_id=str(tenant.id),
            namespace=settings.temporal_namespace,
            prefix=settings.temporal_queue_prefix,
            shards=settings.temporal_queue_shards,
            kind=QueueKind.TENANT,
        )

        await client.start_workflow(
            TenantProvisioningWorkflow.run,
            str(tenant.id),
            id=workflow_id,
            task_queue=route.task_queue,
        )

        # Update workflow execution status to running
        workflow_exec.status = "running"
        workflow_exec.started_at = utc_now()
        await self.session.commit()

        return workflow_id

    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Get tenant by slug."""
        return await self.tenant_repo.get_by_slug(slug)

    async def list_tenants(
        self, cursor: str | None, limit: int, active_only: bool = True
    ) -> tuple[list[Tenant], str | None, bool]:
        """List all tenants with cursor-based pagination.

        Args:
            cursor: Optional cursor for pagination
            limit: Maximum number of results
            active_only: Whether to filter by active status

        Returns:
            Tuple of (items, next_cursor, has_more)
        """
        return await self.tenant_repo.list_all(cursor, limit, active_only)

    async def list_user_tenants(
        self, user_id: UUID, cursor: str | None, limit: int
    ) -> tuple[list[Tenant], str | None, bool]:
        """List tenants where user has active membership with cursor-based pagination.

        Args:
            user_id: User ID to filter by
            cursor: Optional cursor for pagination
            limit: Maximum number of results

        Returns:
            Tuple of (items, next_cursor, has_more)
        """
        return await self.tenant_repo.list_by_user_membership(user_id, cursor, limit)

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
