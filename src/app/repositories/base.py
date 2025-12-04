"""Base repository with common CRUD operations."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select


class BaseRepository[ModelType: SQLModel]:
    """Base repository providing common database operations."""

    model: type[ModelType]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> ModelType | None:
        """Get a record by its primary key."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def add(self, entity: ModelType) -> ModelType:
        """Add a new entity to the session."""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.session.commit()

    async def refresh(self, entity: ModelType) -> ModelType:
        """Refresh entity from database."""
        await self.session.refresh(entity)
        return entity
