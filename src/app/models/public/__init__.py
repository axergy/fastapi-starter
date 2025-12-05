"""Public schema models - Lobby Pattern.

All user identity and authentication models live here.
Tenant-specific data models go in models/tenant/.
"""

# Re-export enums for backward compatibility
from src.app.models.enums import InviteStatus, MembershipRole, TenantStatus

# Models
from src.app.models.public.audit import AuditAction, AuditLog, AuditStatus
from src.app.models.public.auth import (
    EmailVerificationToken,
    RefreshToken,
    TenantInvite,
)
from src.app.models.public.tenant import Tenant
from src.app.models.public.user import User, UserTenantMembership
from src.app.models.public.workflow import WorkflowExecution

__all__ = [
    # Enums
    "AuditAction",
    "AuditStatus",
    "InviteStatus",
    "MembershipRole",
    "TenantStatus",
    # Models
    "AuditLog",
    "EmailVerificationToken",
    "RefreshToken",
    "Tenant",
    "TenantInvite",
    "User",
    "UserTenantMembership",
    "WorkflowExecution",
]
