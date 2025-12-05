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
            cursor_field: The field to use for cursor (e.g., created_at, id)
                         Supports datetime, UUID, and other scalar types.

        Returns:
            Tuple of (items, next_cursor, has_more)
            - items: List of results for this page
            - next_cursor: Base64-encoded cursor for next page, or None
            - has_more: Whether there are more results after this page

        Note:
            Cursor values are stringified before encoding:
            - datetime → isoformat()
            - UUID and other scalars → str()
        """
        # If cursor is provided, decode it and add to query
        if cursor:
            try:
                cursor_str = decode_cursor(cursor)
                # Try to parse as datetime first, then UUID, then use as string
                cursor_value: datetime | UUID | str
                try:
                    cursor_value = datetime.fromisoformat(cursor_str)
                except ValueError:
                    try:
                        cursor_value = UUID(cursor_str)
                    except ValueError:
                        cursor_value = cursor_str
                query = query.where(cursor_field < cursor_value)
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
            value = getattr(last_item, cursor_field.key)
            # Convert to stable string representation
            if isinstance(value, datetime):
                next_cursor = encode_cursor(value.isoformat())
            elif value is not None:
                # UUID and other scalars: stringify
                next_cursor = encode_cursor(str(value))

        return items, next_cursor, has_more
