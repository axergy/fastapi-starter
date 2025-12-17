"""Database utilities - engine, session, migrations.

Re-exports all database-related functions for backward compatibility.
"""

from src.app.core.db.engine import (
    dispose_engine,
    dispose_sync_engine,
    get_engine,
    get_sync_engine,
)
from src.app.core.db.migrations import run_migrations_sync
from src.app.core.db.session import get_public_session, get_tenant_session

__all__ = [
    # Engine (async)
    "dispose_engine",
    "get_engine",
    # Engine (sync - for Temporal activities)
    "dispose_sync_engine",
    "get_sync_engine",
    # Session
    "get_public_session",
    "get_tenant_session",
    # Migrations
    "run_migrations_sync",
]
