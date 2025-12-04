"""Base repository with common CRUD operations."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select


class BaseRepository[ModelType: SQLModel]:
    """Base repository providing common database operations.

    Repositories handle data access only. Transaction control (commit)
    should be done in the service layer.
    """

    model: type[ModelType]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Get a record by its primary key."""
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    def add(self, entity: ModelType) -> None:
        """Add entity to session (no flush/commit)."""
        self.session.add(entity)
