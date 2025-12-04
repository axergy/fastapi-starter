"""User management endpoints."""

from fastapi import APIRouter

from src.app.api.dependencies import CurrentUser, UserServiceDep
from src.app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_current_user(current_user: CurrentUser) -> UserRead:
    """Get current authenticated user."""
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
async def update_current_user(
    data: UserUpdate,
    current_user: CurrentUser,
    service: UserServiceDep,
) -> UserRead:
    """Update current user."""
    updated_user = await service.update(current_user, data)
    return UserRead.model_validate(updated_user)
