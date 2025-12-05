"""Base factory configuration for polyfactory."""

from datetime import UTC, datetime
from uuid import uuid7

from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory


def utc_now() -> datetime:
    """Generate current UTC time (naive for PostgreSQL compatibility)."""
    return datetime.now(UTC).replace(tzinfo=None)


def generate_uuid7():
    """Generate UUID7 for primary keys."""
    return uuid7()


class BaseFactory(SQLAlchemyFactory):
    """Base factory with common configuration for all models.

    Provides:
    - UUID7 generation for primary keys
    - UTC timestamp generation
    - Disabled auto-relationship setting (we control relationships manually)
    """

    __is_base_factory__ = True
    __set_relationships__ = False
    __set_foreign_keys__ = False  # We set FK values explicitly
