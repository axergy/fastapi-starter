"""Pagination schemas for cursor-based pagination."""

import base64
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response with cursor-based pagination.

    Cursor-based pagination is more efficient than offset-based pagination
    for large datasets and provides consistent results even when data changes.

    The cursor is an opaque string that encodes the position in the result set.
    Clients should treat it as an opaque token and pass it back to get the next page.
    """

    items: list[T]
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for fetching the next page. None if no more pages.",
    )
    has_more: bool = Field(
        default=False,
        description="Whether there are more items after this page.",
    )


def encode_cursor(value: str) -> str:
    """Encode a cursor value to base64.

    Args:
        value: The value to encode (typically a timestamp or ID)

    Returns:
        Base64-encoded cursor string
    """
    return base64.urlsafe_b64encode(value.encode()).decode()


def decode_cursor(cursor: str) -> str:
    """Decode a base64 cursor value.

    Args:
        cursor: The base64-encoded cursor string

    Returns:
        Decoded cursor value

    Raises:
        ValueError: If cursor is invalid
    """
    try:
        return base64.urlsafe_b64decode(cursor.encode()).decode()
    except Exception as e:
        raise ValueError("Invalid cursor") from e
