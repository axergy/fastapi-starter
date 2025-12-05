"""Security validators."""

import re

MAX_SCHEMA_LENGTH = 63  # PostgreSQL identifier limit


def validate_schema_name(schema_name: str) -> None:
    """Validate schema name follows strict tenant naming convention.

    Schema names must:
    - Start with 'tenant_' prefix
    - Contain only lowercase letters, numbers, and single underscores as separators
    - Not exceed 63 characters (PostgreSQL limit)
    - Not contain forbidden patterns

    Args:
        schema_name: The schema name to validate

    Raises:
        ValueError: If schema name is invalid

    Examples:
        >>> validate_schema_name("tenant_acme")  # Valid
        >>> validate_schema_name("tenant_acme_corp")  # Valid
        >>> validate_schema_name("acme")  # Invalid - missing prefix
        >>> validate_schema_name("tenant__acme")  # Invalid - consecutive underscores
    """
    # Length check
    if len(schema_name) > MAX_SCHEMA_LENGTH:
        raise ValueError(
            f"Schema name exceeds PostgreSQL limit: {len(schema_name)} > {MAX_SCHEMA_LENGTH}"
        )

    # Format check - must be tenant_<slug> with proper format
    if not re.match(r"^tenant_[a-z][a-z0-9]*(_[a-z0-9]+)*$", schema_name):
        raise ValueError(
            f"Invalid schema name format: {schema_name}. "
            "Must be 'tenant_' followed by lowercase alphanumeric "
            "with single underscores as separators."
        )

    # Defense in depth - forbidden patterns
    forbidden = ["pg_", "information_schema", "public", "--", ";", "/*", "*/"]
    if any(pattern in schema_name.lower() for pattern in forbidden):
        raise ValueError(f"Schema name contains forbidden pattern: {schema_name}")
