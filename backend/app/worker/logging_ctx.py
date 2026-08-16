"""Observability wrapper shared by every Celery task.

Guarantees, for all tasks:

* a TaskExecutionLog row exists before work starts (PENDING),
* the row is closed out as SUCCESS / FAILED / SKIPPED,
* on failure the traceback is stored and an admin Slack alert is fired,
* the exception is re-raised so Celery also marks the task failed.

Logging is best-effort: if the log write itself fails, that is recorded to the
application log but never converts a successful task into a failed one, and
never hides the original exception.
"""

from __future__ import annotations

import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.database import session_scope
from app.core.logging import get_logger
from app.crud.task_crud import task_log_crud
from app.models.enums import TaskStatus
from app.models.task_execution_log import MAX_ERROR_MESSAGE_LENGTH
from app.services.error_alerts import report_error

logger = get_logger(__name__)


class TaskSkipped(Exception):
    """Raised by a task body to record SKIPPED instead of SUCCESS or FAILED.

    Used when a chained task is invoked but has nothing to do — for example
    Task B running after a rank movement that did not meet the threshold.
    Celery always executes chained tasks, so "nothing to do" must be an
    expected, non-error outcome.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class TaskDeferred(Exception):
    """Raised when a task could not run *yet* and should be retried later.

    Distinct from both SKIPPED and FAILED, and the distinction matters:

    * It is not a failure — nothing broke, no provider call was made, and
      alerting an operator about self-inflicted pacing would be pure noise.
    * It is not simply skipped — the work still needs doing, so the caller
      reschedules rather than waiting for the next natural interval.

    ``run_logged`` records it as SKIPPED with a deferral reason and re-raises, so
    the Celery wrapper can call ``self.retry()`` outside the logging context.
    """

    def __init__(self, reason: str, retry_after_seconds: float = 60.0) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry_after_seconds = max(1.0, retry_after_seconds)


@dataclass
class TaskContext:
    """Identifying and diagnostic data for one task run."""

    task_name: str
    target_url: str | None = None
    keyword_text: str | None = None
    celery_task_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def add(self, **values: Any) -> None:
        """Attach extra diagnostics that end up in the log row's JSONB payload."""
        self.payload.update(values)


async def _start_log(context: TaskContext) -> int | None:
    try:
        async with session_scope() as session:
            row = await task_log_crud.start(
                session,
                task_name=context.task_name,
                target_url=context.target_url,
                keyword_text=context.keyword_text,
                celery_task_id=context.celery_task_id,
                payload=dict(context.payload) or None,
            )
            return row.id
    except Exception as exc:
        # A failure here is almost always the database being unreachable, which
        # is exactly the condition an operator most needs to hear about. Without
        # this alert the outage would be invisible: the task log is the usual
        # reporting channel and it is the thing that just broke.
        logger.exception("Failed to write PENDING log row for %s", context.task_name)
        await report_error(
            exc,
            source=f"{context.task_name} (task log write)",
            scope=context.task_name,
            target_url=context.target_url,
            keyword=context.keyword_text,
            context={"phase": "start_log", **context.payload},
            traceback_text="".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ),
        )
        return None


async def _finish_log(
    log_id: int | None,
    context: TaskContext,
    status: TaskStatus,
    error_message: str | None = None,
) -> None:
    if log_id is None:
        return
    try:
        async with session_scope() as session:
            await task_log_crud.finish(
                session,
                log_id,
                status=status,
                error_message=error_message,
                target_url=context.target_url,
                keyword_text=context.keyword_text,
                payload=dict(context.payload) or None,
            )
    except Exception as exc:
        logger.exception("Failed to close log row %s for %s", log_id, context.task_name)
        await report_error(
            exc,
            source=f"{context.task_name} (task log close)",
            scope=context.task_name,
            context={"phase": "finish_log", "log_id": log_id},
        )


async def run_logged(
    context: TaskContext,
    body: Callable[[TaskContext], Awaitable[Any]],
) -> Any:
    """Execute ``body`` with full logging, Slack alerting and re-raise."""
    log_id = await _start_log(context)

    try:
        result = await body(context)
    except TaskSkipped as skipped:
        logger.info("%s skipped: %s", context.task_name, skipped.reason)
        context.add(skip_reason=skipped.reason)
        await _finish_log(log_id, context, TaskStatus.SKIPPED)
        return {"status": "skipped", "reason": skipped.reason}
    except TaskDeferred as deferred:
        # Recorded as SKIPPED with a deferral marker, and deliberately NOT
        # alerted: rate-limit pacing is our own doing, and paging an operator
        # about it would train them to ignore the channel. The retry itself is
        # arranged by the Celery wrapper, which owns self.retry().
        logger.info(
            "%s deferred: %s (retry in %.0fs)",
            context.task_name,
            deferred.reason,
            deferred.retry_after_seconds,
        )
        context.add(
            deferred=True,
            defer_reason=deferred.reason,
            retry_after_seconds=deferred.retry_after_seconds,
        )
        await _finish_log(log_id, context, TaskStatus.SKIPPED)
        raise
    except Exception as exc:
        error_text = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        logger.error("%s failed: %s", context.task_name, exc)

        await _finish_log(
            log_id, context, TaskStatus.FAILED, error_text[:MAX_ERROR_MESSAGE_LENGTH]
        )

        # Classified, throttled operator alert. report_error never raises, so a
        # Slack outage cannot replace the original exception with a delivery one.
        await report_error(
            exc,
            source=context.task_name,
            # Scope is what distinguishes "this keyword is broken" from "the
            # provider is down"; systemic categories ignore it and collapse into
            # a single alert regardless.
            scope=f"{context.task_name}:{context.keyword_text or context.target_url or ''}",
            target_url=context.target_url,
            keyword=context.keyword_text,
            context=context.payload or None,
            traceback_text=error_text,
        )

        raise
    else:
        await _finish_log(log_id, context, TaskStatus.SUCCESS)
        return result
