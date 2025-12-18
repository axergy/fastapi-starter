"""Repository for Project entity (tenant-scoped)."""

from sqlmodel import select

from src.app.models.tenant import Project
from src.app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Repository for Project entity in tenant schema."""

    model = Project

    async def list_all(
        self,
        cursor: str | None = None,
        limit: int = 100,
    ) -> tuple[list[Project], str | None, bool]:
        """List all projects with cursor-based pagination.

        Args:
            cursor: Optional cursor for pagination
            limit: Maximum number of results

        Returns:
            Tuple of (items, next_cursor, has_more)
        """
        query = select(Project)
        return await self.paginate(query, cursor, limit, Project.created_at)

    async def get_by_name(self, name: str) -> Project | None:
        """Get project by name."""
        result = await self.session.execute(select(Project).where(Project.name == name))
        return result.scalar_one_or_none()
