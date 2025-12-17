from __future__ import annotations

from alembic import context


def is_tenant_migration() -> bool:
    """True when Alembic was invoked with `--tag=<tenant_schema>`.

    In this codebase, tags are used to indicate tenant-schema migrations.
    Public-schema migrations must no-op in that mode.
    """
    return bool(context.get_tag_argument())
