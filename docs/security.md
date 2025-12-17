# Security Guide

This document provides comprehensive documentation of the security features and best practices implemented in the FastAPI Multi-Tenant SaaS Starter.

## Tenant Isolation

### Schema-Level Isolation

Each tenant's data is stored in a dedicated PostgreSQL schema, providing strong isolation:

```
public/           # Shared infrastructure
├── tenants
├── users
├── user_tenant_membership
└── audit_logs

tenant_acme/      # Tenant A's data
├── products
└── orders

tenant_globex/    # Tenant B's data
├── products
└── orders
```

**Guarantees:**

- Tenants cannot query each other's schemas
- `search_path` is set to single schema during operations
- No cross-tenant JOINs are possible
- Backup and restore can be done per-tenant

### Statement Cache Disabled

```python
engine = create_async_engine(
    settings.database_url,
    connect_args={"statement_cache_size": 0},  # CRITICAL
)
```

**Why?** PostgreSQL caches prepared statements with the `search_path` at preparation time. With connection pooling, a cached statement from one tenant could execute against another tenant's schema.

## SQL Injection Prevention

### Schema Name Validation

Dynamic schema names are validated at multiple layers:

```python
# src/app/core/security/validators.py
FORBIDDEN_SCHEMA_PATTERNS = frozenset([
    "pg_",              # System schemas
    "information_schema",
    "public",
    "--",               # SQL comments
    ";",                # Statement terminator
    "/*", "*/",         # Block comments
])

def validate_schema_name(name: str) -> None:
    # Length check (PostgreSQL limit: 63)
    if len(name) > MAX_SCHEMA_LENGTH:
        raise ValueError(f"Schema name exceeds {MAX_SCHEMA_LENGTH} chars")

    # Format check
    if not re.match(r"^tenant_[a-z][a-z0-9]*(_[a-z0-9]+)*$", name):
        raise ValueError("Invalid schema name format")

    # Forbidden patterns
    for pattern in FORBIDDEN_SCHEMA_PATTERNS:
        if pattern in name.lower():
            raise ValueError(f"Forbidden pattern: {pattern}")
```

### Quote Identifier

Even validated identifiers are quoted using PostgreSQL's `quote_ident()`:

```python
result = await conn.execute(
    text("SELECT quote_ident(:schema)"),
    {"schema": schema_name}
)
quoted = result.scalar_one()
await conn.execute(text(f"SET search_path TO {quoted}"))
```

### Parameterized Queries

All data queries use parameterized statements:

```python
# GOOD: Parameterized
await session.execute(
    select(User).where(User.email == email)
)

# BAD: String interpolation (never do this)
await session.execute(f"SELECT * FROM users WHERE email = '{email}'")
```

## Password Security

### Argon2id Hashing

Passwords are hashed using Argon2id with configurable parameters:

```python
# src/app/core/config.py
class Settings(BaseSettings):
    argon2_time_cost: int = 3       # Iterations
    argon2_memory_cost: int = 65536 # Memory in KB
    argon2_parallelism: int = 1     # Threads
```

```python
# src/app/core/security/crypto.py
from argon2 import PasswordHasher

ph = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
)

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, password)
    except VerifyMismatchError:
        return False
```

### Password Strength Validation

Passwords are validated using zxcvbn entropy estimation:

```python
# src/app/schemas/auth.py
from zxcvbn import zxcvbn

MIN_PASSWORD_SCORE = 3  # Scale 0-4: "safely unguessable"

@field_validator("password")
def validate_password_strength(cls, v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")

    result = zxcvbn(v)
    if result["score"] < MIN_PASSWORD_SCORE:
        feedback = result.get("feedback", {})
        warning = feedback.get("warning", "Password is too weak")
        raise ValueError(warning)

    return v
```

**Score levels:**

