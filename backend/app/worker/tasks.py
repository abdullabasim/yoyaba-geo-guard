"""Celery task definitions.

Workflow
--------
``dispatch_due_checks`` (Beat, every BEAT_DISPATCH_INTERVAL_SECONDS)
    Finds URLs whose schedule has arrived and whose Client and Project are both
    active, expands them into one work item per active keyword, and enqueues a
    chain for each.

``fetch_serp_data`` (Task A)
    Calls the SERP provider, stores the observation plus a top-10 JSONB
    snapshot, and decides whether the movement warrants AI analysis. Returns a
    small dict that Celery passes straight into Task B.

``analyze_intent_shift`` (Task B)
    Runs only meaningfully when Task A set ``should_analyze``. Loads the current
    and previous snapshots, calls the centralized LLM layer, stores an AIAlert
    and posts to Slack.

Chained tasks always execute, so Task B checks the flag first and records
SKIPPED rather than treating "no analysis needed" as an error.
"""

from __future__ import annotations

from typing import Any

from celery import chain
from celery.result import AsyncResult
from celery.signals import worker_shutdown

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import session_scope
from app.core.logging import get_logger
from app.crud.alert_crud import alert_crud
from app.crud.keyword_crud import keyword_crud
from app.crud.project_crud import project_crud
from app.crud.ranking_crud import ranking_crud
from app.crud.url_crud import target_url_crud
from app.llm.intent_analyzer import detect_intent_shift
from app.models.client import Client
from app.models.enums import IssueType
from app.models.project import Project
from app.models.service_control import ServiceKey
from app.services import controls
from app.services.dataforseo import (
    BatchItem,
    SerpRateLimitError,
    fetch_serp,
    fetch_serp_batch,
)
from app.services.rate_limiter import (
    DailyBudgetExhausted,
    RateLimitDeferred,
    consume_budget_batch,
)
from app.services.health import run_health_check
from app.services.scheduling import chunk_work, collect_due_work, should_trigger_analysis
from app.services.slack import send_intent_shift_alert
from app.worker.logging_ctx import (
    TaskContext,
    TaskDeferred,
    TaskSkipped,
    run_logged,
)
from app.worker.runner import run_async, shutdown_event_loop

logger = get_logger(__name__)

TASK_FETCH = "app.worker.tasks.fetch_serp_data"
TASK_BATCH_FETCH = "app.worker.tasks.fetch_serp_batch_task"
TASK_ANALYZE = "app.worker.tasks.analyze_intent_shift"
TASK_DISPATCH = "app.worker.tasks.dispatch_due_checks"
TASK_RESEND = "app.worker.tasks.resend_alert_to_slack"
TASK_HEALTH = "app.worker.tasks.monitor_system_health"


@worker_shutdown.connect
def _on_worker_shutdown(**_: Any) -> None:
    """Close the pool, the LLM client and Redis when the worker process exits."""
    shutdown_event_loop()


# ----------------------------------------------------------------------
# Health monitor
# ----------------------------------------------------------------------
@celery_app.task(name=TASK_HEALTH, bind=True)
def monitor_system_health(self) -> dict[str, Any]:
    """Probe every dependency so outages surface even when nothing is scheduled.

    Deliberately NOT wrapped in ``run_logged``: that wrapper writes to the
    database, which is one of the things being probed. A database outage would
    turn the monitor itself into a failing task instead of a working alarm.
    """
    try:
        if not run_async(controls.is_enabled(ServiceKey.HEALTH_MONITOR)):
            return {"status": "paused"}
        report = run_async(run_health_check())
        return report.as_dict()
    except Exception as exc:
        logger.exception("Health monitor itself failed")
        try:
            from app.services.error_alerts import report_error

            run_async(
                report_error(
                    exc,
                    source=TASK_HEALTH,
                    scope="health_monitor",
                    context={"note": "the health monitor task itself raised"},
                )
            )
        except Exception:
            logger.exception("Could not report health monitor failure")
        raise


