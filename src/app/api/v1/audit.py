"""Audit log endpoints - admin only."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from src.app.api.dependencies import AdminUser, AuditServiceDep
from src.app.schemas.audit import AuditLogListResponse, AuditLogRead

router = APIRouter(prefix="/audit", tags=["audit"])

# Query parameter types
CursorQuery = Annotated[str | None, Query(description="Pagination cursor")]
LimitQuery = Annotated[int, Query(ge=1, le=100, description="Items per page")]
ActionQuery = Annotated[str | None, Query(description="Filter by action type")]
UserIdQuery = Annotated[UUID | None, Query(description="Filter by user ID")]


@router.get(
    "/logs",
    response_model=AuditLogListResponse,
    responses={
        200: {
            "description": "List of audit logs",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "tenant_id": "550e8400-e29b-41d4-a716-446655440001",
                                "user_id": "550e8400-e29b-41d4-a716-446655440002",
                                "action": "user.login",
                                "entity_type": "user",
                                "entity_id": None,
                                "changes": None,
                                "ip_address": "192.168.1.1",
                                "user_agent": "Mozilla/5.0...",
                                "request_id": "abc-123",
                                "status": "success",
                                "error_message": None,
                                "created_at": "2025-01-01T00:00:00",
                            }
                        ],
                        "next_cursor": "abc123",
                        "has_more": True,
                    }
                }
            },
        },
        403: {"description": "Admin access required"},
    },
)
async def list_audit_logs(
    _: AdminUser,
    audit_service: AuditServiceDep,
    cursor: CursorQuery = None,
    limit: LimitQuery = 50,
    action: ActionQuery = None,
    user_id: UserIdQuery = None,
) -> AuditLogListResponse:
    """List audit logs for the current tenant.

    Requires admin role. Returns paginated results.
    """
    logs, next_cursor, has_more = await audit_service.list_logs(
        cursor=cursor,
        limit=limit,
        action=action,
        user_id=user_id,
    )

    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(log) for log in logs],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get(
    "/logs/entity/{entity_type}/{entity_id}",
    response_model=AuditLogListResponse,
    responses={
        200: {"description": "Audit history for entity"},
        403: {"description": "Admin access required"},
    },
)
async def get_entity_history(
    _: AdminUser,
    audit_service: AuditServiceDep,
    entity_type: str,
    entity_id: UUID,
    cursor: CursorQuery = None,
    limit: LimitQuery = 50,
) -> AuditLogListResponse:
    """Get audit history for a specific entity.

    Requires admin role. Returns paginated results.
    """
    logs, next_cursor, has_more = await audit_service.list_entity_history(
        entity_type=entity_type,
        entity_id=entity_id,
        cursor=cursor,
        limit=limit,
    )

    return AuditLogListResponse(
        items=[AuditLogRead.model_validate(log) for log in logs],
        next_cursor=next_cursor,
        has_more=has_more,
    )
