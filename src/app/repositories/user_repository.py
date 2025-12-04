"""Repository for User entity."""

from sqlmodel import select

from src.app.models.tenant import User
from src.app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User entity in tenant schemas."""

    model = User

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email address."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        """Check if a user with the given email exists."""
        user = await self.get_by_email(email)
        return user is not None