def dispatch_keyword_chain(
    target_url_id: int, keyword_id: int, force_analysis: bool = False
) -> AsyncResult:
    """Enqueue Task A -> Task B for one keyword.

    Task B receives Task A's return value as its first argument, which is the
    event-driven link between fetching and analysis.
    """
    workflow = chain(
        fetch_serp_data.s(target_url_id, keyword_id, force_analysis),
        analyze_intent_shift.s(),
    )
    return workflow.apply_async()


# ----------------------------------------------------------------------
# Beat dispatcher
# ----------------------------------------------------------------------
@celery_app.task(name=TASK_DISPATCH, bind=True)
def dispatch_due_checks(self) -> dict[str, Any]:
    async def body(context: TaskContext) -> dict[str, Any]:
        # Master switch, checked before reading due work: a paused scheduler
        # must cost nothing at all.
        if not await controls.is_enabled(ServiceKey.SCHEDULER):
            raise TaskSkipped("scheduler is paused from the control panel")

        async with session_scope() as session:
            work = await collect_due_work(session)

        if not work:
            context.add(candidates=0, dispatched=0, batches=0)
            return {"candidates": 0, "dispatched": 0, "batches": 0}

        chunks = chunk_work(work)
        dispatched_batches = 0
        dispatched_keywords = 0

        for chunk in chunks:
            try:
                # Each chunk is a list of (target_url_id, keyword_id, url, kw_text).
                # The batch task receives a serialisable list of [url_id, kw_id] pairs.
                pairs = [[url_id, kw_id] for url_id, kw_id, _url, _kw in chunk]
                fetch_serp_batch_task.apply_async(args=[pairs])
                dispatched_batches += 1
                dispatched_keywords += len(chunk)
            except Exception:
                logger.exception(
                    "Failed to enqueue batch of %d keywords", len(chunk)
                )

        context.add(
            candidates=len(work),
            dispatched_keywords=dispatched_keywords,
            batches=dispatched_batches,
            batch_size=settings.dataforseo_batch_size,
        )
        return {
            "candidates": len(work),
            "dispatched_keywords": dispatched_keywords,
            "batches": dispatched_batches,
        }

    context = TaskContext(task_name=TASK_DISPATCH, celery_task_id=self.request.id)
    return run_async(run_logged(context, body))


