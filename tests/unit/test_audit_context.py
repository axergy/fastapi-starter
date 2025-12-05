"""Unit tests for audit context module."""

import pytest

from src.app.core.audit_context import (
    AuditContext,
    clear_audit_context,
    get_audit_context,
    get_client_ip,
    set_audit_context,
)


class TestAuditContext:
    """Tests for AuditContext dataclass."""

    def test_audit_context_is_immutable(self):
        """AuditContext should be frozen (immutable)."""
        from dataclasses import FrozenInstanceError

        ctx = AuditContext(ip_address="1.2.3.4")
        with pytest.raises(FrozenInstanceError):
            ctx.ip_address = "5.6.7.8"  # type: ignore[misc]


class TestSetAndGetAuditContext:
    """Tests for set_audit_context and get_audit_context functions."""

    def test_set_and_get_context(self):
        """Should be able to set and retrieve audit context."""
        set_audit_context(
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            request_id="abc-123",
        )

        ctx = get_audit_context()
        assert ctx is not None
        assert ctx.ip_address == "192.168.1.1"
        assert ctx.user_agent == "Mozilla/5.0"
        assert ctx.request_id == "abc-123"

    def test_get_context_returns_none_when_not_set(self):
        """get_audit_context should return None when not set."""
        clear_audit_context()
        assert get_audit_context() is None

    def test_clear_context(self):
        """clear_audit_context should reset context to None."""
        set_audit_context(ip_address="1.2.3.4")
        clear_audit_context()
        assert get_audit_context() is None

    def test_user_agent_truncation(self):
        """User agent over 500 chars should be truncated."""
        long_user_agent = "x" * 600
        set_audit_context(user_agent=long_user_agent)

        ctx = get_audit_context()
        assert ctx is not None
        assert len(ctx.user_agent) == 500

    def test_user_agent_not_truncated_when_short(self):
        """User agent under 500 chars should not be truncated."""
        user_agent = "Mozilla/5.0"
        set_audit_context(user_agent=user_agent)

        ctx = get_audit_context()
        assert ctx is not None
        assert ctx.user_agent == user_agent


class TestGetClientIp:
    """Tests for get_client_ip function."""

    def test_returns_first_ip_from_forwarded_for(self):
        """Should return first IP from X-Forwarded-For header."""
        result = get_client_ip("1.2.3.4, 5.6.7.8, 9.10.11.12", "192.168.1.1")
        assert result == "1.2.3.4"

    def test_strips_whitespace_from_forwarded_for(self):
        """Should strip whitespace from X-Forwarded-For IPs."""
        result = get_client_ip("  1.2.3.4  , 5.6.7.8", "192.168.1.1")
        assert result == "1.2.3.4"

    def test_returns_client_host_when_no_forwarded_for(self):
        """Should return client host when X-Forwarded-For is None."""
        result = get_client_ip(None, "192.168.1.1")
        assert result == "192.168.1.1"

    def test_returns_client_host_when_forwarded_for_empty(self):
        """Should return client host when X-Forwarded-For is empty string."""
        result = get_client_ip("", "192.168.1.1")
        # Empty string is falsy, so returns client_host
        assert result == "192.168.1.1"

    def test_returns_none_when_both_are_none(self):
        """Should return None when both forwarded_for and client_host are None."""
        result = get_client_ip(None, None)
        assert result is None

    def test_handles_ipv6(self):
        """Should handle IPv6 addresses."""
        result = get_client_ip("2001:db8::1, 2001:db8::2", None)
        assert result == "2001:db8::1"
