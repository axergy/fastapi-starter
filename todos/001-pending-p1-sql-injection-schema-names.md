---
status: ready
priority: p1
issue_id: "001"
tags: [security, sql-injection, multi-tenancy]
dependencies: []
---

# SQL Injection Vulnerability in Schema Name Handling

## Problem Statement
The code uses f-strings to construct SQL statements with schema names, creating SQL injection vulnerabilities. While there is validation (`tenant_schema.replace("_", "").isalnum()`), this validation happens AFTER the schema name is potentially used and is inconsistent across files.

## Findings
- F-string interpolation used for SQL schema names
- Location: `src/app/core/db.py:56`
- Location: `src/alembic/env.py:46-47`
- Validation is inconsistent and applied too late
- Attack scenario: malicious slug like `evil; DROP TABLE users; --` could execute arbitrary SQL

## Proposed Solutions

### Option 1: Use SQLAlchemy identifier quoting + centralized validation (RECOMMENDED)
- **Pros**: Proper SQL escaping, single validation point, defense in depth
- **Cons**: Requires changes in multiple files
- **Effort**: Medium (2-3 hours)
- **Risk**: Low - standard security pattern

Implementation:
```python
# New file: src/app/core/validators.py
import re

def validate_schema_name(schema_name: str) -> None:
    """Validate schema name to prevent SQL injection."""
    if not re.match(r'^[a-z][a-z0-9_]{0,49}$', schema_name):
        raise ValueError(f"Invalid schema name: {schema_name}")

    forbidden = ['pg_', 'information_schema', 'public', '--', ';', '/*', '*/']
    if any(pattern in schema_name.lower() for pattern in forbidden):
        raise ValueError(f"Schema name contains forbidden pattern: {schema_name}")
```

## Recommended Action
Implement Option 1 - centralized validation with SQLAlchemy identifier quoting

## Technical Details
- **Affected Files**:
  - `src/app/core/db.py`
  - `src/alembic/env.py`
  - New file: `src/app/core/validators.py`
- **Related Components**: Tenant provisioning, database migrations
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- OWASP SQL Injection Prevention: https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html

## Acceptance Criteria
- [ ] Centralized schema name validator created
- [ ] Validation applied BEFORE any database operations
- [ ] SQLAlchemy identifier quoting used for schema names
- [ ] Existing validation removed/replaced with centralized version
- [ ] Tests added for validation edge cases
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P1 CRITICAL
- Estimated effort: Medium (2-3 hours)

**Learnings:**
- Multi-tenant schema isolation requires careful SQL construction
- Defense in depth: validate early AND use proper escaping

## Notes
Source: Triage session on 2025-12-04
