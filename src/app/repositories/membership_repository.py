"""Repository for UserTenantMembership entity."""

from uuid import UUID

from sqlmodel import select

from src.app.models.public import MembershipRole, UserTenantMembership
from src.app.repositories.base import BaseRepository


class MembershipRepository(BaseRepository[UserTenantMembership]):
    """Repository for user-tenant memberships in public schema."""

    model = UserTenantMembership

    async def get_membership(
        self, user_id: UUID, tenant_id: UUID
    ) -> UserTenantMembership | None:
        """Get membership for a user in a tenant."""
        result = await self.session.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_id == user_id,
                UserTenantMembership.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_membership(
        self, user_id: UUID, tenant_id: UUID
    ) -> UserTenantMembership | None:
        """Get active membership for a user in a tenant."""
        result = await self.session.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_id == user_id,
                UserTenantMembership.tenant_id == tenant_id,
                UserTenantMembership.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def user_has_active_membership(self, user_id: UUID, tenant_id: UUID) -> bool:
        """Check if user has an active membership in tenant."""
        membership = await self.get_active_membership(user_id, tenant_id)
        return membership is not None

    async def list_user_tenants(self, user_id: UUID) -> list[UserTenantMembership]:
        """List all active tenant memberships for a user."""
        result = await self.session.execute(
            select(UserTenantMembership).where(
                UserTenantMembership.user_id == user_id,
                UserTenantMembership.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    def create_membership(
        self,
        user_id: UUID,
        tenant_id: UUID,
        role: str = MembershipRole.MEMBER.value,
    ) -> UserTenantMembership:
        """Create a new membership (add to session, no commit)."""
        membership = UserTenantMembership(
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
        )
        self.session.add(membership)
        return membership
