"""Repository for AuditLog entity."""

from datetime import timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.engine import CursorResult
from sqlmodel import select

from src.app.models.base import utc_now
from src.app.models.public import AuditLog
from src.app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Repository for AuditLog entity in public schema."""

    model = AuditLog

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
        action: str | None = None,
        user_id: UUID | None = None,
    ) -> tuple[list[AuditLog], str | None, bool]:
        """List audit logs for a tenant with cursor pagination.

        Args:
            tenant_id: Tenant to filter by
            cursor: Pagination cursor
            limit: Maximum items to return
            action: Optional action type filter
            user_id: Optional user filter

        Returns:
            Tuple of (logs, next_cursor, has_more)
        """
        query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

        if action:
            query = query.where(AuditLog.action == action)
        if user_id:
            query = query.where(AuditLog.user_id == user_id)

        return await self.paginate(query, cursor, limit, AuditLog.created_at)

    async def list_by_user(
        self,
        user_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AuditLog], str | None, bool]:
        """List audit logs for a specific user.

        Args:
            user_id: User to filter by
            cursor: Pagination cursor
            limit: Maximum items to return

        Returns:
            Tuple of (logs, next_cursor, has_more)
        """
        query = select(AuditLog).where(AuditLog.user_id == user_id)
        return await self.paginate(query, cursor, limit, AuditLog.created_at)

    async def list_by_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AuditLog], str | None, bool]:
        """List audit logs for a specific entity.

        Args:
            entity_type: Type of entity (e.g., "user", "tenant")
            entity_id: ID of the entity
            cursor: Pagination cursor
            limit: Maximum items to return

        Returns:
            Tuple of (logs, next_cursor, has_more)
        """
        query = select(AuditLog).where(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        )
        return await self.paginate(query, cursor, limit, AuditLog.created_at)

    async def cleanup_old_logs(self, retention_days: int) -> int:
        """Delete audit logs older than retention_days.

        Args:
            retention_days: Number of days to retain logs

        Returns:
            Number of logs deleted
        """
        cutoff = utc_now() - timedelta(days=retention_days)
        stmt = delete(AuditLog).where(AuditLog.created_at < cutoff)  # type: ignore[arg-type]
        result = await self.session.execute(stmt)
        await self.session.commit()
        return cast(CursorResult[Any], result).rowcount or 0
