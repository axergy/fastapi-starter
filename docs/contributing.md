# Contributing Guide

Thank you for your interest in contributing to the FastAPI Multi-Tenant SaaS Starter! This guide will help you get started.

## Code of Conduct

Please be respectful and constructive in all interactions. We're building something together.

## Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/fastapi-starter.git
cd fastapi-starter
```

### 2. Set Up Development Environment

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Copy environment file
cp .env.example .env

# Start services
make docker-up
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

## Development Workflow

### Running the Application

```bash
# Start API in development mode
make dev

# Start Temporal worker (separate terminal)
make worker
```

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific tests
pytest tests/unit/test_security.py -v
```

### Code Quality

```bash
# Format code
make format

# Run linter
make lint

# Type checking
make typecheck
```

## Code Style

### Python Style

We use [ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
```

### Type Annotations

All code should have type annotations:

```python
# Good
async def get_user_by_email(email: str) -> User | None:
    ...

# Bad
async def get_user_by_email(email):
    ...
```

### Docstrings

Use clear, concise docstrings:

```python
async def create_tenant(self, data: TenantCreate) -> Tenant:
    """Create a new tenant with provisioning workflow.

    Args:
        data: Tenant creation data including name and slug.

    Returns:
        The created tenant in provisioning state.

    Raises:
        TenantSlugExistsError: If slug is already taken.
    """
    ...
```

### Async-First

Prefer async functions throughout:

```python
# Good
async def fetch_data() -> Data:
    async with get_session() as session:
        result = await session.execute(select(Data))
        return result.scalar_one()

# Avoid (unless necessary)
def fetch_data_sync() -> Data:
    ...
```

## Migration Guidelines

### Creating Migrations

When adding database changes:

```bash
# Auto-generate migration
alembic revision --autogenerate -m "Add new table"
```

### Migration Requirements

1. **Always use `is_tenant_migration()` guard**:

```python
from src.alembic.migration_utils import is_tenant_migration

def upgrade() -> None:
    if is_tenant_migration():
        return  # Skip for tenant migrations

    # Public schema changes...

def downgrade() -> None:
    if is_tenant_migration():
        return

    # Rollback changes...
```

2. **Specify schema explicitly** for public tables:

```python
op.create_table(
    "new_table",
    sa.Column("id", sa.UUID(), nullable=False),
    schema="public",  # REQUIRED for public schema
)
```

3. **Test both paths**:

```bash
# Test public migration
alembic upgrade head

# Test tenant migration
alembic upgrade head --tag=tenant_test
```

### Migration Checklist

- [ ] Added `is_tenant_migration()` guard
- [ ] Specified `schema="public"` for public tables
- [ ] Tested upgrade path
- [ ] Tested downgrade path
- [ ] Reviewed auto-generated SQL

## Pull Request Process

### 1. Before Submitting

- [ ] All tests pass (`make test`)
- [ ] Code is formatted (`make format`)
- [ ] Linter passes (`make lint`)
- [ ] Type checking passes (`make typecheck`)
- [ ] Added tests for new functionality
- [ ] Updated documentation if needed

### 2. PR Description

Include in your PR description:

```markdown
## Summary
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How did you test these changes?

## Related Issues
Fixes #123
```

### 3. Review Process

1. Submit PR against `main` branch
2. Automated checks run (tests, linting)
3. Code review by maintainers
4. Address feedback
5. Squash and merge

## Security Reporting

### Reporting Vulnerabilities

**Do not** open public issues for security vulnerabilities.

Instead:
1. Email security@your-domain.com
2. Include detailed description
3. Provide steps to reproduce
4. Allow 90 days for fix before disclosure

### Security-Sensitive Code

Extra care required when modifying:

- `src/app/core/security/` - Authentication, validation
- `src/app/api/dependencies/auth.py` - Authorization
- `src/alembic/env.py` - Schema handling
- Any code handling user input in SQL contexts

## Testing Requirements

### New Features

Every new feature should include:

1. **Unit tests** for business logic
2. **Integration tests** for API endpoints
3. **Security tests** if handling user input

### Test Coverage

Maintain test coverage for critical paths:

```bash
# Check coverage
pytest --cov=src --cov-report=html

# View report
open htmlcov/index.html
```

### Test Naming

Use descriptive test names:

```python
# Good
def test_login_with_invalid_password_returns_401():
    ...

def test_schema_name_with_sql_injection_is_rejected():
    ...

# Bad
def test_login():
    ...

def test_validation():
    ...
```

## Documentation

### When to Update Docs

Update documentation when:

- Adding new features
- Changing API endpoints
- Modifying configuration options
- Changing security behavior

### Documentation Style

- Use clear, concise language
- Include code examples
- Add diagrams for complex flows
- Keep sections focused

## Project Structure

When adding new files, follow the existing structure:

```
src/app/
├── api/              # HTTP layer (routes, dependencies)
├── core/             # Configuration, utilities
├── models/           # Database models
├── schemas/          # Pydantic DTOs
├── repositories/     # Data access
├── services/         # Business logic
└── temporal/         # Background workflows
```

### Where to Put New Code

| Type | Location |
|------|----------|
| New endpoint | `src/app/api/v1/` |
| Business logic | `src/app/services/` |
| Database access | `src/app/repositories/` |
| Data models | `src/app/models/` |
| Request/Response schemas | `src/app/schemas/` |
| Utilities | `src/app/core/` |
| Background workflows | `src/app/temporal/` |

## Common Tasks

### Adding a New API Endpoint

1. Create/update schema in `src/app/schemas/`
2. Create/update service in `src/app/services/`
3. Add endpoint in `src/app/api/v1/`
4. Add tests in `tests/`

### Adding a New Model

1. Define model in `src/app/models/`
2. Create migration: `alembic revision --autogenerate -m "Add model"`
3. Add repository in `src/app/repositories/`
4. Add tests

### Adding a New Service

1. Create service class in `src/app/services/`
2. Add dependency in `src/app/api/dependencies/services.py`
3. Add tests in `tests/unit/`

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Security**: Email security@your-domain.com

## Recognition

Contributors are recognized in:
- GitHub contributors page
- Release notes
- Project documentation

Thank you for contributing!
