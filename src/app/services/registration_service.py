"""Registration service - handles user + tenant registration (Lobby Pattern).

This service does NOT require a tenant context because it creates a new tenant.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.config import get_settings
from src.app.core.security import hash_password
from src.app.models.public import User
from src.app.repositories.user_repository import UserRepository
from src.app.temporal.client import get_temporal_client
from src.app.temporal.workflows import TenantProvisioningWorkflow


class RegistrationService:
    """Service for user registration with tenant creation."""

    def __init__(self, user_repo: UserRepository, session: AsyncSession):
        self.user_repo = user_repo
        self.session = session

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
        2. Start TenantProvisioningWorkflow (creates tenant + membership)

        Returns (user, workflow_id).
        Raises ValueError if email already exists or slug is taken.
        """
        # Check if email already exists
        if await self.user_repo.exists_by_email(email):
            raise ValueError("Email already registered")

        # Create user in public schema
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
        )
        self.user_repo.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        # Start tenant provisioning workflow
        settings = get_settings()
        client = await get_temporal_client()
        workflow_id = f"tenant-provision-{tenant_slug}"

        await client.start_workflow(
            TenantProvisioningWorkflow.run,
            args=[tenant_name, tenant_slug, str(user.id)],
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )

        return user, workflow_id
