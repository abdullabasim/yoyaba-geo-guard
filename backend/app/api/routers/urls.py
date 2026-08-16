"""TargetURL endpoints, including the dynamic scheduling form."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep, SuperUser
from app.crud.keyword_crud import keyword_crud
from app.crud.project_crud import project_crud
from app.crud.url_crud import target_url_crud
from app.schemas.common import ActiveToggle, MessageResponse, Page
from app.schemas.keyword_schema import KeywordCreate
from app.schemas.url_schema import (
    InheritScheduleUpdate,
    ScheduleUpdate,
    TargetURLCreate,
    TargetURLResponse,
    TargetURLUpdate,
    TargetURLWithStats,
)

router = APIRouter(prefix="/urls", tags=["urls"])


@router.get("", response_model=Page[TargetURLWithStats])
async def list_urls(
    session: SessionDep,
    pagination: PaginationDep,
    _: CurrentUser,
    project_id: int | None = Query(default=None),
):
    items = await target_url_crud.list_with_stats(
        session, project_id=project_id, skip=pagination.skip, limit=pagination.limit
    )
    total = await target_url_crud.count(
        session, filters={"project_id": project_id} if project_id else None
    )
    return Page[TargetURLWithStats](
        items=items, total=total, skip=pagination.skip, limit=pagination.limit
    )


@router.post("", response_model=TargetURLResponse, status_code=status.HTTP_201_CREATED)
async def create_url(payload: TargetURLCreate, session: SessionDep, _: SuperUser):
    parent = await project_crud.get(session, payload.project_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Project does not exist"
        )
    existing = await target_url_crud.get_by_url_for_project(
        session, payload.project_id, payload.url
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This URL is already tracked in the project",
        )
    initial_kws = payload.initial_keywords
    url_data = payload.model_dump(exclude={"initial_keywords"})
    url_obj = await target_url_crud.create(session, url_data)

    if initial_kws:
        for kw in initial_kws:
            cleaned = kw.strip()
            if cleaned:
                try:
                    await keyword_crud.create(
                        session,
                        KeywordCreate(
                            target_url_id=url_obj.id,
                            keyword_text=cleaned,
                        ),
                    )
                except Exception:
                    pass  # Skip duplicate or invalid keywords silently

    return url_obj


@router.get("/due", response_model=list[TargetURLResponse])
async def list_due_urls(
    session: SessionDep,
    _: CurrentUser,
    window_minutes: int = Query(default=30, ge=1, le=1440),
):
    """Diagnostic view of exactly what Beat would dispatch right now."""
    return await target_url_crud.list_due(session, window_minutes=window_minutes)


@router.get("/{url_id}", response_model=TargetURLResponse)
async def get_url(url_id: int, session: SessionDep, _: CurrentUser):
    url_obj = await target_url_crud.get(session, url_id)
    if url_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")
    return url_obj


@router.patch("/{url_id}", response_model=TargetURLResponse)
async def update_url(
    url_id: int, payload: TargetURLUpdate, session: SessionDep, _: SuperUser
):
    url_obj = await target_url_crud.get(session, url_id)
    if url_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")
    return await target_url_crud.update(session, url_obj, payload)


@router.put("/{url_id}/schedule", response_model=TargetURLResponse)
async def update_schedule(
    url_id: int, payload: ScheduleUpdate, session: SessionDep, _: SuperUser
):
    """Dedicated endpoint for the interval / execution-time / timezone form."""
    url_obj = await target_url_crud.get(session, url_id)
    if url_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")
    return await target_url_crud.update(session, url_obj, payload.model_dump())


@router.patch("/{url_id}/inherit-schedule", response_model=TargetURLResponse)
async def set_schedule_inheritance(
    url_id: int,
    payload: InheritScheduleUpdate,
    session: SessionDep,
    _: SuperUser,
):
    """Switch a URL between its project's default schedule and its own.

    Turning inheritance off keeps whatever is stored in the URL's own columns,
    so the schedule never becomes blank.
    """
    url_obj = await target_url_crud.get(session, url_id)
    if url_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")
    return await target_url_crud.update(
        session, url_obj, {"inherit_schedule": payload.inherit_schedule}
    )


@router.patch("/{url_id}/toggle", response_model=TargetURLResponse)
async def toggle_url(
    url_id: int, payload: ActiveToggle, session: SessionDep, _: SuperUser
):
    url_obj = await target_url_crud.get(session, url_id)
    if url_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")
    return await target_url_crud.set_active(session, url_obj, payload.is_active)


@router.delete("/{url_id}", response_model=MessageResponse)
async def delete_url(url_id: int, session: SessionDep, _: SuperUser):
    deleted = await target_url_crud.remove(session, url_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")
    return MessageResponse(detail="Target URL deleted")
