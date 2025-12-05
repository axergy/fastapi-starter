"""Repository for TenantInvite entity."""

from uuid import UUID

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
