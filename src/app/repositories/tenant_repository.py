"""Repository for Tenant entity."""

from sqlmodel import select

from src.app.models.public import Tenant
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
