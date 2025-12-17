"""
Token Cleanup Workflow.

Clean up expired tokens and invites.

Runs cleanup activities for:
1. Refresh tokens (expired or revoked)
2. Email verification tokens (expired or used)
3. Tenant invites (expired, cancelled, or accepted)

Designed to be run on a schedule (e.g., daily at 3am UTC via Temporal cron).

Idempotent: All cleanup activities use DELETE which is idempotent - safe
to run multiple times without side effects.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.app.temporal.activities import (
        cleanup_email_verification_tokens,
        cleanup_expired_invites,
        cleanup_refresh_tokens,
    )


@workflow.defn
class TokenCleanupWorkflow:
    """
    Clean up expired tokens and invites.

    Runs cleanup activities for:
    1. Refresh tokens (expired or revoked)
    2. Email verification tokens (expired or used)
    3. Tenant invites (expired, cancelled, or accepted)

    Designed to be run on a schedule (e.g., daily at 3am UTC via Temporal cron).

    Idempotent: All cleanup activities use DELETE which is idempotent - safe
    to run multiple times without side effects.
    """

    @workflow.run
    async def run(self, retention_days: int = 30) -> dict[str, int]:
        """
        Run all token cleanup activities.

        Args:
            retention_days: Number of days to retain expired/revoked/used tokens
                           (default: 30 days from config)

        Returns:
            dict with counts of deleted tokens by type:
            {
                "refresh_tokens": int,
                "email_verification_tokens": int,
                "invites": int,
                "total": int
            }
        """
        workflow.logger.info(f"Starting token cleanup (retention: {retention_days} days)")

        # Run all cleanup activities in parallel for efficiency
        # Each activity is independent and idempotent
        refresh_count_task = workflow.execute_activity(
            cleanup_refresh_tokens,
            retention_days,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
            ),
        )

        email_count_task = workflow.execute_activity(
            cleanup_email_verification_tokens,
            retention_days,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
            ),
        )

        invite_count_task = workflow.execute_activity(
            cleanup_expired_invites,
            retention_days,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
            ),
        )

        # Wait for all activities to complete
        refresh_count = await refresh_count_task
        email_count = await email_count_task
        invite_count = await invite_count_task

        total = refresh_count + email_count + invite_count

        result = {
            "refresh_tokens": refresh_count,
            "email_verification_tokens": email_count,
            "invites": invite_count,
            "total": total,
        }

        workflow.logger.info(
            f"Token cleanup complete: {result['refresh_tokens']} refresh, "
            f"{result['email_verification_tokens']} email, "
            f"{result['invites']} invites (total: {result['total']})"
        )

        return result
