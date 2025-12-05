---
status: resolved
priority: p1
issue_id: "004"
tags: [security, authorization-bypass, multi-tenant]
dependencies: ["003"]
---

# Tenant Schema Name Collision Risk

## Problem Statement
The `schema_name` property constructs tenant schemas as `f"tenant_{self.slug}"` without length validation. PostgreSQL truncates identifiers at 63 characters. Two tenants with slugs that differ only after character 56 (`63 - len("tenant_")`) will map to the SAME schema, causing complete multi-tenant authorization bypass.

## Findings
- Location: `src/app/models/public/tenant.py:26-28`
- No length validation on slug or resulting schema name
- PostgreSQL silently truncates identifiers > 63 characters
- Multi-tenant isolation completely broken for long slugs

**Attack Scenario:**
1. Tenant A registers with slug: `aaaaaaaaaabbbbbbbbbbccccccccccddddddddddeeeeeeeeee_victim`
2. Tenant B registers with slug: `aaaaaaaaaabbbbbbbbbbccccccccccddddddddddeeeeeeeeee_attacker`
3. Both resolve to schema: `tenant_aaaaaaaaaabbbbbbbbbbccccccccccddddddddddeeeeeeee`
4. Tenant B now has full access to Tenant A's data
5. **Complete multi-tenant isolation bypass**

**Current Code:**
```python
@property
def schema_name(self) -> str:
    return f"tenant_{self.slug}"  # No length validation
```

## Proposed Solutions

### Option 1: Add Length Validation at Multiple Layers
- Add validation in `schema_name` property (raises error if too long)
- Add `max_length=56` constraint in `RegisterRequest` schema for slug
- Add database CHECK constraint for slug length
- **Pros**: Defense in depth, prevents issue at all layers
- **Cons**: Requires migration for existing tenants
- **Effort**: Small (1-2 hours)
- **Risk**: Low (existing tenants unlikely to have 56+ char slugs)

## Recommended Action
Implement length validation at schema, model, and database levels

## Technical Details
- **Affected Files**:
  - `src/app/models/public/tenant.py`
  - `src/app/schemas/auth.py` (RegisterRequest)
  - New migration for CHECK constraint
- **Related Components**: Tenant provisioning, registration flow
- **Database Changes**: Yes - ADD CHECK constraint on slug length

## Resources
- Original finding: Code review triage session
- PostgreSQL identifier limits: https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS

## Acceptance Criteria
- [x] `schema_name` property raises ValueError if resulting name > 63 chars
- [x] `RegisterRequest` schema validates slug max_length=56
- [x] Database has CHECK constraint on tenant slug length
- [x] Existing tenants validated (none should have slug > 56 chars)
- [x] Tests cover collision attempt scenario
- [x] Clear error message when slug too long

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P1 CRITICAL (Security - Authorization Bypass)
- Estimated effort: Small (1-2 hours)
- Added dependency on Issue #003 (schema validation)

**Learnings:**
- PostgreSQL identifier truncation is a known attack vector
- Multi-tenant apps must validate identifier lengths explicitly

### 2025-12-05 - Implementation Complete
**By:** Claude Code
**Actions:**
- Updated `RegisterRequest.tenant_slug` to `max_length=56` with explanatory comment
- Updated `Tenant.slug` model field to use `MAX_SLUG_LENGTH` constant
- Modified `schema_name` property to call `validate_schema_name()` for defense-in-depth
- Created migration `010_add_tenant_slug_length_constraint.py`:
  - CHECK constraint `ck_tenants_slug_length` for length <= 56
  - CHECK constraint `ck_tenants_slug_format` for valid slug format regex
- Created comprehensive test suite `tests/test_schema_name_collision.py` (17 tests):
  - Slug length validation tests
  - Schema name validation tests
  - Tenant model schema_name property tests
  - Collision attack scenario tests
  - Constants verification tests

**Results:**
- Multi-tenant isolation bypass attack prevented at multiple layers
- All 17 tests passing
- Defense-in-depth: validation at schema, model, and database levels

**Learnings:**
- Using constants (`MAX_SLUG_LENGTH`, `MAX_SCHEMA_LENGTH`) ensures consistency
- PostgreSQL regex syntax differs from Python (uses `~` operator)
- Property-level validation provides last line of defense even if other validations bypassed

## Notes
Source: Triage session on 2025-12-05
Status: RESOLVED - Implemented multi-layer length validation to prevent schema name collisions.
