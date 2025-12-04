from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.app.core.migrations import run_migrations_async
from src.app.models.public import Tenant


class TenantService:
    """Tenant provisioning service."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_tenant(self, name: str, slug: str) -> Tenant:
        """
        Create a new tenant with its own schema.

        1. Creates tenant record in public schema
        2. Runs migrations which create the schema and tables
        """
        result = await self.session.execute(select(Tenant).where(Tenant.slug == slug))
        if result.scalar_one_or_none() is not None:
            raise ValueError(f"Tenant with slug '{slug}' already exists")

        tenant = Tenant(name=name, slug=slug)
        self.session.add(tenant)
        await self.session.commit()
        await self.session.refresh(tenant)

        # Run migrations which will create the schema and tables
        await run_migrations_async(tenant.schema_name)

        return tenant

    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Get tenant by slug."""
        result = await self.session.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    async def list_tenants(self, active_only: bool = True) -> list[Tenant]:
        """List all tenants."""
        query = select(Tenant)
        if active_only:
            query = query.where(Tenant.is_active == True)  # noqa: E712
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def deactivate_tenant(self, tenant: Tenant) -> Tenant:
        """Deactivate a tenant."""
        tenant.is_active = False
        await self.session.commit()
        await self.session.refresh(tenant)
        return tenant