| Score | Description | Time to Crack |
|-------|-------------|---------------|
| 0 | Too guessable | < 10^3 guesses |
| 1 | Very guessable | < 10^6 guesses |
| 2 | Somewhat guessable | < 10^8 guesses |
| 3 | Safely unguessable | < 10^10 guesses |
| 4 | Very unguessable | >= 10^10 guesses |

### Timing-Safe Authentication

Authentication uses a dummy hash to prevent timing attacks:

```python
# src/app/services/auth_service.py
DUMMY_PASSWORD_HASH = hash_password("dummy_password_for_timing_safety")

async def authenticate(self, email: str, password: str) -> User | None:
    user = await self.user_repo.get_by_email(email)

    if user is None:
        # Still verify against dummy hash to prevent timing oracle
        verify_password(password, DUMMY_PASSWORD_HASH)
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user
```

## JWT Security

### Token Structure

Access tokens contain tenant scoping:

```python
def create_access_token(subject: str | UUID, tenant_id: str | UUID) -> str:
    payload = {
        "sub": str(subject),           # User ID
        "tenant_id": str(tenant_id),   # Tenant scope
        "exp": datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "access",
        "jti": str(uuid7()),           # Unique ID for revocation
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
```

### Token Validation

```python
# src/app/api/dependencies/auth.py
async def get_current_user(
    session: DBSession,
    tenant: ValidatedTenant,
    authorization: str | None = Header(default=None),
) -> User:
    # 1. Validate Bearer format
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing authorization header")

    token = authorization[7:]

    # 2. Decode and validate JWT
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

    # 3. Validate token type
    if payload.get("type") not in ("access", "assumed_access"):
        raise HTTPException(401, "Invalid token type")

    # 4. CRITICAL: Verify tenant_id matches X-Tenant-Slug header
    if str(payload.get("tenant_id")) != str(tenant.id):
        raise HTTPException(403, "Token not valid for this tenant")

    # 5. Verify user exists and is active
    user = await session.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")

    # 6. Verify membership
    membership = await session.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.tenant_id == tenant.id,
            UserTenantMembership.is_active == True,
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(403, "User not a member of this tenant")

    return user
```

### Refresh Token Rotation

Refresh tokens implement rotation for security:

```python
async def refresh_access_token(self, refresh_token: str, tenant_id: UUID) -> TokenPair:
    # 1. Hash the token for lookup
    token_hash = hash_token(refresh_token)

    # 2. Find token with FOR UPDATE lock (prevent race conditions)
    token = await self.token_repo.get_by_hash_for_update(token_hash)

    if not token:
        raise InvalidTokenError("Invalid refresh token")

    if token.revoked:
        # Potential token theft - revoke all user tokens
        await self.token_repo.revoke_all_for_user(token.user_id)
        raise InvalidTokenError("Token already used - all tokens revoked")

    if token.expires_at < datetime.now(UTC):
        raise InvalidTokenError("Token expired")

    # 3. Revoke old token
    await self.token_repo.revoke(token.id)

    # 4. Issue new token pair
    return await self._create_token_pair(token.user_id, tenant_id)
```

### Assumed Identity Tokens

Superusers can impersonate other users with auditable tokens:

```python
def create_assumed_identity_token(
    assumed_user_id: UUID,
    operator_user_id: UUID,
    tenant_id: UUID,
    reason: str | None = None,
) -> str:
    payload = {
        "sub": str(assumed_user_id),
        "tenant_id": str(tenant_id),
        "type": "assumed_access",
        "exp": datetime.now(UTC) + timedelta(minutes=15),  # Shorter TTL
        "assumed_identity": {
            "operator_user_id": str(operator_user_id),
            "reason": reason,
            "started_at": datetime.now(UTC).isoformat(),
        },
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
```

## Rate Limiting

### Global Middleware

Rate limiting protects against DoS attacks:

