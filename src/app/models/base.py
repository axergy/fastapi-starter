from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current UTC time as naive datetime (for PostgreSQL TIMESTAMP).

    Database columns use TIMESTAMP WITHOUT TIME ZONE, so we strip tzinfo.
    All times are stored in UTC by convention.
    """
    return datetime.now(UTC).replace(tzinfo=None)
