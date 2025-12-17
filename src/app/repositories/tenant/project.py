"""Repository for Project entity (tenant-scoped)."""

from sqlmodel import col, select

from src.app.models.tenant import Project
from src.app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for Project entity in tenant schema."""

    model = Project

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Project]:
        """List all projects with simple offset pagination."""
        result = await self.session.execute(
            select(Project).order_by(col(Project.created_at).desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> Project | None:
        """Get project by name."""
        result = await self.session.execute(select(Project).where(Project.name == name))
        return result.scalar_one_or_none()
