"""AI alert endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep
from app.crud.alert_crud import alert_crud
from app.models.enums import IssueType
from app.schemas.alert_schema import AIAlertDetail, AIAlertStats
from app.schemas.common import MessageResponse, Page

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=Page[AIAlertDetail])
async def list_alerts(
    session: SessionDep,
    pagination: PaginationDep,
    _: CurrentUser,
    issue_type: IssueType | None = Query(default=None),
    client_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
):
    items = await alert_crud.list_detailed(
        session,
        issue_type=issue_type,
        client_id=client_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    total = await alert_crud.count(
        session, issue_type=issue_type, client_id=client_id, search=search
    )
    return Page[AIAlertDetail](
        items=items, total=total, skip=pagination.skip, limit=pagination.limit
    )


@router.get("/stats", response_model=AIAlertStats)
async def get_alert_stats(
    session: SessionDep,
    _: CurrentUser,
    window_days: int = Query(default=30, ge=1, le=365),
):
    return await alert_crud.get_stats(session, window_days=window_days)


@router.get("/{alert_id}", response_model=AIAlertDetail)
async def get_alert(alert_id: int, session: SessionDep, _: CurrentUser):
    items = await alert_crud.list_detailed(session, alert_id=alert_id, limit=1)
    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return items[0]


@router.post("/{alert_id}/resend", response_model=MessageResponse)
async def resend_alert(alert_id: int, session: SessionDep, _: CurrentUser):
    """Queue a Slack re-delivery by clearing the sent flag."""
    alert = await alert_crud.get(session, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    from app.worker.tasks import resend_alert_to_slack

    await alert_crud.mark_slack_sent(session, alert_id, sent=False)
    resend_alert_to_slack.delay(alert_id)
    return MessageResponse(detail="Slack re-delivery queued")
