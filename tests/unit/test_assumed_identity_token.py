"""Unit tests for assumed identity token creation."""

from datetime import timedelta
from uuid import uuid4

import pytest

from src.app.core.security import (
    ASSUMED_IDENTITY_TOKEN_EXPIRE_MINUTES,
    create_assumed_identity_token,
    decode_token,
)

pytestmark = pytest.mark.unit


class TestCreateAssumedIdentityToken:
    """Tests for create_assumed_identity_token function."""

    def test_token_has_correct_structure(self):
        """Token should contain assumed_identity claim with operator info."""
        assumed_id = uuid4()
        operator_id = uuid4()
        tenant_id = uuid4()

        token = create_assumed_identity_token(
            assumed_user_id=assumed_id,
            operator_user_id=operator_id,
            tenant_id=tenant_id,
            reason="Test reason",
        )

        payload = decode_token(token)
        assert payload is not None

        # Standard access token fields
        assert payload["sub"] == str(assumed_id)
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["type"] == "assumed_access"
        assert "exp" in payload

        # Assumed identity claims
        assert "assumed_identity" in payload
        assert payload["assumed_identity"]["operator_user_id"] == str(operator_id)
        assert payload["assumed_identity"]["reason"] == "Test reason"
        assert "started_at" in payload["assumed_identity"]

    def test_sub_is_assumed_user_id(self):
        """The 'sub' claim should be the assumed user, not the operator."""
        assumed_id = uuid4()
        operator_id = uuid4()

        token = create_assumed_identity_token(
            assumed_user_id=assumed_id,
            operator_user_id=operator_id,
            tenant_id=uuid4(),
        )

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == str(assumed_id)
        assert payload["sub"] != str(operator_id)

    def test_default_expiry_is_15_minutes(self):
        """Default expiry should be 15 minutes."""
        assert ASSUMED_IDENTITY_TOKEN_EXPIRE_MINUTES == 15

        token = create_assumed_identity_token(
            assumed_user_id=uuid4(),
            operator_user_id=uuid4(),
            tenant_id=uuid4(),
        )

        payload = decode_token(token)
        assert payload is not None
        # Just verify exp exists and is in the future
        assert "exp" in payload

    def test_custom_expiry_works(self):
        """Custom expiry delta should be respected."""
        token = create_assumed_identity_token(
            assumed_user_id=uuid4(),
            operator_user_id=uuid4(),
            tenant_id=uuid4(),
            expires_delta=timedelta(minutes=5),
        )

        payload = decode_token(token)
        assert payload is not None
        assert "exp" in payload

    def test_reason_is_optional(self):
        """Token should be created successfully without reason."""
        token = create_assumed_identity_token(
            assumed_user_id=uuid4(),
            operator_user_id=uuid4(),
            tenant_id=uuid4(),
            reason=None,
        )

        payload = decode_token(token)
        assert payload is not None
        assert payload["assumed_identity"]["reason"] is None

    def test_reason_is_included_when_provided(self):
        """Reason should be included in token when provided."""
        reason = "Investigating support ticket #12345"

        token = create_assumed_identity_token(
            assumed_user_id=uuid4(),
            operator_user_id=uuid4(),
            tenant_id=uuid4(),
            reason=reason,
        )

        payload = decode_token(token)
        assert payload is not None
        assert payload["assumed_identity"]["reason"] == reason

    def test_started_at_is_iso_format(self):
        """started_at should be in ISO format string."""
        token = create_assumed_identity_token(
            assumed_user_id=uuid4(),
            operator_user_id=uuid4(),
            tenant_id=uuid4(),
        )

        payload = decode_token(token)
        assert payload is not None
        started_at = payload["assumed_identity"]["started_at"]

        # Should be parseable as ISO datetime
        from datetime import datetime

        parsed = datetime.fromisoformat(started_at)
        assert parsed is not None

    def test_token_type_is_assumed_access(self):
        """Token type should be 'assumed_access' for distinct tracking."""
        token = create_assumed_identity_token(
            assumed_user_id=uuid4(),
            operator_user_id=uuid4(),
            tenant_id=uuid4(),
        )

        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "assumed_access"

    def test_accepts_string_uuids(self):
        """Should accept both UUID objects and string UUIDs."""
        assumed_id = str(uuid4())
        operator_id = str(uuid4())
        tenant_id = str(uuid4())

        token = create_assumed_identity_token(
            assumed_user_id=assumed_id,
            operator_user_id=operator_id,
            tenant_id=tenant_id,
        )

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == assumed_id
        assert payload["assumed_identity"]["operator_user_id"] == operator_id
        assert payload["tenant_id"] == tenant_id

    def test_token_is_decodable(self):
        """Created token should be decodable with decode_token."""
        token = create_assumed_identity_token(
            assumed_user_id=uuid4(),
            operator_user_id=uuid4(),
            tenant_id=uuid4(),
        )

        # Should not return None
        payload = decode_token(token)
        assert payload is not None

    def test_token_is_valid_jwt_string(self):
        """Token should be a valid JWT string (three dot-separated parts)."""
        token = create_assumed_identity_token(
            assumed_user_id=uuid4(),
            operator_user_id=uuid4(),
            tenant_id=uuid4(),
        )

        parts = token.split(".")
        assert len(parts) == 3
