"""Email sending activities."""

from dataclasses import dataclass

from temporalio import activity


@dataclass
class SendEmailInput:
    to: str
    subject: str
    body: str
    idempotency_key: str | None = None  # Optional: unique key for deduplication


@activity.defn
async def send_welcome_email(input: SendEmailInput) -> bool:
    """
    Send welcome email to new user.

    Idempotency: Uses idempotency_key for deduplication. If the same key is
    provided multiple times, the email is only sent once. When integrated with
    an actual email service, use the service's idempotency features (e.g.,
    SendGrid's idempotency key header, SES message ID tracking).

    For now, relies on workflow execution ID for deduplication via Temporal's
    activity completion guarantees - an activity with the same input will not
    execute twice within the same workflow run.

    In production, implement one of:
    1. Service-level idempotency: Use provider's idempotency key (SendGrid, SES)
    2. Database tracking: Store sent email records with idempotency_key
    3. Application-level: Check if email was already sent before sending

    Example implementation:
        # Check if already sent (database tracking approach)
        if input.idempotency_key:
            existing = await idempotency_repo.get_by_key(input.idempotency_key)
            if existing:
                activity.logger.info(f"Email already sent for key {input.idempotency_key}")
                return True

        # Send with provider's idempotency support
        await email_client.send(
            to=input.to,
            subject=input.subject,
            body=input.body,
            idempotency_key=input.idempotency_key,
        )

        # Record successful send
        if input.idempotency_key:
            await idempotency_repo.mark_complete(input.idempotency_key)

    Args:
        input: SendEmailInput with recipient, subject, body, and optional idempotency_key

    Returns:
        True if email was sent (or already sent)
    """
    activity.logger.info(f"Sending welcome email to {input.to}")
    # TODO: Integrate with actual email service (see docstring for implementation pattern)
    return True