```python
# src/app/core/rate_limit.py
class RateLimitMiddleware:
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Get client IP (only source - not X-Tenant-Slug)
        client_ip = self._get_client_ip(scope)

        # Check rate limit
        allowed = await self.limiter.check(client_ip)

        if not allowed:
            response = JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Retry-After": "1"},
            )
            return await response(scope, receive, send)

        return await self.app(scope, receive, send)
```

### Token Bucket Algorithm

```python
class TokenBucket:
    def __init__(self, rate: float, burst: int):
        self.rate = rate    # Tokens per second
        self.burst = burst  # Maximum tokens

    async def check(self, key: str) -> bool:
        # Redis Lua script for atomic operation
        script = """
        local tokens = tonumber(redis.call('GET', KEYS[1]) or ARGV[2])
        local last = tonumber(redis.call('GET', KEYS[2]) or ARGV[3])
        local now = tonumber(ARGV[3])
        local rate = tonumber(ARGV[1])
        local burst = tonumber(ARGV[2])

        -- Replenish tokens
        local elapsed = now - last
        tokens = math.min(burst, tokens + (elapsed * rate))

        if tokens >= 1 then
            tokens = tokens - 1
            redis.call('SET', KEYS[1], tokens)
            redis.call('SET', KEYS[2], now)
            return 1
        end
        return 0
        """
```

### Configuration

```python
class Settings(BaseSettings):
    global_rate_limit_per_second: int = 10
    global_rate_limit_burst: int = 20
```

> **Warning**: Rate limit keys use only client IP, never user-supplied headers like `X-Tenant-Slug`. This prevents attackers from bypassing limits by rotating headers.

## Email Verification

### Secure Token Generation

```python
# src/app/services/email_verification_service.py
import secrets

async def create_verification_token(self, user_id: UUID) -> str:
    # Generate cryptographically secure token
    token = secrets.token_urlsafe(32)

    # Store hashed version
    await self.verification_repo.create(
        user_id=user_id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )

    return token  # Return plaintext for email
```

### Verification Flow

1. User registers with email
2. System creates hashed token with expiry
3. Email sent with plaintext token
4. User clicks verification link
5. Token validated and marked as used
6. User's `email_verified` flag set

### Enumeration Prevention

```python
async def resend_verification(self, email: str) -> bool:
    """Always returns True to prevent email enumeration."""
    user = await self.user_repo.get_by_email(email)
    if user and not user.email_verified:
        await self._send_verification_email(user)
    return True  # Always True
```

## Tenant Invites

### Invite Security

```python
async def create_invite(
    self,
    tenant_id: UUID,
    email: str,
    role: MembershipRole,
    inviter_id: UUID,
) -> TenantInvite:
    # Invalidate existing pending invites
    await self.invite_repo.invalidate_pending(tenant_id, email)

    # Generate secure token
    token = secrets.token_urlsafe(32)

    invite = await self.invite_repo.create(
        tenant_id=tenant_id,
        email=email,
        role=role.value,
        inviter_id=inviter_id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    return invite, token
```

### Accept Invite Validation

```python
async def accept_invite(self, token: str, email: str, password: str) -> User:
    # Find invite by hashed token
    invite = await self.invite_repo.get_by_token_hash(hash_token(token))

    if not invite:
        raise InvalidInviteError("Invalid invite token")

    if invite.email.lower() != email.lower():
        raise InvalidInviteError("Email does not match invite")

    if invite.expires_at < datetime.now(UTC):
        raise InvalidInviteError("Invite expired")

    if invite.status != InviteStatus.PENDING.value:
        raise InvalidInviteError("Invite already used")

    # Create user and membership in transaction
    async with self.session.begin():
        user = await self._create_user(email, password)
        await self._create_membership(user.id, invite.tenant_id, invite.role)
        await self.invite_repo.mark_accepted(invite.id)

    return user
```

## Audit Logging

### Audit Log Model

