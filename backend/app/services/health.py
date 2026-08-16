"""Periodic health probe for the pieces nothing else notices are broken.

The task pipeline only alerts when a task *runs* and fails. That leaves real
blind spots:

* If PostgreSQL is down, ``dispatch_due_checks`` cannot even read which URLs are
  due, so no per-keyword task ever runs to fail.
* If nothing happens to be scheduled overnight, an exhausted API key or a dead
  database is silent until the morning.
* A missing credential is not an error until the first call needs it.

This module probes each dependency directly on a fixed schedule, so an outage is
reported within one probe interval regardless of workload. It also emits a
recovery notice when a previously failing subsystem comes back, because silence
is ambiguous: it could mean recovery, or it could mean the alerting broke too.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.core.database import session_scope
from app.core.logging import get_logger
from app.core.redis_client import get_redis, ping_redis
from app.services.error_alerts import (
    ErrorCategory,
    report_error,
    report_recovery,
)
from app.services.slack import send_recovery_notice

logger = get_logger(__name__)

#: Redis key marking a subsystem as currently in the failed state, so exactly one
#: recovery notice is sent when it heals.
_FAILED_FLAG = "seo:health:failed:{subsystem}"

FAILED_FLAG_TTL_SECONDS = 60 * 60 * 24 * 7


class ConfigurationMissingError(RuntimeError):
    """A required credential is absent, so a whole capability is disabled."""

    error_category = ErrorCategory.CONFIGURATION


@dataclass
class HealthReport:
    database_ok: bool = False
    redis_ok: bool = False
    serp_configured: bool = False
    llm_configured: bool = False
    slack_configured: bool = False
    slack_delivery_enabled: bool = False

    def as_dict(self) -> dict[str, Any]:
        if not self.slack_configured:
            slack = "MISSING"
        elif not self.slack_delivery_enabled:
            # Distinguished from MISSING on purpose: "deliberately off" and
            # "nobody configured it" call for completely different responses.
            slack = "set (delivery disabled)"
        else:
            slack = "set"
        return {
            "database": "ok" if self.database_ok else "FAILED",
            "redis": "ok" if self.redis_ok else "FAILED",
            "serp_credentials": "set" if self.serp_configured else "MISSING",
            "llm_credentials": "set" if self.llm_configured else "MISSING",
            "slack_webhook": slack,
        }

    @property
    def healthy(self) -> bool:
        return self.database_ok and self.redis_ok


async def _mark_failed(subsystem: str) -> bool:
    """Record a subsystem as failed. Returns True if this is a new failure."""
    try:
        client = get_redis()
        first = await client.set(
            _FAILED_FLAG.format(subsystem=subsystem),
            "1",
            ex=FAILED_FLAG_TTL_SECONDS,
            nx=True,
        )
        return bool(first)
    except Exception:
        # Redis itself may be the failure. Treat as new so the alert is sent;
        # throttling in report_error still prevents a flood.
        return True


async def _clear_failed(subsystem: str) -> bool:
    """Clear the failed flag. Returns True if it had been set (i.e. recovered)."""
    try:
        client = get_redis()
        removed = await client.delete(_FAILED_FLAG.format(subsystem=subsystem))
        return bool(removed)
    except Exception:
        return False


async def check_database() -> tuple[bool, Exception | None]:
    try:
        async with session_scope() as session:
            await session.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False, exc


async def run_health_check() -> HealthReport:
    """Probe every dependency and alert on state changes."""
    report = HealthReport(
        serp_configured=settings.serp_provider_configured,
        llm_configured=settings.llm_enabled,
        slack_configured=bool(settings.error_webhook),
        slack_delivery_enabled=settings.error_alerts_deliverable,
    )

    # -- Database --------------------------------------------------
    report.database_ok, db_error = await check_database()
    if not report.database_ok and db_error is not None:
        if await _mark_failed("database"):
            await report_error(
                db_error,
                source="health_monitor",
                scope="database",
                context={"probe": "SELECT 1", **report.as_dict()},
            )
    elif report.database_ok and await _clear_failed("database"):
        await report_recovery(ErrorCategory.DATABASE_CONNECTION, "database")
        await send_recovery_notice(
            subsystem="PostgreSQL",
            detail="The database is reachable again. Scheduled checks resume "
            "automatically at their next window.",
        )

    # -- Redis -----------------------------------------------------
    report.redis_ok = await ping_redis()
    if not report.redis_ok:
        if await _mark_failed("redis"):
            await report_error(
                ConnectionError("Redis PING did not succeed"),
                source="health_monitor",
                scope="redis",
                context={"probe": "PING", **report.as_dict()},
            )
    elif await _clear_failed("redis"):
        await report_recovery(ErrorCategory.REDIS_CONNECTION, "redis")
        await send_recovery_notice(
            subsystem="Redis",
            detail="Redis is reachable again. Queued work will drain normally.",
        )

    # -- Credentials -----------------------------------------------
    # Reported once per throttle window rather than on every probe: a missing key
    # is a standing condition, not a recurring event.
    if not report.serp_configured:
        await report_error(
            ConfigurationMissingError(
                "DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD are empty, so no rank "
                "check can run."
            ),
            source="health_monitor",
            scope="serp_credentials",
            context=report.as_dict(),
        )

    if not report.llm_configured:
        await report_error(
            ConfigurationMissingError(
                "OPENAI_API_KEY is empty, so ranking drops are recorded but never "
                "analyzed."
            ),
            source="health_monitor",
            scope="llm_credentials",
            context=report.as_dict(),
        )

    logger.info("Health check: %s", report.as_dict())
    return report
