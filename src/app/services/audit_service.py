"""Audit logging service - records actions for compliance and security."""

import contextlib
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.audit_context import get_audit_context
from src.app.core.logging import get_logger
from src.app.models.public import AuditAction, AuditLog, AuditStatus
from src.app.repositories.public import AuditLogRepository

logger = get_logger(__name__)


class AuditService:
    """Service for recording audit logs.

    Fire-and-forget design: logging failures should not block business operations.
    """

    def __init__(
        self,
        audit_repo: AuditLogRepository,
        session: AsyncSession,
        tenant_id: UUID,
    ):
        self.audit_repo = audit_repo
        self.session = session
        self.tenant_id = tenant_id

    async def log_action(
        self,
        action: AuditAction | str,
        entity_type: str,
        entity_id: UUID | None = None,
        user_id: UUID | None = None,
        changes: dict[str, Any] | None = None,
        status: AuditStatus = AuditStatus.SUCCESS,
        error_message: str | None = None,
    ) -> AuditLog | None:
        """Record an audit log entry.

        Extracts request metadata from context (IP, user agent, request_id).
        Failures are logged but do not raise exceptions.

        Args:
            action: The action being performed (AuditAction enum or string)
            entity_type: Type of entity affected (e.g., "user", "tenant")
            entity_id: ID of the affected entity
            user_id: ID of the user performing the action
            changes: Dictionary of changes for update operations
            status: Success or failure status
            error_message: Error details if status is failure

        Returns:
            The created AuditLog, or None if logging failed
        """
        try:
            # Get request context
            ctx = get_audit_context()
            ip_address = ctx.ip_address if ctx else None
            user_agent = ctx.user_agent if ctx else None
            request_id = ctx.request_id if ctx else None

            # Create audit log entry
            audit_log = AuditLog(
                tenant_id=self.tenant_id,
                user_id=user_id,
                action=action.value if isinstance(action, AuditAction) else action,
                entity_type=entity_type,
                entity_id=entity_id,
                changes=changes,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                status=status.value if isinstance(status, AuditStatus) else status,
                error_message=error_message[:1000] if error_message else None,
            )

            self.audit_repo.add(audit_log)
            await self.session.commit()

            logger.debug(
                "Audit log recorded",
                action=audit_log.action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id else None,
            )

            return audit_log

        except Exception as e:
            # Fire-and-forget: log the failure but don't propagate
            logger.warning(
                "Failed to record audit log",
                action=action.value if isinstance(action, AuditAction) else action,
                entity_type=entity_type,
                error=str(e),
            )
            # Rollback to clean up the failed transaction
            with contextlib.suppress(Exception):
                await self.session.rollback()
            return None

    async def log_success(
        self,
        action: AuditAction | str,
        entity_type: str,
        entity_id: UUID | None = None,
        user_id: UUID | None = None,
        changes: dict[str, Any] | None = None,
    ) -> AuditLog | None:
        """Record a successful action."""
        return await self.log_action(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            changes=changes,
            status=AuditStatus.SUCCESS,
        )

    async def log_failure(
        self,
        action: AuditAction | str,
        entity_type: str,
        error_message: str,
        entity_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> AuditLog | None:
        """Record a failed action."""
        return await self.log_action(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            status=AuditStatus.FAILURE,
            error_message=error_message,
        )

    async def list_logs(
        self,
        cursor: str | None = None,
        limit: int = 50,
        action: str | None = None,
        user_id: UUID | None = None,
    ) -> tuple[list[AuditLog], str | None, bool]:
        """List audit logs for the current tenant."""
        return await self.audit_repo.list_by_tenant(
            tenant_id=self.tenant_id,
            cursor=cursor,
            limit=limit,
            action=action,
            user_id=user_id,
        )

    async def list_entity_history(
        self,
        entity_type: str,
        entity_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AuditLog], str | None, bool]:
        """List audit logs for a specific entity."""
        return await self.audit_repo.list_by_entity(
            entity_type=entity_type,
            entity_id=entity_id,
            cursor=cursor,
            limit=limit,
        )
