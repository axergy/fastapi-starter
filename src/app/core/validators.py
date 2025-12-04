import re


def validate_schema_name(schema_name: str) -> None:
    """Validate schema name to prevent SQL injection."""
    if not re.match(r'^[a-z][a-z0-9_]{0,49}$', schema_name):
        raise ValueError(f"Invalid schema name: {schema_name}")

    forbidden = ['pg_', 'information_schema', 'public', '--', ';', '/*', '*/']
    if any(pattern in schema_name.lower() for pattern in forbidden):
        raise ValueError(f"Schema name contains forbidden pattern: {schema_name}")
