"""Tests for security-critical functionality."""

import pytest
from pydantic import ValidationError

from src.app.core.security import validate_schema_name
from src.app.schemas.auth import RegisterRequest


class TestSchemaNameValidation:
    """Tests for schema name SQL injection prevention."""

    def test_valid_schema_name(self):
        """Valid schema names should pass validation."""
        validate_schema_name("tenant_123")
        validate_schema_name("acme")
        validate_schema_name("a" * 50)  # Max length

    def test_invalid_schema_name_uppercase(self):
        """Uppercase letters should be rejected."""
        with pytest.raises(ValueError, match="Invalid schema name"):
            validate_schema_name("Tenant")

    def test_invalid_schema_name_starts_with_number(self):
        """Schema names starting with numbers should be rejected."""
        with pytest.raises(ValueError, match="Invalid schema name"):
            validate_schema_name("123tenant")

    def test_sql_injection_semicolon(self):
        """SQL injection with semicolon should be rejected."""
        with pytest.raises(ValueError, match="Invalid schema name"):
            validate_schema_name("tenant; DROP TABLE users;--")

    def test_sql_injection_comment(self):
        """SQL injection with comments should be rejected."""
        with pytest.raises(ValueError, match="Invalid schema name"):
            validate_schema_name("tenant--comment")

    def test_forbidden_pg_prefix(self):
        """pg_ prefix should be rejected."""
        with pytest.raises(ValueError, match="forbidden pattern"):
            validate_schema_name("pg_catalog")

    def test_forbidden_public(self):
        """public schema name should be rejected."""
        with pytest.raises(ValueError, match="forbidden pattern"):
            validate_schema_name("public")


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
