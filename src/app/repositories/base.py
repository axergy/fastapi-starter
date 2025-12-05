"""Base repository with common CRUD operations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from src.app.schemas.pagination import decode_cursor, encode_cursor


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
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    def add(self, entity: ModelType) -> None:
        """Add entity to session (no flush/commit)."""
        self.session.add(entity)

    async def paginate(
        self,
        query: Any,  # SelectOfScalar or Select - SQLModel/SQLAlchemy query
        cursor: str | None,
        limit: int,
        cursor_field: Any,
    ) -> tuple[list[ModelType], str | None, bool]:
        """Execute cursor-based pagination on a query.

        Args:
            query: The base SQLAlchemy query to paginate
            cursor: Optional cursor from previous page (base64-encoded)
            limit: Maximum number of items to return
            cursor_field: The field to use for cursor (typically created_at or id)

        Returns:
            Tuple of (items, next_cursor, has_more)
            - items: List of results for this page
            - next_cursor: Base64-encoded cursor for next page, or None
            - has_more: Whether there are more results after this page
        """
        # If cursor is provided, decode it and add to query
        if cursor:
            try:
                cursor_value = decode_cursor(cursor)
                # Parse cursor value as ISO datetime
                cursor_dt = datetime.fromisoformat(cursor_value)
                query = query.where(cursor_field < cursor_dt)
            except (ValueError, TypeError):
                # Invalid cursor - ignore and start from beginning
                pass

        # Order by cursor field descending (newest first)
        query = query.order_by(cursor_field.desc())

        # Fetch limit + 1 to determine if there are more results
        query = query.limit(limit + 1)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        # Check if there are more results
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        # Generate next cursor from last item
        next_cursor = None
        if has_more and items:
            last_item = items[-1]
            cursor_value = getattr(last_item, cursor_field.key)
            if isinstance(cursor_value, datetime):
                next_cursor = encode_cursor(cursor_value.isoformat())

        return items, next_cursor, has_more
