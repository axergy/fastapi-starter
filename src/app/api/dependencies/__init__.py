"""FastAPI dependency injection definitions - Lobby Pattern.

Re-exports all dependencies for backward compatibility.
"""

# Database
# Auth
from src.app.api.dependencies.auth import (
    AdminUser,
    AuthenticatedUser,
    CurrentUser,
    SuperUser,
    get_authenticated_user,
    get_current_user,
    require_admin_role,
    require_superuser,
)
from src.app.api.dependencies.db import (
    DBSession,
    PublicDBSession,
    get_db_session,
)

# Repositories
from src.app.api.dependencies.repositories import (
    EmailVerificationRepo,
    InviteRepo,
    MembershipRepo,
    TenantRepo,
    TokenRepo,
    UserRepo,
    WorkflowExecRepo,
    get_email_verification_repository,
    get_invite_repository,
    get_membership_repository,
    get_tenant_repository,
    get_token_repository,
    get_user_repository,
    get_workflow_execution_repository,
)

# Services
from src.app.api.dependencies.services import (
    AdminServiceDep,
    AuthServiceDep,
    EmailVerificationServiceDep,
    InviteServiceDep,
    InviteServicePublicDep,
    RegistrationServiceDep,
    TenantServiceDep,
    UserServiceDep,
    get_admin_service,
    get_auth_service,
    get_email_verification_service,
    get_invite_service,
    get_invite_service_public,
    get_registration_service,
    get_tenant_service,
    get_user_service,
)

# Tenant
from src.app.api.dependencies.tenant import (
    ValidatedTenant,
    get_tenant_id_from_header,
    get_validated_tenant,
)

__all__ = [
    # Database
    "DBSession",
    "PublicDBSession",
    "get_db_session",
    # Tenant
    "ValidatedTenant",
    "get_tenant_id_from_header",
    "get_validated_tenant",
    # Auth
    "AdminUser",
    "AuthenticatedUser",
    "CurrentUser",
    "SuperUser",
    "get_authenticated_user",
    "get_current_user",
    "require_admin_role",
    "require_superuser",
    # Repositories
    "EmailVerificationRepo",
    "InviteRepo",
    "MembershipRepo",
    "TenantRepo",
    "TokenRepo",
    "UserRepo",
    "WorkflowExecRepo",
    "get_email_verification_repository",
    "get_invite_repository",
    "get_membership_repository",
    "get_tenant_repository",
    "get_token_repository",
    "get_user_repository",
    "get_workflow_execution_repository",
    # Services
    "AdminServiceDep",
    "AuthServiceDep",
    "EmailVerificationServiceDep",
    "InviteServiceDep",
    "InviteServicePublicDep",
    "RegistrationServiceDep",
    "TenantServiceDep",
    "UserServiceDep",
    "get_admin_service",
    "get_auth_service",
    "get_email_verification_service",
    "get_invite_service",
    "get_invite_service_public",
    "get_registration_service",
    "get_tenant_service",
    "get_user_service",
]
