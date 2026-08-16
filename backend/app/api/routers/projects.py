"""Project endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep, SuperUser
from app.crud.client_crud import client_crud
from app.crud.project_crud import project_crud
from app.schemas.common import ActiveToggle, MessageResponse, Page
from app.schemas.project_schema import (
    ProjectCreate,
    ProjectResponse,
    ProjectScheduleResponse,
    ProjectScheduleUpdate,
    ProjectUpdate,
    ProjectWithStats,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=Page[ProjectWithStats])
async def list_projects(
    session: SessionDep,
    pagination: PaginationDep,
    _: CurrentUser,
    client_id: int | None = Query(default=None),
):
    items = await project_crud.list_with_stats(
        session, client_id=client_id, skip=pagination.skip, limit=pagination.limit
    )
    total = await project_crud.count(
        session, filters={"client_id": client_id} if client_id else None
    )
    return Page[ProjectWithStats](
        items=items, total=total, skip=pagination.skip, limit=pagination.limit
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, session: SessionDep, _: SuperUser):
    parent = await client_crud.get(session, payload.client_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Client does not exist"
        )
    return await project_crud.create(session, payload)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, session: SessionDep, _: CurrentUser):
    project = await project_crud.get(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int, payload: ProjectUpdate, session: SessionDep, _: SuperUser
):
    project = await project_crud.get(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await project_crud.update(session, project, payload)


@router.get("/{project_id}/schedule", response_model=ProjectScheduleResponse)
async def get_project_schedule(project_id: int, session: SessionDep, _: CurrentUser):
    """Project default plus how many URLs follow it versus override it."""
    project = await project_crud.get(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    inheriting, overriding = await project_crud.count_schedule_modes(session, project_id)
    return ProjectScheduleResponse(
        project_id=project.id,
        default_check_interval=project.default_check_interval,
        default_execution_time=project.default_execution_time,
        default_timezone=project.default_timezone,
        inheriting_url_count=inheriting,
        overriding_url_count=overriding,
    )


@router.put("/{project_id}/schedule", response_model=ProjectScheduleResponse)
async def update_project_schedule(
    project_id: int,
    payload: ProjectScheduleUpdate,
    session: SessionDep,
    _: SuperUser,
):
    """Set the project cron default for every URL that inherits it.

    ``apply_to_all_urls`` additionally forces overriding URLs back to inheriting.
    It defaults to false because discarding deliberately staggered per-URL times
    is destructive and must be an explicit choice.
    """
    project = await project_crud.get(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    await project_crud.update(
        session,
        project,
        {
            "default_check_interval": payload.default_check_interval,
            "default_execution_time": payload.default_execution_time,
            "default_timezone": payload.default_timezone,
        },
    )

    if payload.apply_to_all_urls:
        await project_crud.force_inherit_all_urls(session, project_id)

    inheriting, overriding = await project_crud.count_schedule_modes(session, project_id)
    return ProjectScheduleResponse(
        project_id=project.id,
        default_check_interval=project.default_check_interval,
        default_execution_time=project.default_execution_time,
        default_timezone=project.default_timezone,
        inheriting_url_count=inheriting,
        overriding_url_count=overriding,
    )


@router.patch("/{project_id}/toggle", response_model=ProjectResponse)
async def toggle_project(
    project_id: int, payload: ActiveToggle, session: SessionDep, _: SuperUser
):
    project = await project_crud.get(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await project_crud.set_active(session, project, payload.is_active)


@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(project_id: int, session: SessionDep, _: SuperUser):
    deleted = await project_crud.remove(session, project_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return MessageResponse(detail="Project deleted")
