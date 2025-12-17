---
status: done
priority: p3
issue_id: "040"
tags: [validators, constants, DRY]
dependencies: []
---

# Extract Hardcoded Schema Regex Constant

## Problem Statement
The `validate_schema_name()` function contains a hardcoded regex pattern that duplicates the `TENANT_SLUG_REGEX` pattern with a prefix added. This violates DRY principles and creates a maintenance burden if the slug pattern changes.

## Findings
- Location: `src/app/core/security/validators.py`

- Line 9 - Existing slug regex:
  ```python
  TENANT_SLUG_REGEX: Final[str] = r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$"
  ```

- Line 55 - Hardcoded schema regex:
  ```python
  if not re.match(r"^tenant_[a-z][a-z0-9]*(_[a-z0-9]+)*$", schema_name):
  ```

- The schema regex is essentially: `"^" + TENANT_SCHEMA_PREFIX + TENANT_SLUG_REGEX[1:]`
- If TENANT_SLUG_REGEX changes, the hardcoded pattern won't be updated

## Proposed Solutions

### Option 1: Create TENANT_SCHEMA_REGEX constant
- **Pros**: DRY, single source of truth, compiled pattern for performance
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

```python
# Add near other constants:
TENANT_SCHEMA_REGEX: Final[str] = rf"^{TENANT_SCHEMA_PREFIX}[a-z][a-z0-9]*(_[a-z0-9]+)*$"
_TENANT_SCHEMA_PATTERN: Final[re.Pattern[str]] = re.compile(TENANT_SCHEMA_REGEX)

# Update validate_schema_name():
def validate_schema_name(schema_name: str) -> str:
    """Validate schema name for SQL safety."""
    if not schema_name:
        raise ValueError("Schema name cannot be empty")

    if not _TENANT_SCHEMA_PATTERN.match(schema_name):
        raise ValueError(f"Invalid schema name format: {schema_name}")

    return schema_name
```

### Option 2: Derive from TENANT_SLUG_REGEX dynamically
- **Pros**: Guaranteed sync with slug regex
- **Cons**: More complex, harder to read
- **Effort**: Small
- **Risk**: Low

```python
# The slug pattern without ^ anchor
_SLUG_BODY = TENANT_SLUG_REGEX[1:]  # Removes "^"
TENANT_SCHEMA_REGEX: Final[str] = rf"^{TENANT_SCHEMA_PREFIX}{_SLUG_BODY}"
```

## Recommended Action
Implement Option 1 - create a clear, separate `TENANT_SCHEMA_REGEX` constant with compiled pattern.

## Technical Details
- **Affected Files**: `src/app/core/security/validators.py`
- **Related Components**: Schema validation, tenant creation
- **Database Changes**: No

## Resources
- Original finding: REVIEW2.md - Polish #8
- Related issues: None

## Acceptance Criteria
- [ ] TENANT_SCHEMA_REGEX constant added
- [ ] _TENANT_SCHEMA_PATTERN compiled pattern added
- [ ] validate_schema_name() uses compiled pattern
- [ ] Hardcoded regex removed
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2024-12-17 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW2.md code review
- Categorized as POLISH (DRY)
- Estimated effort: Small

**Learnings:**
- Compiled regex patterns are more efficient for repeated use
- Deriving patterns from constants ensures consistency

## Notes
Source: REVIEW2.md Polish #8
