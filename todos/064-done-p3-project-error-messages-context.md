---
status: done
priority: p3
issue_id: "064"
tags: [ux, debugging, api, error-handling]
dependencies: []
---

# Generic Error Messages Without Context

## Problem Statement
The project endpoints use generic error messages like "Project not found" without including the project ID. This makes debugging harder for both users and developers reviewing logs.

## Findings
- "Project not found" appears in 3 locations without ID
- Location: `src/app/api/v1/projects.py:63, 120, 155`
- No request context in error responses
- Log correlation difficult without IDs

## Proposed Solutions

### Option 1: Include resource ID in error messages
- **Pros**: Better debugging, clearer errors
- **Cons**: Minimal information disclosure (UUIDs are not sensitive)
- **Effort**: Small (10 minutes)
- **Risk**: Low

## Recommended Action
Update error messages to include project ID:

```python
# get_project (line 63)
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"Project {project_id} not found",
)

# update_project (line 120)
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"Project {project_id} not found",
)

# delete_project (line 155)
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"Project {project_id} not found",
)
```

Consider creating a helper function for consistency:

```python
def project_not_found(project_id: UUID) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Project {project_id} not found",
    )
```

## Technical Details
- **Affected Files**: `src/app/api/v1/projects.py`
- **Related Components**: Error handling across all endpoints
- **Database Changes**: No

## Resources
- Original finding: Code review triage session
- API error message best practices

## Acceptance Criteria
- [ ] All 404 errors include project ID
- [ ] Error messages consistent across endpoints
- [ ] Tests verify error message format
- [ ] Consider pattern for other resources

## Work Log

### 2025-12-17 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending to ready
- Ready to be picked up and worked on

**Learnings:**
- Error messages should include context for debugging
- UUIDs are safe to include in error responses
- Consistent error format improves developer experience

## Notes
Source: Triage session on 2025-12-17
Quick fix, can be done alongside other project endpoint changes
