"""User management service."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.security import hash_password
from src.app.models.public import User
from src.app.repositories.user_repository import UserRepository
from src.app.schemas.user import UserUpdate


class UserService:
    """User management service - business logic only."""

    def __init__(self, user_repo: UserRepository, session: AsyncSession):
        self.user_repo = user_repo
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        return await self.user_repo.get_by_id(user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        return await self.user_repo.get_by_email(email)

    async def update(self, user: User, data: UserUpdate) -> User:
        """Update user with provided data."""
        update_data = data.model_dump(exclude_unset=True)

        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def deactivate(self, user: User) -> User:
        """Deactivate user account."""
        user.is_active = False
        user.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(user)
        return user
