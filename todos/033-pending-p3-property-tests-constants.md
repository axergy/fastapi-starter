---
status: pending
priority: p3
issue_id: "033"
tags: [tests, dry, constants]
dependencies: ["026"]
---

# Update Property Tests to Use Constants

## Problem Statement
Property tests in test_validators_property.py hardcode "56" instead of using the centralized constants from validators.py.

## Findings
- `tests/unit/test_validators_property.py` hardcoded values:
  - Line 19: `1 <= len(s) <= 56`
  - Line 41: `st.text(min_size=57, max_size=100)` (tests > 56)
  - Line 68: `lambda s: 1 <= len(s) <= 56`
  - Line 81: `lambda s: 1 <= len(s) <= 56`
  - Line 93: `lambda s: 1 <= len(s) <= 56`
  - Line 131: `slug = "a" * 56`
- Should import `MAX_TENANT_SLUG_LENGTH` and `TENANT_SLUG_REGEX` from validators.py

## Proposed Solutions

### Option 1: Import and use constants
- **Pros**: Single source of truth, tests stay in sync with implementation
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Import constants from validators.py and replace all hardcoded values.

## Technical Details
- **Affected Files**:
  - `tests/unit/test_validators_property.py`
- **Related Components**: Property tests, validators
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - High #5d
- Related issues: #026 (centralize constants - dependency)

## Acceptance Criteria
- [ ] Import `MAX_TENANT_SLUG_LENGTH`, `TENANT_SLUG_REGEX` from validators.py
- [ ] Replace hardcoded "56" with `MAX_TENANT_SLUG_LENGTH`
- [ ] Replace hardcoded "57" with `MAX_TENANT_SLUG_LENGTH + 1`
- [ ] Replace hardcoded regex with `TENANT_SLUG_REGEX`
- [ ] Tests pass

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P3 (polish)
- Estimated effort: Small
- Depends on Issue 026

**Learnings:**
- Tests should use the same constants as production code

## Notes
Source: REVIEW.md Round 3 - Code Cleanup

Change:
```python
# Before
valid_slug = st.from_regex(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", fullmatch=True).filter(
    lambda s: 1 <= len(s) <= 56
)

@given(slug=st.text(min_size=57, max_size=100))
def test_long_slugs_rejected(slug: str):
    """Slugs longer than 56 characters should be rejected."""

# After
from src.app.core.security.validators import MAX_TENANT_SLUG_LENGTH, TENANT_SLUG_REGEX

valid_slug = st.from_regex(TENANT_SLUG_REGEX, fullmatch=True).filter(
    lambda s: 1 <= len(s) <= MAX_TENANT_SLUG_LENGTH
)

@given(slug=st.text(min_size=MAX_TENANT_SLUG_LENGTH + 1, max_size=100))
def test_long_slugs_rejected(slug: str):
    """Slugs longer than MAX_TENANT_SLUG_LENGTH should be rejected."""
```
