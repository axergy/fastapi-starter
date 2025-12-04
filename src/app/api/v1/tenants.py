from fastapi import APIRouter, HTTPException, status
from temporalio.client import WorkflowExecutionStatus

from src.app.core.config import get_settings
from src.app.core.db import get_public_session
from src.app.schemas.tenant import (
    TenantCreate,
    TenantProvisioningResponse,
    TenantRead,
    TenantStatusResponse,
)
from src.app.services.tenant_service import TenantService
from src.app.temporal.client import get_temporal_client
from src.app.temporal.workflows import TenantProvisioningWorkflow

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _get_workflow_id(slug: str) -> str:
    """Generate deterministic workflow ID for a tenant slug."""
    return f"tenant-provision-{slug}"


@router.post("", response_model=TenantProvisioningResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_tenant(request: TenantCreate) -> TenantProvisioningResponse:
    """
    Start tenant provisioning workflow.

    Returns immediately with workflow ID. Poll /tenants/{slug}/status for progress.
    """
    settings = get_settings()
    client = await get_temporal_client()
    workflow_id = _get_workflow_id(request.slug)

    # Check if tenant already exists
    async with get_public_session() as session:
        service = TenantService(session)
        existing = await service.get_by_slug(request.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tenant with slug '{request.slug}' already exists",
            )

    # Start the provisioning workflow
    await client.start_workflow(
        TenantProvisioningWorkflow.run,
        args=[request.name, request.slug],
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )

    return TenantProvisioningResponse(
        workflow_id=workflow_id,
        slug=request.slug,
        status="provisioning",
    )


@router.get("/{slug}/status", response_model=TenantStatusResponse)
async def get_tenant_status(slug: str) -> TenantStatusResponse:
    """
    Check tenant provisioning status.

    Returns:
    - provisioning: Workflow is still running
    - ready: Tenant is provisioned and ready to use
    - failed: Provisioning failed (check error field)
    """
    client = await get_temporal_client()
    workflow_id = _get_workflow_id(slug)

    # First check if tenant exists in database
    async with get_public_session() as session:
        service = TenantService(session)
        tenant = await service.get_by_slug(slug)

    # Try to get workflow handle
    handle = client.get_workflow_handle(workflow_id)

    try:
        description = await handle.describe()
        workflow_status = description.status

        if workflow_status == WorkflowExecutionStatus.COMPLETED:
            if tenant:
                return TenantStatusResponse(
                    status="ready",
                    tenant=TenantRead.model_validate(tenant),
                )
            # Workflow completed but tenant not found (shouldn't happen)
            return TenantStatusResponse(
                status="failed",
                error="Workflow completed but tenant not found",
            )

        elif workflow_status == WorkflowExecutionStatus.RUNNING:
            return TenantStatusResponse(status="provisioning")

        elif workflow_status in (
            WorkflowExecutionStatus.FAILED,
            WorkflowExecutionStatus.CANCELED,
            WorkflowExecutionStatus.TERMINATED,
        ):
            return TenantStatusResponse(
                status="failed",
                error=f"Workflow {workflow_status.name}",
            )

        else:
            return TenantStatusResponse(status="provisioning")

    except Exception:
        # Workflow not found - check if tenant exists anyway
        if tenant:
            return TenantStatusResponse(
                status="ready",
                tenant=TenantRead.model_validate(tenant),
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No provisioning workflow found for tenant '{slug}'",
        ) from None


@router.get("", response_model=list[TenantRead])
async def list_tenants() -> list[TenantRead]:
    """List all active tenants."""
    async with get_public_session() as session:
        service = TenantService(session)
        tenants = await service.list_tenants()
        return [TenantRead.model_validate(t) for t in tenants]


@router.get("/{slug}", response_model=TenantRead)
async def get_tenant(slug: str) -> TenantRead:
    """Get tenant by slug."""
    async with get_public_session() as session:
        service = TenantService(session)
        tenant = await service.get_by_slug(slug)
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )
        return TenantRead.model_validate(tenant)
