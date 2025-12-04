"""Tests for security-critical functionality."""
import pytest
from pydantic import ValidationError

from src.app.core.validators import validate_schema_name
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
    """Tests for password strength validation."""

    def test_valid_password(self):
        """Strong passwords should be accepted."""
        request = RegisterRequest(
            email="test@example.com",
            password="SecurePass123",
            full_name="Test User",
            tenant_name="Test Tenant",
            tenant_slug="test_tenant",
        )
        assert request.password == "SecurePass123"

    def test_password_missing_uppercase(self):
        """Passwords without uppercase should be rejected."""
        with pytest.raises(ValidationError, match="uppercase"):
            RegisterRequest(
                email="test@example.com",
                password="securepass123",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug="test_tenant",
            )

    def test_password_missing_lowercase(self):
        """Passwords without lowercase should be rejected."""
        with pytest.raises(ValidationError, match="lowercase"):
            RegisterRequest(
                email="test@example.com",
                password="SECUREPASS123",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug="test_tenant",
            )

    def test_password_missing_digit(self):
        """Passwords without digits should be rejected."""
        with pytest.raises(ValidationError, match="digit"):
            RegisterRequest(
                email="test@example.com",
                password="SecurePassword",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug="test_tenant",
            )

    def test_common_password_rejected(self):
        """Common passwords should be rejected."""
        with pytest.raises(ValidationError, match="too common"):
            RegisterRequest(
                email="test@example.com",
                password="Password1",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug="test_tenant",
            )
