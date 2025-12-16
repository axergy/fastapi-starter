---
id: "021"
title: "Property-Based Tests for Validators"
status: done
priority: p3
source: "REVIEW.md - MEDIUM #12"
category: testing
---

# Property-Based Tests for Validators

## Problem

No property-based tests for slug/schema validators. All tests are example-based, which may miss edge cases like double underscores, leading/trailing underscores, etc.

## Risk

- **Edge case bugs**: Unusual inputs not covered
- **Regression risk**: Future changes may break edge cases
- **Incomplete coverage**: Manual examples can't cover all patterns

## Verified Findings

| Location | Issue |
|----------|-------|
| `tests/unit/` | No hypothesis imports found |
| All test files | Example-based tests only |
| Slug validation | Edge cases not systematically tested |

### Missing Edge Case Coverage

```python
# These edge cases may not be tested:
"__double_underscore"  # Leading double underscore
"trailing_"            # Trailing underscore
"UPPERCASE"            # Case sensitivity
"with-hyphen"          # Hyphens (should reject)
"with space"           # Spaces (should reject)
"123_starts_digit"     # Leading digit
```

## Fix (Future Enhancement)

1. Add hypothesis to dev dependencies
2. Create property-based tests for slug validation

### Code Changes

**pyproject.toml:**
```toml
[tool.poetry.group.dev.dependencies]
hypothesis = "^6.0"
```

**tests/unit/test_validators_property.py:**
```python
from hypothesis import given, strategies as st
from src.app.schemas.tenant import TenantCreate

# Strategy for valid slugs
valid_slug = st.from_regex(r"[a-z][a-z0-9_]{2,55}", fullmatch=True)

# Strategy for invalid slugs (should be rejected)
invalid_slug = st.one_of(
    st.from_regex(r"[A-Z].*"),         # Uppercase
    st.from_regex(r".*-.*"),           # Contains hyphen
    st.from_regex(r".* .*"),           # Contains space
    st.from_regex(r"[0-9].*"),         # Starts with digit
    st.text(min_size=1, max_size=2),   # Too short
    st.text(min_size=57),              # Too long
)

@given(slug=valid_slug)
def test_valid_slugs_accepted(slug: str):
    """All valid slugs should pass validation."""
    tenant = TenantCreate(name="Test", slug=slug)
    assert tenant.slug == slug

@given(slug=invalid_slug)
def test_invalid_slugs_rejected(slug: str):
    """All invalid slugs should be rejected."""
    with pytest.raises(ValidationError):
        TenantCreate(name="Test", slug=slug)
```

## Files to Modify

- `pyproject.toml` (add hypothesis)
- New: `tests/unit/test_validators_property.py`

## Acceptance Criteria

- [x] hypothesis added to dev dependencies
- [x] Property tests for valid slug patterns
- [x] Property tests for invalid slug patterns
- [x] Tests cover edge cases: double underscores, leading/trailing, case, etc.
- [x] All property tests pass
