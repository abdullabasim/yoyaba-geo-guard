"""Task monitor endpoints and manual run triggers."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep, SuperUser
from app.crud.keyword_crud import keyword_crud
from app.crud.task_crud import task_log_crud
from app.crud.url_crud import target_url_crud
from app.models.enums import TaskStatus
from app.schemas.common import Page
from app.schemas.task_schema import (
    ManualRunRequest,
    ManualRunResponse,
    TaskExecutionLogResponse,
    TaskStatsResponse,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=Page[TaskExecutionLogResponse])
async def list_task_logs(
    session: SessionDep,
    pagination: PaginationDep,
    _: CurrentUser,
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    task_name: str | None = Query(default=None),
):
    """Feeds the live System Task Monitor table."""
    items = await task_log_crud.list_recent(
        session,
        status=task_status,
        task_name=task_name,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    total = await task_log_crud.count(session, status=task_status, task_name=task_name)
    return Page[TaskExecutionLogResponse](
        items=[TaskExecutionLogResponse.model_validate(item) for item in items],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/stats", response_model=TaskStatsResponse)
async def get_task_stats(
    session: SessionDep,
    _: CurrentUser,
    window_hours: int = Query(default=24, ge=1, le=720),
):
    return await task_log_crud.get_stats(session, window_hours=window_hours)


@router.post("/run", response_model=ManualRunResponse)
async def trigger_manual_run(
    payload: ManualRunRequest, session: SessionDep, _: SuperUser
):
    """Dispatch Task A immediately, bypassing the schedule.

    Imported inside the handler so the API process does not need the worker
    module resolved at import time.
    """
    from app.worker.tasks import dispatch_keyword_chain

    url_obj = await target_url_crud.get(session, payload.target_url_id)
    if url_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="URL not found")

    if payload.keyword_id is not None:
        keyword = await keyword_crud.get(session, payload.keyword_id)
        if keyword is None or keyword.target_url_id != url_obj.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Keyword does not belong to this URL",
            )
        keywords = [keyword]
    else:
        keywords = await keyword_crud.list_active_for_url(session, url_obj.id)

    if not keywords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active keywords for this URL",
        )

    task_ids: list[str] = []
    for keyword in keywords:
        async_result = dispatch_keyword_chain(
            url_obj.id, keyword.id, payload.force_analysis
        )
        task_ids.append(async_result.id)

    return ManualRunResponse(dispatched=len(task_ids), celery_task_ids=task_ids)


@router.get("/{log_id}", response_model=TaskExecutionLogResponse)
async def get_task_log(log_id: int, session: SessionDep, _: CurrentUser):
    log = await task_log_crud.get(session, log_id)
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task log not found"
        )
    return TaskExecutionLogResponse.model_validate(log)
