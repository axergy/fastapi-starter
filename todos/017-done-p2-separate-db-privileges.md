---
id: "017"
title: "Separate DB Privileges"
status: pending
priority: p2
source: "REVIEW.md - HIGH #8"
category: security-enhancement
---

# Separate DB Privileges

## Problem

Same database URL (and thus same DB role) is used for both runtime operations (CRUD) and migrations (DDL). This violates the principle of least privilege.

## Risk

- **Excessive privileges**: Runtime app has DDL permissions it doesn't need
- **SQL injection escalation**: Compromised app can DROP tables
- **Audit trail**: Can't distinguish app operations from migrations

## Verified Findings

| Location | Line | Issue |
|----------|------|-------|
| `src/app/core/config.py` | 29 | Only `database_url: str` exists |
| `src/alembic/env.py` | 24 | Uses `get_settings().database_url` |
| - | - | No separation between runtime and migration DB roles |

### Ideal Setup

```
app_runtime role:   SELECT, INSERT, UPDATE, DELETE on tables
app_migrator role:  CREATE, ALTER, DROP, plus app_runtime grants
```

## Fix (Future Enhancement)

1. Add optional `database_migrations_url` config
2. Use migrations URL in alembic env.py when set
3. Document recommended DB role setup

### Code Changes

**src/app/core/config.py:**
```python
class Settings(BaseSettings):
    database_url: str
    database_migrations_url: str | None = None  # Optional separate migration URL
```

**src/alembic/env.py:**
```python
def get_database_url() -> str:
    """Get database URL for migrations, preferring dedicated migrations URL."""
    settings = get_settings()
    return settings.database_migrations_url or settings.database_url
```

### Recommended DB Setup

```sql
-- Runtime role (app uses this)
CREATE ROLE app_runtime WITH LOGIN PASSWORD '...';
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO app_runtime;

-- Migration role (alembic uses this)
CREATE ROLE app_migrator WITH LOGIN PASSWORD '...';
GRANT app_runtime TO app_migrator;  -- Inherits runtime permissions
GRANT CREATE ON SCHEMA public TO app_migrator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_migrator;
```

## Files to Modify

- `src/app/core/config.py`
- `src/alembic/env.py`
- `src/app/core/db/migrations.py` (if exists)
- Documentation for DB setup

## Acceptance Criteria

- [ ] `database_migrations_url` config option added (optional)
- [ ] Alembic uses migrations URL when set, falls back to database_url
- [ ] Documentation for recommended DB role separation
- [ ] Works with existing single-URL setup (backwards compatible)
