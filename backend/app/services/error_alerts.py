"""Error classification and throttled Slack alerting.

Purpose
-------
Turn an arbitrary exception into an *actionable* Slack message. A raw traceback
tells an operator that something broke; it does not tell them whether to top up
a DataForSEO balance, rotate an OpenAI key, or restart Postgres. This module maps
exceptions onto a small set of categories, each with a severity and a concrete
remediation hint.

Throttling
----------
Without de-duplication, a single upstream outage produces one Slack message per
due keyword — hundreds of identical messages. Teams then mute the channel, which
is strictly worse than having no alerting at all. So alerts are keyed by
(category, scope) and only the first within ``ALERT_THROTTLE_SECONDS`` is sent;
subsequent ones increment a counter that the next delivered alert reports.

Throttling fails open: if the Redis holding that state is unreachable, the alert
is sent. Duplicate noise is recoverable; a silently dropped alert is not.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis_client import claim_alert_slot

logger = get_logger(__name__)


class ErrorCategory(StrEnum):
    """What broke, in terms an operator can act on."""

    SERP_AUTH = "SERP_AUTH"
    SERP_QUOTA = "SERP_QUOTA"
    SERP_RATE_LIMIT = "SERP_RATE_LIMIT"
    SERP_UNAVAILABLE = "SERP_UNAVAILABLE"
    SERP_MALFORMED = "SERP_MALFORMED"

    LLM_AUTH = "LLM_AUTH"
    LLM_RATE_LIMIT = "LLM_RATE_LIMIT"
    LLM_QUOTA = "LLM_QUOTA"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LLM_INVALID_OUTPUT = "LLM_INVALID_OUTPUT"
    LLM_NOT_CONFIGURED = "LLM_NOT_CONFIGURED"

    DATABASE_CONNECTION = "DATABASE_CONNECTION"
    DATABASE_ERROR = "DATABASE_ERROR"
    REDIS_CONNECTION = "REDIS_CONNECTION"

    CONFIGURATION = "CONFIGURATION"
    UNKNOWN = "UNKNOWN"


class Severity(StrEnum):
    #: Work is dropping on the floor right now and no retry will fix it.
    CRITICAL = "CRITICAL"
    #: Degraded: this run failed, but the system may recover on its own.
    WARNING = "WARNING"
    #: Worth knowing, not worth waking anyone.
    INFO = "INFO"


@dataclass(frozen=True)
class ErrorProfile:
    category: ErrorCategory
    severity: Severity
    title: str
    #: What the operator should actually do. This is the point of the whole file.
    remediation: str
    #: Whether the same failure is likely to repeat across many keywords.
    #: Repeating failures get a longer throttle window.
    systemic: bool


_PROFILES: dict[ErrorCategory, ErrorProfile] = {
    ErrorCategory.SERP_AUTH: ErrorProfile(
        category=ErrorCategory.SERP_AUTH,
        severity=Severity.CRITICAL,
        title="DataForSEO authentication rejected",
        remediation=(
            "DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD are wrong, expired, or revoked. "
            "Verify them in the DataForSEO dashboard and restart the worker. "
            "No rank checks will succeed until this is fixed."
        ),
        systemic=True,
    ),
    ErrorCategory.SERP_QUOTA: ErrorProfile(
        category=ErrorCategory.SERP_QUOTA,
        severity=Severity.CRITICAL,
        title="DataForSEO quota or balance exhausted",
        remediation=(
            "The account is out of credit or has hit its plan limit. Top up the "
            "balance. Every scheduled check is failing until then. Consider "
            "pausing low-priority clients to control spend when it resumes."
        ),
        systemic=True,
    ),
    ErrorCategory.SERP_RATE_LIMIT: ErrorProfile(
        category=ErrorCategory.SERP_RATE_LIMIT,
        severity=Severity.WARNING,
        title="DataForSEO rate limit hit",
        remediation=(
            "Too many concurrent SERP requests. Lower the Celery worker "
            "--concurrency, or spread execution_time values across the day so "
            "checks are not all scheduled at the same hour."
        ),
        systemic=True,
    ),
    ErrorCategory.SERP_UNAVAILABLE: ErrorProfile(
        category=ErrorCategory.SERP_UNAVAILABLE,
        severity=Severity.WARNING,
        title="DataForSEO unreachable",
        remediation=(
            "Network failure or provider outage after the built-in retries. "
            "Check the DataForSEO status page. Missed checks are retried at the "
            "next scheduled window; no data is lost."
        ),
        systemic=True,
    ),
    ErrorCategory.SERP_MALFORMED: ErrorProfile(
        category=ErrorCategory.SERP_MALFORMED,
        severity=Severity.WARNING,
        title="DataForSEO returned an unusable payload",
        remediation=(
            "The response shape did not match what the parser expects, which "
            "usually means a provider API change. Inspect the task log payload "
            "and review services/dataforseo.py::_extract_organic_items."
        ),
        systemic=False,
    ),
    ErrorCategory.LLM_AUTH: ErrorProfile(
        category=ErrorCategory.LLM_AUTH,
        severity=Severity.CRITICAL,
        title="OpenAI authentication rejected",
        remediation=(
            "OPENAI_API_KEY is invalid or revoked. Rotate it in the OpenAI console and "
            "restart the worker. Rank tracking continues, but no intent-shift "
            "analysis will run."
        ),
        systemic=True,
    ),
    ErrorCategory.LLM_RATE_LIMIT: ErrorProfile(
        category=ErrorCategory.LLM_RATE_LIMIT,
        severity=Severity.WARNING,
        title="OpenAI rate limit hit",
        remediation=(
            "Analysis requests are exceeding the xAI rate limit. Lower worker "
            "--concurrency, or raise RANK_DROP_THRESHOLD so fewer movements "
            "trigger an LLM call. Affected drops keep their ranking data and can "
            "be re-analyzed."
        ),
        systemic=True,
    ),
    ErrorCategory.LLM_QUOTA: ErrorProfile(
        category=ErrorCategory.LLM_QUOTA,
        severity=Severity.CRITICAL,
        title="OpenAI quota or billing limit reached",
        remediation=(
            "The xAI account is out of credit or past its spending cap. Add "
            "credit. Ranking data is still being collected; only the AI diagnosis "
            "is unavailable."
        ),
        systemic=True,
    ),
    ErrorCategory.LLM_TIMEOUT: ErrorProfile(
        category=ErrorCategory.LLM_TIMEOUT,
        severity=Severity.WARNING,
        title="OpenAI request timed out",
        remediation=(
            "The model did not respond within OPENAI_TIMEOUT_SECONDS. Raise that "
            "value, or switch OPENAI_MODEL to a faster variant. Reasoning models "
            "are markedly slower on large SERP comparisons."
        ),
        systemic=False,
    ),
    ErrorCategory.LLM_UNAVAILABLE: ErrorProfile(
        category=ErrorCategory.LLM_UNAVAILABLE,
        severity=Severity.WARNING,
        title="OpenAI API unreachable or erroring",
        remediation=(
            "Provider-side 5xx or a network failure. Check the xAI status page. "
            "Ranking collection is unaffected."
        ),
        systemic=True,
    ),
    ErrorCategory.LLM_INVALID_OUTPUT: ErrorProfile(
        category=ErrorCategory.LLM_INVALID_OUTPUT,
        severity=Severity.WARNING,
        title="OpenAI produced no schema-valid analysis",
        remediation=(
            "All OPENAI_MAX_RETRIES attempts failed validation even after the error "
            "was fed back. The model is repeatedly failing to generate JSON valid "
            "for the schema: try a different OPENAI_MODEL or simplify "
            "llm/output_models.py::IntentShiftAnalysis."
        ),
        systemic=False,
    ),
    ErrorCategory.LLM_NOT_CONFIGURED: ErrorProfile(
        category=ErrorCategory.LLM_NOT_CONFIGURED,
        severity=Severity.CRITICAL,
        title="OpenAI API key is not configured",
        remediation=(
            "OPENAI_API_KEY is empty, so every analysis is failing immediately. Set "
            "it in .env and restart the worker. Until then the platform records "
            "rank drops but cannot explain them."
        ),
        systemic=True,
    ),
    ErrorCategory.DATABASE_CONNECTION: ErrorProfile(
        category=ErrorCategory.DATABASE_CONNECTION,
        severity=Severity.CRITICAL,
        title="PostgreSQL unreachable",
        remediation=(
            "The database refused or dropped the connection. Check that the "
            "postgres service is running and that DATABASE_URL is correct for "
            "this context — compose hostnames do not resolve outside Docker. "
            "Nothing can be read or written while this persists."
        ),
        systemic=True,
    ),
    ErrorCategory.DATABASE_ERROR: ErrorProfile(
        category=ErrorCategory.DATABASE_ERROR,
        severity=Severity.CRITICAL,
        title="Database error",
        remediation=(
            "The connection worked but the statement failed — often a pending "
            "migration or a constraint violation. Run 'alembic current' and "
            "compare against 'alembic heads'."
        ),
        systemic=False,
    ),
    ErrorCategory.REDIS_CONNECTION: ErrorProfile(
        category=ErrorCategory.REDIS_CONNECTION,
        severity=Severity.CRITICAL,
        title="Redis unreachable",
        remediation=(
            "Celery cannot broker work without Redis: no scheduled check will "
            "run. Verify the redis service and CELERY_BROKER_URL. Queued tasks "
            "survive if appendonly persistence is enabled."
        ),
        systemic=True,
    ),
    ErrorCategory.CONFIGURATION: ErrorProfile(
        category=ErrorCategory.CONFIGURATION,
        severity=Severity.CRITICAL,
        title="Configuration problem",
        remediation=(
            "A required setting is missing or invalid. Compare .env against "
            "backend/app/core/config.py, which is the authoritative list."
        ),
        systemic=True,
    ),
    ErrorCategory.UNKNOWN: ErrorProfile(
        category=ErrorCategory.UNKNOWN,
        severity=Severity.WARNING,
        title="Unclassified background failure",
        remediation=(
            "This error is not recognized by services/error_alerts.py. Read the "
            "traceback below; if the pattern recurs, add a classification rule "
            "so future occurrences arrive with guidance."
        ),
        systemic=False,
    ),
}


def _profile(category: ErrorCategory) -> ErrorProfile:
    return _PROFILES.get(category, _PROFILES[ErrorCategory.UNKNOWN])


def classify_exception(exc: BaseException) -> ErrorProfile:
    """Map an exception onto an actionable profile.

    Typed application exceptions are checked first — they carry an explicit
    category and are unambiguous. Library exceptions are matched by class, and
    only then does the function fall back to message inspection, which is the
    least reliable signal.
    """
    # 1. Our own typed exceptions know their own category.
    category = getattr(exc, "error_category", None)
    if isinstance(category, ErrorCategory):
        return _profile(category)

    module = type(exc).__module__ or ""
    name = type(exc).__name__
    message = str(exc).lower()

    # 2. SQLAlchemy / asyncpg.
    if module.startswith("sqlalchemy") or module.startswith("asyncpg"):
        connection_markers = (
            "OperationalError",
            "InterfaceError",
            "DBAPIError",
            "ConnectionDoesNotExistError",
            "CannotConnectNowError",
        )
        if name in connection_markers or any(
            marker in message
            for marker in (
                "connection refused",
                "could not connect",
                "server closed the connection",
                "connection reset",
                "too many clients",
                "terminating connection",
            )
        ):
            return _profile(ErrorCategory.DATABASE_CONNECTION)
        return _profile(ErrorCategory.DATABASE_ERROR)

    # 3. Redis.
    if module.startswith("redis") or "redis" in module:
        return _profile(ErrorCategory.REDIS_CONNECTION)

    # 4. Celery broker connectivity surfaces as kombu errors.
    if module.startswith("kombu") or module.startswith("amqp"):
        return _profile(ErrorCategory.REDIS_CONNECTION)

    # 5. OpenAI SDK exception classes.
    if module.startswith("openai"):
        if name in ("RateLimitError",):
            # The SDK reports billing exhaustion as a 429 too; the message is
            # the only way to tell "slow down" from "out of money".
            if any(
                marker in message
                for marker in ("quota", "billing", "credit", "insufficient", "exceeded your")
            ):
                return _profile(ErrorCategory.LLM_QUOTA)
            return _profile(ErrorCategory.LLM_RATE_LIMIT)
        if name in ("AuthenticationError", "PermissionDeniedError"):
            return _profile(ErrorCategory.LLM_AUTH)
        if name in ("APITimeoutError",):
            return _profile(ErrorCategory.LLM_TIMEOUT)
        if name in ("InternalServerError", "APIConnectionError", "APIStatusError", "APIError"):
            return _profile(ErrorCategory.LLM_UNAVAILABLE)
        return _profile(ErrorCategory.LLM_UNAVAILABLE)

    # 6. httpx transport failures, which reach here only if a service layer
    #    did not already wrap them in a typed exception.
    if module.startswith("httpx"):
        if "timeout" in name.lower() or "timeout" in message:
            return _profile(ErrorCategory.SERP_UNAVAILABLE)
        return _profile(ErrorCategory.SERP_UNAVAILABLE)

    # 7. Last resort: message keywords.
    if "rate limit" in message or "429" in message:
        return _profile(ErrorCategory.LLM_RATE_LIMIT)
    if "connection refused" in message or "could not connect" in message:
        return _profile(ErrorCategory.DATABASE_CONNECTION)

    return _profile(ErrorCategory.UNKNOWN)


def build_throttle_key(
    category: ErrorCategory, scope: str | None = None
) -> str:
    """Group alerts that an operator would treat as one incident.

    Systemic failures (a dead database, an exhausted quota) are keyed by
    category alone, so 200 failing keywords produce one message. Non-systemic
    failures are additionally keyed by scope, so a genuinely per-keyword problem
    is not hidden behind an unrelated one.
    """
    profile = _profile(category)
    if profile.systemic or not scope:
        return f"seo:alert:{category.value}"
    digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:16]
    return f"seo:alert:{category.value}:{digest}"


def throttle_window_seconds(profile: ErrorProfile) -> int:
    """Systemic incidents get a longer quiet period than one-off failures."""
    base = settings.alert_throttle_seconds
    return base * 3 if profile.systemic else base


async def report_error(
    exc: BaseException,
    *,
    source: str,
    scope: str | None = None,
    target_url: str | None = None,
    keyword: str | None = None,
    context: dict[str, Any] | None = None,
    traceback_text: str | None = None,
) -> bool:
    """Classify, throttle, and send an operator-facing Slack alert.

    Returns whether a message was actually delivered. Never raises: alerting is
    a side channel and must not be able to fail the caller's work.
    """
    # Imported here to avoid a circular import: slack imports nothing from this
    # module, but this module needs slack.
    from app.services.slack import send_classified_error_alert

    try:
        profile = classify_exception(exc)

        if not settings.error_alerts_enabled:
            logger.info(
                "Error alerts disabled in config; not sending %s from %s",
                profile.category,
                source,
            )
            return False

        # Master Slack switch. Checked here as well as inside slack._post so the
        # throttle slot is not consumed while delivery is off — otherwise the
        # first real alert after re-enabling Slack would be silently suppressed
        # as a "duplicate" of one that never actually went anywhere.
        if not settings.slack_enabled:
            logger.info(
                "SLACK_ENABLED=false; %s from %s not delivered",
                profile.category,
                source,
            )
            if settings.slack_log_suppressed_messages:
                logger.info(
                    "Would have alerted: [%s] %s — %s | remediation: %s",
                    profile.severity,
                    profile.title,
                    str(exc)[:500],
                    profile.remediation,
                )
            return False

        # Runtime kill switch, checked after the config flag so a paused switch
        # is visible in the log even when config would have allowed the send.
        # Wrapped defensively: if the switch cannot be read (for instance the
        # database is the thing that failed), the alert still goes out.
        try:
            from app.models.service_control import ServiceKey
            from app.services import controls

            if not await controls.is_enabled(ServiceKey.ERROR_ALERTS):
                logger.info(
                    "Error alerts paused from the control panel; dropping %s from %s",
                    profile.category,
                    source,
                )
                return False
        except Exception:
            logger.warning(
                "Could not read the ERROR_ALERTS switch; sending the alert anyway"
            )

        key = build_throttle_key(profile.category, scope)
        allowed, suppressed = await claim_alert_slot(
            key, throttle_window_seconds(profile)
        )

        if not allowed:
            logger.info(
                "Suppressed duplicate %s alert from %s (%s suppressed in window)",
                profile.category,
                source,
                suppressed,
            )
            return False

        return await send_classified_error_alert(
            profile=profile,
            error=f"{type(exc).__name__}: {exc}",
            source=source,
            target_url=target_url,
            keyword=keyword,
            context=context,
            traceback_text=traceback_text,
            suppressed_since_last=suppressed,
        )
    except Exception:
        logger.exception("Failed to report error to Slack (original error: %r)", exc)
        return False


async def report_recovery(category: ErrorCategory, scope: str | None = None) -> None:
    """Clear a throttle window after a subsystem is confirmed healthy again.

    Without this, a failure occurring shortly after a recovery could be silenced
    by the previous incident's still-open window.
    """
    from app.core.redis_client import reset_alert_slot

    await reset_alert_slot(build_throttle_key(category, scope))
