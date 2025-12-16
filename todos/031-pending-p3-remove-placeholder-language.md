---
status: pending
priority: p3
issue_id: "031"
tags: [cleanup, docs, polish]
dependencies: []
---

# Remove Placeholder Language from Tenant Packages

## Problem Statement
Tenant model and repository packages have template placeholder comments like "Add tenant-specific business models here". These are template leftovers that should be replaced with neutral descriptions.

## Findings
- `src/app/models/tenant/__init__.py` lines 1-5:
  - "Tenant-specific models. Add tenant-specific business models here (e.g., Project, Document, etc.)"
- `src/app/repositories/tenant/__init__.py` lines 1-5:
  - "Tenant-specific repositories. Add tenant-specific business repositories here (e.g., ProjectRepository, etc.)"
- Both are placeholder/instructional comments for template users

## Proposed Solutions

### Option 1: Simplify to neutral descriptions
- **Pros**: Clean, professional, no template noise
- **Cons**: None
- **Effort**: Small
- **Risk**: Low

## Recommended Action
Replace placeholder docstrings with neutral descriptions.

## Technical Details
- **Affected Files**:
  - `src/app/models/tenant/__init__.py`
  - `src/app/repositories/tenant/__init__.py`
- **Related Components**: Package documentation
- **Database Changes**: No

## Resources
- Original finding: REVIEW.md - Polish #9
- Related issues: None

## Acceptance Criteria
- [ ] models/tenant/__init__.py has neutral docstring: "Tenant-schema models."
- [ ] repositories/tenant/__init__.py has neutral docstring: "Tenant-schema repositories."
- [ ] No "Add ... here" placeholder language
- [ ] No example suggestions (e.g., "Project, Document")

## Work Log

### 2025-12-16 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during REVIEW.md analysis
- Categorized as P3 (polish)
- Estimated effort: Small

**Learnings:**
- Template placeholders become noise in production code

## Notes
Source: REVIEW.md Round 3 - Code Cleanup

Change:
```python
# Before (models/tenant/__init__.py)
"""Tenant-specific models.

Tenant-specific data models go in models/tenant/ directory.
These are separate from public schema models.
"""
# Add tenant-specific business models here as you build your application

# After
"""Tenant-schema models.

This package is reserved for schema-per-tenant SQLModel tables.
"""
```
