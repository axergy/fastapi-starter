---
status: ready
priority: p1
issue_id: "002"
tags: [data-integrity, transactions, invites]
dependencies: []
---

# Missing Transaction Boundary in Accept Invite Flow

## Problem Statement
The `accept_invite` endpoint performs critical operations (user authentication, invite acceptance, membership creation) but retrieves the tenant AFTER the transaction completes. If the tenant is deleted or deactivated between the service commit and tenant retrieval, the endpoint returns a success response with missing/invalid tenant data.

## Findings
- Location: `src/app/api/v1/invites.py:351-464`
- Service commits membership at line 170/246 in `invite_service.py`
- Controller retrieves tenant separately at line 417-418
- No transaction protection between membership creation and tenant retrieval

**Problem Scenario:**
1. User accepts invite, service creates membership and commits
2. Transaction boundary ends
3. Another admin deletes/deactivates the tenant (race condition)
4. Controller retrieves tenant - gets deleted/invalid data
5. User receives success response but cannot access tenant

## Proposed Solutions

### Option 1: Include Tenant in Service Response
- Move tenant retrieval into the service method before commit
- Return tenant as part of the same transaction
- Validate tenant is active before creating membership
- **Pros**: Single transaction, data consistency guaranteed
- **Cons**: Minor service interface change
- **Effort**: Small (1-2 hours)
- **Risk**: Low

## Recommended Action
Refactor service to include tenant validation and retrieval within transaction

## Technical Details
- **Affected Files**:
  - `src/app/services/invite_service.py`
  - `src/app/api/v1/invites.py`
- **Related Components**: Invite acceptance flow, membership creation
- **Database Changes**: No

## Resources
- Original finding: Code review triage session

## Acceptance Criteria
- [ ] Tenant is retrieved within the same transaction as membership creation
- [ ] Tenant status is validated before membership is created
- [ ] If tenant is deleted/inactive, invite acceptance fails with clear error
- [ ] Tests cover race condition scenario
- [ ] No orphaned memberships can be created

## Work Log

### 2025-12-05 - Initial Discovery
**By:** Claude Triage System
**Actions:**
- Issue discovered during code review triage session
- Categorized as P1 CRITICAL (Data Integrity)
- Estimated effort: Small (1-2 hours)

**Learnings:**
- Transaction boundaries must encompass all related data operations
- TOCTOU issues can occur between service and controller layers

## Notes
Source: Triage session on 2025-12-05
