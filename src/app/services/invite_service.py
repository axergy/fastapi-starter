"""Tenant invite service."""

import secrets
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.config import get_settings
from src.app.core.logging import get_logger
from src.app.core.notifications import send_invite_email
from src.app.core.security import hash_password, hash_token
from src.app.models.base import utc_now
from src.app.models.public import (
    InviteStatus,
    MembershipRole,
    Tenant,
    TenantInvite,
    User,
)
from src.app.repositories import (
    MembershipRepository,
    TenantInviteRepository,
    TenantRepository,
    UserRepository,
)

logger = get_logger(__name__)


class InviteService:
    """Service for tenant invite operations."""

    def __init__(
        self,
        invite_repo: TenantInviteRepository,
        user_repo: UserRepository,
        membership_repo: MembershipRepository,
        tenant_repo: TenantRepository,
        session: AsyncSession,
        tenant_id: UUID | None = None,
    ):
        self.invite_repo = invite_repo
        self.user_repo = user_repo
        self.membership_repo = membership_repo
        self.tenant_repo = tenant_repo
        self.session = session
        self.tenant_id = tenant_id

    async def create_invite(
        self,
        email: str,
        invited_by_user_id: UUID,
        role: str = MembershipRole.MEMBER.value,
    ) -> tuple[TenantInvite, str]:
        """Create and send an invite.

        Returns (invite, plaintext_token).

        If an existing pending invite exists, it will be invalidated
        and a new one created (resend behavior).
        """
        if self.tenant_id is None:
            raise ValueError("Tenant context required for creating invites")

        settings = get_settings()

        try:
            # Check if user already has membership in this tenant
            existing_user = await self.user_repo.get_by_email(email)
            if existing_user:
                has_membership = await self.membership_repo.user_has_active_membership(
                    existing_user.id, self.tenant_id
                )
                if has_membership:
                    raise ValueError("User is already a member of this tenant")

            # Invalidate any existing pending invites for this email+tenant
            await self.invite_repo.invalidate_existing(email, self.tenant_id)

            # Generate cryptographically secure token
            token = secrets.token_urlsafe(32)
            token_hash = hash_token(token)

            # Calculate expiry
            expires_at = utc_now() + timedelta(days=settings.invite_expire_days)

            # Create invite
            invite = TenantInvite(
                tenant_id=self.tenant_id,
                email=email,
                token_hash=token_hash,
                role=role,
                invited_by_user_id=invited_by_user_id,
                expires_at=expires_at,
            )
            self.invite_repo.add(invite)
            await self.session.commit()
            await self.session.refresh(invite)

            # Get tenant name for email
            tenant = await self.tenant_repo.get_by_id(self.tenant_id)
            inviter = await self.user_repo.get_by_id(invited_by_user_id)

            # Send invite email
            send_invite_email(
                to=email,
                token=token,
                tenant_name=tenant.name if tenant else "Unknown",
                inviter_name=inviter.full_name if inviter else "A team member",
            )

            logger.info(
                "Invite created",
                tenant_id=str(self.tenant_id),
                email=email,
                invited_by=str(invited_by_user_id),
            )
            return invite, token

        except ValueError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to create invite", error=str(e))
            raise

    async def accept_invite(
        self,
        token: str,
        email: str,
        password: str,
        full_name: str,
    ) -> tuple[TenantInvite, User, Tenant]:
        """Accept invite and create new user account.

        Users can only belong to ONE tenant, so invites are only valid
        for users who don't have an account yet.

        Validates:
        1. Token is valid and not expired
        2. Token email matches provided email
        3. Email not already registered
        4. Tenant exists and is not deleted

        Returns (invite, user, tenant).

        Note: New user is automatically email-verified since they
        received the invite email.
        """
        try:
            token_hash = hash_token(token)
            invite = await self.invite_repo.get_valid_by_hash(token_hash)

            if invite is None:
                raise ValueError("Invalid or expired invite token")

            # Token must match provided email
            if invite.email.lower() != email.lower():
                raise ValueError("Email does not match invite")

            # Check email not already registered (users can only belong to one tenant)
            existing_user = await self.user_repo.get_by_email(email)
            if existing_user:
                raise ValueError("Email already registered. Please login to your existing tenant.")

            # Get and validate tenant WITHIN transaction
            tenant = await self.tenant_repo.get_by_id(invite.tenant_id)
            if not tenant or tenant.deleted_at is not None:
                raise ValueError("Tenant is no longer available")

            # Create new user (email verified since they received invite)
            # Normalize email to lowercase to prevent case-sensitivity issues
            user = User(
                email=email.lower().strip(),
                hashed_password=hash_password(password),
                full_name=full_name,
                email_verified=True,
                email_verified_at=utc_now(),
            )
            self.user_repo.add(user)
            await self.session.flush()  # Get user.id

            # Complete the invite acceptance
            return await self._complete_invite_acceptance(invite, user, tenant)

        except ValueError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to accept invite", error=str(e))
            raise

    async def _complete_invite_acceptance(
        self,
        invite: TenantInvite,
        user: User,
        tenant: Tenant,
    ) -> tuple[TenantInvite, User, Tenant]:
        """Complete invite acceptance after validation.

        Creates membership, marks invite as accepted, commits, and refreshes objects.
        """
        # Create membership
        self.membership_repo.create_membership(
            user_id=user.id,
            tenant_id=invite.tenant_id,
            role=invite.role,
        )

        # Mark invite as accepted
        await self.invite_repo.mark_accepted(invite, user.id)

        # Capture IDs before commit (to avoid lazy loading issues after commit)
        invite_id = str(invite.id)
        user_id = str(user.id)

        await self.session.commit()

        # Refresh objects to ensure they're usable after commit
        await self.session.refresh(invite)
        await self.session.refresh(user)
        await self.session.refresh(tenant)

        logger.info(
            "Invite accepted",
            invite_id=invite_id,
            user_id=user_id,
        )
        return invite, user, tenant

    async def get_invite_info(self, token: str) -> dict[str, Any] | None:
        """Get invite info for display (before accepting).

        Returns public info about the invite without revealing sensitive data.
        Used to show "You've been invited to join X" screen.
        """
        token_hash = hash_token(token)
        invite = await self.invite_repo.get_valid_by_hash(token_hash)

        if invite is None:
            return None

        tenant = await self.tenant_repo.get_by_id(invite.tenant_id)

        return {
            "email": invite.email,
            "tenant_name": tenant.name if tenant else "Unknown",
            "tenant_slug": tenant.slug if tenant else None,
            "role": invite.role,
            "expires_at": invite.expires_at,
        }

    async def get_invite_by_id(self, invite_id: UUID) -> TenantInvite | None:
        """Get invite by ID (admin view)."""
        if self.tenant_id is None:
            raise ValueError("Tenant context required")

        invite = await self.invite_repo.get_by_id(invite_id)
        if invite is None or invite.tenant_id != self.tenant_id:
            return None
        return invite

    async def list_pending_invites(
        self, cursor: str | None, limit: int
    ) -> tuple[list[TenantInvite], str | None, bool]:
        """List pending invites for current tenant with cursor-based pagination.

        Args:
            cursor: Optional cursor for pagination
            limit: Maximum number of results

        Returns:
            Tuple of (items, next_cursor, has_more)
        """
        if self.tenant_id is None:
            raise ValueError("Tenant context required for listing invites")

        return await self.invite_repo.get_pending_by_tenant(self.tenant_id, cursor, limit)

    async def cancel_invite(self, invite_id: UUID) -> TenantInvite:
        """Cancel a pending invite."""
        if self.tenant_id is None:
            raise ValueError("Tenant context required for cancelling invites")

        try:
            invite = await self.invite_repo.get_by_id(invite_id)

            if invite is None:
                raise ValueError("Invite not found")

            if invite.tenant_id != self.tenant_id:
                raise ValueError("Invite does not belong to this tenant")

            if invite.status != InviteStatus.PENDING.value:
                raise ValueError(f"Cannot cancel invite with status: {invite.status}")

            await self.invite_repo.mark_cancelled(invite)
            await self.session.commit()

            logger.info("Invite cancelled", invite_id=str(invite_id))
            return invite

        except ValueError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error("Failed to cancel invite", error=str(e))
            raise

    async def resend_invite(
        self, invite_id: UUID, resent_by_user_id: UUID
    ) -> tuple[TenantInvite, str]:
        """Resend an invite (creates new token, invalidates old)."""
        if self.tenant_id is None:
            raise ValueError("Tenant context required for resending invites")

        invite = await self.invite_repo.get_by_id(invite_id)

        if invite is None:
            raise ValueError("Invite not found")

        if invite.tenant_id != self.tenant_id:
            raise ValueError("Invite does not belong to this tenant")

        # Create new invite for same email (which invalidates old one)
        return await self.create_invite(
            email=invite.email,
            invited_by_user_id=resent_by_user_id,
            role=invite.role,
        )
