from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.app.api.v1.router import api_router
from src.app.core.config import get_settings
from src.app.core.db import dispose_engine
from src.app.temporal.client import close_temporal_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan - startup and shutdown."""
    settings = get_settings()
    print(f"Starting {settings.app_name}")

    yield

    print("Shutting down...")
    await close_temporal_client()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    app.include_router(api_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    return app


app = create_app()
