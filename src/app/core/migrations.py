"""Reusable migration runner for both production and tests."""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def _get_alembic_config() -> Config:
    """Get Alembic config with correct path resolution."""
    # Try current directory first (for Docker), then project root
    if os.path.exists("alembic.ini"):
        return Config("alembic.ini")

    # Fallback to project root (when running from src/app/...)
    project_root = Path(__file__).parent.parent.parent.parent
    config_path = project_root / "alembic.ini"
    return Config(str(config_path))


def run_migrations_sync(schema_name: str | None = None) -> None:
    """Run Alembic migrations synchronously.

    Args:
        schema_name: If provided, runs tenant migrations for this schema.
                    If None, runs public schema migrations.
    """
    alembic_cfg = _get_alembic_config()
    if schema_name:
        command.upgrade(alembic_cfg, "head", tag=schema_name)
    else:
        command.upgrade(alembic_cfg, "head")
