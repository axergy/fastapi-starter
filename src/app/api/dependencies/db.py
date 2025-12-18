"""Database session dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.api.dependencies.tenant import get_tenant
from src.app.core.db import get_session
from src.app.models import Tenant


async def get_db_session(
    tenant: Annotated[Tenant | None, Depends(get_tenant)],
) -> AsyncGenerator[AsyncSession]:
    """Get database session scoped to tenant if X-Tenant-Slug header provided."""
    schema = tenant.schema_name if tenant else None
    async with get_session(schema) as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db_session)]
