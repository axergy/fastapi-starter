from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time as naive datetime (for PostgreSQL TIMESTAMP)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
