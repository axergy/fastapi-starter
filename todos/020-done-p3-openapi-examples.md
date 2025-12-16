---
id: "020"
title: "OpenAPI Examples for Slugs"
status: pending
priority: p3
source: "REVIEW.md - POLISH #13"
category: documentation
---

# OpenAPI Examples for Slugs

## Problem

No OpenAPI examples showing valid slug format. Developers must read code to understand slug requirements (lowercase, underscores only, no hyphens).

## Risk

- **Developer confusion**: API consumers don't know valid format
- **Trial and error**: Users submit invalid slugs, get validation errors
- **Poor DX**: OpenAPI/Swagger UI shows no guidance

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/app/schemas/tenant.py` | 14-19 | Validator requires underscores |
| `src/app/schemas/auth.py` | 68-74 | Same validator |
| Both files | - | Neither has `examples` or `json_schema_extra` in Field() |

### Current Schema (No Examples)

```python
slug: str = Field(..., min_length=3, max_length=56)
# No examples shown in OpenAPI
```

## Fix

Add `json_schema_extra` with examples to slug fields.

### Code Changes

**src/app/schemas/tenant.py:**
```python
slug: str = Field(
    ...,
    min_length=3,
    max_length=56,
    json_schema_extra={
        "examples": ["acme_corp", "my_company", "tenant_123"],
        "description": "Lowercase alphanumeric with underscores only. No hyphens."
    }
)
```

**src/app/schemas/auth.py:**
```python
tenant_slug: str = Field(
    ...,
    min_length=3,
    max_length=56,
    json_schema_extra={
        "examples": ["acme_corp", "my_company"],
        "description": "Tenant identifier. Lowercase alphanumeric with underscores."
    }
)
```

## Files to Modify

- `src/app/schemas/tenant.py`
- `src/app/schemas/auth.py`

## Acceptance Criteria

- [ ] Slug fields have `json_schema_extra` with examples
- [ ] Examples show valid format (lowercase, underscores)
- [ ] Description explains the format requirements
- [ ] OpenAPI/Swagger UI displays examples