# ----------------------------------------------------------------------
# Task A — data fetcher
# ----------------------------------------------------------------------
@celery_app.task(name=TASK_FETCH, bind=True)
def fetch_serp_data(
    self, target_url_id: int, keyword_id: int, force_analysis: bool = False
) -> dict[str, Any]:
    async def body(context: TaskContext) -> dict[str, Any]:
        # Checked here as well as in the dispatcher, because a chain already in
        # the queue when the switch was flipped would otherwise still bill the
        # provider.
        if not await controls.is_enabled(ServiceKey.SERP_FETCH):
            raise TaskSkipped("SERP fetching is paused from the control panel")

        async with session_scope() as session:
            url_obj = await target_url_crud.get(session, target_url_id)
            keyword = await keyword_crud.get(session, keyword_id)

            if url_obj is None or keyword is None:
                raise TaskSkipped(
                    f"url {target_url_id} or keyword {keyword_id} no longer exists"
                )
            if keyword.target_url_id != url_obj.id:
                raise ValueError(
                    f"keyword {keyword_id} does not belong to url {target_url_id}"
                )
            if not (url_obj.is_active and keyword.is_active):
                raise TaskSkipped("url or keyword was disabled before execution")

            context.target_url = url_obj.url
            context.keyword_text = keyword.keyword_text

            project = await project_crud.get(session, url_obj.project_id)
            effective_depth = url_obj.effective_dataforseo_depth(project)

            previous = await ranking_crud.get_latest_for_keyword(session, keyword.id)
            previous_rank = previous.current_rank if previous else None

            try:
                fetched = await fetch_serp(
                    keyword=keyword.keyword_text,
                    target_url=url_obj.url,
                    location_code=keyword.location_code,
                    language_code=keyword.language_code,
                    depth=effective_depth,
                )
            except RateLimitDeferred as deferred:
                # No provider call was made. Retry rather than losing the check
                # until the next interval, which for a daily keyword is a day.
                raise TaskDeferred(
                    deferred.reason,
                    retry_after_seconds=max(
                        deferred.retry_after_seconds,
                        settings.dataforseo_rate_limit_retry_delay_seconds,
                    ),
                ) from deferred
            except SerpRateLimitError as limited:
                # The provider rejected us. Its Retry-After wins over our pacing;
                # the limiter has already been told, so siblings back off too.
                raise TaskDeferred(
                    str(limited),
                    retry_after_seconds=limited.retry_after_seconds
                    or settings.dataforseo_rate_limit_penalty_seconds,
                ) from limited
            except DailyBudgetExhausted as exhausted:
                # Retrying today cannot help: the ceiling only moves at midnight.
                # Skipped, not deferred, so worker slots are not burned waiting.
                raise TaskSkipped(str(exhausted)) from exhausted

            observation = await ranking_crud.create_observation(
                session,
                keyword_id=keyword.id,
                current_rank=fetched.rank,
                previous_rank=previous_rank,
                snapshot=fetched.snapshot,
                total_results_checked=fetched.total_results_checked,
                serp_url=fetched.serp_url,
            )

            # Written even when the rank did not move, so the interval check in
            # the due query advances and the URL is not re-fetched next tick.
            await target_url_crud.mark_checked(session, url_obj.id)

            effective_threshold = url_obj.effective_rank_drop_threshold(project)
            should_analyze = force_analysis or should_trigger_analysis(
                previous_rank, fetched.rank, threshold=effective_threshold
            )

            context.add(
                history_id=observation.id,
                current_rank=fetched.rank,
                previous_rank=previous_rank,
                results_checked=fetched.total_results_checked,
                provider_cost=fetched.cost,
                should_analyze=should_analyze,
                threshold=effective_threshold,
            )

            return {
                "history_id": observation.id,
                "keyword_id": keyword.id,
                "target_url_id": url_obj.id,
                "current_rank": fetched.rank,
                "previous_rank": previous_rank,
                "should_analyze": should_analyze,
            }

    context = TaskContext(task_name=TASK_FETCH, celery_task_id=self.request.id)
    context.add(target_url_id=target_url_id, keyword_id=keyword_id)
    try:
        return run_async(run_logged(context, body))
    except TaskDeferred as deferred:
        # Retry is arranged here rather than inside run_logged, because self.retry
        # raises Celery's Retry control-flow exception — raising it inside the
        # logging wrapper would be caught by the generic handler and recorded as a
        # FAILED task with a Slack alert.
        if self.request.retries >= settings.dataforseo_rate_limit_max_retries:
            logger.warning(
                "Giving up on %s for keyword %s after %s rate-limit retries; "
                "the next scheduled interval will pick it up",
                TASK_FETCH,
                keyword_id,
                self.request.retries,
            )
            return {
                "status": "skipped",
                "reason": f"rate limited: {deferred.reason}",
                "should_analyze": False,
            }
        raise self.retry(
            exc=deferred,
            countdown=int(deferred.retry_after_seconds),
            max_retries=settings.dataforseo_rate_limit_max_retries,
        )


