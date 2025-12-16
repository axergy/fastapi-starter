# Penetration Test Report - FastAPI SaaS Starter

**Date:** 2025-12-16
**Application:** FastAPI Multi-Tenant SaaS Starter
**Auditor:** Automated Penetration Testing Suite
**Scope:** Full codebase security assessment (OWASP Top 10, Auth, Injection, Access Control)

---

## Executive Summary

A comprehensive penetration test was conducted covering reconnaissance, authentication analysis, injection testing, access control verification, and configuration review. The application demonstrates **strong security fundamentals** with proper implementation of modern security patterns.

### Overall Security Rating: **B+ (Good)**

| Category | Rating | Critical | High | Medium | Low |
|----------|--------|----------|------|--------|-----|
| Authentication | A- | 0 | 2 | 3 | 2 |
| Authorization | A | 0 | 0 | 2 | 1 |
| Injection | A+ | 0 | 0 | 0 | 0 |
| Configuration | B+ | 0 | 1 | 3 | 2 |
| Data Protection | B | 0 | 1 | 2 | 2 |
| SSRF/External | B+ | 0 | 1 | 1 | 0 |
| **TOTAL** | **B+** | **0** | **5** | **11** | **7** |

**Note:** Previous critical finding (CFG-001: Database SSL) has been **FIXED** in commit `6effd90`.

---

## Risk Summary

### Critical (0)
No critical vulnerabilities identified.

### High (5)

| ID | Vulnerability | Location | CVSS |
|----|--------------|----------|------|
| AUTH-001 | Email Verification Status Enumeration | `src/app/api/v1/auth.py:66-75` | 7.5 |
| AUTH-002 | TOCTOU Race Condition in Token Refresh | `src/app/services/auth_service.py:152-188` | 7.3 |
| DATA-001 | Error Message Information Leakage | `src/app/api/v1/auth.py` | 7.1 |
| SSRF-001 | Email URL Configuration Injection | `src/app/core/notifications/email.py:37` | 7.0 |
| CFG-001 | CORS with Credentials Misconfiguration | `src/app/api/middlewares/__init__.py:34-41` | 7.0 |

### Medium (11)

| ID | Vulnerability | Location | CVSS |
|----|--------------|----------|------|
| AUTH-003 | No Rate Limit on Email Verification | `src/app/api/v1/auth.py:224-268` | 5.8 |
| AUTH-004 | No Assumed Identity Token Revocation | `src/app/services/assume_identity_service.py` | 5.7 |
| AUTH-005 | Password Verification Timing Attack | `src/app/core/security/crypto.py:37-45` | 5.5 |
| AUTH-006 | Missing JTI in Access Tokens | `src/app/core/security/crypto.py:48-71` | 5.3 |
| AUTHZ-001 | Registration Workflow TOCTOU | `src/app/services/registration_service.py` | 5.4 |
| AUTHZ-002 | Email Case Sensitivity in Invites | `src/app/services/invite_service.py:154-162` | 5.3 |
| CFG-002 | CSP Contains unsafe-inline | `src/app/api/middlewares/security_headers.py` | 5.0 |
| CFG-003 | X-Forwarded-For Header Trust | `src/app/api/middlewares/request_context.py` | 5.0 |
| CFG-004 | Missing Cache-Control Headers | Security headers middleware | 4.5 |
| DATA-002 | User Email in Logs | `src/app/core/logging.py:92` | 4.3 |
| SSRF-002 | External Service Call Timeouts | `src/app/core/notifications/email.py:48-58` | 4.0 |

### Low (7)

| ID | Vulnerability | Location | CVSS |
|----|--------------|----------|------|
| AUTH-007 | Assumed Identity Expiry (15 min) | `src/app/core/security/crypto.py:115-116` | 3.5 |
| AUTH-008 | Verification Endpoint Info Disclosure | `src/app/services/email_verification_service.py` | 3.0 |
| CFG-005 | Metrics Endpoint Exposure | Rate limit whitelist | 2.5 |
| CFG-006 | Rate Limiting Disabled in Tests | `src/app/core/rate_limit.py:98` | 2.5 |
| DATA-003 | Audit Log Field Exposure | `src/app/schemas/audit.py:10-32` | 2.5 |
| AUTHZ-003 | Tenant Validation Scope | `src/app/api/dependencies/tenant.py` | 2.0 |
| CFG-007 | Default Development Config | `.env.example` | 2.0 |

