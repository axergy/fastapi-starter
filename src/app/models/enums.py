"""Shared enums for models."""

from enum import Enum


class TenantStatus(str, Enum):
    """Tenant provisioning status."""

    PROVISIONING = "provisioning"
    READY = "ready"
    FAILED = "failed"


class MembershipRole(str, Enum):
    """User role within a tenant."""

    ADMIN = "admin"
    MEMBER = "member"


class InviteStatus(str, Enum):
    """Tenant invite status."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
