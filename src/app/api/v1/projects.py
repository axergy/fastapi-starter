"""Project endpoints - tenant-scoped CRUD example.

This module demonstrates tenant data isolation using TenantDBSession.
Each tenant has its own 'projects' table in their schema.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.app.api.dependencies import AuthenticatedUser, TenantDBSession
from src.app.models.base import utc_now
from src.app.models.tenant import Project
from src.app.repositories.tenant import ProjectRepository
from src.app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get(
    "",
    response_model=list[ProjectRead],
    summary="List projects",
    description="List all projects in the current tenant. Requires X-Tenant-Slug header.",
    responses={
        200: {"description": "List of projects"},
    },
)
async def list_projects(
    session: TenantDBSession,
    _user: AuthenticatedUser,
    limit: Annotated[int, Query(ge=1, le=100, description="Max items to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> list[ProjectRead]:
    """List all projects in tenant schema."""
    repo = ProjectRepository(session)
    projects = await repo.list_all(limit=limit, offset=offset)
    return [ProjectRead.model_validate(p) for p in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
    summary="Get project",
    description="Get a project by ID. Requires X-Tenant-Slug header.",
    responses={
        200: {"description": "Project details"},
        404: {"description": "Project not found"},
    },
)
async def get_project(
    project_id: UUID,
    session: TenantDBSession,
    _user: AuthenticatedUser,
) -> ProjectRead:
    """Get a project by ID."""
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return ProjectRead.model_validate(project)


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new project in the current tenant. Requires X-Tenant-Slug header.",
    responses={
        201: {"description": "Project created"},
    },
)
async def create_project(
    request: ProjectCreate,
    session: TenantDBSession,
    _user: AuthenticatedUser,
) -> ProjectRead:
    """Create a new project."""
    repo = ProjectRepository(session)

    project = Project(
        name=request.name,
        description=request.description,
    )
    repo.add(project)
    await session.commit()
    await session.refresh(project)

    return ProjectRead.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    summary="Update project",
    description="Update an existing project. Requires X-Tenant-Slug header.",
    responses={
        200: {"description": "Project updated"},
        404: {"description": "Project not found"},
    },
)
async def update_project(
    project_id: UUID,
    request: ProjectUpdate,
    session: TenantDBSession,
    _user: AuthenticatedUser,
) -> ProjectRead:
    """Update an existing project."""
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Update only provided fields
    if request.name is not None:
        project.name = request.name
    if request.description is not None:
        project.description = request.description

    project.updated_at = utc_now()
    await session.commit()
    await session.refresh(project)

    return ProjectRead.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Delete a project. Requires X-Tenant-Slug header.",
    responses={
        204: {"description": "Project deleted"},
        404: {"description": "Project not found"},
    },
)
async def delete_project(
    project_id: UUID,
    session: TenantDBSession,
    _user: AuthenticatedUser,
) -> None:
    """Delete a project."""
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    await session.delete(project)
    await session.commit()