---

## Detailed Findings

### AUTH-001: Email Verification Status Enumeration (HIGH)

**Severity:** HIGH
**CVSS Score:** 7.5
**OWASP Category:** A07:2021 - Identification and Authentication Failures

**Description:**
The login endpoint returns different error messages for unverified emails vs invalid credentials, allowing attackers to enumerate valid accounts.

**Location:** `src/app/api/v1/auth.py:66-75`

**Vulnerable Code:**
```python
except ValueError as e:
    if str(e) == "Email not verified":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your email for verification link.",
        ) from e
```

**Impact:**
- Attackers can enumerate valid email addresses
- Distinguish between non-existent, unverified, and active accounts
- Target unverified accounts for takeover attempts

**Proof of Concept:**
```bash
# Returns 403 with "Email not verified" - confirms valid email
curl -X POST /api/v1/auth/login -d '{"email":"target@example.com","password":"any"}'

# Returns 401 with "Invalid credentials" - email doesn't exist or wrong password
curl -X POST /api/v1/auth/login -d '{"email":"fake@example.com","password":"any"}'
```

**Remediation:**
```python
# Return same error for all auth failures
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid credentials or account not verified",
)
```

---

### AUTH-002: TOCTOU Race Condition in Token Refresh (HIGH)

**Severity:** HIGH
**CVSS Score:** 7.3
**OWASP Category:** A02:2021 - Cryptographic Failures

**Description:**
Multiple concurrent refresh token requests can result in multiple valid access tokens being issued from a single refresh token due to a time-of-check to time-of-use race condition.

**Location:** `src/app/services/auth_service.py:152-188`

**Vulnerable Window:**
1. Thread 1: Reads token from DB (valid)
2. Thread 2: Reads same token from DB (valid - not yet revoked)
3. Thread 1: Marks token revoked, creates new tokens
4. Thread 2: Also marks token revoked (idempotent), creates DIFFERENT new tokens
5. Result: Two valid token pairs from one parent token

**Impact:**
- Token rotation security bypassed
- Stolen refresh token can generate multiple sessions
- Audit trail corruption

**Proof of Concept:**
```bash
# Race multiple refresh requests
for i in {1..5}; do
  curl -X POST /api/v1/auth/refresh \
    -d '{"refresh_token":"STOLEN_TOKEN"}' &
done
wait
# Multiple requests may succeed with different access tokens
```

**Remediation:**
```python
# Use SELECT FOR UPDATE to lock the row
db_token = await self.session.execute(
    select(RefreshToken)
    .where(RefreshToken.token_hash == token_hash)
    .with_for_update()  # Pessimistic locking
)
```

---

### AUTH-003: No Rate Limit on Email Verification (MEDIUM)

**Severity:** MEDIUM
**CVSS Score:** 5.8
**OWASP Category:** A07:2021 - Identification and Authentication Failures

**Description:**
The `/verify-email` endpoint lacks rate limiting, allowing brute force attacks on verification tokens.

**Location:** `src/app/api/v1/auth.py:224-268`

**Remediation:**
```python
@router.post("/verify-email")
@limiter.limit("5/minute")  # Add rate limiting
async def verify_email(...):
```

---

### AUTH-004: No Assumed Identity Token Revocation (MEDIUM)

**Severity:** MEDIUM
**CVSS Score:** 5.7
**OWASP Category:** A07:2021 - Identification and Authentication Failures

**Description:**
Assumed identity tokens (15-minute validity) cannot be revoked before expiry. If a superuser's workstation is compromised, the attacker has full access for the remaining token lifetime.

**Location:** `src/app/services/assume_identity_service.py`

