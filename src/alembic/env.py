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


def get_url() -> str:
    """Get sync database URL (convert asyncpg to psycopg2)."""
    url = get_settings().database_url
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
        )
    else:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
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
