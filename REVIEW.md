Critical (legacy removal / dead code)
1) Delete redundant migration 002_add_tenant_status (it’s already in 001)

Why: In the provided migrations, 001_initial already creates public.tenants.status

code

, yet 002_add_tenant_status conditionally adds the same column again

code

. This is classic “historical artifact” that makes the template harder to understand.

Change: delete the file and re-point 003 to 001.

diff --git a/src/alembic/versions/002_add_tenant_status.py b/src/alembic/versions/002_add_tenant_status.py
deleted file mode 100644
index 4b6d7a1..0000000
--- a/src/alembic/versions/002_add_tenant_status.py
+++ /dev/null
@@ -1,69 +0,0 @@
-"""add tenant status column
-...

diff --git a/src/alembic/versions/003_add_performance_indexes.py b/src/alembic/versions/003_add_performance_indexes.py
index 2a1b9a0..e3c4d1f 100644
--- a/src/alembic/versions/003_add_performance_indexes.py
+++ b/src/alembic/versions/003_add_performance_indexes.py
@@
-revision = "003"
-down_revision = "002"
+revision = "003"
+down_revision = "001"


Also update the header comment in 003 (“Revises: 002” → “Revises: 001”) if present, so the file reads cleanly.

Note: This is ideal for a starter template (new DBs). If you must support already-deployed DBs that stamped/ran 002, keep it in a legacy branch/tag rather than shipping it in the clean template.

2) Remove placeholder / future-planning blocks in migrations (especially 001)

Why: 001_initial still contains a tenant-tag branch that does nothing except a placeholder comment (“Future tenant-specific tables go here”)

code

. That’s dead code in practice and is exactly the kind of template cruft that confuses maintainers.

Change: make it a clean “public-only migration” with an early return (and do the same in downgrade).

diff --git a/src/alembic/versions/001_initial.py b/src/alembic/versions/001_initial.py
index 6b9a0f1..9c52f5a 100644
--- a/src/alembic/versions/001_initial.py
+++ b/src/alembic/versions/001_initial.py
@@
-from alembic import context, op
+from alembic import op
+from src.alembic.migration_utils import is_tenant_migration
@@
 def upgrade():
-    schema = context.get_tag_argument()
-    if schema:
-        # Future tenant-specific tables go here
-        pass
-    else:
-        # Create public schema tables
+    if is_tenant_migration():
+        return
+    # Create public schema tables
     op.create_table(
         ...
     )
@@
 def downgrade():
-    schema = context.get_tag_argument()
-    if schema:
-        pass
-    else:
-        op.drop_table("user_tenant_membership", schema="public")
-        ...
+    if is_tenant_migration():
+        return
+    op.drop_table("user_tenant_membership", schema="public")
+    ...

3) Delete “xfail + TODO doc reference” integration test that encodes legacy expectations

Why: tests/integration/test_provisioning.py includes an xfail test that’s literally documenting behavior you don’t implement and points to a TODO markdown file

code

. That’s noise in a template repo and will rot.

Change: remove the whole test, and rewrite the comment in the remaining test to state what’s actually being verified.

diff --git a/tests/integration/test_provisioning.py b/tests/integration/test_provisioning.py
index 8d7c2ad..a3bd8a1 100644
--- a/tests/integration/test_provisioning.py
+++ b/tests/integration/test_provisioning.py
@@
 class TestProvisioningLifecycle:
@@
-    @pytest.mark.xfail(
-        reason="Registration service doesn't yet create workflow_execution records. "
-        "See todos/016-done-p1-workflow-execution-observability.md for the activity "
-        "that updates status - registration service needs to create initial record."
-    )
-    async def test_registration_creates_workflow_execution(...):
-        ...
-
     async def test_tenant_transitions_to_ready(...):
@@
-        # NOTE: To test the full transition to "ready" status, we would need to:
-        # 1. Either use a real Temporal worker (integration test), OR
-        # 2. Directly call the workflow completion activity
-        # For now, this test verifies the initial provisioning state.
-        # Full workflow integration testing should be added when Temporal test
-        # infrastructure is set up.
+        # This test intentionally verifies the *initial* provisioning state because
+        # Temporal is mocked in this suite.


That removes both the dead expectation and the future-planning comment block

code

.

High (DRY wins)
4) Add a shared Alembic helper for “public-only migration skips” and apply everywhere

Why: Many migrations repeat if context.get_tag_argument(): return and import context only for that

code

. This is exactly the sort of repetition that causes inconsistent behavior over time.

Add a helper:

diff --git a/src/alembic/migration_utils.py b/src/alembic/migration_utils.py
new file mode 100644
--- /dev/null
+++ b/src/alembic/migration_utils.py
@@
+from __future__ import annotations
+
+from alembic import context
+
+
+def is_tenant_migration() -> bool:
+    """True when Alembic was invoked with `--tag=<tenant_schema>`.
+
+    In this codebase, tags are used to indicate tenant-schema migrations.
+    Public-schema migrations must no-op in that mode.
+    """
+    return bool(context.get_tag_argument())


Apply it to each public migration (mechanical change):

Replace from alembic import context, op → from alembic import op + from src.alembic.migration_utils import is_tenant_migration

Replace the guard with:

if is_tenant_migration():
    return


Example (004 shown; same pattern across 003–015)

code

:

diff --git a/src/alembic/versions/004_add_workflow_executions.py b/src/alembic/versions/004_add_workflow_executions.py
index 1d2c9f4..c4a2f4d 100644
--- a/src/alembic/versions/004_add_workflow_executions.py
+++ b/src/alembic/versions/004_add_workflow_executions.py
@@
-from alembic import context, op
+from alembic import op
+from src.alembic.migration_utils import is_tenant_migration
@@
 def upgrade():
-    # Skip if running tenant schema migrations (this is public schema only)
-    if context.get_tag_argument():
-        return
+    if is_tenant_migration():
+        return
@@
 def downgrade():
-    # Skip if running tenant schema migrations
-    if context.get_tag_argument():
-        return
+    if is_tenant_migration():
+        return


This simultaneously removes repeated comments and unused imports across the migration set.

5) Centralize tenant identifier constants + slug validation (remove repeated regex + “56” literals)

Why: The same slug rules are duplicated in:

RegisterRequest validator

code

TenantCreate validator

code

property-based tests hardcode <= 56 all over

code

the Tenant model computes MAX_SLUG_LENGTH = 63 - len("tenant_") inline

code

Goal: One source of truth in core/security/validators.py, used by models, schemas, and tests.

5a) Replace validators.py with a single canonical implementation

(Your code dump contains multiple versions of this file; this replacement removes ambiguity and centralizes constants.)

diff --git a/src/app/core/security/validators.py b/src/app/core/security/validators.py
index 3f1c2ab..9d1b7c1 100644
--- a/src/app/core/security/validators.py
+++ b/src/app/core/security/validators.py
@@
-"""Security validators for tenant schema names."""
-
-import re
-from typing import Final
-
-MAX_SCHEMA_LENGTH: Final[int] = 63  # PostgreSQL identifier limit
-
-# Forbidden patterns to prevent SQL injection and reserved names
-FORBIDDEN_PATTERNS: Final[list[str]] = [
-    ";",
-    "--",
-    "/*",
-    "*/",
-    "pg_",
-    "information_schema",
-    "public",
-]
-
-# Schema name must start with tenant_ and contain only lowercase letters, numbers, and underscores
-# The slug part must start with a letter and not end with underscore
-_SCHEMA_NAME_PATTERN = re.compile(r"^tenant_[a-z][a-z0-9]*(_[a-z0-9]+)*$")
-
-
-def validate_schema_name(schema_name: str) -> None:
-    """Validate schema name for safety.
-    ...
-    """
-    ...
+"""Security validators.
+
+Single source of truth for tenant identifier rules (slug + schema name).
+
+This module is intentionally dependency-light so it can be imported from:
+- request schemas (Pydantic)
+- models
+- Alembic env/migrations
+- test utilities
+"""
+
+from __future__ import annotations
+
+import re
+from typing import Final
+
+MAX_SCHEMA_LENGTH: Final[int] = 63  # PostgreSQL identifier limit
+TENANT_SCHEMA_PREFIX: Final[str] = "tenant_"
+
+# Slug is the portion after `tenant_`. Keep total identifier length <= 63.
+MAX_TENANT_SLUG_LENGTH: Final[int] = MAX_SCHEMA_LENGTH - len(TENANT_SCHEMA_PREFIX)
+
+# NOTE: Keep these regexes consistent with DB constraints (see migration 010).
+TENANT_SLUG_REGEX: Final[str] = r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$"
+TENANT_SCHEMA_NAME_REGEX: Final[str] = (
+    rf"^{TENANT_SCHEMA_PREFIX}[a-z][a-z0-9]*(_[a-z0-9]+)*$"
+)
+
+FORBIDDEN_PATTERNS: Final[tuple[str, ...]] = (
+    ";",
+    "--",
+    "/*",
+    "*/",
+    "pg_",
+    "information_schema",
+    "public",
+)
+
+_TENANT_SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(TENANT_SLUG_REGEX)
+_TENANT_SCHEMA_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(TENANT_SCHEMA_NAME_REGEX)
+
+
+def validate_tenant_slug_format(slug: str) -> str:
+    """Validate tenant slug format (no `tenant_` prefix).
+
+    This validates **format only**. Length is enforced by Field(max_length=...),
+    DB constraints, and schema-name validation.
+    """
+    if not _TENANT_SLUG_PATTERN.match(slug):
+        # Keep message stable; tests expect this wording.
+        raise ValueError(
+            "Slug must start with a letter and contain only lowercase letters, numbers, "
+            "and single underscores as separators"
+        )
+    return slug
+
+
+def validate_schema_name(schema_name: str) -> str:
+    """Validate tenant schema name for safety."""
+    if not schema_name:
+        raise ValueError("Schema name cannot be empty")
+
+    if len(schema_name) > MAX_SCHEMA_LENGTH:
+        raise ValueError(
+            f"Schema name exceeds PostgreSQL limit of {MAX_SCHEMA_LENGTH} characters"
+        )
+
+    schema_lower = schema_name.lower()
+    for pattern in FORBIDDEN_PATTERNS:
+        if pattern in schema_name or pattern in schema_lower:
+            raise ValueError(f"Schema name contains forbidden pattern: {pattern}")
+
+    if not _TENANT_SCHEMA_NAME_PATTERN.match(schema_name):
+        raise ValueError(
+            "Invalid schema name format. Must start with 'tenant_' and contain only lowercase letters, "
+            "numbers, and underscores. Must have exactly one underscore after 'tenant' and no consecutive "
+            "or trailing underscores."
+        )
+
+    return schema_name

5b) Tenant model: stop recomputing slug length + stop hardcoding "tenant_"
diff --git a/src/app/models/public/tenant.py b/src/app/models/public/tenant.py
index 4a5b31c..2f3b5d4 100644
--- a/src/app/models/public/tenant.py
+++ b/src/app/models/public/tenant.py
@@
-from src.app.core.security.validators import MAX_SCHEMA_LENGTH, validate_schema_name
+from src.app.core.security.validators import (
+    MAX_SCHEMA_LENGTH,
+    MAX_TENANT_SLUG_LENGTH,
+    TENANT_SCHEMA_PREFIX,
+    validate_schema_name,
+)
@@
-# Max slug length: PostgreSQL limit (63) - prefix length (7 for "tenant_")
-MAX_SLUG_LENGTH = MAX_SCHEMA_LENGTH - len("tenant_")  # 56
+# Backwards-compatible alias (tests import MAX_SLUG_LENGTH today).
+MAX_SLUG_LENGTH = MAX_TENANT_SLUG_LENGTH
@@
     @property
     def schema_name(self) -> str:
-        """Compute schema name from tenant slug."""
-        schema_name = f"tenant_{self.slug}"
+        """Compute schema name from tenant slug."""
+        schema_name = f"{TENANT_SCHEMA_PREFIX}{self.slug}"
         validate_schema_name(schema_name)
         return schema_name


This removes the inline duplication

code

 and makes “tenant_” a single constant.

5c) Schemas: reuse the shared slug validator + shared max length

Auth schema (RegisterRequest) currently repeats the regex and message

code

:

diff --git a/src/app/schemas/auth.py b/src/app/schemas/auth.py
index 9f2c1b1..ddc9c56 100644
--- a/src/app/schemas/auth.py
+++ b/src/app/schemas/auth.py
@@
-import re
@@
 from pydantic import BaseModel, EmailStr, Field, field_validator
@@
+from src.app.core.security.validators import (
+    MAX_TENANT_SLUG_LENGTH,
+    validate_tenant_slug_format,
+)
@@
-    tenant_slug: str = Field(..., max_length=56)
+    tenant_slug: str = Field(..., max_length=MAX_TENANT_SLUG_LENGTH)
@@
     @field_validator("tenant_slug")
     @classmethod
     def validate_slug(cls, v: str) -> str:
-        if not re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", v):
-            raise ValueError(
-                "Slug must start with a letter and contain only lowercase letters, numbers, "
-                "and single underscores as separators"
-            )
-        return v
+        return validate_tenant_slug_format(v)


Tenant schema (TenantCreate) currently repeats the same logic

code

:

diff --git a/src/app/schemas/tenant.py b/src/app/schemas/tenant.py
index 3a0b4d1..b8c0d92 100644
--- a/src/app/schemas/tenant.py
+++ b/src/app/schemas/tenant.py
@@
-import re
@@
 from pydantic import BaseModel, Field, field_validator
@@
+from src.app.core.security.validators import (
+    MAX_TENANT_SLUG_LENGTH,
+    validate_tenant_slug_format,
+)
@@
-    slug: str = Field(..., min_length=1, max_length=56)
+    slug: str = Field(..., min_length=1, max_length=MAX_TENANT_SLUG_LENGTH)
@@
     @field_validator("slug")
     @classmethod
     def validate_slug(cls, v: str) -> str:
-        if not re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", v):
-            raise ValueError(
-                "Slug must start with a letter and contain only lowercase letters, numbers, "
-                "and single underscores as separators"
-            )
-        return v
+        return validate_tenant_slug_format(v)

5d) Tests: remove hardcoded 56/57 and reuse constants

Property tests currently hardcode length bounds everywhere

code

.

diff --git a/tests/unit/test_validators_property.py b/tests/unit/test_validators_property.py
index 0c2b1f0..68b4c82 100644
--- a/tests/unit/test_validators_property.py
+++ b/tests/unit/test_validators_property.py
@@
 from src.app.schemas.tenant import TenantCreate
+from src.app.core.security.validators import MAX_TENANT_SLUG_LENGTH, TENANT_SLUG_REGEX
@@
-valid_slug = st.from_regex(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", fullmatch=True).filter(
-    lambda s: 1 <= len(s) <= 56
-)
+valid_slug = st.from_regex(TENANT_SLUG_REGEX, fullmatch=True).filter(
+    lambda s: 1 <= len(s) <= MAX_TENANT_SLUG_LENGTH
+)
@@
-@given(slug=st.text(min_size=57, max_size=100))
+@given(slug=st.text(min_size=MAX_TENANT_SLUG_LENGTH + 1, max_size=100))
 def test_long_slugs_rejected(slug: str):
-    """Slugs longer than 56 characters should be rejected."""
+    """Slugs longer than MAX_TENANT_SLUG_LENGTH should be rejected."""

6) DRY the deterministic workflow_id generation (stop duplicating the format string)

Why: You already have a canonical workflow ID builder in TenantService.get_workflow_id()

code

, but RegistrationService re-implements the string format inline

code

.

Change:

diff --git a/src/app/services/registration_service.py b/src/app/services/registration_service.py
index 51a8c3b..0f0e0e1 100644
--- a/src/app/services/registration_service.py
+++ b/src/app/services/registration_service.py
@@
-from src.app.services.tenant_service import TenantService
+from src.app.services.tenant_service import TenantService
@@
-        workflow_id = f"tenant-provision-{req.tenant_slug}"
+        workflow_id = TenantService.get_workflow_id(req.tenant_slug)


This is a pure DRY/readability win (no behavior change).

Medium (consistency / readability)
7) Tests: stop duplicating rate-limit reset logic and align tests to the current key strategy

Your conftest already provides reset_rate_limit_buckets

code

, but the rate limit tests also define their own autouse reset fixture (duplicated) in at least one version of the file in the dump. Keep it single-source.

Change (pattern):

@@
-@pytest.fixture(autouse=True)
-def _reset_rate_limit_state():
-    ...
+@pytest.fixture(autouse=True)
+def _reset_rate_limit_state(reset_rate_limit_buckets):
+    # Delegate to shared fixture in tests/conftest.py
+    yield


Also: your code dump contains two conflicting versions of the rate-limit key behavior (one uses IP+tenant header, one explicitly warns not to)

code



code

. Keep only the “IP-only, tenant header ignored” version (the one with the warning), and delete the older one. Then ensure the unit test matches that behavior (the newer test already does in the dump).

If you want a concrete patch to enforce the “IP-only” behavior (and remove legacy logic):

diff --git a/src/app/core/rate_limit.py b/src/app/core/rate_limit.py
index 7d9ab12..b3aa8d9 100644
--- a/src/app/core/rate_limit.py
+++ b/src/app/core/rate_limit.py
@@
 def get_rate_limit_key(request: Request) -> str:
@@
-    tenant_id = request.headers.get("X-Tenant-ID")
-    if tenant_id:
-        return f"{ip}:{tenant_id}"
-    return ip
+    # Deliberately ignore tenant header to prevent user-controlled partitioning.
+    return ip

8) Cleanup utils: reuse the real schema validator instead of re-implementing it in tests

Why: tests/utils/cleanup.py duplicates schema validation with its own regex and length checks

code

. That’s unnecessary and becomes inconsistent over time.

Change:

diff --git a/tests/utils/cleanup.py b/tests/utils/cleanup.py
index 1c2f0a1..2e4e7a9 100644
--- a/tests/utils/cleanup.py
+++ b/tests/utils/cleanup.py
@@
-import re
-from typing import Final
-
-MAX_SCHEMA_LENGTH: Final[int] = 63
-_SCHEMA_NAME_PATTERN: Final = re.compile(r"^tenant_[a-z][a-z0-9]*(_[a-z0-9]+)*$")
+from src.app.core.security.validators import validate_schema_name
@@
 def _validate_schema_name_for_drop(schema_name: str) -> None:
-    if not schema_name or not schema_name.startswith("tenant_"):
-        raise ValueError("Invalid schema name for cleanup")
-    if len(schema_name) > MAX_SCHEMA_LENGTH:
-        raise ValueError("Schema name too long for cleanup")
-    if not _SCHEMA_NAME_PATTERN.match(schema_name):
-        raise ValueError("Invalid schema name format for cleanup")
+    validate_schema_name(schema_name)

Polish (comments / style)
9) Remove “TODO/placeholder” language from tenant package stubs

These are template leftovers (models + repositories tenant packages)

code

. Keep the packages, but make them neutral.

diff --git a/src/app/models/tenant/__init__.py b/src/app/models/tenant/__init__.py
index 19bcad1..90b7d22 100644
--- a/src/app/models/tenant/__init__.py
+++ b/src/app/models/tenant/__init__.py
@@
-"""Tenant-specific models.
-
-Tenant-specific data models go in models/tenant/ directory.
-These are separate from public schema models.
-"""
+"""Tenant-schema models.
+
+This package is reserved for schema-per-tenant SQLModel tables.
+"""
@@
-# Add tenant-specific business models here as you build your application
 __all__ = []

diff --git a/src/app/repositories/tenant/__init__.py b/src/app/repositories/tenant/__init__.py
index 77caa11..6c7c912 100644
--- a/src/app/repositories/tenant/__init__.py
+++ b/src/app/repositories/tenant/__init__.py
@@
-"""Tenant-specific repositories.
-
-These repositories handle data access for tenant-specific tables.
-"""
+"""Tenant-schema repositories."""
@@
-# Add tenant-specific repositories here
 __all__ = []

10) Remove “TODO #002” wording from regression test docstrings

Example: tests/integration/test_invite_transaction_boundary.py starts with “Tests for TODO #002 …”

code

. Rename it to “Regression tests: Accept-invite transaction boundary” (same meaning, no internal tracker leakage).
