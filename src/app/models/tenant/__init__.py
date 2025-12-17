"""Tenant-schema models.

This package contains SQLModel tables that exist in tenant schemas.
These tables are created via tenant migrations (not public migrations).
"""

from src.app.models.tenant.project import Project

__all__ = ["Project"]
