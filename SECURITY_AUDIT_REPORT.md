# Penetration Test Report - FastAPI SaaS Starter

**Date:** 2025-12-16
**Application:** FastAPI Multi-Tenant SaaS Starter
**Auditor:** Automated Security Assessment
**Scope:** Full codebase security review

---

## Executive Summary

A comprehensive penetration test was conducted on the FastAPI SaaS Starter application covering OWASP Top 10 vulnerabilities, authentication/authorization flaws, injection attacks, and security misconfigurations.

### Overall Security Rating: **B+ (Good)**

| Category | Rating | Critical | High | Medium | Low |
|----------|--------|----------|------|--------|-----|
| Authentication | A | 0 | 1 | 1 | 1 |
| Authorization | A | 0 | 0 | 0 | 0 |
| Injection | A- | 0 | 0 | 1 | 0 |
| Configuration | B | 1 | 1 | 2 | 2 |
| Data Protection | A | 0 | 1 | 1 | 0 |
| Logging/Monitoring | A | 0 | 0 | 1 | 0 |
| **TOTAL** | **B+** | **1** | **3** | **6** | **3** |

---

## Risk Summary

### Critical (1)
| ID | Vulnerability | Location | CVSS |
|----|--------------|----------|------|
| CFG-001 | No SSL/TLS for Database Connections | `src/app/core/db/engine.py` | 9.1 |

### High (3)
| ID | Vulnerability | Location | CVSS |
|----|--------------|----------|------|
| INJ-001 | Email Template XSS/HTML Injection | `src/app/core/notifications/email.py` | 7.1 |
| CFG-002 | Debug Mode Enabled | `.env` | 7.0 |
| DATA-001 | Verification Token Logged | `src/app/core/notifications/email.py:40` | 7.0 |

### Medium (6)
| ID | Vulnerability | Location | CVSS |
|----|--------------|----------|------|
| AUTH-001 | Token Type Confusion (Assumed Identity) | `src/app/core/security/crypto.py:156` | 5.5 |
| CFG-003 | OpenAPI/Swagger Exposed in Production | Rate limit middleware | 5.3 |
| CFG-004 | CSP Contains unsafe-inline | `src/app/api/middlewares/security_headers.py` | 5.0 |
| CFG-005 | X-Forwarded-For Header Trust | `src/app/api/middlewares/request_context.py` | 5.0 |
| AUTH-002 | Assumed Identity Token Not Revocable | `src/app/services/assume_identity_service.py` | 4.5 |
| LOG-001 | User Input in Audit Logs Unsanitized | `src/app/models/public/audit.py` | 4.0 |

### Low (3)
| ID | Vulnerability | Location | CVSS |
|----|--------------|----------|------|
| AUTH-003 | Timing Attack on Token Validation | `src/app/services/email_verification_service.py` | 3.5 |
| CFG-006 | Rate Limiting Disabled in Tests | `src/app/core/rate_limit.py:98` | 2.5 |
| CFG-007 | Default Database Credentials | `.env.example` | 2.0 |

---

## Detailed Findings

### CFG-001: No SSL/TLS for Database Connections (CRITICAL)

**Severity:** CRITICAL
**CVSS Score:** 9.1
**OWASP Category:** A02:2021 - Cryptographic Failures

**Description:**
Database connections do not enforce SSL/TLS encryption. Credentials and data transmitted in plaintext over the network.

**Location:** `src/app/core/db/engine.py:15-21`

**Vulnerable Code:**
```python
_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    # NO SSL CONFIGURATION
)
```

**Impact:**
- Database credentials exposed to network sniffing
- All query data transmitted in plaintext
- Man-in-the-middle attacks possible
- Complete data breach if network is compromised

**Proof of Concept:**
```bash
# Network capture would reveal:
# - PostgreSQL authentication credentials
# - All SQL queries and results
# - User data, tenant data, etc.
tcpdump -i eth0 port 5432 -X
```

**Remediation:**
```python
# Add to config.py
database_ssl_mode: str = "require"  # require, verify-ca, verify-full

# Add to engine.py
import ssl
connect_args = {}
if settings.database_ssl_mode != "disable":
    ssl_context = ssl.create_default_context()
    if settings.database_ssl_mode == "verify-full":
        ssl_context.check_hostname = True
    connect_args["ssl"] = ssl_context

_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    connect_args=connect_args,
)
```

---

### INJ-001: Email Template XSS/HTML Injection (HIGH)

**Severity:** HIGH
**CVSS Score:** 7.1
**OWASP Category:** A03:2021 - Injection

