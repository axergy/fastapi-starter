# Testing Guide

This document covers the test structure, philosophy, and practices for the FastAPI Multi-Tenant SaaS Starter.

## Test Philosophy

The test suite follows these principles:

1. **Test behavior, not implementation** - Focus on what the code does, not how
2. **Security-first testing** - Critical security paths have thorough coverage
3. **Isolation** - Tests don't depend on each other or external state
4. **Speed** - Unit tests are fast; integration tests use efficient fixtures
5. **Clarity** - Test names describe expected behavior

## Test Categories

### Unit Tests (`tests/unit/`)

Fast, isolated tests for individual components:

- Service logic
- Validators and utilities
- Schema validation
- Pure functions

```bash
# Run only unit tests
pytest tests/unit/ -v
```

### Integration Tests (`tests/integration/`)

Tests that involve multiple components:

- API endpoints
- Database operations
- Service interactions
- Tenant provisioning

```bash
# Run only integration tests
pytest tests/integration/ -v
```

### End-to-End Tests (`tests/e2e/`)

Full workflow tests:

- Complete user journeys
- Multi-step operations
- Cross-service flows

```bash
# Run only e2e tests
pytest tests/e2e/ -v
```

## Directory Structure

```
tests/
├── conftest.py              # Shared fixtures
├── utils/
│   ├── cleanup.py           # Test cleanup utilities
│   └── factories.py         # Test data factories
├── unit/
│   ├── test_security.py     # Security validators
│   ├── test_rate_limit.py   # Rate limiting logic
│   ├── test_audit_*.py      # Audit logging
│   └── ...
├── integration/
│   ├── test_auth.py         # Authentication endpoints
│   ├── test_provisioning.py # Tenant provisioning
│   ├── test_invite_*.py     # Invite workflows
│   └── ...
└── e2e/
    └── ...
```

## Running Tests

### All Tests

```bash
# Using Makefile
make test

# Or directly with pytest
pytest

# With parallel execution (faster)
pytest -n auto
```

### With Coverage

```bash
# Generate coverage report
make test-cov

# Or directly
pytest --cov=src --cov-report=html
```

### Specific Tests

```bash
# Run a specific test file
pytest tests/unit/test_security.py -v

# Run a specific test class
pytest tests/unit/test_security.py::TestSchemaValidation -v

# Run a specific test
pytest tests/unit/test_security.py::TestSchemaValidation::test_valid_schema_name -v

# Run tests matching a pattern
pytest -k "test_auth" -v
```

## Key Test Fixtures

### Database Session

```python
# tests/conftest.py
@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test."""
    async with async_session_maker() as session:
        yield session
        await session.rollback()
```

### Test Client

