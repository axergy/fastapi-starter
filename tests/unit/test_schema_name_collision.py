"""Tests for tenant schema name collision prevention.

These tests verify that the system properly prevents schema name collisions
that could occur when two tenant slugs differ only after the 56th character,
which would result in identical schema names after PostgreSQL's 63-char truncation.
"""

import pytest
from pydantic import ValidationError

from src.app.core.security.validators import MAX_SCHEMA_LENGTH, validate_schema_name
from src.app.models.public.tenant import MAX_SLUG_LENGTH, Tenant
from src.app.schemas.auth import RegisterRequest

pytestmark = pytest.mark.unit


class TestSlugLengthValidation:
    """Test slug length validation at schema level."""

    def test_valid_short_slug(self):
        """Short slugs should be accepted."""
        request = RegisterRequest(
            email="test@example.com",
            password="SecureP@ssw0rd!123xyz",
            full_name="Test User",
            tenant_name="Test Tenant",
            tenant_slug="acme",
        )
        assert request.tenant_slug == "acme"

    def test_valid_max_length_slug(self):
        """Slug at exactly max length should be accepted."""
        slug = "a" * MAX_SLUG_LENGTH  # 56 characters
        request = RegisterRequest(
            email="test@example.com",
            password="SecureP@ssw0rd!123xyz",
            full_name="Test User",
            tenant_name="Test Tenant",
            tenant_slug=slug,
        )
        assert len(request.tenant_slug) == MAX_SLUG_LENGTH

    def test_slug_too_long_rejected(self):
        """Slug exceeding max length should be rejected."""
        slug = "a" * (MAX_SLUG_LENGTH + 1)  # 57 characters
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                email="test@example.com",
                password="SecureP@ssw0rd!123xyz",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug=slug,
            )
        assert "String should have at most 56 characters" in str(exc_info.value)

    def test_slug_format_validation(self):
        """Slug must contain only valid characters."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                email="test@example.com",
                password="SecureP@ssw0rd!123xyz",
                full_name="Test User",
                tenant_name="Test Tenant",
                tenant_slug="Invalid-Slug!",
            )
        assert "lowercase letters, numbers, and underscores" in str(exc_info.value)


class TestSchemaNameValidation:
    """Test schema name validation in validators module."""

    def test_valid_schema_name(self):
        """Valid schema names should pass validation."""
        validate_schema_name("tenant_acme")
        validate_schema_name("tenant_acme_corp")
        validate_schema_name("tenant_a1b2c3")

    def test_schema_name_length_limit(self):
        """Schema name at exactly 63 chars should pass."""
        # 63 - 7 (tenant_) = 56 char slug
        slug = "a" * 56
        schema_name = f"tenant_{slug}"
        assert len(schema_name) == MAX_SCHEMA_LENGTH
        validate_schema_name(schema_name)

    def test_schema_name_too_long(self):
        """Schema name exceeding 63 chars should fail."""
        slug = "a" * 57
        schema_name = f"tenant_{slug}"
        assert len(schema_name) == 64
        with pytest.raises(ValueError) as exc_info:
            validate_schema_name(schema_name)
        assert "exceeds PostgreSQL limit" in str(exc_info.value)

    def test_schema_name_missing_prefix(self):
        """Schema name without tenant_ prefix should fail."""
        with pytest.raises(ValueError) as exc_info:
            validate_schema_name("acme")
        assert "Invalid schema name format" in str(exc_info.value)

    def test_schema_name_invalid_characters(self):
        """Schema name with invalid chars should fail."""
        with pytest.raises(ValueError) as exc_info:
            validate_schema_name("tenant_ACME")  # uppercase
        assert "Invalid schema name format" in str(exc_info.value)


class TestTenantModelSchemaName:
    """Test Tenant model schema_name property validation."""

    def test_valid_tenant_schema_name(self):
        """Valid tenant slug should produce valid schema name."""
        tenant = Tenant(
            name="Acme Corp",
            slug="acme",
        )
        assert tenant.schema_name == "tenant_acme"

    def test_tenant_schema_name_max_length(self):
        """Tenant with max-length slug should produce valid schema name."""
        slug = "a" * MAX_SLUG_LENGTH
        tenant = Tenant(
            name="Test Tenant",
            slug=slug,
        )
        schema_name = tenant.schema_name
        assert len(schema_name) == MAX_SCHEMA_LENGTH

    def test_tenant_schema_name_too_long_raises(self):
        """Tenant with over-long slug should raise on schema_name access."""
        # This tests defense-in-depth: even if validation is bypassed elsewhere,
        # the schema_name property will catch it
        slug = "a" * 57
        tenant = Tenant(
            name="Test Tenant",
            slug=slug,
        )
        with pytest.raises(ValueError) as exc_info:
            _ = tenant.schema_name
        assert "exceeds PostgreSQL limit" in str(exc_info.value)


class TestCollisionScenario:
    """Test the specific collision attack scenario from the issue."""

    def test_collision_attack_prevented(self):
        """Two slugs differing only after char 56 cannot both be registered.

        Without length validation, these slugs would resolve to the same schema:
        - tenant_aaaaa...victim (60 chars) -> tenant_aaaaa... (truncated to 63)
        - tenant_aaaaa...attacker (62 chars) -> tenant_aaaaa... (same truncation)

        With proper validation, the second slug would be rejected before truncation.
        """
        # Base slug that fills up to the limit
        base_slug = "a" * 50

        # "Victim" slug - just over the limit
        victim_slug = base_slug + "_victim"  # 57 chars - INVALID
        assert len(victim_slug) == 57
        assert len(victim_slug) > MAX_SLUG_LENGTH

        # "Attacker" slug - also over the limit
        attacker_slug = base_slug + "_attacker"  # 59 chars - INVALID
        assert len(attacker_slug) == 59
        assert len(attacker_slug) > MAX_SLUG_LENGTH

        # Both should be rejected at registration
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="victim@example.com",
                password="SecureP@ssw0rd!123xyz",
                full_name="Victim User",
                tenant_name="Victim Tenant",
                tenant_slug=victim_slug,
            )

        with pytest.raises(ValidationError):
            RegisterRequest(
                email="attacker@example.com",
                password="SecureP@ssw0rd!123xyz",
                full_name="Attacker User",
                tenant_name="Attacker Tenant",
                tenant_slug=attacker_slug,
            )

    def test_valid_distinct_slugs_remain_distinct(self):
        """Two valid slugs should produce distinct schema names."""
        slug1 = "acme_corp"
        slug2 = "acme_inc"

        tenant1 = Tenant(name="Acme Corp", slug=slug1)
        tenant2 = Tenant(name="Acme Inc", slug=slug2)

        # Schema names should be distinct
        assert tenant1.schema_name != tenant2.schema_name
        assert tenant1.schema_name == "tenant_acme_corp"
        assert tenant2.schema_name == "tenant_acme_inc"


class TestConstants:
    """Test that constants are correctly defined."""

    def test_max_schema_length(self):
        """PostgreSQL identifier limit is 63 characters."""
        assert MAX_SCHEMA_LENGTH == 63

    def test_max_slug_length(self):
        """Max slug should account for 'tenant_' prefix."""
        assert MAX_SLUG_LENGTH == 56
        assert MAX_SCHEMA_LENGTH - len("tenant_") == MAX_SLUG_LENGTH

    def test_slug_plus_prefix_equals_max_schema(self):
        """Slug at max length + prefix should equal max schema length."""
        slug = "a" * MAX_SLUG_LENGTH
        schema_name = f"tenant_{slug}"
        assert len(schema_name) == MAX_SCHEMA_LENGTH
