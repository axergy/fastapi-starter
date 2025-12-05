"""Audit log model for tracking tenant-scoped actions."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from src.app.models.base import utc_now


class AuditAction(str, Enum):
    """Audit action types for type-safe logging."""

    # Auth
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_REGISTER = "user.register"
    TOKEN_REFRESH = "token.refresh"
    PASSWORD_CHANGE = "password.change"

    # Tenant
    TENANT_CREATE = "tenant.create"
    TENANT_UPDATE = "tenant.update"
    TENANT_DELETE = "tenant.delete"

    # Membership
    MEMBER_INVITE = "member.invite"
    MEMBER_JOIN = "member.join"
    MEMBER_REMOVE = "member.remove"
    MEMBER_ROLE_CHANGE = "member.role_change"

    # User
    USER_UPDATE = "user.update"
    USER_EMAIL_VERIFY = "user.email_verify"


class AuditStatus(str, Enum):
    """Audit log status."""

    SUCCESS = "success"
    FAILURE = "failure"


class AuditLog(SQLModel, table=True):
    """Audit log for tracking tenant-scoped actions.

    Stored in public schema for centralized querying and compliance audits.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        {"schema": "public"},
    )

    id: UUID = Field(default_factory=uuid7, primary_key=True)

    # Context
    tenant_id: UUID = Field(foreign_key="public.tenants.id", index=True)
    user_id: UUID | None = Field(foreign_key="public.users.id", index=True, default=None)

    # Action details
    action: str = Field(max_length=50)  # AuditAction value
    entity_type: str = Field(max_length=50)  # "user", "tenant", "membership", "invite"
    entity_id: UUID | None = Field(default=None)  # ID of affected entity

    # Change tracking (for update operations)
    changes: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )

    # Request metadata
    ip_address: str | None = Field(max_length=45, default=None)  # IPv4/IPv6
    user_agent: str | None = Field(max_length=500, default=None)
    request_id: str | None = Field(max_length=36, default=None)  # Correlation ID

    # Result
    status: str = Field(default=AuditStatus.SUCCESS.value, max_length=20)
    error_message: str | None = Field(max_length=1000, default=None)

    # Timestamp
    created_at: datetime = Field(default_factory=utc_now)
