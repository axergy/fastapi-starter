"""Notification utilities - email.

Re-exports all notification-related functions for backward compatibility.
"""

from src.app.core.notifications.email import (
    send_invite_email,
    send_verification_email,
    send_welcome_email,
)

__all__ = [
    "send_invite_email",
    "send_verification_email",
    "send_welcome_email",
]