# ----------------------------------------------------------------------
# Task A-Batch — batch data fetcher
# ----------------------------------------------------------------------
@celery_app.task(name=TASK_BATCH_FETCH, bind=True)
def fetch_serp_batch_task(
    self, pairs: list[list[int]],
) -> dict[str, Any]:
    """Fetch SERPs for a batch of keywords in a single API call.

    ``pairs`` is a list of ``[target_url_id, keyword_id]`` pairs, produced by
    the dispatcher's ``chunk_work()`` helper. The task:

    1. Loads all URLs and keywords from the database.
    2. Builds ``BatchItem`` objects and calls ``fetch_serp_batch()``.
    3. Stores observations and marks URLs as checked.
    4. Fans out ``analyze_intent_shift`` for any keyword that dropped.
    """

    async def body(context: TaskContext) -> dict[str, Any]:
        if not await controls.is_enabled(ServiceKey.SERP_FETCH):
            raise TaskSkipped("SERP fetching is paused from the control panel")

        async with session_scope() as session:
            # ---- Load all rows in one pass ----
            batch_items: list[BatchItem] = []
            url_cache: dict[int, Any] = {}
            keyword_cache: dict[int, Any] = {}
            project_cache: dict[int, Any] = {}
            previous_ranks: dict[int, int | None] = {}

            for url_id, kw_id in pairs:
                if url_id not in url_cache:
                    url_cache[url_id] = await target_url_crud.get(session, url_id)
                if kw_id not in keyword_cache:
                    keyword_cache[kw_id] = await keyword_crud.get(session, kw_id)

                url_obj = url_cache[url_id]
                keyword = keyword_cache[kw_id]

                if url_obj is None or keyword is None:
                    logger.warning(
                        "Skipping batch item: url %s or keyword %s no longer exists",
                        url_id, kw_id,
                    )
                    continue
                if not (url_obj.is_active and keyword.is_active):
                    continue

                prev = await ranking_crud.get_latest_for_keyword(session, keyword.id)
                previous_ranks[keyword.id] = prev.current_rank if prev else None

                if url_obj.project_id not in project_cache:
                    project_cache[url_obj.project_id] = await project_crud.get(session, url_obj.project_id)
                project = project_cache[url_obj.project_id]

                batch_items.append(BatchItem(
                    keyword=keyword.keyword_text,
                    target_url=url_obj.url,
                    location_code=keyword.location_code,
                    language_code=keyword.language_code,
                    target_url_id=url_obj.id,
                    keyword_id=keyword.id,
                    depth=url_obj.effective_dataforseo_depth(project),
                ))

            if not batch_items:
                raise TaskSkipped("no active keywords in this batch")

            context.add(batch_size=len(batch_items))

            # ---- Call the provider ----
            try:
                results = await fetch_serp_batch(batch_items)
            except RateLimitDeferred as deferred:
                raise TaskDeferred(
                    deferred.reason,
                    retry_after_seconds=max(
                        deferred.retry_after_seconds,
                        settings.dataforseo_rate_limit_retry_delay_seconds,
                    ),
                ) from deferred
            except SerpRateLimitError as limited:
                raise TaskDeferred(
                    str(limited),
                    retry_after_seconds=limited.retry_after_seconds
                    or settings.dataforseo_rate_limit_penalty_seconds,
                ) from limited
            except DailyBudgetExhausted as exhausted:
                raise TaskSkipped(str(exhausted)) from exhausted

            # ---- Store observations and fan out analysis ----
            fetched_count = 0
            analyzed_count = 0
            error_count = 0

            for batch_result in results:
                item = batch_result.item
                if not batch_result.ok:
                    error_count += 1
                    logger.warning(
                        "Batch item error for keyword %s: %s",
                        item.keyword, batch_result.error,
                    )
                    continue

                fetched = batch_result.result
                assert fetched is not None  # guaranteed by batch_result.ok
                previous_rank = previous_ranks.get(item.keyword_id)

                observation = await ranking_crud.create_observation(
                    session,
                    keyword_id=item.keyword_id,
                    current_rank=fetched.rank,
                    previous_rank=previous_rank,
                    snapshot=fetched.snapshot,
                    total_results_checked=fetched.total_results_checked,
                    serp_url=fetched.serp_url,
                )

                await target_url_crud.mark_checked(session, item.target_url_id)
                fetched_count += 1

                # Determine if AI analysis is warranted.
                url_obj = url_cache[item.target_url_id]
                project = await project_crud.get(session, url_obj.project_id)
                effective_threshold = url_obj.effective_rank_drop_threshold(project)
                should_analyze = should_trigger_analysis(
                    previous_rank, fetched.rank, threshold=effective_threshold
                )

                if should_analyze:
                    # Fan out: enqueue individual Task B for this keyword.
                    upstream = {
                        "history_id": observation.id,
                        "keyword_id": item.keyword_id,
                        "target_url_id": item.target_url_id,
                        "current_rank": fetched.rank,
                        "previous_rank": previous_rank,
                        "should_analyze": True,
                    }
                    analyze_intent_shift.apply_async(args=[upstream])
                    analyzed_count += 1

            context.add(
                fetched=fetched_count,
                analyzed=analyzed_count,
                errors=error_count,
            )
            return {
                "fetched": fetched_count,
                "analyzed": analyzed_count,
                "errors": error_count,
            }

    context = TaskContext(task_name=TASK_BATCH_FETCH, celery_task_id=self.request.id)
    context.add(batch_pairs=len(pairs))
    try:
        return run_async(run_logged(context, body))
    except TaskDeferred as deferred:
        if self.request.retries >= settings.dataforseo_rate_limit_max_retries:
            logger.warning(
                "Giving up on batch of %d keywords after %s rate-limit retries",
                len(pairs),
                self.request.retries,
            )
            return {
                "status": "skipped",
                "reason": f"rate limited: {deferred.reason}",
                "fetched": 0,
                "analyzed": 0,
                "errors": len(pairs),
            }
        raise self.retry(
            exc=deferred,
            countdown=int(deferred.retry_after_seconds),
            max_retries=settings.dataforseo_rate_limit_max_retries,
        )


