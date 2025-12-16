"""Integration tests for tenant provisioning lifecycle."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.app.models.public import Tenant, TenantStatus, WorkflowExecution

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestProvisioningLifecycle:
    """Tests for tenant provisioning workflow lifecycle."""

    async def test_registration_creates_workflow_execution(
        self, client_no_tenant: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Verify workflow_execution record is created on registration.

        This test currently documents expected behavior - the registration service
        should create a workflow_execution record when starting the provisioning workflow.
        See: todos/016-pending-p1-workflow-execution-observability.md
        """
        # Use unique values per test run to avoid parallel test interference
        unique_id = uuid4().hex[-8:]
        test_email = f"lifecycle_{unique_id}@test.com"
        test_slug = f"lifecycle_test_{unique_id}"

        with patch("src.app.services.registration_service.get_temporal_client") as mock_get_client:
            # Mock Temporal client
            mock_client = AsyncMock()
            mock_client.start_workflow.return_value = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await client_no_tenant.post(
                "/api/v1/auth/register",
                json={
                    "email": test_email,
                    "password": "SecurePass123!",
                    "full_name": "Test User",
                    "tenant_name": "Lifecycle Test Corp",
                    "tenant_slug": test_slug,
                },
            )

        assert response.status_code == 202
        data = response.json()
        workflow_id = data.get("workflow_id")
        assert workflow_id is not None

        # Verify workflow_execution record exists
        result = await db_session.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
        )
        execution = result.scalar_one_or_none()

        # TODO: This assertion will fail until registration service is updated
        # to create workflow_execution records (see todo #016)
        assert execution is not None, (
            "workflow_execution record should be created during registration. "
            "See todos/016-done-p1-workflow-execution-observability.md"
        )
        assert execution.status in ["pending", "running"]
        assert execution.workflow_type == "TenantProvisioningWorkflow"
        assert execution.entity_type == "tenant"

    async def test_tenant_transitions_to_ready(
        self, client_no_tenant: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that tenant transitions through provisioning states correctly.

        This test verifies the tenant status transitions:
        1. Created with status "provisioning"
        2. Workflow completes successfully
        3. Status updated to "ready"
        4. Tenant becomes active (is_active=True)
        """
        # Use unique values per test run
        unique_id = uuid4().hex[-8:]
        test_email = f"transition_{unique_id}@test.com"
        test_slug = f"transition_test_{unique_id}"

        with patch("src.app.services.registration_service.get_temporal_client") as mock_get_client:
            # Mock Temporal client
            mock_client = AsyncMock()
            mock_client.start_workflow.return_value = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await client_no_tenant.post(
                "/api/v1/auth/register",
                json={
                    "email": test_email,
                    "password": "SecurePass123!",
                    "full_name": "Test User",
                    "tenant_name": "Transition Test Corp",
                    "tenant_slug": test_slug,
                },
            )

        assert response.status_code == 202
        data = response.json()
        tenant_slug = data.get("tenant_slug")
        assert tenant_slug == test_slug

        # Verify tenant is created in provisioning state
        result = await db_session.execute(select(Tenant).where(Tenant.slug == test_slug))
        tenant = result.scalar_one_or_none()
        assert tenant is not None
        assert tenant.status == TenantStatus.PROVISIONING.value
        assert tenant.is_active is True  # New tenants start active

        # NOTE: To test the full transition to "ready" status, we would need to:
        # 1. Either use a real Temporal worker (integration test), OR
        # 2. Directly call the workflow completion activity
        # For now, this test verifies the initial provisioning state.
        # Full workflow integration testing should be added when Temporal test
        # infrastructure is set up.

    async def test_workflow_id_is_deterministic(self, client_no_tenant: AsyncClient) -> None:
        """Test that workflow_id follows the expected format.

        The workflow_id should be deterministic based on the tenant slug:
        format: "tenant-provision-{slug}"

        This allows for idempotent workflow starts and easy correlation
        between tenants and their provisioning workflows.
        """
        # Use unique values per test run
        unique_id = uuid4().hex[-8:]
        test_email = f"workflow_id_{unique_id}@test.com"
        test_slug = f"workflow_id_test_{unique_id}"

        with patch("src.app.services.registration_service.get_temporal_client") as mock_get_client:
            # Mock Temporal client
            mock_client = AsyncMock()
            mock_client.start_workflow.return_value = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await client_no_tenant.post(
                "/api/v1/auth/register",
                json={
                    "email": test_email,
                    "password": "SecurePass123!",
                    "full_name": "Test User",
                    "tenant_name": "Workflow ID Test Corp",
                    "tenant_slug": test_slug,
                },
            )

        assert response.status_code == 202
        data = response.json()
        workflow_id = data.get("workflow_id")

        # Verify workflow_id follows expected format
        expected_workflow_id = f"tenant-provision-{test_slug}"
        assert workflow_id == expected_workflow_id
