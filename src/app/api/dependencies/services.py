"""Service factory dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.api.dependencies.db import DBSession
from src.app.api.dependencies.repositories import (
    EmailVerificationRepo,
    InviteRepo,
    MembershipRepo,
    TenantRepo,
    TokenRepo,
    UserRepo,
    WorkflowExecRepo,
)
from src.app.api.dependencies.tenant import ValidatedTenant
from src.app.core.db.engine import get_engine
from src.app.repositories import AuditLogRepository
from src.app.services.admin_service import AdminService
from src.app.services.assume_identity_service import AssumeIdentityService
from src.app.services.audit_service import AuditService
from src.app.services.auth_service import AuthService
from src.app.services.email_verification_service import EmailVerificationService
from src.app.services.invite_service import InviteService
from src.app.services.registration_service import RegistrationService
from src.app.services.tenant_service import TenantService
from src.app.services.user_service import UserService


def get_user_service(user_repo: UserRepo, session: DBSession) -> UserService:
    """Get user service."""
    return UserService(user_repo, session)


def get_auth_service(
    user_repo: UserRepo,
    token_repo: TokenRepo,
    membership_repo: MembershipRepo,
    session: DBSession,
    tenant: ValidatedTenant,
) -> AuthService:
    """Get auth service with repositories and tenant context."""
    return AuthService(
        user_repo,
        token_repo,
        membership_repo,
        session,
        tenant.id,  # Pass UUID, not slug
    )


def get_tenant_service(
    tenant_repo: TenantRepo,
    workflow_exec_repo: WorkflowExecRepo,
    session: DBSession,
) -> TenantService:
    """Get tenant service."""
    return TenantService(tenant_repo, workflow_exec_repo, session)


def get_registration_service(
    user_repo: UserRepo,
    email_verification_repo: EmailVerificationRepo,
    session: DBSession,
) -> RegistrationService:
    """Get registration service (no tenant context required)."""
    email_verification_service = EmailVerificationService(
        user_repo, email_verification_repo, session
    )
    return RegistrationService(user_repo, session, email_verification_service)


def get_email_verification_service(
    user_repo: UserRepo,
    email_verification_repo: EmailVerificationRepo,
    session: DBSession,
) -> EmailVerificationService:
    """Get email verification service (no tenant context required)."""
    return EmailVerificationService(user_repo, email_verification_repo, session)


def get_invite_service(
    invite_repo: InviteRepo,
    user_repo: UserRepo,
    membership_repo: MembershipRepo,
    tenant_repo: TenantRepo,
    session: DBSession,
    tenant: ValidatedTenant,
) -> InviteService:
    """Get invite service with tenant context (for admin operations)."""
    return InviteService(invite_repo, user_repo, membership_repo, tenant_repo, session, tenant.id)


def get_invite_service_public(
    invite_repo: InviteRepo,
    user_repo: UserRepo,
    membership_repo: MembershipRepo,
    tenant_repo: TenantRepo,
    session: DBSession,
) -> InviteService:
    """Get invite service without tenant context (for public accept endpoints)."""
    return InviteService(invite_repo, user_repo, membership_repo, tenant_repo, session, None)


def get_admin_service(
    tenant_repo: TenantRepo,
    session: DBSession,
) -> AdminService:
    """Get admin service (no tenant context required)."""
    return AdminService(tenant_repo, session)


async def get_audit_service(
    tenant: ValidatedTenant,
) -> AsyncGenerator[AuditService]:
    """Get audit service with its own isolated session.

    Uses a dedicated session that commits independently from business transactions.
    This ensures audit logs are preserved even if the main transaction rolls back.
    """
    engine = get_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = AuditLogRepository(session)
        yield AuditService(repo, session, tenant.id)


def get_assume_identity_service(
    user_repo: UserRepo,
    membership_repo: MembershipRepo,
    tenant_repo: TenantRepo,
    session: DBSession,
) -> AssumeIdentityService:
    """Get assume identity service."""
    return AssumeIdentityService(user_repo, membership_repo, tenant_repo, session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]
RegistrationServiceDep = Annotated[RegistrationService, Depends(get_registration_service)]
EmailVerificationServiceDep = Annotated[
    EmailVerificationService, Depends(get_email_verification_service)
]
InviteServiceDep = Annotated[InviteService, Depends(get_invite_service)]
InviteServicePublicDep = Annotated[InviteService, Depends(get_invite_service_public)]
AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
AssumeIdentityServiceDep = Annotated[AssumeIdentityService, Depends(get_assume_identity_service)]
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]