# ----------------------------------------------------------------------
# Task B — AI analyzer
# ----------------------------------------------------------------------
@celery_app.task(name=TASK_ANALYZE, bind=True)
def analyze_intent_shift(self, upstream: dict[str, Any] | None = None) -> dict[str, Any]:
    async def body(context: TaskContext) -> dict[str, Any]:
        if not await controls.is_enabled(ServiceKey.AI_ANALYSIS):
            # The observation and its snapshot are already stored, so the drop
            # can be re-analyzed once analysis is resumed.
            raise TaskSkipped("AI analysis is paused from the control panel")

        if not isinstance(upstream, dict):
            raise TaskSkipped("no upstream result to analyze")
        if upstream.get("status") == "skipped":
            raise TaskSkipped("upstream fetch was skipped")
        if not upstream.get("should_analyze"):
            raise TaskSkipped(
                f"rank movement below threshold of {settings.rank_drop_threshold}"
            )

        history_id = upstream.get("history_id")
        if not history_id:
            raise TaskSkipped("upstream result carried no history_id")

        context.add(history_id=history_id)

        async with session_scope() as session:
            current = await ranking_crud.get(session, int(history_id))
            if current is None:
                raise TaskSkipped(f"history {history_id} no longer exists")

            keyword = await keyword_crud.get(session, current.keyword_id)
            if keyword is None:
                raise TaskSkipped("keyword no longer exists")

            url_obj = await target_url_crud.get(session, keyword.target_url_id)
            if url_obj is None:
                raise TaskSkipped("target url no longer exists")

            context.target_url = url_obj.url
            context.keyword_text = keyword.keyword_text

            previous = await ranking_crud.get_latest_for_keyword(
                session, current.keyword_id, before_id=current.id
            )
            previous_snapshot = previous.top_10_serp_snapshot if previous else []

            outcome = await detect_intent_shift(
                keyword=keyword.keyword_text,
                target_url=url_obj.url,
                previous_rank=current.previous_rank,
                current_rank=current.current_rank,
                previous_snapshot=previous_snapshot,
                current_snapshot=current.top_10_serp_snapshot,
                previous_check_date=previous.check_date if previous else None,
                current_check_date=current.check_date,
                location_code=keyword.location_code,
                language_code=keyword.language_code,
            )
            analysis = outcome.analysis

            alert = await alert_crud.create(
                session,
                history_id=current.id,
                issue_type=analysis.issue_type,
                ai_diagnosis=analysis.ai_diagnosis,
                actionable_advice=analysis.actionable_advice,
                confidence=analysis.confidence,
                competitor_signals=[s.model_dump() for s in analysis.competitor_signals],
                model_used=outcome.model_used,
            )

            project = await session.get(Project, url_obj.project_id)
            project_name = project.name if project else None
            client = (
                await session.get(Client, project.client_id) if project else None
            )
            client_name = client.name if client else None

            delivered = False
            if await controls.is_enabled(ServiceKey.SLACK_ALERTS):
                delivered = await send_intent_shift_alert(
                    keyword=keyword.keyword_text,
                    url=url_obj.url,
                    client_name=client_name,
                    project_name=project_name,
                    previous_rank=current.previous_rank,
                    current_rank=current.current_rank,
                    issue_type=analysis.issue_type,
                    ai_diagnosis=analysis.ai_diagnosis,
                    actionable_advice=analysis.actionable_advice,
                    confidence=analysis.confidence,
                    competitor_signals=[s.model_dump() for s in analysis.competitor_signals],
                    model_used=outcome.model_used,
                )
                if delivered:
                    await alert_crud.mark_slack_sent(session, alert.id)
            else:
                # Stored but undelivered. The Alerts page exposes 'Resend' so
                # nothing is lost while notifications are paused.
                logger.info(
                    "Slack business alerts paused; alert %s stored undelivered",
                    alert.id,
                )

            context.add(
                alert_id=alert.id,
                issue_type=analysis.issue_type.value,
                intent_shift_detected=analysis.intent_shift_detected,
                confidence=analysis.confidence,
                llm_attempts=outcome.attempts,
                prompt_tokens=outcome.prompt_tokens,
                completion_tokens=outcome.completion_tokens,
                slack_sent=delivered,
            )

            return {
                "alert_id": alert.id,
                "issue_type": analysis.issue_type.value,
                "intent_shift_detected": analysis.intent_shift_detected,
                "slack_sent": delivered,
            }

    context = TaskContext(task_name=TASK_ANALYZE, celery_task_id=self.request.id)
    return run_async(run_logged(context, body))


