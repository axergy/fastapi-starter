"""Project endpoints - tenant-scoped CRUD example.

This module demonstrates tenant data isolation using TenantDBSession.
Each tenant has its own 'projects' table in their schema.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from src.app.api.dependencies import CurrentUser, TenantDBSession
from src.app.models.base import utc_now
from src.app.models.tenant import Project
from src.app.repositories.tenant import ProjectRepository
from src.app.schemas.pagination import PaginatedResponse
from src.app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get(
    "",
    response_model=PaginatedResponse[ProjectRead],
    summary="List projects",
    description="List all projects in the current tenant with cursor-based pagination.",
    responses={
        200: {"description": "Paginated list of projects"},
    },
)
async def list_projects(
    session: TenantDBSession,
    _user: CurrentUser,
    cursor: Annotated[str | None, Query(description="Cursor for pagination")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max items to return")] = 50,
) -> PaginatedResponse[ProjectRead]:
    """List all projects in tenant schema with cursor-based pagination."""
    repo = ProjectRepository(session)
    projects, next_cursor, has_more = await repo.list_all(cursor=cursor, limit=limit)
    return PaginatedResponse(
        items=[ProjectRead.model_validate(p) for p in projects],
        next_cursor=next_cursor,
        has_more=has_more,
    )


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
    _user: CurrentUser,
) -> ProjectRead:
    """Get a project by ID."""
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
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
        409: {"description": "Project with this name already exists"},
    },
)
async def create_project(
    request: ProjectCreate,
    session: TenantDBSession,
    _user: CurrentUser,
) -> ProjectRead:
    """Create a new project."""
    repo = ProjectRepository(session)

    # Check for duplicate name before creation
    existing = await repo.get_by_name(request.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{request.name}' already exists",
        )

    project = Project(
        name=request.name,
        description=request.description,
    )
    repo.add(project)

    try:
        await session.commit()
        await session.refresh(project)
    except IntegrityError as e:
        # Fallback in case of race condition
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{request.name}' already exists",
        ) from e
    except Exception:
        await session.rollback()
        raise

    return ProjectRead.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectRead,
    summary="Update project",
    description="Update an existing project. Requires X-Tenant-Slug header.",
    responses={
        200: {"description": "Project updated"},
        404: {"description": "Project not found"},
        409: {"description": "Project with this name already exists"},
    },
)
async def update_project(
    project_id: UUID,
    request: ProjectUpdate,
    session: TenantDBSession,
    _user: CurrentUser,
) -> ProjectRead:
    """Update an existing project."""
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Check for duplicate name if name is being updated
    if request.name is not None and request.name != project.name:
        existing = await repo.get_by_name(request.name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with name '{request.name}' already exists",
            )

    # Update only provided fields
    if request.name is not None:
        project.name = request.name
    if request.description is not None:
        project.description = request.description

    # Explicitly set updated_at timestamp since SQLModel doesn't support onupdate callbacks
    # This ensures the audit trail is maintained for all project modifications
    project.updated_at = utc_now()

    try:
        await session.commit()
        await session.refresh(project)
    except IntegrityError as e:
        # Fallback in case of race condition
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with name '{request.name}' already exists",
        ) from e
    except Exception:
        await session.rollback()
        raise

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
    _user: CurrentUser,
) -> None:
    """Delete a project."""
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    await session.delete(project)

    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete project due to existing references",
        ) from e
    except Exception:
        await session.rollback()
        raise