```python
@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for API testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

### Authenticated User

```python
@pytest.fixture
async def authenticated_user(
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> tuple[User, str]:
    """Create a user with valid access token."""
    user = await create_test_user(db_session, test_tenant.id)
    token = create_access_token(user.id, test_tenant.id)
    return user, token
```

### Test Tenant

```python
@pytest.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a ready tenant for testing."""
    tenant = Tenant(
        name="Test Tenant",
        slug=f"test_{uuid4().hex[:8]}",
        status=TenantStatus.READY.value,
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant
```

### Rate Limit Reset

```python
@pytest.fixture(autouse=True)
async def reset_rate_limits():
    """Reset rate limit state between tests."""
    from src.app.core.rate_limit import _in_memory_buckets
    _in_memory_buckets.clear()
    yield
```

## Security Tests

### Schema Name Validation

```python
# tests/unit/test_security.py
class TestSchemaValidation:
    """Test schema name validation for SQL injection prevention."""

    def test_valid_schema_name(self):
        """Valid schema names should pass."""
        validate_schema_name("tenant_acme")
        validate_schema_name("tenant_acme_corp")
        validate_schema_name("tenant_a1b2c3")

    def test_schema_too_long(self):
        """Schema names over 63 chars should fail."""
        long_slug = "a" * 57
        with pytest.raises(ValueError, match="exceeds PostgreSQL limit"):
            validate_schema_name(f"tenant_{long_slug}")

    def test_sql_injection_attempts(self):
        """SQL injection patterns should be rejected."""
        malicious_names = [
            "tenant_acme; DROP TABLE users;--",
            "tenant_acme'--",
            "tenant_acme/**/",
            "pg_catalog",
            "information_schema",
        ]
        for name in malicious_names:
            with pytest.raises(ValueError):
                validate_schema_name(name)

    def test_forbidden_patterns(self):
        """Names containing forbidden patterns should fail."""
        with pytest.raises(ValueError, match="forbidden pattern"):
            validate_schema_name("tenant_pg_admin")
```

### Password Strength

```python
class TestPasswordStrength:
    """Test zxcvbn password validation."""

    def test_strong_password_accepted(self):
        """Strong passwords should pass validation."""
        RegisterRequest(
            email="test@example.com",
            password="correct-horse-battery-staple",
            full_name="Test User",
            tenant_name="Test",
            tenant_slug="test",
        )

    def test_weak_password_rejected(self):
        """Weak passwords should fail."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="password123",  # Common password
                full_name="Test User",
                tenant_name="Test",
                tenant_slug="test",
            )

    def test_keyboard_pattern_rejected(self):
        """Keyboard patterns should fail."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="qwertyuiop",
                full_name="Test User",
                tenant_name="Test",
                tenant_slug="test",
            )
```

### Authentication

```python
# tests/integration/test_auth.py
class TestAuthentication:
    """Test authentication endpoints."""

    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Valid credentials should return tokens."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "TestPassword123!"},
            headers={"X-Tenant-ID": test_user.tenant_slug},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Wrong password should return 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "wrong"},
            headers={"X-Tenant-ID": test_user.tenant_slug},
        )
        assert response.status_code == 401

    async def test_login_wrong_tenant(self, client: AsyncClient, test_user: User):
        """Token for wrong tenant should be rejected."""
        # Login to get token
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "TestPassword123!"},
            headers={"X-Tenant-ID": test_user.tenant_slug},
        )
        token = response.json()["access_token"]

        # Try to use token with different tenant
        response = await client.get(
            "/api/v1/users/me",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": "different_tenant",
            },
        )
        assert response.status_code == 403
```

### Rate Limiting

```python
# tests/unit/test_rate_limit.py
class TestRateLimit:
    """Test rate limiting logic."""

    async def test_requests_within_limit_allowed(self):
        """Requests within limit should succeed."""
        limiter = TokenBucket(rate=10, burst=20)
        for _ in range(15):
            assert await limiter.check("test_key")

    async def test_requests_over_limit_blocked(self):
        """Requests over limit should be blocked."""
        limiter = TokenBucket(rate=1, burst=2)
        assert await limiter.check("test_key")
        assert await limiter.check("test_key")
        assert not await limiter.check("test_key")

    async def test_tokens_replenish(self):
        """Tokens should replenish over time."""
        limiter = TokenBucket(rate=10, burst=10)

        # Exhaust tokens
        for _ in range(10):
            await limiter.check("test_key")

        # Wait for replenishment
        await asyncio.sleep(0.5)

        # Should have ~5 tokens now
        assert await limiter.check("test_key")
```

## Tenant Lifecycle Tests

```python
# tests/integration/test_provisioning.py
class TestProvisioningLifecycle:
    """Test tenant provisioning workflow."""

    async def test_tenant_transitions_to_ready(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """New tenant should transition through provisioning states."""
        unique_id = uuid4().hex[:8]

        with patch("src.app.services.registration_service.get_temporal_client") as mock:
            mock_client = AsyncMock()
            mock_client.start_workflow.return_value = AsyncMock()
            mock.return_value = mock_client

            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"test_{unique_id}@example.com",
                    "password": "SecurePassword123!",
                    "full_name": "Test User",
                    "tenant_name": "Test Corp",
                    "tenant_slug": f"test_{unique_id}",
                },
            )

        assert response.status_code == 202

        # Verify tenant created in provisioning state
        result = await db_session.execute(
            select(Tenant).where(Tenant.slug == f"test_{unique_id}")
        )
        tenant = result.scalar_one()
        assert tenant.status == TenantStatus.PROVISIONING.value
```

## Test Utilities

### Cleanup Utilities

```python
# tests/utils/cleanup.py
async def cleanup_test_tenant(session: AsyncSession, slug: str) -> None:
    """Remove test tenant and its schema."""
    from src.app.core.security.validators import validate_schema_name

    schema_name = f"tenant_{slug}"
    validate_schema_name(schema_name)

    # Drop schema
    await session.execute(
        text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
    )

    # Delete tenant record
    await session.execute(
        delete(Tenant).where(Tenant.slug == slug)
    )
    await session.commit()
```

### Test Factories

```python
# tests/utils/factories.py
async def create_test_user(
    session: AsyncSession,
    tenant_id: UUID,
    **overrides,
) -> User:
    """Create a test user with membership."""
    defaults = {
        "email": f"test_{uuid4().hex[:8]}@example.com",
        "full_name": "Test User",
        "hashed_password": hash_password("TestPassword123!"),
        "email_verified": True,
    }
    defaults.update(overrides)

    user = User(**defaults)
    session.add(user)
    await session.flush()

    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=tenant_id,
        role=MembershipRole.MEMBER.value,
    )
    session.add(membership)
    await session.commit()

    return user
```

## Configuration

### pytest.ini / pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
filterwarnings = [
    "ignore::DeprecationWarning",
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "e2e: End-to-end tests",
    "slow: Slow tests",
]
```

### Environment for Testing

```bash
# Set testing environment
APP_ENV=testing pytest

# This disables:
# - Rate limiting
# - External service calls (mocked)
```

## Best Practices

### 1. Use Markers

```python
import pytest

@pytest.mark.unit
def test_validator():
    ...

@pytest.mark.integration
async def test_api_endpoint():
    ...

@pytest.mark.slow
async def test_full_workflow():
    ...
```

### 2. Isolate Database State

```python
@pytest.fixture(autouse=True)
async def clean_db(db_session: AsyncSession):
    """Ensure clean state for each test."""
    yield
    await db_session.rollback()
```

### 3. Mock External Services

```python
@pytest.fixture
def mock_temporal():
    with patch("src.app.temporal.client.get_temporal_client") as mock:
        mock_client = AsyncMock()
        mock.return_value = mock_client
        yield mock_client
```

### 4. Use Descriptive Names

```python
# Good
def test_login_with_invalid_password_returns_401():
    ...

# Bad
def test_login():
    ...
```

### 5. Test Edge Cases

```python
class TestSlugValidation:
    def test_minimum_length(self):
        ...

    def test_maximum_length(self):
        ...

    def test_boundary_length_56_chars(self):
        ...

    def test_unicode_characters_rejected(self):
        ...
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync

      - name: Run tests
        run: uv run pytest --cov=src
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test
          JWT_SECRET_KEY: test-secret-key-for-ci-only-32chars
```

## Next Steps

- [Security Guide](../security.md) - Security testing details
- [Contributing Guide](../contributing.md) - Contributing tests
- [Deployment Guide](../production/deployment.md) - CI/CD setup
