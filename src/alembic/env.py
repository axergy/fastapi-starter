import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool, text
from sqlmodel import SQLModel

from alembic import context
from src.app.core.config import get_settings
from src.app.core.security import validate_schema_name

# Import all models for metadata
from src.app.models import RefreshToken, Tenant, User  # noqa: F401

config = context.config

if config.config_file_name is not None and os.path.exists(config.config_file_name):
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def get_database_url() -> str:
    """Get database URL for migrations, preferring dedicated migrations URL."""
    settings = get_settings()
    return settings.database_migrations_url or settings.database_url


def get_url() -> str:
    """Get sync database URL (convert asyncpg to psycopg2)."""
    url = get_database_url()
    # Convert async URL to sync for Alembic
    return url.replace("+asyncpg", "")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    """
    Filter objects to prevent cross-schema contamination.
    - Public migrations: only touch tables with schema='public'
    - Tenant migrations: only touch tables WITHOUT schema='public'
    """
    if type_ == "table":
        is_tenant_migration = context.get_tag_argument() is not None
        object_schema = getattr(object, "schema", None)

        if is_tenant_migration:
            # Tenant migrations should ONLY touch tables WITHOUT 'public' schema
            return object_schema != "public"
        else:
            # Public migrations should ONLY touch tables WITH 'public' schema
            return object_schema == "public"

    return True


def do_run_migrations(connection, schema: str | None = None) -> None:
    """Run migrations for a specific schema."""
    if schema:
        # Validate schema name before any SQL execution
        validate_schema_name(schema)

        # Use quote_ident to properly quote the schema name
        quoted_schema = connection.execute(
            text("SELECT quote_ident(:schema)").bindparams(schema=schema)
        ).scalar()

        # Create schema and set search_path for tenant migrations
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}"))
        connection.execute(text(f"SET search_path TO {quoted_schema}"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=schema,
            include_schemas=True,
            compare_type=True,
            include_object=include_object,
        )
    else:
        # Public migrations - explicitly set search_path to prevent
        # tables from being created in wrong schema with non-standard defaults
        connection.execute(text("SET search_path TO public"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="public",
            compare_type=True,
            include_object=include_object,
        )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with sync engine."""
    url = get_url()

    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )

    # Get schema from alembic command-line tag (--tag)
    schema = context.get_tag_argument()

    with connectable.connect() as connection:
        do_run_migrations(connection, schema)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
