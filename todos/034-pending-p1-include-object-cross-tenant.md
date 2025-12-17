---
status: done
priority: p1
issue_id: "034"
tags: [alembic, migrations, security, multi-tenancy]
dependencies: []
---

# Fix include_object Cross-Tenant Contamination Risk

## Problem Statement
The current `include_object` function in Alembic env.py allows reflected tables from OTHER tenant schemas during autogenerate. While it correctly excludes public schema tables, it doesn't restrict to ONLY the current tag schema. This can cause drift detection noise and potentially mask real diffs.

## Findings
- Location: `src/alembic/env.py:49-66`
- Current logic for tenant migrations:
  ```python
  if is_tenant_migration:
      return object_schema != "public"  # Includes ALL non-public schemas!
  ```
- This means when running `alembic --autogenerate --tag=tenant_acme`, reflected tables from `tenant_globex`, `tenant_initech`, etc. are also included
- Even if all tenants are "supposed" to be in sync, drift happens
- Autogenerate noise or false diffs become inevitable
- Can mask real diffs in the target tenant schema

## Proposed Solutions

### Option 1: Restrict reflected objects to current tag schema
- **Pros**: Clean separation, no cross-tenant contamination, clear autogenerate output
- **Cons**: None - this is the correct behavior
- **Effort**: Small
- **Risk**: Low

```python
def include_object(obj, name, type_, reflected, compare_to):
    """
    Prevent cross-schema contamination.

    - Public migrations (no --tag): include only public schema tables.
    - Tenant migrations (--tag <schema>): include:
      * metadata tenant tables (schema=None) and explicitly-tagged tenant tables
      * reflected DB objects only for the active tenant schema (avoid drift/noise)
    """
    tag_schema = context.get_tag_argument()

    if type_ != "table":
        return True

    object_schema = getattr(obj, "schema", None)

    # Public migration: only public schema tables.
    if not tag_schema:
        return object_schema == "public"

    # Tenant migration:
    if reflected:
        # Only the active tenant schema should be compared/reflected.
        return object_schema == tag_schema

    # metadata side: keep tenant tables (schema=None) and drop public ones
    return object_schema != "public"
```

## Recommended Action
Implement Option 1 - modify include_object to restrict reflected objects to only the active tenant schema.

## Technical Details
- **Affected Files**: `src/alembic/env.py`
- **Related Components**: Alembic autogenerate, tenant migrations
- **Database Changes**: No

## Resources
- Original finding: REVIEW2.md - Critical #1
- Related issues: None

## Acceptance Criteria
- [ ] include_object function updated with reflected object filtering
- [ ] Autogenerate with `--tag=tenant_x` only shows objects from that schema
- [ ] Public migrations still work correctly
- [ ] Tests pass
- [ ] Code reviewed

## Work Log

### 2024-12-17 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW2.md code review
- Categorized as CRITICAL
- Estimated effort: Small

**Learnings:**
- Cross-tenant contamination during autogenerate can cause subtle issues
- The `reflected` parameter is key to distinguishing DB-reflected vs metadata objects

## Notes
Source: REVIEW2.md Critical #1
