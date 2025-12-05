"""Tests for TenantStatus enum validation and usage."""

from datetime import UTC, datetime

import pytest

from src.app.models.public import Tenant, TenantStatus

pytestmark = pytest.mark.unit


class TestTenantStatusEnum:
    """Tests for TenantStatus enum values and transitions."""

    def test_tenant_status_values(self):
        """Test that TenantStatus has expected values."""
        assert TenantStatus.PROVISIONING.value == "provisioning"
        assert TenantStatus.READY.value == "ready"
        assert TenantStatus.FAILED.value == "failed"

    def test_tenant_status_from_string(self):
        """Test creating TenantStatus from string values."""
        assert TenantStatus("provisioning") == TenantStatus.PROVISIONING
        assert TenantStatus("ready") == TenantStatus.READY
        assert TenantStatus("failed") == TenantStatus.FAILED

    def test_tenant_status_invalid_value(self):
        """Test that invalid status values are rejected."""
        with pytest.raises(ValueError):
            TenantStatus("invalid_status")

    def test_tenant_status_case_sensitive(self):
        """Test that TenantStatus values are case-sensitive."""
        with pytest.raises(ValueError):
            TenantStatus("PROVISIONING")

        with pytest.raises(ValueError):
            TenantStatus("Ready")


class TestTenantModel:
    """Tests for Tenant model status handling."""

    def test_tenant_default_status(self):
        """Test that new tenants default to PROVISIONING status."""
        tenant = Tenant(name="Test Tenant", slug="test_tenant")
        assert tenant.status == TenantStatus.PROVISIONING.value

    def test_tenant_status_enum_property(self):
        """Test that status_enum property returns correct TenantStatus."""
        tenant = Tenant(
            name="Test Tenant",
            slug="test_tenant",
            status=TenantStatus.READY.value,
        )
        assert tenant.status_enum == TenantStatus.READY

    def test_tenant_status_ready(self):
        """Test tenant with READY status."""
        tenant = Tenant(
            name="Ready Tenant",
            slug="ready_tenant",
            status=TenantStatus.READY.value,
        )
        assert tenant.status == TenantStatus.READY.value
        assert tenant.status_enum == TenantStatus.READY

    def test_tenant_status_failed(self):
        """Test tenant with FAILED status."""
        tenant = Tenant(
            name="Failed Tenant",
            slug="failed_tenant",
            status=TenantStatus.FAILED.value,
        )
        assert tenant.status == TenantStatus.FAILED.value
        assert tenant.status_enum == TenantStatus.FAILED

    def test_tenant_invalid_status_string(self):
        """Test that tenant with invalid status string raises error when converting to enum."""
        tenant = Tenant(
            name="Invalid Status Tenant",
            slug="invalid_tenant",
            status="invalid_status",  # SQLModel allows any string
        )
        # The model accepts the string, but status_enum property should fail
        with pytest.raises(ValueError):
            _ = tenant.status_enum

    def test_tenant_schema_name_generation(self):
        """Test that schema_name property generates correct schema name."""
        tenant = Tenant(name="Test Company", slug="test_company")
        assert tenant.schema_name == "tenant_test_company"


class TestTenantStatusTransitions:
    """Tests for logical status transitions (business logic validation)."""

    def test_valid_status_transition_provisioning_to_ready(self):
        """Test valid transition from PROVISIONING to READY."""
        tenant = Tenant(
            name="Test Tenant",
            slug="test_tenant",
            status=TenantStatus.PROVISIONING.value,
        )
        # Simulate successful provisioning
        tenant.status = TenantStatus.READY.value
        assert tenant.status_enum == TenantStatus.READY

    def test_valid_status_transition_provisioning_to_failed(self):
        """Test valid transition from PROVISIONING to FAILED."""
        tenant = Tenant(
            name="Test Tenant",
            slug="test_tenant",
            status=TenantStatus.PROVISIONING.value,
        )
        # Simulate provisioning failure
        tenant.status = TenantStatus.FAILED.value
        assert tenant.status_enum == TenantStatus.FAILED

    def test_status_ready_is_terminal(self):
        """Test that READY status represents successful completion."""
        tenant = Tenant(
            name="Test Tenant",
            slug="test_tenant",
            status=TenantStatus.READY.value,
        )
        # Once ready, tenant should remain operational
        assert tenant.status_enum == TenantStatus.READY
        assert tenant.is_active is True

    def test_tenant_is_deleted_property_false(self):
        """Test is_deleted returns False when deleted_at is None."""
        tenant = Tenant(name="Test Tenant", slug="test_tenant")
        assert tenant.deleted_at is None
        assert tenant.is_deleted is False

    def test_tenant_is_deleted_property_true(self):
        """Test is_deleted returns True when deleted_at is set."""
        tenant = Tenant(name="Test Tenant", slug="test_tenant")
        tenant.deleted_at = datetime.now(UTC)
        assert tenant.deleted_at is not None
        assert tenant.is_deleted is True

    def test_tenant_deleted_at_default_none(self):
        """Test that deleted_at defaults to None for new tenants."""
        tenant = Tenant(name="Fresh Tenant", slug="fresh_tenant")
        assert tenant.deleted_at is None