```python
class AuditLog(SQLModel, table=True):
    __table_args__ = {"schema": "public"}

    id: UUID = Field(default_factory=uuid7, primary_key=True)
    tenant_id: UUID = Field(foreign_key="public.tenants.id")
    user_id: UUID | None
    assumed_by_user_id: UUID | None  # If superuser impersonating
    action: str                       # e.g., "user.login"
    entity_type: str                  # e.g., "user"
    entity_id: UUID | None
    changes: dict[str, Any] = Field(default_factory=dict, sa_type=JSONB)
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    status: str = "success"           # or "failure"
    error_message: str | None
    created_at: datetime
```

### Context-Aware Logging

```python
# src/app/services/audit_service.py
async def log(
    self,
    action: AuditAction,
    entity_type: str,
    entity_id: UUID | None = None,
    changes: dict | None = None,
    status: str = "success",
) -> None:
    # Get request context
    audit_ctx = get_audit_context()
    assumed_ctx = get_assumed_identity_context()

    # Enrich changes with assumed identity info
    if assumed_ctx:
        changes = changes or {}
        changes["_assumed_identity"] = {
            "operator_user_id": str(assumed_ctx.operator_user_id),
            "reason": assumed_ctx.reason,
        }

    await self.audit_repo.create(
        tenant_id=self.tenant_id,
        user_id=self.user_id,
        assumed_by_user_id=assumed_ctx.operator_user_id if assumed_ctx else None,
        action=action.value,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes or {},
        ip_address=audit_ctx.ip_address if audit_ctx else None,
        user_agent=audit_ctx.user_agent if audit_ctx else None,
        request_id=audit_ctx.request_id if audit_ctx else None,
        status=status,
    )
```

### Audit Actions

| Category | Actions |
|----------|---------|
| Auth | `user.login`, `user.logout`, `user.register`, `token.refresh` |
| User | `user.update`, `user.delete`, `user.email_verify`, `user.password_change` |
| Tenant | `tenant.create`, `tenant.update`, `tenant.delete` |
| Membership | `member.invite`, `member.join`, `member.remove`, `member.role_change` |
| Identity | `identity.assumed` |

## Security Headers

```python
# src/app/api/middlewares/security_headers.py
class SecurityHeadersMiddleware:
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }

    # Strict CSP for API responses
    CSP = "default-src 'none'; frame-ancestors 'none'"

    # HSTS for production
    HSTS = "max-age=31536000; includeSubDomains"
```

## Soft Deletes

### Implementation

```python
class Tenant(SQLModel, table=True):
    deleted_at: datetime | None = Field(default=None)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
```

### Query Filtering

```python
# Always filter out deleted tenants
result = await session.execute(
    select(Tenant).where(
        Tenant.slug == slug,
        Tenant.deleted_at.is_(None),  # Not deleted
    )
)
```

### Benefits

- Maintains audit trail
- Allows undelete if needed
- Preserves referential integrity
- Supports compliance requirements

## Future Enhancements

### Row-Level Security (RLS)

For additional defense in depth:

```sql
-- Enable RLS on tenant tables
ALTER TABLE tenant_products ENABLE ROW LEVEL SECURITY;

-- Policy based on session variable
CREATE POLICY tenant_isolation ON tenant_products
    USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

### Per-Tenant Database Roles

```sql
-- Create role per tenant
CREATE ROLE tenant_acme;
GRANT USAGE ON SCHEMA tenant_acme TO tenant_acme;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA tenant_acme TO tenant_acme;
```

### Encryption at Rest

- Use PostgreSQL's `pgcrypto` for sensitive fields
- Consider AWS RDS encryption or equivalent
- Implement key rotation procedures

## Security Checklist

- [ ] Change default `JWT_SECRET_KEY` (min 32 characters)
- [ ] Configure rate limiting for production load
- [ ] Enable HTTPS/TLS termination
- [ ] Set up audit log monitoring
- [ ] Review and customize password requirements
- [ ] Configure trusted proxy headers
- [ ] Enable database connection SSL
- [ ] Set up security alerting for failed logins
- [ ] Regular dependency updates for security patches
