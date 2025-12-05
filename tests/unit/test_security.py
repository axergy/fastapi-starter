"""Tests for security-critical functionality."""

import pytest
from pydantic import ValidationError

from src.app.core.security import validate_schema_name
from src.app.schemas.auth import RegisterRequest

pytestmark = pytest.mark.unit


class TestSchemaNameValidation:
    """Tests for schema name SQL injection prevention."""

    def test_valid_schema_names(self):
        """Valid tenant schema names should pass validation."""
        validate_schema_name("tenant_acme")
        validate_schema_name("tenant_a")
        validate_schema_name("tenant_abc123")
        validate_schema_name("tenant_acme_corp")
        validate_schema_name("tenant_acme_corp_2024")
        # Max length with tenant_ prefix (63 chars total)
        validate_schema_name("tenant_" + "a" * 56)

    def test_missing_tenant_prefix(self):
        """Schema names without tenant_ prefix should be rejected."""
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("acme")
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("myschema")
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant123")  # Missing underscore after tenant

    def test_invalid_tenant_prefix_format(self):
        """Schema names with tenant_ prefix but invalid format should be rejected."""
        # Starts with number after prefix
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_123")
        # Starts with underscore after prefix
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant__acme")

    def test_consecutive_underscores(self):
        """Consecutive underscores should be rejected."""
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_acme__corp")
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_a__b")

    def test_trailing_underscore(self):
        """Trailing underscores should be rejected."""
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_acme_")

    def test_invalid_characters(self):
        """Special characters and uppercase should be rejected."""
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_Acme")  # Uppercase
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_acme-corp")  # Hyphen
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_acme.corp")  # Period
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_acme corp")  # Space

    def test_exceeds_max_length(self):
        """Schema names over 63 characters should be rejected."""
        # 64 characters total
        long_name = "tenant_" + "a" * 57
        with pytest.raises(ValueError, match="exceeds PostgreSQL limit"):
            validate_schema_name(long_name)

    def test_sql_injection_semicolon(self):
        """SQL injection with semicolon should be rejected."""
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_acme; DROP TABLE users;--")

    def test_sql_injection_comment(self):
        """SQL injection with comments should be rejected."""
        # The regex catches this before the forbidden pattern check
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_acme--comment")

    def test_sql_injection_block_comment(self):
        """SQL injection with block comments should be rejected."""
        # The regex catches this before the forbidden pattern check
        with pytest.raises(ValueError, match="Invalid schema name format"):
            validate_schema_name("tenant_acme/*comment*/")

    def test_forbidden_pg_prefix(self):
        """pg_ prefix should be rejected (even within tenant_ schema)."""
        with pytest.raises(ValueError, match="forbidden pattern"):
            validate_schema_name("tenant_pg_catalog")

    def test_forbidden_public(self):
        """public keyword should be rejected."""
        with pytest.raises(ValueError, match="forbidden pattern"):
            validate_schema_name("tenant_public")

    def test_forbidden_information_schema(self):
        """information_schema keyword should be rejected."""
        with pytest.raises(ValueError, match="forbidden pattern"):
            validate_schema_name("tenant_information_schema")


class TestPasswordValidation:
    """Tests for password strength validation using zxcvbn."""

    def test_strong_password_accepted(self):
        """Strong passwords with high entropy should be accepted."""
        # zxcvbn scores this as 4 (very strong)
        request = RegisterRequest(
            email="test@example.com",
            password="correct-horse-battery-staple",
            full_name="Test User",
            tenant_name="Test Tenant",
            tenant_slug="test_tenant",
        )
        assert request.password == "correct-horse-battery-staple"

    def test_random_strong_password(self):
        """Random-looking strong passwords should be accepted."""
        request = RegisterRequest(
            email="test@example.com",
            password="Xk9$mP2vL#nQ8wR",
            full_name="Test User",
            tenant_name="Test Tenant",
            tenant_slug="test_tenant",
        )
        assert len(request.password) > 8

    def test_weak_password_rejected(self):
        """Weak passwords should be rejected by zxcvbn."""
        with pytest.raises(ValidationError, match="[Ww]eak password"):
            RegisterRequest(
                email="test@example.com",
                password="password123",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug="test_tenant",
            )

    def test_common_password_rejected(self):
        """Common passwords should be rejected."""
        with pytest.raises(ValidationError, match="[Ww]eak password"):
            RegisterRequest(
                email="test@example.com",
                password="qwerty12345",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug="test_tenant",
            )

    def test_short_simple_password_rejected(self):
        """Short simple passwords should be rejected."""
        with pytest.raises(ValidationError, match="[Ww]eak password"):
            RegisterRequest(
                email="test@example.com",
                password="abcd1234",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug="test_tenant",
            )

    def test_repeated_characters_rejected(self):
        """Passwords with repeated patterns should be rejected."""
        with pytest.raises(ValidationError, match="[Ww]eak password"):
            RegisterRequest(
                email="test@example.com",
                password="aaaaaaaa",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug="test_tenant",
            )

    def test_keyboard_pattern_rejected(self):
        """Keyboard patterns should be rejected."""
        with pytest.raises(ValidationError, match="[Ww]eak password"):
            RegisterRequest(
                email="test@example.com",
                password="qwertyuiop",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug="test_tenant",
            )