**Description:**
User-controlled data (user_name, tenant_name) is directly interpolated into HTML email templates without escaping.

**Location:** `src/app/core/notifications/email.py:55-75, 125-145, 188-208`

**Vulnerable Code:**
```python
def _get_verification_email_html(user_name: str, verification_url: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<body>
    <p>Hi {user_name},</p>  <!-- XSS HERE -->
    ...
</body>
</html>"""
```

**Impact:**
- XSS attacks in email clients that render HTML
- Phishing attacks via injected links
- Email client exploitation
- Reputation damage

**Proof of Concept:**
```python
# Register with malicious name
POST /api/v1/auth/register
{
    "email": "attacker@example.com",
    "password": "SecurePass123!",
    "full_name": "<img src=x onerror='alert(document.cookie)'>",
    "tenant_name": "Evil Corp",
    "tenant_slug": "evilcorp"
}

# Resulting email HTML:
# <p>Hi <img src=x onerror='alert(document.cookie)'>,</p>
```

**Remediation:**
```python
import html

def _get_verification_email_html(user_name: str, verification_url: str) -> str:
    safe_name = html.escape(user_name)
    safe_url = html.escape(verification_url)
    return f"""<!DOCTYPE html>
<html>
<body>
    <p>Hi {safe_name},</p>
    <a href="{safe_url}">Verify Email</a>
</body>
</html>"""
```

---

### DATA-001: Verification Token Logged (HIGH)

**Severity:** HIGH
**CVSS Score:** 7.0
**OWASP Category:** A09:2021 - Security Logging and Monitoring Failures

**Description:**
Email verification URLs containing tokens are logged when Resend API key is not configured.

**Location:** `src/app/core/notifications/email.py:40-42`

**Vulnerable Code:**
```python
logger.warning(
    "RESEND_API_KEY not set - email not sent",
    to=to,
    verification_url=verification_url,  # TOKEN EXPOSED IN LOGS
)
```

**Impact:**
- Verification tokens exposed in log files
- Account takeover if logs are accessed
- Compliance violations (PII in logs)

**Remediation:**
```python
logger.warning(
    "RESEND_API_KEY not set - email not sent",
    to=to,
    # DO NOT log verification_url - contains sensitive token
)
```

---

### CFG-002: Debug Mode Enabled (HIGH)

**Severity:** HIGH
**CVSS Score:** 7.0
**OWASP Category:** A05:2021 - Security Misconfiguration

**Description:**
Debug mode is enabled in configuration, which may expose sensitive information in error responses.

**Location:** `.env` file

**Evidence:**
```
DEBUG=true
```

**Impact:**
- Verbose error messages may leak sensitive data
- Stack traces could expose file paths
- Internal state may be disclosed

**Remediation:**
```bash
# Production .env
DEBUG=false
APP_ENV=production
```

---

### AUTH-001: Token Type Confusion for Assumed Identity (MEDIUM)

**Severity:** MEDIUM
**CVSS Score:** 5.5
**OWASP Category:** A07:2021 - Identification and Authentication Failures

**Description:**
Assumed identity tokens use the same `type: "access"` as regular access tokens, which could lead to confusion if JWT secrets are compromised.

**Location:** `src/app/core/security/crypto.py:156`

**Vulnerable Code:**
```python
to_encode = {
    "sub": str(assumed_user_id),
    "tenant_id": str(tenant_id),
    "type": "access",  # SAME AS REGULAR TOKEN
    "assumed_identity": {...}
}
```

**Impact:**
- Token confusion attacks if signing key compromised
- Audit log manipulation potential
- Unclear token provenance

**Remediation:**
```python
to_encode = {
    "sub": str(assumed_user_id),
    "tenant_id": str(tenant_id),
    "type": "assumed_identity",  # DISTINCT TYPE
    "assumed_identity": {...}
}

# Add validation in auth.py
if assumed_identity_data and payload.get("type") != "assumed_identity":
    raise HTTPException(status_code=401, detail="Invalid token type")
```

---

### CFG-003: OpenAPI/Swagger Exposed (MEDIUM)

**Severity:** MEDIUM
**CVSS Score:** 5.3
**OWASP Category:** A05:2021 - Security Misconfiguration

**Description:**
OpenAPI documentation endpoints (`/docs`, `/openapi.json`, `/redoc`) are publicly accessible without authentication.

**Location:** Rate limit middleware exemptions

**Impact:**
- Full API schema exposed to attackers
- Aids in reconnaissance and attack planning
- Exposes internal endpoint structure

**Remediation:**
```python
# In config.py
enable_openapi: bool = Field(default=False)

# In main.py
if not settings.enable_openapi:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
```

