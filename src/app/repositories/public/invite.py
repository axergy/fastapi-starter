"""Repository for TenantInvite entity."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, delete, or_
from sqlmodel import select, update

from src.app.models.base import utc_now
from src.app.models.public import InviteStatus, TenantInvite
from src.app.repositories.base import BaseRepository


class TenantInviteRepository(BaseRepository[TenantInvite]):
    """Repository for TenantInvite entity in public schema."""

    model = TenantInvite

    async def get_valid_by_hash(self, token_hash: str) -> TenantInvite | None:
        """Get a valid (pending, non-expired) invite by its hash."""
        result = await self.session.execute(
            select(TenantInvite).where(
                TenantInvite.token_hash == token_hash,
                TenantInvite.status == InviteStatus.PENDING.value,
                TenantInvite.expires_at > utc_now(),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email_and_tenant(self, email: str, tenant_id: UUID) -> TenantInvite | None:
        """Get pending invite for email in tenant."""
        result = await self.session.execute(
            select(TenantInvite).where(
                TenantInvite.email == email,
                TenantInvite.tenant_id == tenant_id,
                TenantInvite.status == InviteStatus.PENDING.value,
            )
        )
        return result.scalar_one_or_none()

    async def get_pending_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[TenantInvite]:
        """List pending invites for a tenant."""
        result = await self.session.execute(
            select(TenantInvite)
            .where(
                TenantInvite.tenant_id == tenant_id,
                TenantInvite.status == InviteStatus.PENDING.value,
            )
            .order_by(TenantInvite.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_pending_by_tenant_paginated(
        self, tenant_id: UUID, cursor: str | None, limit: int
    ) -> tuple[list[TenantInvite], str | None, bool]:
        """List pending invites for a tenant with cursor-based pagination.

        Args:
            tenant_id: Tenant ID to filter by
            cursor: Optional cursor for pagination
            limit: Maximum number of results

        Returns:
            Tuple of (items, next_cursor, has_more)
        """
        query = select(TenantInvite).where(
            TenantInvite.tenant_id == tenant_id,
            TenantInvite.status == InviteStatus.PENDING.value,
        )
        return await self.paginate(query, cursor, limit, TenantInvite.created_at)

    async def mark_accepted(self, invite: TenantInvite, user_id: UUID) -> TenantInvite:
        """Mark an invite as accepted."""
        invite.status = InviteStatus.ACCEPTED.value
        invite.accepted_at = utc_now()
        invite.accepted_by_user_id = user_id
        self.session.add(invite)
        await self.session.flush()
        return invite

    async def mark_cancelled(self, invite: TenantInvite) -> TenantInvite:
        """Mark an invite as cancelled."""
        invite.status = InviteStatus.CANCELLED.value
        self.session.add(invite)
        await self.session.flush()
        return invite

    async def invalidate_existing(self, email: str, tenant_id: UUID) -> None:
        """Invalidate existing pending invites for email in tenant."""
        await self.session.execute(
            update(TenantInvite)
            .where(TenantInvite.email == email)  # type: ignore[arg-type]
            .where(TenantInvite.tenant_id == tenant_id)  # type: ignore[arg-type]
            .where(TenantInvite.status == InviteStatus.PENDING.value)  # type: ignore[arg-type]
            .values(status=InviteStatus.CANCELLED.value)
        )

    async def cleanup_expired(self, retention_days: int) -> int:
        """Delete invites expired more than retention_days ago.

        Also deletes cancelled or accepted invites older than retention_days.
        Idempotent: DELETE operations are inherently idempotent.

        Args:
            retention_days: Number of days to retain expired/cancelled/accepted invites

        Returns:
            Number of invites deleted
        """
        cutoff = utc_now() - timedelta(days=retention_days)
        stmt = delete(TenantInvite).where(
            or_(
                TenantInvite.expires_at < cutoff,  # type: ignore[arg-type]
                and_(
                    TenantInvite.status.in_(  # type: ignore[union-attr, attr-defined]
                        [InviteStatus.CANCELLED.value, InviteStatus.ACCEPTED.value]
                    ),
                    TenantInvite.created_at < cutoff,  # type: ignore[arg-type]
                ),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0  # type: ignore[attr-defined]
