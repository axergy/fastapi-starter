---
status: ready
priority: p2
issue_id: "017"
tags: [testing, security, quality]
dependencies: []
---

# Missing Tests for Critical Paths

## Problem Statement
Several critical scenarios lack test coverage: tenant schema isolation, token tenant mismatch, race conditions, workflow failures, database rollback scenarios, and integration tests between API and Temporal.

## Findings
- No tests for tenant schema isolation
- No tests for token/tenant mismatch scenarios
- No tests for race conditions in registration
- No tests for Temporal workflow failures
- No tests for database rollback scenarios
- Missing integration tests between API and Temporal
- Location: `tests/`

## Proposed Solutions

### Option 1: Add comprehensive test suites (RECOMMENDED)
- **Pros**: Catches regressions, documents expected behavior
- **Cons**: Significant effort
- **Effort**: Large (8-10 hours)
- **Risk**: Low

Test categories to add:
```python
# tests/test_security.py
class TestTenantIsolation:
    async def test_token_from_tenant_a_cannot_access_tenant_b(self):
        """Verify JWT tenant_id validation."""

    async def test_user_without_membership_cannot_login(self):
        """Verify membership required for login."""

    async def test_schema_name_sql_injection_prevented(self):
        """Verify schema name validation prevents SQL injection."""

# tests/test_race_conditions.py
class TestConcurrentRegistration:
    async def test_concurrent_same_slug_registration(self):
        """Only one tenant created for concurrent same-slug requests."""

# tests/test_workflows.py
class TestWorkflowFailures:
    async def test_tenant_provisioning_failure_marks_failed(self):
        """Failed workflow updates tenant status correctly."""

    async def test_registration_rollback_on_workflow_failure(self):
        """User creation rolls back if workflow fails to start."""

# tests/test_transactions.py
class TestDatabaseRollback:
    async def test_rollback_on_commit_failure(self):
        """Session rolled back on commit failure."""
```

## Recommended Action
Implement Option 1 - prioritize security tests first

## Technical Details
- **Affected Files**:
  - `tests/test_security.py` (new)
  - `tests/test_race_conditions.py` (new)
  - `tests/test_workflows.py` (new or extend)
  - `tests/test_transactions.py` (new)
- **Related Components**: All security-critical paths
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/

## Acceptance Criteria
- [ ] Tenant isolation tests added
- [ ] Token/tenant mismatch tests added
- [ ] Race condition tests for registration
- [ ] Workflow failure handling tests
- [ ] Database rollback scenario tests
- [ ] All new tests pass
- [ ] Code reviewed

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P2 IMPORTANT
- Estimated effort: Large (8-10 hours)

**Learnings:**
- Security-critical code needs comprehensive test coverage
- Tests document expected behavior and catch regressions

## Notes
Source: Triage session on 2025-12-04
