from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current UTC time as naive datetime (for PostgreSQL TIMESTAMP)."""
    return datetime.now(UTC).replace(tzinfo=None)
