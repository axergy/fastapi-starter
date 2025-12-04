"""Reusable migration runner for both production and tests."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from alembic.config import Config

from alembic import command


def run_migrations_sync(schema_name: str | None = None) -> None:
    """Run Alembic migrations synchronously.

    Args:
        schema_name: If provided, runs tenant migrations for this schema.
                    If None, runs public schema migrations.
    """
    alembic_cfg = Config("alembic.ini")
    if schema_name:
        command.upgrade(alembic_cfg, "head", tag=schema_name)
    else:
        command.upgrade(alembic_cfg, "head")


async def run_migrations_async(schema_name: str | None = None) -> None:
    """Run Alembic migrations from async context.

    Uses ThreadPoolExecutor to avoid event loop conflicts with Alembic.
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, run_migrations_sync, schema_name)
