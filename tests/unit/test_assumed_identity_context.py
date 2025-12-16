"""Unit tests for assumed identity context module."""

from uuid import uuid4

import pytest

from src.app.api.context import (
    AssumedIdentityContext,
    clear_assumed_identity_context,
    get_assumed_identity_context,
    is_assuming_identity,
    set_assumed_identity_context,
)


class TestAssumedIdentityContext:
    """Tests for AssumedIdentityContext dataclass."""

    def test_context_is_immutable(self):
        """AssumedIdentityContext should be frozen (immutable)."""
        from dataclasses import FrozenInstanceError

        ctx = AssumedIdentityContext(
            operator_user_id=uuid4(),
            assumed_user_id=uuid4(),
            tenant_id=uuid4(),
        )
        with pytest.raises(FrozenInstanceError):
            ctx.operator_user_id = uuid4()  # type: ignore[misc]

    def test_context_default_values(self):
        """Optional fields should have None defaults."""
        ctx = AssumedIdentityContext(
            operator_user_id=uuid4(),
            assumed_user_id=uuid4(),
            tenant_id=uuid4(),
        )
        assert ctx.reason is None
        assert ctx.started_at is None


class TestSetAndGetAssumedIdentityContext:
    """Tests for set/get/clear functions."""

    def setup_method(self):
        """Clear context before each test."""
        clear_assumed_identity_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_assumed_identity_context()

    def test_set_and_get_context(self):
        """Should be able to set and retrieve assumed identity context."""
        operator_id = uuid4()
        assumed_id = uuid4()
        tenant_id = uuid4()

        set_assumed_identity_context(
            operator_user_id=operator_id,
            assumed_user_id=assumed_id,
            tenant_id=tenant_id,
            reason="Testing user issue",
        )

        ctx = get_assumed_identity_context()
        assert ctx is not None
        assert ctx.operator_user_id == operator_id
        assert ctx.assumed_user_id == assumed_id
        assert ctx.tenant_id == tenant_id
        assert ctx.reason == "Testing user issue"

    def test_get_context_returns_none_when_not_set(self):
        """get_assumed_identity_context should return None when not set."""
        assert get_assumed_identity_context() is None

    def test_clear_context(self):
        """clear_assumed_identity_context should reset context to None."""
        set_assumed_identity_context(
            operator_user_id=uuid4(),
            assumed_user_id=uuid4(),
            tenant_id=uuid4(),
        )
        clear_assumed_identity_context()
        assert get_assumed_identity_context() is None

    def test_reason_truncation(self):
        """Reason over 500 chars should be truncated."""
        long_reason = "x" * 600
        set_assumed_identity_context(
            operator_user_id=uuid4(),
            assumed_user_id=uuid4(),
            tenant_id=uuid4(),
            reason=long_reason,
        )

        ctx = get_assumed_identity_context()
        assert ctx is not None
        assert len(ctx.reason) == 500

    def test_reason_not_truncated_when_short(self):
        """Reason under 500 chars should not be truncated."""
        reason = "Testing user issue #123"
        set_assumed_identity_context(
            operator_user_id=uuid4(),
            assumed_user_id=uuid4(),
            tenant_id=uuid4(),
            reason=reason,
        )

        ctx = get_assumed_identity_context()
        assert ctx is not None
        assert ctx.reason == reason

    def test_reason_none_is_valid(self):
        """Reason can be None."""
        set_assumed_identity_context(
            operator_user_id=uuid4(),
            assumed_user_id=uuid4(),
            tenant_id=uuid4(),
            reason=None,
        )

        ctx = get_assumed_identity_context()
        assert ctx is not None
        assert ctx.reason is None


class TestIsAssumingIdentity:
    """Tests for is_assuming_identity helper function."""

    def setup_method(self):
        """Clear context before each test."""
        clear_assumed_identity_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_assumed_identity_context()

    def test_returns_false_when_not_assuming(self):
        """Should return False when no identity assumption is active."""
        assert is_assuming_identity() is False

    def test_returns_true_when_assuming(self):
        """Should return True when identity assumption is active."""
        set_assumed_identity_context(
            operator_user_id=uuid4(),
            assumed_user_id=uuid4(),
            tenant_id=uuid4(),
        )
        assert is_assuming_identity() is True

    def test_returns_false_after_clear(self):
        """Should return False after context is cleared."""
        set_assumed_identity_context(
            operator_user_id=uuid4(),
            assumed_user_id=uuid4(),
            tenant_id=uuid4(),
        )
        clear_assumed_identity_context()
        assert is_assuming_identity() is False