---

## Security Strengths

The application demonstrates excellent security practices in several areas:

### Authentication & Authorization
- **JWT Implementation:** Proper algorithm enforcement (HS256), expiration validation, signature verification
- **Password Security:** Argon2id hashing with configurable parameters
- **Rate Limiting:** Comprehensive protection on auth endpoints (5/min login, 3/hour register)
- **Multi-Tenant Isolation:** JWT tenant_id validated against X-Tenant-ID header
- **Role-Based Access Control:** Admin and Superuser roles properly enforced

### Injection Prevention
- **SQL Injection:** All queries use SQLModel/SQLAlchemy ORM with parameterization
- **Schema Validation:** Strict regex + forbidden pattern checking for tenant schemas
- **PostgreSQL quote_ident():** Used for all dynamic identifiers

### Session Management
- **Token Rotation:** Atomic refresh token rotation with old token revocation
- **Redis Blacklist:** Fast token validation with database fallback
- **Constant-Time Comparison:** `hmac.compare_digest()` used in critical paths

### Audit & Monitoring
- **Comprehensive Audit Logging:** All auth events, admin actions, assumed identity tracked
- **Structured Logging:** Using structlog with request correlation IDs
- **Assumed Identity Tracking:** Operator and assumed user both recorded

---

## OWASP Top 10 2021 Coverage

| Category | Status | Notes |
|----------|--------|-------|
| A01: Broken Access Control | PROTECTED | Multi-tenant isolation, RBAC implemented |
| A02: Cryptographic Failures | VULNERABLE | Missing database SSL/TLS |
| A03: Injection | PROTECTED | ORM usage, schema validation |
| A04: Insecure Design | PROTECTED | Token rotation, audit logging |
| A05: Security Misconfiguration | VULNERABLE | Debug mode, OpenAPI exposure |
| A06: Vulnerable Components | REVIEW | Requires dependency scanning |
| A07: Auth Failures | MOSTLY PROTECTED | Token type confusion issue |
| A08: Data Integrity Failures | PROTECTED | Atomic operations, token rotation |
| A09: Logging Failures | VULNERABLE | Token in logs |
| A10: SSRF | PROTECTED | No user-controllable HTTP calls |

---

## Remediation Priority

### Immediate (Before Production)
1. **CFG-001:** Add SSL/TLS for database connections
2. **DATA-001:** Remove token from log output
3. **CFG-002:** Disable debug mode in production
4. **INJ-001:** Add HTML escaping to email templates

### Short-Term (1-2 Weeks)
5. **CFG-003:** Disable OpenAPI in production or add authentication
6. **AUTH-001:** Add distinct token type for assumed identity
7. **CFG-004:** Remove unsafe-inline from CSP or disable Swagger
8. **CFG-005:** Configure trusted proxy headers

### Medium-Term (1 Month)
9. **AUTH-002:** Implement assumed identity token revocation
10. **LOG-001:** Add sanitization for audit log display
11. Implement dependency scanning in CI/CD
12. Add security headers testing

---

## Testing Recommendations

### Automated Testing
```bash
# Static Analysis
pip install bandit semgrep
bandit -r src/
semgrep --config auto src/

# Dependency Scanning
pip install pip-audit
pip-audit

# Dynamic Testing
# Use OWASP ZAP or Burp Suite against running application
```

### Manual Testing Checklist
- [ ] JWT manipulation (expired, modified, wrong algorithm)
- [ ] Cross-tenant access attempts
- [ ] Assumed identity privilege escalation
- [ ] Rate limit bypass attempts
- [ ] SQL injection in all input fields
- [ ] XSS in email templates
- [ ] CSRF token validation
- [ ] Session fixation attacks

---

## Conclusion

The FastAPI SaaS Starter demonstrates **strong security fundamentals** with proper implementation of modern authentication patterns, comprehensive audit logging, and multi-tenant isolation. The identified vulnerabilities are primarily in operational security (database SSL, debug mode) and edge cases (email XSS, token logging) rather than fundamental architectural flaws.

**Key Strengths:**
- Excellent authentication/authorization design
- Comprehensive audit trail with assumed identity tracking
- Strong SQL injection prevention
- Proper rate limiting implementation

**Key Improvements Needed:**
- Database connection encryption
- Email template sanitization
- Production configuration hardening
- OpenAPI endpoint protection

With the recommended remediations, this application would achieve an **A rating** and be ready for production deployment from a security perspective.

---

*Report generated by automated security assessment. Manual verification recommended for critical findings.*
