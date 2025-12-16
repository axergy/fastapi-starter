"""Tests for structured logging context."""

from uuid import uuid7

import pytest
import structlog
from structlog.testing import CapturingLogger

from src.app.core.logging import (
    bind_request_context,
    bind_user_context,
    clear_request_context,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def capturing_logger():
    """Create a capturing logger for tests."""
    # Create a capturing logger instance
    cap_logger = CapturingLogger()

    # Save original configuration to restore later
    old_config = structlog.get_config()

    # Configure structlog to use the capturing logger
    # Use *args, **kwargs to accept any arguments passed by structlog
    structlog.configure(
        processors=[structlog.contextvars.merge_contextvars],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=lambda *args, **kwargs: cap_logger,
        cache_logger_on_first_use=False,
    )

    # Clear any existing context
    clear_request_context()
    yield cap_logger
    # Clean up
    clear_request_context()
    # Restore original configuration
    structlog.configure(**old_config)


def test_bind_request_context(capturing_logger):
    """Test binding request_id to log context."""
    request_id = "test-request-123"

    bind_request_context(request_id)
    logger = structlog.get_logger()
    logger.info("test message")

    # Get the captured log entry
    entries = capturing_logger.calls
    assert len(entries) == 1
    assert entries[0].kwargs["request_id"] == request_id


def test_bind_request_context_with_none(capturing_logger):
    """Test that None request_id is not bound."""
    bind_request_context(None)
    logger = structlog.get_logger()
    logger.info("test message")

    entries = capturing_logger.calls
    assert len(entries) == 1
    assert "request_id" not in entries[0].kwargs


def test_bind_user_context(capturing_logger):
    """Test binding user and tenant context to logs.

    Note: Email is only logged when log_user_emails=True (GDPR compliance).
    """
    user_id = uuid7()
    tenant_id = uuid7()
    email = "test@example.com"

    bind_user_context(user_id, tenant_id, email)
    logger = structlog.get_logger()
    logger.info("test message")

    entries = capturing_logger.calls
    assert len(entries) == 1
    assert entries[0].kwargs["user_id"] == str(user_id)
    assert entries[0].kwargs["tenant_id"] == str(tenant_id)
    # Email is NOT logged by default (GDPR compliance - log_user_emails=False)
    assert "user_email" not in entries[0].kwargs


def test_bind_user_context_with_email_logging_enabled(capturing_logger, monkeypatch):
    """Test binding user context with email logging enabled."""
    from unittest.mock import MagicMock

    from src.app.core import config

    user_id = uuid7()
    tenant_id = uuid7()
    email = "test@example.com"

    # Mock settings to enable email logging
    mock_settings = MagicMock()
    mock_settings.log_user_emails = True
    monkeypatch.setattr(config, "get_settings", lambda: mock_settings)

    bind_user_context(user_id, tenant_id, email)
    logger = structlog.get_logger()
    logger.info("test message")

    entries = capturing_logger.calls
    assert len(entries) == 1
    assert entries[0].kwargs["user_id"] == str(user_id)
    assert entries[0].kwargs["tenant_id"] == str(tenant_id)
    assert entries[0].kwargs["user_email"] == email


def test_bind_user_context_without_email(capturing_logger):
    """Test binding user context without email."""
    user_id = uuid7()
    tenant_id = uuid7()

    bind_user_context(user_id, tenant_id)
    logger = structlog.get_logger()
    logger.info("test message")

    entries = capturing_logger.calls
    assert len(entries) == 1
    assert entries[0].kwargs["user_id"] == str(user_id)
    assert entries[0].kwargs["tenant_id"] == str(tenant_id)
    assert "user_email" not in entries[0].kwargs


def test_clear_request_context(capturing_logger):
    """Test clearing request context."""
    request_id = "test-request-123"
    user_id = uuid7()
    tenant_id = uuid7()

    # Bind context
    bind_request_context(request_id)
    bind_user_context(user_id, tenant_id)

    # Clear context
    clear_request_context()

    # Log should not have any context
    logger = structlog.get_logger()
    logger.info("test message")
    entries = capturing_logger.calls
    assert len(entries) == 1
    assert "request_id" not in entries[0].kwargs
    assert "user_id" not in entries[0].kwargs
    assert "tenant_id" not in entries[0].kwargs


def test_context_accumulation(capturing_logger):
    """Test that context accumulates across multiple bind calls."""
    request_id = "test-request-123"
    user_id = uuid7()
    tenant_id = uuid7()

    # Bind request context first
    bind_request_context(request_id)

    # Then bind user context
    bind_user_context(user_id, tenant_id)

    # Both should be present
    logger = structlog.get_logger()
    logger.info("test message")
    entries = capturing_logger.calls
    assert len(entries) == 1
    assert entries[0].kwargs["request_id"] == request_id
    assert entries[0].kwargs["user_id"] == str(user_id)
    assert entries[0].kwargs["tenant_id"] == str(tenant_id)
