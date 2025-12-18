---
status: ready
priority: p2
issue_id: "086"
tags: [testing, security, sql-injection, validation]
dependencies: []
---

# Missing SQL Injection Tests

## Problem Statement
Schema name validation should be tested with comprehensive SQL injection payloads to ensure all attack vectors are blocked.

## Findings
- Location: Tests directory - incomplete coverage
- Schema validation exists but limited test cases
- No comprehensive injection payload testing
- OWASP top payloads not tested
- Security regression risk

## Proposed Solutions

### Option 1: Add parameterized SQL injection tests
- **Pros**: Comprehensive coverage, catches regressions
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

```python
import pytest
from src.app.core.security.validators import (
    validate_tenant_slug_format,
    validate_schema_name,
)

# Comprehensive SQL injection payloads
SQL_INJECTION_PAYLOADS = [
    # Basic injection
    "'; DROP TABLE users; --",
    "' OR '1'='1",
    "' OR 1=1--",
    "' UNION SELECT * FROM users--",

    # Comment-based
    "test/**/OR/**/1=1",
    "test--comment",
    "test#comment",

    # Encoded attacks
    "test%27%20OR%201=1",
    "test%00null",

    # PostgreSQL specific
    "test'; COPY users TO '/tmp/data'--",
    "test'; SELECT pg_sleep(10)--",
    "$$malicious$$",

    # Path traversal in schema
    "../../../etc/passwd",
    "..\\..\\windows",

    # Null byte injection
    "test\x00admin",
    "test\0",

    # Unicode tricks
    "test\u0000",
    "tëst",  # Non-ASCII

    # Reserved schemas
    "pg_catalog",
    "information_schema",
    "pg_temp",
    "pg_toast",
]

@pytest.mark.parametrize("malicious_input", SQL_INJECTION_PAYLOADS)
def test_slug_rejects_sql_injection(malicious_input: str):
    """Test that SQL injection payloads are rejected."""
    with pytest.raises((ValueError, ValidationError)):
        validate_tenant_slug_format(malicious_input)

@pytest.mark.parametrize("malicious_input", SQL_INJECTION_PAYLOADS)
def test_schema_name_rejects_sql_injection(malicious_input: str):
    """Test that schema validation rejects injection attempts."""
    with pytest.raises((ValueError, ValidationError)):
        validate_schema_name(f"tenant_{malicious_input}")
```

## Recommended Action
Add comprehensive parameterized tests for SQL injection payloads in slug and schema validation.

## Technical Details
- **Affected Files**: `tests/unit/test_security.py` or new `tests/unit/test_sql_injection.py`
- **Related Components**: Validators, tenant creation
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- OWASP SQL Injection: https://owasp.org/www-community/attacks/SQL_Injection

## Acceptance Criteria
- [ ] Parameterized tests with comprehensive payloads
- [ ] Basic injection patterns tested
- [ ] PostgreSQL-specific attacks tested
- [ ] Encoding and null byte attacks tested
- [ ] Reserved schema names tested
- [ ] All tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-18 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Security tests should cover known attack patterns
- Parameterized tests make adding new payloads easy

## Notes
Source: Triage session on 2025-12-18