# ----------------------------------------------------------------------
# Slack re-delivery
# ----------------------------------------------------------------------
@celery_app.task(name=TASK_RESEND, bind=True)
def resend_alert_to_slack(self, alert_id: int) -> dict[str, Any]:
    async def body(context: TaskContext) -> dict[str, Any]:
        async with session_scope() as session:
            details = await alert_crud.list_detailed(session, alert_id=alert_id, limit=1)
            if not details:
                raise TaskSkipped(f"alert {alert_id} no longer exists")
            detail = details[0]

            context.target_url = detail.url
            context.keyword_text = detail.keyword_text

            delivered = await send_intent_shift_alert(
                keyword=detail.keyword_text or "",
                url=detail.url or "",
                client_name=detail.client_name,
                project_name=detail.project_name,
                previous_rank=detail.previous_rank,
                current_rank=detail.current_rank,
                issue_type=IssueType(detail.issue_type),
                ai_diagnosis=detail.ai_diagnosis,
                actionable_advice=detail.actionable_advice,
                confidence=detail.confidence,
                competitor_signals=detail.competitor_signals,
                model_used=detail.model_used,
            )
            if delivered:
                await alert_crud.mark_slack_sent(session, alert_id)

            context.add(slack_sent=delivered)
            return {"alert_id": alert_id, "slack_sent": delivered}

    context = TaskContext(task_name=TASK_RESEND, celery_task_id=self.request.id)
    context.add(alert_id=alert_id)
    return run_async(run_logged(context, body))