**Missing Features:**
- No `POST /admin/assume-identity/revoke` endpoint
- No Redis blacklist check for assumed identity tokens
- No way to end session early

**Remediation:**
1. Store assumed identity tokens in DB with revocation flag
2. Check revocation status on each request
3. Add explicit revocation endpoint

---

### SSRF-001: Email URL Configuration Injection (HIGH)

**Severity:** HIGH
**CVSS Score:** 7.0
**OWASP Category:** A10:2021 - Server-Side Request Forgery

**Description:**
The `APP_URL` configuration is directly interpolated into email URLs without domain validation. A misconfigured or compromised APP_URL could redirect users to malicious sites.

**Location:** `src/app/core/notifications/email.py:37`

**Vulnerable Code:**
```python
verification_url = f"{settings.app_url}/verify-email?token={token}"
```

**Remediation:**
```python
# Add URL validation in config
@field_validator("app_url")
def validate_app_url(cls, v):
    allowed_domains = ["yourdomain.com", "localhost"]
    parsed = urlparse(v)
    if parsed.netloc not in allowed_domains:
        raise ValueError(f"APP_URL domain not in allowed list")
    return v
```

---

### CFG-001: CORS with Credentials Misconfiguration (HIGH)

**Severity:** HIGH
**CVSS Score:** 7.0
**OWASP Category:** A05:2021 - Security Misconfiguration

**Description:**
CORS is configured with `allow_credentials=True` and configurable origins. Misconfiguration could expose authentication tokens to malicious origins.

**Location:** `src/app/api/middlewares/__init__.py:34-41`

**Configuration:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # High risk with misconfigured origins
)
```

**Remediation:**
1. Validate CORS origins are strictly controlled
2. Add validation to reject wildcard `*` with credentials
3. Document production CORS requirements

---

### AUTHZ-002: Email Case Sensitivity in Invites (MEDIUM)

**Severity:** MEDIUM
**CVSS Score:** 5.3
**OWASP Category:** A01:2021 - Broken Access Control

**Description:**
Email comparison uses `.lower()` for matching but doesn't normalize emails before storage, potentially allowing duplicate accounts with case variations.

**Location:** `src/app/services/invite_service.py:154-162`

**Remediation:**
```python
# Normalize email on creation
user = User(
    email=email.lower().strip(),
    ...
)
```

---

## Security Strengths

The application demonstrates excellent security practices in several areas:

### Authentication & Authorization
- **JWT Implementation:** Proper algorithm enforcement (HS256), expiration validation
- **Password Security:** Argon2id hashing with strong parameters (64MB memory, 3 iterations)
- **Token Rotation:** Atomic refresh token rotation with Redis blacklist
- **Multi-Tenant Isolation:** JWT tenant_id validated against X-Tenant-ID header
- **Role-Based Access Control:** Admin and Superuser roles properly enforced
- **Assumed Identity Audit:** Full audit trail with operator and reason

### Injection Prevention
- **SQL Injection:** All queries use SQLModel/SQLAlchemy ORM with parameterization
- **Schema Validation:** Strict regex + forbidden pattern checking for tenant schemas
- **PostgreSQL quote_ident():** Used for all dynamic identifiers
- **No Raw SQL:** No user-controllable SQL strings found
- **HTML Escaping:** Email templates properly escape user content with `html.escape()`

### Security Headers
- **HSTS:** Properly configured (1 year, includeSubDomains)
- **X-Frame-Options:** DENY (prevents clickjacking)
- **X-Content-Type-Options:** nosniff
- **CSP:** Implemented (though with unsafe-inline for Swagger)
- **Referrer-Policy:** strict-origin-when-cross-origin

### Monitoring & Audit
- **Comprehensive Audit Logging:** All auth events, admin actions tracked
- **Structured Logging:** Using structlog with request correlation IDs
- **Assumed Identity Tracking:** Operator and assumed user both recorded

---

## OWASP Top 10 2021 Coverage

| Category | Status | Notes |
|----------|--------|-------|
| A01: Broken Access Control | PROTECTED | Multi-tenant isolation, RBAC implemented |
| A02: Cryptographic Failures | PROTECTED | SSL fixed, Argon2id passwords, SHA256 tokens |
| A03: Injection | EXCELLENT | ORM usage, schema validation, HTML escaping |
| A04: Insecure Design | PROTECTED | Token rotation, audit logging |
| A05: Security Misconfiguration | MOSTLY PROTECTED | OpenAPI configurable, CORS needs review |
| A06: Vulnerable Components | REVIEW | Requires dependency scanning |
| A07: Auth Failures | NEEDS WORK | Email enumeration, rate limiting gaps |
| A08: Data Integrity Failures | PROTECTED | Atomic operations, token rotation |
| A09: Logging Failures | PROTECTED | Comprehensive audit, token not logged |
| A10: SSRF | NEEDS REVIEW | APP_URL validation recommended |

---

## Remediation Priority

### Immediate (Before Production)
1. **AUTH-001:** Fix login endpoint to return identical error for all failures
2. **AUTH-002:** Add database locking to token refresh (SELECT FOR UPDATE)
3. **AUTH-003:** Add rate limiting to `/verify-email` endpoint
4. **SSRF-001:** Add APP_URL domain validation

### Short-Term (1-2 Weeks)
5. **AUTH-004:** Implement assumed identity token revocation
6. **CFG-001:** Document and validate CORS configuration for production
7. **AUTHZ-002:** Normalize emails to lowercase on creation
8. **AUTH-006:** Add JTI claims to access tokens for revocation support

### Medium-Term (1 Month)
9. **CFG-002:** Review CSP for production (remove unsafe-inline if possible)
10. **CFG-004:** Add Cache-Control headers on auth endpoints
11. **DATA-002:** Review email logging for GDPR compliance
12. Implement dependency scanning in CI/CD

---

## Testing Recommendations

### Automated Testing
```bash
# Static Analysis
pip install bandit semgrep
bandit -r src/
semgrep --config auto src/

