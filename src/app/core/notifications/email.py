"""Email client using Resend API."""

import html
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

import resend

from src.app.core.config import get_settings
from src.app.core.logging import get_logger

logger = get_logger(__name__)

# Thread pool for email sending with timeout support
_email_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="email_sender")

# Shared email styles
_BODY_STYLE = (
    "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; "
    "line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;"
)
_BUTTON_STYLE = (
    "background-color: #2563eb; color: white; padding: 12px 24px; "
    "text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 500;"
)
_LINK_STYLE = "color: #2563eb; word-break: break-all;"
_MUTED_STYLE = "color: #666; font-size: 14px;"


def send_verification_email(to: str, token: str, user_name: str) -> bool:
    """Send email verification link to user.

    Args:
        to: Recipient email address
        token: Verification token (plaintext, will be included in URL)
        user_name: User's name for personalization

    Returns:
        True if email was sent (or logged in dev mode), False on error
    """
    settings = get_settings()
    verification_url = f"{settings.app_url}/verify-email?token={token}"

    if not settings.resend_api_key:
        # Dev mode: log email content instead of sending
        logger.warning(
            "RESEND_API_KEY not set - email not sent",
            to=to,
            email_type="verification",
        )
        return True

    resend.api_key = settings.resend_api_key

    def _send() -> None:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [to],
                "subject": "Verify your email address",
                "html": _get_verification_email_html(user_name, verification_url),
            }
        )

    try:
        # Use thread pool with timeout to prevent hanging on slow API responses
        future = _email_executor.submit(_send)
        future.result(timeout=settings.email_send_timeout_seconds)
        logger.info("Verification email sent", to=to)
        return True
    except FuturesTimeoutError:
        logger.error("Email send timed out", to=to, timeout=settings.email_send_timeout_seconds)
        return False
    except Exception as e:
        logger.error("Failed to send verification email", to=to, error=str(e))
        return False


def send_welcome_email(to: str, user_name: str) -> bool:
    """Send welcome email after successful verification.

    Args:
        to: Recipient email address
        user_name: User's name for personalization

    Returns:
        True if email was sent, False on error
    """
    settings = get_settings()

    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set - welcome email not sent", to=to)
        return True

    resend.api_key = settings.resend_api_key

    def _send() -> None:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [to],
                "subject": f"Welcome to {settings.app_name}!",
                "html": _get_welcome_email_html(user_name, settings.app_name),
            }
        )

    try:
        future = _email_executor.submit(_send)
        future.result(timeout=settings.email_send_timeout_seconds)
        logger.info("Welcome email sent", to=to)
        return True
    except FuturesTimeoutError:
        logger.error("Email send timed out", to=to, timeout=settings.email_send_timeout_seconds)
        return False
    except Exception as e:
        logger.error("Failed to send welcome email", to=to, error=str(e))
        return False


def _get_verification_email_html(user_name: str, verification_url: str) -> str:
    """Generate HTML content for verification email."""
    safe_user_name = html.escape(user_name)
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="{_BODY_STYLE}">
    <h1 style="color: #2563eb; margin-bottom: 24px;">Verify your email</h1>
    <p>Hi {safe_user_name},</p>
    <p>Thanks for signing up! Please verify your email address by clicking below:</p>
    <p style="margin: 32px 0;">
        <a href="{verification_url}" style="{_BUTTON_STYLE}">Verify Email</a>
    </p>
    <p style="{_MUTED_STYLE}">
        Or copy and paste this link into your browser:<br>
        <a href="{verification_url}" style="{_LINK_STYLE}">{verification_url}</a>
    </p>
    <p style="{_MUTED_STYLE} margin-top: 32px;">
        This link will expire in 24 hours. If you didn't create an account,
        you can safely ignore this email.
    </p>
</body>
</html>"""


def _get_welcome_email_html(user_name: str, app_name: str) -> str:
    """Generate HTML content for welcome email."""
    safe_user_name = html.escape(user_name)
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="{_BODY_STYLE}">
    <h1 style="color: #2563eb; margin-bottom: 24px;">Welcome to {app_name}!</h1>
    <p>Hi {safe_user_name},</p>
    <p>Your email has been verified and your account is now active.</p>
    <p>You're all set to start using {app_name}. If you have any questions,
    feel free to reach out to our support team.</p>
    <p style="margin-top: 32px;">
        Best regards,<br>
        The {app_name} Team
    </p>
</body>
</html>"""


def send_invite_email(to: str, token: str, tenant_name: str, inviter_name: str) -> bool:
    """Send tenant invite email.

    Args:
        to: Recipient email address
        token: Invite token (plaintext, included in URL)
        tenant_name: Name of the tenant being invited to
        inviter_name: Name of the person who sent the invite

    Returns:
        True if email was sent, False on error
    """
    settings = get_settings()
    invite_url = f"{settings.app_url}/accept-invite?token={token}"

    if not settings.resend_api_key:
        logger.warning(
            "RESEND_API_KEY not set - invite email not sent",
            to=to,
            email_type="invite",
        )
        return True

    resend.api_key = settings.resend_api_key

    def _send() -> None:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [to],
                "subject": f"You've been invited to join {tenant_name}",
                "html": _get_invite_email_html(tenant_name, inviter_name, invite_url),
            }
        )

    try:
        future = _email_executor.submit(_send)
        future.result(timeout=settings.email_send_timeout_seconds)
        logger.info("Invite email sent", to=to)
        return True
    except FuturesTimeoutError:
        logger.error("Email send timed out", to=to, timeout=settings.email_send_timeout_seconds)
        return False
    except Exception as e:
        logger.error("Failed to send invite email", to=to, error=str(e))
        return False


def _get_invite_email_html(tenant_name: str, inviter_name: str, invite_url: str) -> str:
    """Generate HTML content for invite email."""
    safe_tenant_name = html.escape(tenant_name)
    safe_inviter_name = html.escape(inviter_name)
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="{_BODY_STYLE}">
    <h1 style="color: #2563eb; margin-bottom: 24px;">You're invited!</h1>
    <p>{safe_inviter_name} has invited you to join <strong>{safe_tenant_name}</strong>.</p>
    <p>Click the button below to accept the invitation:</p>
    <p style="margin: 32px 0;">
        <a href="{invite_url}" style="{_BUTTON_STYLE}">Accept Invitation</a>
    </p>
    <p style="{_MUTED_STYLE}">
        Or copy and paste this link into your browser:<br>
        <a href="{invite_url}" style="{_LINK_STYLE}">{invite_url}</a>
    </p>
    <p style="{_MUTED_STYLE} margin-top: 32px;">
        This invitation will expire in 7 days. If you didn't expect this invitation,
        you can safely ignore this email.
    </p>
</body>
</html>"""
