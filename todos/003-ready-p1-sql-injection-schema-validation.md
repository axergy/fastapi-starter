---
status: ready
priority: p1
issue_id: "003"
tags: [security, sql-injection, validation]
dependencies: []
---

# SQL Injection Risk in Schema Name Validation

## Problem Statement
The `validate_schema_name` function uses a regex that allows underscores anywhere in the schema name and uses a denylist approach which is inherently less secure than an allowlist. The validation may be called after `quote_ident` in some code paths, creating a TOCTOU vulnerability where malicious input could bypass validation.

## Findings
- Location: `src/app/core/security/validators.py:6-13`
- Current regex `^[a-z][a-z0-9_]{0,49}$` allows multiple consecutive underscores
- Denylist approach (`forbidden` patterns) can miss new attack vectors
- Validation order inconsistent across code paths
- No enforcement of `tenant_` prefix in validator

**Current Code:**
```python
def validate_schema_name(schema_name: str) -> None:
    if not re.match(r"^[a-z][a-z0-9_]{0,49}$", schema_name):
        raise ValueError(f"Invalid schema name: {schema_name}")
    forbidden = ["pg_", "information_schema", "public", "--", ";", "/*", "*/"]
    if any(pattern in schema_name.lower() for pattern in forbidden):
        raise ValueError(f"Schema name contains forbidden pattern: {schema_name}")
```

## Proposed Solutions

### Option 1: Strengthen Validation with Allowlist Approach
- Enforce `tenant_` prefix in regex
- Limit consecutive underscores (single underscore as separator only)
- Add PostgreSQL identifier length limit (63 chars)
- Always validate BEFORE any database operations
- **Pros**: More secure, explicit format requirement
- **Cons**: Stricter than current implementation
- **Effort**: Small (1-2 hours)
- **Risk**: Low

**Proposed Regex:**
```python
r"^tenant_[a-z][a-z0-9]*(_[a-z0-9]+)*$"
```

## Recommended Action
Implement allowlist-based validation with stricter format requirements

## Technical Details
- **Affected Files**:
  - `src/app/core/security/validators.py`
  - `src/app/temporal/activities.py` (ensure validation order)
- **Related Components**: Tenant provisioning, schema management
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- PostgreSQL identifier limits: https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS

## Acceptance Criteria
- [ ] Regex enforces `tenant_` prefix
- [ ] No consecutive underscores allowed (single underscore as separator)
- [ ] Length validation for PostgreSQL 63-char limit
- [ ] Validation always occurs BEFORE any SQL operations
- [ ] Comprehensive test cases for edge cases and attack patterns
- [ ] Existing valid tenant schemas still pass validation

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P1 CRITICAL (Security)
- Estimated effort: Small (1-2 hours)

**Learnings:**
- Denylist approaches are inherently weaker than allowlists
- Validation order matters for security-critical operations

## Notes
Source: Triage session on 2025-12-05
