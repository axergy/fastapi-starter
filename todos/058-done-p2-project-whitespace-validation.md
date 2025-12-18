---
status: done
priority: p2
issue_id: "058"
tags: [validation, data-quality, api, schemas]
dependencies: []
---

# Missing Whitespace Validation for Project Name

## Problem Statement
The `ProjectCreate` and `ProjectUpdate` schemas enforce `min_length=1` but don't trim whitespace. A user could submit `"   "` (spaces only) as a valid name, which passes validation but creates poor data quality.

## Findings
- `ProjectCreate.name` has `min_length=1` but no whitespace handling
- `ProjectUpdate.name` same issue
- `ProjectUpdate.description` allows empty strings (inconsistent with None)
- Location: `src/app/schemas/project.py:12-24`

## Proposed Solutions

### Option 1: Add field validators to strip and validate
- **Pros**: Clean data, consistent behavior
- **Cons**: Slightly more code
- **Effort**: Small (15 minutes)
- **Risk**: Low

## Recommended Action
Add Pydantic field validators to both schemas:

```python
from pydantic import field_validator

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be empty or whitespace only")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v
```

Apply same validators to `ProjectUpdate`.

## Technical Details
- **Affected Files**: `src/app/schemas/project.py`
- **Related Components**: Project API endpoints
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- Pydantic field validators documentation

## Acceptance Criteria
- [x] Whitespace-only names rejected with clear error
- [x] Names are trimmed before storage
- [x] Empty descriptions converted to None
- [ ] Tests verify whitespace handling
- [x] Both ProjectCreate and ProjectUpdate updated

## Work Log

### 2025-12-18 - Implementation Complete
**By:** Claude Code Assistant
**Actions:**
- Added `field_validator` import to project schemas
- Implemented `validate_name` for both ProjectCreate and ProjectUpdate
  - Strips whitespace from name
  - Raises ValueError if name is empty after stripping
- Implemented `validate_description` for both ProjectCreate and ProjectUpdate
  - Strips whitespace from description
  - Converts empty strings to None
- Updated todo status to done

**Learnings:**
- Field validators handle both required and optional fields appropriately
- Consistent whitespace handling prevents data quality issues
- Empty description normalization to None maintains consistency

### 2025-12-17 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending to ready
- Ready to be picked up and worked on

**Learnings:**
- min_length validation doesn't account for whitespace
- Consistent data normalization improves data quality
- Empty string vs None should be handled consistently

## Notes
Source: Triage session on 2025-12-17
