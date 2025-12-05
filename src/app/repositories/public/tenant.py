"""Repository for Tenant entity."""

from uuid import UUID

from sqlmodel import select

from src.app.models.public import Tenant, UserTenantMembership
from src.app.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    """Repository for Tenant entity in public schema."""

    model = Tenant

    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Get tenant by slug."""
        result = await self.session.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    async def exists_by_slug(self, slug: str) -> bool:
        """Check if a tenant with the given slug exists."""
        tenant = await self.get_by_slug(slug)
        return tenant is not None

    async def list_all(self, active_only: bool = True) -> list[Tenant]:
        """List all tenants, optionally filtering by active status."""
        query = select(Tenant)
        if active_only:
            query = query.where(Tenant.is_active == True)  # noqa: E712
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_user_membership(self, user_id: UUID) -> list[Tenant]:
        """List tenants where user has active membership."""
        query = (
            select(Tenant)
            .join(
                UserTenantMembership,
                Tenant.id == UserTenantMembership.tenant_id,  # type: ignore[arg-type]
            )
            .where(
                UserTenantMembership.user_id == user_id,
                UserTenantMembership.is_active == True,  # noqa: E712
                Tenant.is_active == True,  # noqa: E712
            )
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_for_deletion(self, status_filter: str | None = None) -> list[Tenant]:
        """List tenants eligible for deletion (not already soft-deleted).

        Args:
            status_filter: Optional status to filter by (e.g., 'failed')

        Returns:
            List of tenants that can be deleted
        """
        query = select(Tenant).where(Tenant.deleted_at.is_(None))  # type: ignore[union-attr]
        if status_filter:
            query = query.where(Tenant.status == status_filter)
        result = await self.session.execute(query)
        return list(result.scalars().all())
