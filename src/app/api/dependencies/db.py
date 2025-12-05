"""Database session dependencies - Lobby Pattern."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.db import get_public_session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for public schema (Lobby Pattern)."""
    async with get_public_session() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(get_db_session)]

# Alias for clarity
PublicDBSession = DBSession
