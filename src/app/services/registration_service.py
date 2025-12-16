"""Registration service - handles user + tenant registration (Lobby Pattern).

This service does NOT require a tenant context because it creates a new tenant.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.config import get_settings
from src.app.core.logging import get_logger
from src.app.core.security import hash_password
from src.app.models.public import Tenant, TenantStatus, User
from src.app.repositories import UserRepository
from src.app.services.email_verification_service import EmailVerificationService
from src.app.temporal.client import get_temporal_client
from src.app.temporal.workflows import TenantProvisioningWorkflow

logger = get_logger(__name__)


class RegistrationService:
    """Service for user registration with tenant creation."""

    def __init__(
        self,
        user_repo: UserRepository,
        session: AsyncSession,
        email_verification_service: EmailVerificationService | None = None,
    ):
        self.user_repo = user_repo
        self.session = session
        self.email_verification_service = email_verification_service

    async def register(
        self,
        email: str,
        password: str,
        full_name: str,
        tenant_name: str,
        tenant_slug: str,
    ) -> tuple[User, str]:
        """Register new user AND create a new tenant.

        1. Create user in public.users
        2. Create tenant record (unique constraint on slug handles races)
        3. COMMIT the session (point of no return)
        4. Refresh objects to ensure IDs are available
        5. Start TenantProvisioningWorkflow (provisions tenant + creates membership)

        Returns (user, workflow_id).
        Raises ValueError if email already exists or IntegrityError on commit.
        """
        # Create user in public schema
        # Normalize email to lowercase to prevent case-sensitivity issues
        user = User(
            email=email.lower().strip(),
            hashed_password=hash_password(password),
            full_name=full_name,
        )
        self.user_repo.add(user)

        # Create tenant record (unique constraint on slug handles races)
        tenant = Tenant(name=tenant_name, slug=tenant_slug, status=TenantStatus.PROVISIONING.value)
        self.session.add(tenant)

        # COMMIT before starting workflow - this is the point of no return
        try:
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            # Check which constraint failed
            if "email" in str(e).lower() or "users" in str(e).lower():
                raise ValueError("Email already registered") from e
            else:
                raise ValueError(f"Tenant with slug '{tenant_slug}' already exists") from e

        # Refresh objects to ensure all IDs are populated
        await self.session.refresh(user)
        await self.session.refresh(tenant)

        # Start tenant provisioning workflow AFTER commit
        settings = get_settings()
        client = await get_temporal_client()
        workflow_id = f"tenant-provision-{tenant_slug}"

        try:
            await client.start_workflow(
                TenantProvisioningWorkflow.run,
                args=[str(tenant.id), str(user.id)],
                id=workflow_id,
                task_queue=settings.temporal_task_queue,
            )
        except Exception as e:
            # Workflow start failed, but DB is committed - tenant exists in "provisioning" state
            # Don't rollback - log the error and allow manual retry
            logger.error(
                "Failed to start provisioning workflow - tenant created but workflow not started",
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                workflow_id=workflow_id,
                error=str(e),
            )
            raise ValueError(f"Failed to start tenant provisioning: {e}") from e

        # Send verification email if service is available
        if self.email_verification_service:
            try:
                await self.email_verification_service.create_and_send_verification(user)
            except Exception as e:
                # Log error but don't fail registration - user can resend verification
                logger.error(
                    "Failed to send verification email during registration",
                    user_id=str(user.id),
                    error=str(e),
                )

        return user, workflow_id
