"""Repository factory dependencies."""

from typing import Annotated

from fastapi import Depends

from src.app.api.dependencies.db import DBSession
from src.app.repositories import (
    AuditLogRepository,
    EmailVerificationTokenRepository,
    MembershipRepository,
    RefreshTokenRepository,
    TenantInviteRepository,
    TenantRepository,
    UserRepository,
    WorkflowExecutionRepository,
)


def get_user_repository(session: DBSession) -> UserRepository:
    """Get user repository with public schema session."""
    return UserRepository(session)


def get_token_repository(session: DBSession) -> RefreshTokenRepository:
    """Get refresh token repository with public schema session."""
    return RefreshTokenRepository(session)


def get_membership_repository(session: DBSession) -> MembershipRepository:
    """Get membership repository with public schema session."""
    return MembershipRepository(session)


def get_tenant_repository(session: DBSession) -> TenantRepository:
    """Get tenant repository with public schema session."""
    return TenantRepository(session)


def get_workflow_execution_repository(
    session: DBSession,
) -> WorkflowExecutionRepository:
    """Get workflow execution repository with public schema session."""
    return WorkflowExecutionRepository(session)


def get_email_verification_repository(
    session: DBSession,
) -> EmailVerificationTokenRepository:
    """Get email verification token repository with public schema session."""
    return EmailVerificationTokenRepository(session)


def get_invite_repository(session: DBSession) -> TenantInviteRepository:
    """Get invite repository with public schema session."""
    return TenantInviteRepository(session)


def get_audit_log_repository(session: DBSession) -> AuditLogRepository:
    """Get audit log repository with public schema session."""
    return AuditLogRepository(session)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]
TokenRepo = Annotated[RefreshTokenRepository, Depends(get_token_repository)]
MembershipRepo = Annotated[MembershipRepository, Depends(get_membership_repository)]
TenantRepo = Annotated[TenantRepository, Depends(get_tenant_repository)]
WorkflowExecRepo = Annotated[
    WorkflowExecutionRepository, Depends(get_workflow_execution_repository)
]
EmailVerificationRepo = Annotated[
    EmailVerificationTokenRepository, Depends(get_email_verification_repository)
]
InviteRepo = Annotated[TenantInviteRepository, Depends(get_invite_repository)]
AuditLogRepo = Annotated[AuditLogRepository, Depends(get_audit_log_repository)]
