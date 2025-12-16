"""Assume identity service - allows superusers to act as other users."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.logging import get_logger
from src.app.core.security import (
    ASSUMED_IDENTITY_TOKEN_EXPIRE_MINUTES,
    create_assumed_identity_token,
)
from src.app.models.public import User
from src.app.repositories import MembershipRepository, TenantRepository, UserRepository
from src.app.schemas.assume_identity import AssumeIdentityResponse

logger = get_logger(__name__)


class AssumeIdentityService:
    """Service for managing assumed identity sessions.

    Allows superusers to assume the identity of any non-superuser
    in any tenant where the target user has membership.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
        tenant_repo: TenantRepository,
        session: AsyncSession,
    ):
        self.user_repo = user_repo
        self.membership_repo = membership_repo
        self.tenant_repo = tenant_repo
        self.session = session

    async def assume_identity(
        self,
        operator: User,
        target_user_id: UUID,
        tenant_id: UUID,
        reason: str | None = None,
    ) -> AssumeIdentityResponse:
        """Start an assumed identity session.

        Creates a time-limited JWT token that allows the operator (superuser)
        to act as the target user within the specified tenant context.

        Args:
            operator: The superuser initiating the assumption
            target_user_id: ID of the user whose identity to assume
            tenant_id: Tenant context for the session
            reason: Optional reason for the assumption (for audit)

        Returns:
            AssumeIdentityResponse with token and metadata

        Raises:
            ValueError: If validation fails (user not found, inactive,
                       is superuser, or not in tenant)
        """
        # Validate target user exists and is active
        target_user = await self.user_repo.get_by_id(target_user_id)
        if target_user is None:
            raise ValueError("Target user not found")
        if not target_user.is_active:
            raise ValueError("Target user is inactive")

        # Security: Cannot assume another superuser's identity
        if target_user.is_superuser:
            raise ValueError("Cannot assume identity of another superuser")

        # Validate tenant exists and is active
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if tenant is None:
            raise ValueError("Tenant not found")
        if not tenant.is_active:
            raise ValueError("Tenant is inactive")

        # Validate target user has active membership in tenant
        has_membership = await self.membership_repo.user_has_active_membership(
            target_user_id, tenant_id
        )
        if not has_membership:
            raise ValueError("Target user does not have access to this tenant")

        # Create assumed identity token
        access_token = create_assumed_identity_token(
            assumed_user_id=target_user_id,
            operator_user_id=operator.id,
            tenant_id=tenant_id,
            reason=reason,
        )

        logger.info(
            "Assumed identity session started",
            operator_user_id=str(operator.id),
            operator_email=operator.email,
            assumed_user_id=str(target_user_id),
            assumed_user_email=target_user.email,
            tenant_id=str(tenant_id),
            tenant_slug=tenant.slug,
            reason=reason,
        )

        return AssumeIdentityResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ASSUMED_IDENTITY_TOKEN_EXPIRE_MINUTES * 60,
            assumed_user_id=target_user.id,
            assumed_user_email=target_user.email,
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
        )
