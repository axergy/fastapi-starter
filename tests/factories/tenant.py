"""Tenant factory for test data generation."""

from polyfactory import Use

from src.app.models.enums import TenantStatus
from src.app.models.public import Tenant
from tests.factories.base import BaseFactory, generate_uuid7, utc_now


class TenantFactory(BaseFactory):
    """Factory for generating Tenant test data."""

    __model__ = Tenant

    id = Use(generate_uuid7)
    name = Use(lambda: f"Test Tenant {generate_uuid7().hex[-8:]}")
    slug = Use(lambda: f"test_{generate_uuid7().hex[-8:]}")
    status = TenantStatus.READY.value
    is_active = True
    created_at = Use(utc_now)
    deleted_at = None

    @classmethod
    def provisioning(cls, **kwargs):
        """Create a tenant in provisioning status."""
        return cls.build(status=TenantStatus.PROVISIONING.value, **kwargs)

    @classmethod
    def failed(cls, **kwargs):
        """Create a failed tenant."""
        return cls.build(status=TenantStatus.FAILED.value, is_active=False, **kwargs)

    @classmethod
    def deleted(cls, **kwargs):
        """Create a soft-deleted tenant."""
        return cls.build(deleted_at=utc_now(), **kwargs)
