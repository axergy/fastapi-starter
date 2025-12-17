"""Schema management activities."""

import asyncio
from dataclasses import dataclass

from sqlalchemy import text
from sqlmodel import Session
from temporalio import activity

from src.app.core.db import get_sync_engine, run_migrations_sync
from src.app.core.security import validate_schema_name
from src.app.temporal.context import TenantCtx


@dataclass
class RunMigrationsInput:
    ctx: TenantCtx


@dataclass
class DropSchemaInput:
    ctx: TenantCtx


@dataclass
class DropSchemaOutput:
    success: bool
    schema_existed: bool


def _sync_run_tenant_migrations(schema_name: str) -> bool:
    """Synchronous migration logic."""
    # Validate schema name BEFORE any operations to prevent injection
    validate_schema_name(schema_name)

    run_migrations_sync(schema_name)
    return True


@activity.defn
async def run_tenant_migrations(input: RunMigrationsInput) -> bool:
    """
    Run Alembic migrations for tenant schema.

    Idempotency: This activity is fully idempotent through multiple mechanisms:

    1. Schema Creation: Uses `CREATE SCHEMA IF NOT EXISTS` in Alembic's env.py,
       so creating an existing schema is a no-op.

    2. Migration Tracking: Alembic maintains an `alembic_version` table per
       schema that tracks which migrations have been applied. It will only run
       migrations that haven't been applied yet.

    3. Safe Retries: If this activity is retried after a partial migration
       failure, Alembic will resume from where it left off, not re-run
       completed migrations.

    This makes the activity safe to retry at any point without risk of:
    - Duplicate schema creation errors
    - Re-running already applied migrations
    - Inconsistent database state

    Args:
        input: RunMigrationsInput with schema_name

    Returns:
        True if migrations completed successfully
    """
    if not input.ctx.schema_name:
        raise ValueError("schema_name is required for run_tenant_migrations")
    activity.logger.info(f"Running migrations for schema: {input.ctx.schema_name}")
    await asyncio.to_thread(_sync_run_tenant_migrations, input.ctx.schema_name)
    activity.logger.info(f"Migrations complete for schema: {input.ctx.schema_name}")
    return True


def _sync_drop_tenant_schema(schema_name: str) -> DropSchemaOutput:
    """Synchronous schema drop logic with validation."""
    # Validate schema name BEFORE any SQL execution
    validate_schema_name(schema_name)

    engine = get_sync_engine()
    with Session(engine) as session:
        conn = session.connection()

        # Use quote_ident for safe identifier quoting
        quoted_schema = conn.execute(
            text("SELECT quote_ident(:schema)"), {"schema": schema_name}
        ).scalar()

        # Check if schema exists first
        schema_exists = conn.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = :schema
                )
                """
            ),
            {"schema": schema_name},
        ).scalar()

        if schema_exists:
            # CASCADE drops all contained objects
            conn.execute(text(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"))
            session.commit()

        return DropSchemaOutput(success=True, schema_existed=bool(schema_exists))


@activity.defn
async def drop_tenant_schema(input: DropSchemaInput) -> DropSchemaOutput:
    """
    Drop a tenant schema from the database.

    Idempotency: Uses `DROP SCHEMA IF EXISTS` which makes this operation fully
    idempotent. If the schema doesn't exist, the operation succeeds without
    error. Returns explicit status (schema_existed=True/False) to indicate
    whether the schema was actually dropped or was already gone.

    This allows retries to be safe:
    - 1st call: schema exists, DROP executes, returns schema_existed=True
    - 2nd call: schema gone, DROP is no-op, returns schema_existed=False
    - Nth call: schema still gone, still safe

    Security: Validates schema name before execution to prevent SQL injection.

    Args:
        input: DropSchemaInput with schema_name

    Returns:
        DropSchemaOutput with:
        - success: Always True (operation succeeded)
        - schema_existed: True if schema was dropped, False if already gone
    """
    if not input.ctx.schema_name:
        raise ValueError("schema_name is required for drop_tenant_schema")
    activity.logger.info(f"Dropping schema: {input.ctx.schema_name}")
    result = await asyncio.to_thread(_sync_drop_tenant_schema, input.ctx.schema_name)

    if result.schema_existed:
        activity.logger.info(f"Schema {input.ctx.schema_name} dropped successfully")
    else:
        activity.logger.info(f"Schema {input.ctx.schema_name} did not exist (already clean)")

    return result
