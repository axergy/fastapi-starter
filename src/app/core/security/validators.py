"""Security validators."""

import re
from typing import Final

MAX_SCHEMA_LENGTH: Final[int] = 63  # PostgreSQL identifier limit
TENANT_SCHEMA_PREFIX: Final[str] = "tenant_"
MAX_TENANT_SLUG_LENGTH: Final[int] = MAX_SCHEMA_LENGTH - len(TENANT_SCHEMA_PREFIX)  # 56
TENANT_SLUG_REGEX: Final[str] = r"^[a-z][a-z0-9]*([-_][a-z0-9]+)*$"
TENANT_SCHEMA_REGEX: Final[str] = rf"^{TENANT_SCHEMA_PREFIX}[a-z][a-z0-9]*(_[a-z0-9]+)*$"

_TENANT_SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(TENANT_SLUG_REGEX)
_TENANT_SCHEMA_PATTERN: Final[re.Pattern[str]] = re.compile(TENANT_SCHEMA_REGEX)


def validate_tenant_slug_format(slug: str) -> str:
    """Validate tenant slug format (no `tenant_` prefix).

    This validates **format only**. Length is enforced by Field(max_length=...).
    """
    if not _TENANT_SLUG_PATTERN.match(slug):
        raise ValueError(
            "Slug must start with a letter and contain only lowercase letters, numbers, "
            "and single hyphens or underscores as separators"
        )
    return slug


def slug_to_schema_name(slug: str) -> str:
    """Convert a tenant slug to a PostgreSQL schema name.

    Hyphens are converted to underscores for PostgreSQL compatibility.
    E.g., 'acme-corp' -> 'tenant_acme_corp'
    """
    return f"{TENANT_SCHEMA_PREFIX}{slug.replace('-', '_')}"


def normalize_slug_for_comparison(slug: str) -> str:
    """Normalize a slug for collision detection.

    Both 'acme-corp' and 'acme_corp' normalize to 'acme_corp'.
    Used to prevent slugs that would map to the same schema name.
    """
    return slug.replace("-", "_")


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
    if not _TENANT_SCHEMA_PATTERN.match(schema_name):
        raise ValueError(
            f"Invalid schema name format: {schema_name}. "
            "Must be 'tenant_' followed by lowercase alphanumeric "
            "with single underscores as separators."
        )

    # Defense in depth - forbidden patterns
    forbidden = ["pg_", "information_schema", "public", "--", ";", "/*", "*/"]
    if any(pattern in schema_name.lower() for pattern in forbidden):
        raise ValueError(f"Schema name contains forbidden pattern: {schema_name}")