# Dependency Scanning
pip install pip-audit safety
pip-audit
safety check

# Dynamic Testing
# Use OWASP ZAP or Burp Suite against running application
```

### Manual Testing Checklist
- [ ] JWT manipulation (expired, modified, wrong algorithm)
- [ ] Cross-tenant access attempts
- [ ] Assumed identity privilege escalation
- [ ] Rate limit bypass attempts (X-Forwarded-For manipulation)
- [ ] Token refresh race condition testing
- [ ] Email enumeration via login/register/forgot-password
- [ ] CORS origin testing with credentials

---

## Comparison with Previous Audit

### Fixed Since Last Audit
| ID | Issue | Status |
|----|-------|--------|
| CFG-001 (old) | No SSL/TLS for Database | **FIXED** (commit 6effd90) |
| INJ-001 | Email Template XSS | **FIXED** (html.escape added) |
| DATA-001 (old) | Token Logged | **FIXED** (removed from logs) |
| AUTH-001 (old) | Token Type Confusion | **FIXED** (assumed_access type) |
| CFG-003 (old) | OpenAPI Exposed | **FIXED** (configurable) |

### New Findings This Audit
- AUTH-001: Email enumeration via verification status
- AUTH-002: Token refresh race condition (TOCTOU)
- AUTH-003: Missing rate limit on email verification
- AUTH-004: No assumed identity revocation
- SSRF-001: APP_URL validation missing

---

## Conclusion

The FastAPI SaaS Starter demonstrates **strong security fundamentals** with excellent SQL injection prevention, proper password hashing, comprehensive audit logging, and good security headers. The critical database SSL issue has been fixed.

**Key Improvements Needed:**
- Fix authentication enumeration vulnerabilities
- Add database-level locking for token refresh
- Implement assumed identity token revocation
- Validate APP_URL configuration

With the recommended remediations, this application would achieve an **A rating** and be production-ready from a security perspective.

---

*Report generated by automated penetration testing suite. Manual verification recommended for high-severity findings.*
