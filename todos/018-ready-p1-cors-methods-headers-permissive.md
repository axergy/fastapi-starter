---
status: ready
priority: p1
issue_id: "018"
tags: [security, cors, middleware]
dependencies: []
---

# CORS Methods/Headers Too Permissive

## Problem Statement
The CORS middleware uses `allow_methods=["*"]` and `allow_headers=["*"]` which is overly permissive. Combined with `allow_credentials=True`, this creates a serious vulnerability for cross-origin attacks. Any method (including dangerous ones like DELETE, PATCH) can be invoked from any origin.

## Findings
- Location: `src/app/main.py:55-57`
- Current configuration allows ALL HTTP methods and ALL headers
- Combined with `allow_credentials=True`, attackers can perform authenticated actions
- Browser preflight requests (OPTIONS) will accept ANY method/header combination

## Proposed Solutions

### Option 1: Restrict to explicit methods and headers (Recommended)
```python
allow_methods=["GET", "POST", "PATCH", "DELETE"],
allow_headers=["Authorization", "Content-Type", "X-Tenant-ID", "X-Request-ID"],
```
- **Pros**: Minimal attack surface, explicit allow-list
- **Cons**: Must update if new headers needed
- **Effort**: Small (< 30 minutes)
- **Risk**: Low

## Recommended Action
Implement Option 1 - restrict CORS to explicit methods and headers.

## Technical Details
- **Affected Files**: `src/app/main.py`
- **Related Components**: CORSMiddleware configuration
- **Database Changes**: No

## Resources
- OWASP CORS Security: https://owasp.org/www-community/attacks/CORS_OriginHeaderScrutiny

## Acceptance Criteria
- [ ] CORS allow_methods restricted to explicit list
- [ ] CORS allow_headers restricted to explicit list
- [ ] API still works with frontend (if applicable)
- [ ] Tests pass

## Work Log

### 2025-12-04 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage
- Categorized as P1 (Critical Security)
- Estimated effort: Small

**Learnings:**
- Wildcard CORS settings are a common security oversight

## Notes
Source: Triage session on 2025-12-04
