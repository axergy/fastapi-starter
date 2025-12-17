"""Shared workflow step utilities."""

from datetime import timedelta

from temporalio.common import RetryPolicy

DEFAULT_RETRY = RetryPolicy(
    maximum_attempts=5,
    initial_interval=timedelta(seconds=1),
)


def short_activity_opts() -> dict[str, object]:
    """Options for quick activities (DB reads, status updates)."""
    return {
        "start_to_close_timeout": timedelta(seconds=30),
        "retry_policy": RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=1),
        ),
    }


def medium_activity_opts() -> dict[str, object]:
    """Options for medium activities (external API calls)."""
    return {
        "start_to_close_timeout": timedelta(seconds=60),
        "retry_policy": DEFAULT_RETRY,
    }


def long_activity_opts() -> dict[str, object]:
    """Options for long activities (migrations, schema operations)."""
    return {
        "start_to_close_timeout": timedelta(minutes=10),
        "retry_policy": RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=2),
        ),
    }
