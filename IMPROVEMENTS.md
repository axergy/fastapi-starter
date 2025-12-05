# Improvements

Validated code review findings for the FastAPI SaaS Starter project.

---

## Critical / Security

### 1. ~~Rate Limiting by IP + Tenant~~ ✅ DONE
**Risk:** Medium
**Current:** ~~Rate limiter uses only IP address~~ Now uses IP + tenant
**Fix:** Implemented `get_rate_limit_key()` with composite key `{ip}:{tenant_id}`
**File:** `src/app/core/rate_limit.py`

### 2. ~~Unprotected /metrics Endpoint~~ ✅ DONE
**Risk:** Medium
**Current:** ~~Prometheus metrics exposed without auth~~ Now protected with API key
**Fix:** Added `METRICS_API_KEY` env var; requires `X-Metrics-Key` header when set
**Files:** `src/app/main.py`, `src/app/core/config.py`

### 3. ~~CSP Missing frame-ancestors Directive~~ ✅ DONE
**Risk:** Low
**Current:** ~~CSP was `default-src 'self'` only~~ Now includes `frame-ancestors 'none'`
**Fix:** Updated CSP to `default-src 'self'; frame-ancestors 'none'`
**File:** `src/app/core/security_headers.py:15`

---

## Major Features

### 4. ~~Add /users/me/tenants Endpoint~~ ✅ DONE
**Current:** ~~User must call `/users/me` and `/tenants` separately~~ Now has dedicated endpoint
**Benefit:** Single endpoint to list all tenants a user belongs to
**Implementation:** Added `GET /users/me/tenants` using `AuthenticatedUser` (no tenant context required)
**File:** `src/app/api/v1/users.py`

### 5. ~~Email Verification Flow~~ ✅ DONE
**Current:** ~~Users can register with any email, no verification~~ Now requires email verification
**Benefit:** Prevents fake accounts, confirms email ownership
**Implementation:**
- Added `EmailVerificationToken` model with SHA256 hashed tokens
- Added `POST /auth/verify-email` and `POST /auth/resend-verification` endpoints
- Registration sends verification email via Resend API
- Login blocked (403) until email is verified
- Rate limited resend (3/hour) to prevent abuse
**Files:** `src/app/core/email.py`, `src/app/services/email_verification_service.py`, `src/app/api/v1/auth.py`

### 6. ~~User Invite Flow~~ ✅ DONE
**Current:** ~~No way to add users to existing tenants~~ Now supports inviting users
**Benefit:** Essential for team collaboration
**Implementation:**
- Added `TenantInvite` model with SHA256 hashed tokens and 7-day expiry
- Admin endpoints: `POST/GET/DELETE/PUT /api/v1/invites` (require admin role)
- Public endpoints: `GET /api/v1/invites/t/{token}`, `POST /api/v1/invites/t/{token}/accept`
- Supports both existing users (auth header) and new user registration
- Invite emails via Resend API
**Files:** `src/app/api/v1/invites.py`, `src/app/services/invite_service.py`, `src/app/schemas/invite.py`

### 7. ~~Superuser/Admin Endpoints~~ ✅ DONE
**Current:** ~~`is_superuser` field exists on User model but not exposed~~ Now exposed with admin endpoints
**Benefit:** Admin dashboard capabilities
**Implementation:**
- Exposed `is_superuser` in `UserRead` schema
- Added `SuperUser` dependency (requires `is_superuser=True`)
- Added `GET /api/v1/admin/tenants` to list all tenants (superuser only)
**Files:** `src/app/schemas/user.py`, `src/app/api/dependencies/auth.py`, `src/app/api/v1/admin.py`

### 8. ~~UUID7 or ULID Instead of uuid4~~ ✅ DONE
**Risk:** Low
**Current:** ~~All models use `uuid4()` for primary keys~~ Now uses `uuid7()` from stdlib
**Benefit:** Better database index performance (time-ordered, reduces fragmentation)
**Implementation:** Upgraded to Python 3.14.1, replaced `uuid4` with `uuid7` from stdlib
**Files:** `src/app/models/public/*.py`, `pyproject.toml`

### 9. ~~OpenAPI Tags and Response Examples~~ ✅ DONE
**Current:** ~~Minimal API documentation~~ Now has full OpenAPI documentation
**Benefit:** Better developer experience, clearer API structure
**Implementation:**
- Added `openapi_tags` with descriptions for all 5 API groups
- Added `description` and `version` to FastAPI app
- Added `responses={}` with examples to all endpoints
**Files:** `src/app/main.py`, `src/app/api/v1/users.py`, `src/app/api/v1/invites.py`, `src/app/api/v1/admin.py`

---

## Minor / Polish

### 10. Extract get_current_user Logic
**Current:** ~90 lines with 10+ validation steps in single function
**Benefit:** Better testability, separation of concerns
**Implementation:** Extract token validation, UUID parsing, membership check into service
**File:** `src/app/api/dependencies.py:183-272`

### 11. Add revoke_all_tokens_for_user Function
**Current:** Only single-token revocation exists
**Benefit:** Security for password reset, account compromise scenarios
**Implementation:** Add `revoke_all_tokens_for_user(tenant_id, user_id)` to auth service
**File:** `src/app/services/auth_service.py`

### 12. Soft-Delete + Cleanup for Failed Tenants
**Current:** Failed tenants remain in DB with `status=failed`, schemas may be orphaned
**Benefit:** Clean state, ability to retry or cleanup resources
**Implementation:**
- Add `deleted_at` timestamp field
- Add cleanup workflow for failed provisioning
- Add scheduled job to clean orphaned schemas
**Files:** `src/app/models/public.py`, `src/app/temporal/workflows.py`

### 13. Compensation Logic in Workflows
**Current:** On failure, only marks tenant as "failed" - no undo
**Benefit:** Clean rollback of partial resources (Saga pattern)
**Implementation:** Add compensating activities that undo each step on failure
**File:** `src/app/temporal/workflows.py:165-177`

### 14. Add drop_tenant_schema Activity
**Current:** No programmatic way to drop tenant schemas
**Benefit:** Enable cleanup workflows, tenant deletion
**Implementation:** Add `drop_tenant_schema` activity with idempotency
**File:** `src/app/temporal/activities.py`

### 15. Add Redis for Distributed State
**Current:** Rate limiting uses in-memory storage (per-process)
**Issues:**
- Rate limits don't work across multiple app instances
- Token revocation requires DB query on every request
- No request-level caching
**Implementation:**
- Add `redis` or `aioredis` dependency
- Configure slowapi with Redis backend
- Cache token revocation status
- Cache frequently accessed tenant data
**Files:** `pyproject.toml`, `src/app/core/rate_limit.py`, `src/app/core/config.py`
