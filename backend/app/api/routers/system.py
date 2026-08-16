"""System health and alerting diagnostics.

Exists so Slack wiring can be verified deliberately, rather than discovered to
be broken during a real incident.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep, SuperUser
from app.core.config import settings
from app.services.error_alerts import (
    ErrorCategory,
    Severity,
    classify_exception,
    report_error,
)
from app.services import rate_limiter
from app.services.health import run_health_check
from app.services.slack import (
    SlackChannel,
    channel_state,
    delivery_status,
    reset_suppressed_counts,
    suppressed_counts,
)

router = APIRouter(prefix="/system", tags=["system"])


class HealthResponse(BaseModel):
    healthy: bool
    database: str
    redis: str
    serp_credentials: str
    llm_credentials: str
    slack_webhook: str


class AlertTestResponse(BaseModel):
    sent: bool
    category: str
    severity: str
    note: str


class ErrorCatalogEntry(BaseModel):
    category: str
    severity: str
    title: str
    remediation: str
    systemic: bool


@router.get("/health", response_model=HealthResponse)
async def system_health(_: CurrentUser):
    """Run the same probe the scheduled health monitor performs."""
    report = await run_health_check()
    return HealthResponse(healthy=report.healthy, **report.as_dict())


@router.get("/rate-limit")
async def rate_limit_status(_: CurrentUser):
    """Live SERP provider rate-limiter usage.

    Answers "are we being throttled, and by whom" — our own pacing, our daily
    budget, or the provider. Reads state without consuming any of it.
    """
    snap = await rate_limiter.snapshot()
    return snap.as_dict()


@router.post("/rate-limit/reset")
async def reset_rate_limit(
    _: SuperUser,
    include_budget: bool = Query(
        default=False,
        description="Also clear today's consumed budget. Use only deliberately.",
    ),
):
    """Clear pacing state, e.g. after raising a provider plan mid-day.

    The daily budget is excluded by default: resetting it hides real spend and is
    the kind of thing that should require an explicit flag.
    """
    await rate_limiter.reset(include_budget=include_budget)
    snap = await rate_limiter.snapshot()
    return {"reset": True, "budget_cleared": include_budget, "state": snap.as_dict()}


@router.get("/slack/status")
async def slack_status(_: CurrentUser):
    """Exactly what Slack would do right now, and why.

    Answers "why did I get no Slack message" without reading code or logs: each
    channel reports whether it is deliverable and the specific setting blocking
    it, plus how many messages have been suppressed since the process started.
    """
    return delivery_status()


@router.post("/slack/reset-suppressed-counts")
async def reset_slack_counters(_: SuperUser):
    """Zero the suppressed-message counters, to start a clean test run."""
    reset_suppressed_counts()
    return {"reset": True, "suppressed_since_start": suppressed_counts()}


@router.post("/alerts/test", response_model=AlertTestResponse)
async def test_error_alert(
    _: CurrentUser,
    category: ErrorCategory = Query(
        default=ErrorCategory.UNKNOWN,
        description="Which classified alert to simulate.",
    ),
):
    """Send a real alert to the error webhook, to verify delivery end to end.

    Subject to the same throttling as genuine alerts, so calling it twice in
    quick succession will suppress the second message. That is intentional: the
    throttle is part of what needs verifying.

    With Slack disabled this still exercises classification and formatting, and
    the payload is written to the log — so the wiring is testable before any
    webhook exists.
    """
    deliverable, reason = channel_state(SlackChannel.ERROR)
    if not deliverable and settings.slack_configured and settings.slack_enabled:
        # A real misconfiguration rather than a deliberate switch: worth a 400.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error alerts cannot be delivered: {reason}",
        )

    class SimulatedFailure(RuntimeError):
        error_category = category

    sent = await report_error(
        SimulatedFailure(
            f"Simulated {category.value} raised by POST /system/alerts/test"
        ),
        source="system.alerts.test",
        scope="manual-test",
        context={"triggered_by": "manual API call", "simulated": True},
    )

    profile = classify_exception(SimulatedFailure("probe"))

    if sent:
        note = "Delivered to the error webhook."
    elif not deliverable:
        note = (
            f"Not delivered because {reason}. The alert was classified and "
            "formatted, and the payload was written to the backend log, so the "
            "wiring is verified apart from the final HTTP call."
        )
    else:
        note = (
            "Not delivered: either throttled by a recent identical alert, or "
            "Slack rejected the message. Check the backend log."
        )

    return AlertTestResponse(
        sent=sent,
        category=profile.category.value,
        severity=profile.severity.value,
        note=note,
    )


@router.get("/alerts/catalog", response_model=list[ErrorCatalogEntry])
async def alert_catalog(_: CurrentUser):
    """Every error category with its severity and remediation guidance."""
    from app.services.error_alerts import _PROFILES

    return [
        ErrorCatalogEntry(
            category=profile.category.value,
            severity=profile.severity.value,
            title=profile.title,
            remediation=profile.remediation,
            systemic=profile.systemic,
        )
        for profile in _PROFILES.values()
    ]


class SeedResponse(BaseModel):
    seeded: bool
    detail: str
    counts: dict[str, int] = Field(default_factory=dict)


@router.post("/seed-demo-data", response_model=SeedResponse)
async def seed_demo(
    session: SessionDep,
    _: SuperUser,
    with_history: bool = Query(default=True),
):
    """Insert the demo hierarchy, but only into an empty database.

    Guarded on "no clients exist" rather than on a marker row, so this endpoint
    can never overwrite or duplicate real customer data. Superuser only.
    """
    from app.core.seed import demo_data_exists, seed_demo_data

    if await demo_data_exists(session):
        return SeedResponse(
            seeded=False,
            detail=(
                "Clients already exist. Seeding is refused so real data cannot be "
                "duplicated or overwritten. Delete existing clients first if you "
                "genuinely want demo data."
            ),
        )

    counts = await seed_demo_data(session, with_history=with_history)
    return SeedResponse(
        seeded=True,
        detail="Demo data inserted.",
        counts=counts,
    )


@router.get("/severities", response_model=list[str])
async def list_severities(_: CurrentUser):
    return [severity.value for severity in Severity]
