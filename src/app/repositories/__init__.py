"""Repository layer - data access abstraction.

Re-exports all repositories for backward compatibility.
"""

from src.app.repositories.base import BaseRepository
from src.app.repositories.public import (
    AuditLogRepository,
    EmailVerificationTokenRepository,
    MembershipRepository,
    RefreshTokenRepository,
    TenantInviteRepository,
    TenantRepository,
    UserRepository,
    WorkflowExecutionRepository,
)
from src.app.repositories.tenant import ProjectRepository

__all__ = [
    # Base
    "BaseRepository",
    # Public schema
    "AuditLogRepository",
    "EmailVerificationTokenRepository",
    "MembershipRepository",
    "RefreshTokenRepository",
    "TenantInviteRepository",
    "TenantRepository",
    "UserRepository",
    "WorkflowExecutionRepository",
    # Tenant schema
    "ProjectRepository",
]
