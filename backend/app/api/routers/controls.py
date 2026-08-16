"""Service control endpoints — the UI's kill switches and status view.

Deliberately no container start/stop. Doing that from the browser would require
mounting the Docker socket into the backend container, which is equivalent to
granting the web application root on the host. Pausing the *work* achieves the
operational goal with none of that exposure, and it is auditable: every pause
records who did it and why.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, SuperUser
from app.core.config import settings
from app.core.redis_client import ping_redis
from app.models.service_control import SERVICE_METADATA, ServiceKey
from app.models.task_execution_log import TaskExecutionLog
from app.schemas.control_schema import (
    ContainerStatus,
    ServiceControlResponse,
    ServiceControlSummary,
    ServiceControlUpdate,
    SystemStatusResponse,
)
from app.services import controls

router = APIRouter(prefix="/controls", tags=["controls"])

#: A worker that has logged nothing for longer than this is treated as stalled.
WORKER_STALE_MINUTES = 30


def _to_response(row) -> ServiceControlResponse:
    name, summary, impact = SERVICE_METADATA[row.service_key]
    return ServiceControlResponse(
        id=row.id,
        service_key=row.service_key,
        is_enabled=row.is_enabled,
        paused_reason=row.paused_reason,
        paused_by=row.paused_by,
        paused_at=row.paused_at,
        updated_at=row.updated_at,
        display_name=name,
        summary=summary,
        impact=impact,
    )


def _summarize(rows) -> ServiceControlSummary:
    paused = [row.service_key for row in rows if not row.is_enabled]
    return ServiceControlSummary(
        total=len(rows),
        enabled=len(rows) - len(paused),
        paused=len(paused),
        scheduler_paused=ServiceKey.SCHEDULER in paused,
        paused_keys=paused,
    )


@router.get("", response_model=list[ServiceControlResponse])
async def list_controls(session: SessionDep, _: CurrentUser):
    rows = await controls.list_controls(session)
    return [_to_response(row) for row in rows]


@router.get("/summary", response_model=ServiceControlSummary)
async def controls_summary(session: SessionDep, _: CurrentUser):
    rows = await controls.list_controls(session)
    return _summarize(rows)


@router.patch("/{service_key}", response_model=ServiceControlResponse)
async def update_control(
    service_key: ServiceKey,
    payload: ServiceControlUpdate,
    session: SessionDep,
    current_user: SuperUser,
):
    """Pause or resume one subsystem. Effective on the next task, no restart."""
    if not payload.is_enabled and not (payload.reason or "").strip():
        # Forcing a reason here is what makes the audit trail worth having.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A reason is required when pausing a service",
        )

    row = await controls.set_enabled(
        session,
        service_key,
        enabled=payload.is_enabled,
        reason=payload.reason,
        actor=current_user.email,
    )
    return _to_response(row)


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(session: SessionDep, _: CurrentUser):
    """Kill-switch states plus a read-only liveness view of each process.

    Liveness is inferred from observable evidence — recent task rows, database
    and Redis reachability — not from the Docker API.
    """
    rows = await controls.list_controls(session)

    since = datetime.now(UTC) - timedelta(minutes=WORKER_STALE_MINUTES)
    recent_result = await session.execute(
        select(func.count())
        .select_from(TaskExecutionLog)
        .where(TaskExecutionLog.started_at >= since)
    )
    recent_tasks = int(recent_result.scalar_one())

    last_result = await session.execute(
        select(func.max(TaskExecutionLog.started_at))
    )
    last_task_at = last_result.scalar_one()

    redis_ok = await ping_redis()

    containers = [
        ContainerStatus(
            name="backend",
            role="FastAPI API",
            status="running",
            detail="Serving this request, so it is alive by definition.",
        ),
        ContainerStatus(
            name="postgres",
            role="Database",
            status="running",
            detail="Answered the queries backing this response.",
        ),
        ContainerStatus(
            name="redis",
            role="Broker, results, alert state",
            status="running" if redis_ok else "unreachable",
            detail=(
                "PING succeeded."
                if redis_ok
                else "PING failed. No scheduled work can be brokered."
            ),
        ),
        ContainerStatus(
            name="worker",
            role="Celery task executor",
            status=(
                "active"
                if recent_tasks > 0
                else "idle" if last_task_at is not None else "unknown"
            ),
            detail=(
                f"{recent_tasks} task(s) started in the last "
                f"{WORKER_STALE_MINUTES} minutes."
                if recent_tasks > 0
                else (
                    f"No task since {last_task_at.isoformat()}. Idle is normal "
                    "outside scheduled windows."
                    if last_task_at is not None
                    else "No task has ever run. Expected on a fresh install."
                )
            ),
        ),
        ContainerStatus(
            name="beat",
            role="Celery scheduler",
            status=(
                "paused"
                if any(
                    row.service_key is ServiceKey.SCHEDULER and not row.is_enabled
                    for row in rows
                )
                else "scheduled"
            ),
            detail=(
                f"Dispatch interval {settings.beat_dispatch_interval_seconds}s, "
                f"health probe {settings.health_check_interval_seconds}s."
            ),
        ),
    ]

    return SystemStatusResponse(
        controls=[_to_response(row) for row in rows],
        summary=_summarize(rows),
        containers=containers,
    )
