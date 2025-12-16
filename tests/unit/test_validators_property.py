"""Property-based tests for validators using hypothesis."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from src.app.schemas.tenant import TenantCreate

pytestmark = pytest.mark.unit


# Strategy for valid slugs: lowercase alphanumeric + underscores, 3-56 chars
# Pattern: ^[a-z][a-z0-9]*(_[a-z0-9]+)*$
# - Starts with lowercase letter
# - Contains lowercase letters, numbers
# - Underscores only as separators (not consecutive, not trailing)
valid_slug = st.from_regex(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", fullmatch=True).filter(
    lambda s: 1 <= len(s) <= 56
)


@given(slug=valid_slug)
@settings(max_examples=100)
def test_valid_slugs_accepted(slug: str):
    """Valid slugs should pass validation."""
    tenant = TenantCreate(name="Test Company", slug=slug)
    assert tenant.slug == slug


@given(slug=st.text(min_size=1, max_size=0))
def test_empty_slugs_rejected(slug: str):
    """Empty slugs should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        TenantCreate(name="Test", slug=slug)
    # Verify it's a validation error for the slug field
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("slug",) for error in errors)


@given(slug=st.text(min_size=57, max_size=100))
def test_long_slugs_rejected(slug: str):
    """Slugs longer than 56 characters should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        TenantCreate(name="Test", slug=slug)
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("slug",) for error in errors)


@given(slug=st.from_regex(r"^[A-Z][a-z0-9_]*$", fullmatch=True).filter(lambda s: 1 <= len(s) <= 56))
def test_uppercase_start_rejected(slug: str):
    """Slugs starting with uppercase letter should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        TenantCreate(name="Test", slug=slug)
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("slug",) for error in errors)


@given(slug=st.from_regex(r"^[0-9][a-z0-9_]*$", fullmatch=True).filter(lambda s: 1 <= len(s) <= 56))
def test_digit_start_rejected(slug: str):
    """Slugs starting with a digit should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        TenantCreate(name="Test", slug=slug)
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("slug",) for error in errors)


@given(
    slug=st.from_regex(r"^[a-z][a-z0-9_]*-[a-z0-9_]*$", fullmatch=True).filter(
        lambda s: 1 <= len(s) <= 56
    )
)
def test_hyphen_rejected(slug: str):
    """Slugs containing hyphens should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        TenantCreate(name="Test", slug=slug)
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("slug",) for error in errors)


@given(
    slug=st.from_regex(r"^[a-z][a-z0-9]*__[a-z0-9_]*$", fullmatch=True).filter(
        lambda s: 1 <= len(s) <= 56
    )
)
def test_double_underscore_rejected(slug: str):
    """Slugs with consecutive underscores should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        TenantCreate(name="Test", slug=slug)
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("slug",) for error in errors)


@given(
    slug=st.from_regex(r"^[a-z][a-z0-9_]*_$", fullmatch=True).filter(lambda s: 1 <= len(s) <= 56)
)
def test_trailing_underscore_rejected(slug: str):
    """Slugs ending with underscore should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        TenantCreate(name="Test", slug=slug)
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("slug",) for error in errors)


@given(slug=st.from_regex(r"^_[a-z0-9_]*$", fullmatch=True).filter(lambda s: 1 <= len(s) <= 56))
def test_leading_underscore_rejected(slug: str):
    """Slugs starting with underscore should be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        TenantCreate(name="Test", slug=slug)
    errors = exc_info.value.errors()
    assert any(error["loc"] == ("slug",) for error in errors)


class TestSlugValidatorEdgeCases:
    """Test specific edge cases for slug validation."""

    def test_single_char_slug_accepted(self):
        """Single lowercase letter should be accepted."""
        tenant = TenantCreate(name="Test", slug="a")
        assert tenant.slug == "a"

    def test_slug_with_numbers_accepted(self):
        """Slug with numbers (after letter) should be accepted."""
        tenant = TenantCreate(name="Test", slug="test123")
        assert tenant.slug == "test123"

    def test_slug_with_single_underscore_separator_accepted(self):
        """Slug with single underscore separators should be accepted."""
        tenant = TenantCreate(name="Test", slug="test_company_name")
        assert tenant.slug == "test_company_name"

    def test_max_length_slug_accepted(self):
        """Slug with exactly 56 characters should be accepted."""
        slug = "a" * 56
        tenant = TenantCreate(name="Test", slug=slug)
        assert tenant.slug == slug

    def test_slug_with_space_rejected(self):
        """Slug with space should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TenantCreate(name="Test", slug="test slug")
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("slug",) for error in errors)

    def test_slug_with_special_chars_rejected(self):
        """Slug with special characters should be rejected."""
        special_chars = ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")", "+", "="]
        for char in special_chars:
            with pytest.raises(ValidationError) as exc_info:
                TenantCreate(name="Test", slug=f"test{char}slug")
            errors = exc_info.value.errors()
            assert any(error["loc"] == ("slug",) for error in errors)

    def test_slug_all_uppercase_rejected(self):
        """Slug with all uppercase letters should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TenantCreate(name="Test", slug="TESTSLUG")
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("slug",) for error in errors)

    def test_slug_mixed_case_rejected(self):
        """Slug with mixed case should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TenantCreate(name="Test", slug="TestSlug")
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("slug",) for error in errors)
