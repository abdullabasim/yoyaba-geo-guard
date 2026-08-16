"""Slack webhook delivery.

Two destinations: business alerts and system failures. Delivery failures are
logged and reported through the return value — never raised — because a Slack
outage must not turn a successful analysis into a failed task.

All delivery funnels through ``_post``, which is the single place the enable
switches are enforced. Checking them at each call site would guarantee that a
new sender eventually forgets one and posts to a live channel during testing.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import IssueType

logger = get_logger(__name__)

SLACK_TIMEOUT_SECONDS = 15.0


class SlackChannel(StrEnum):
    """Which switch and webhook a message belongs to.

    Business and error alerts are separately switchable: a noisy customer
    channel must be silenceable without also going blind to system failures.
    """

    BUSINESS = "business"
    ERROR = "error"


#: Counters of messages suppressed while Slack is disabled, per channel. Exposed
#: through the API so a test run can prove alerts *would* have fired.
_suppressed_counts: dict[SlackChannel, int] = {channel: 0 for channel in SlackChannel}


def suppressed_counts() -> dict[str, int]:
    return {channel.value: count for channel, count in _suppressed_counts.items()}


def reset_suppressed_counts() -> None:
    for channel in SlackChannel:
        _suppressed_counts[channel] = 0


def channel_state(channel: SlackChannel) -> tuple[bool, str]:
    """``(deliverable, reason)`` for one channel.

    The reason is surfaced verbatim in logs and in the API, so "why did I get no
    Slack message" is answered without reading the code.
    """
    if not settings.slack_enabled:
        return False, "SLACK_ENABLED=false (master switch)"

    if channel is SlackChannel.BUSINESS:
        if not settings.slack_business_alerts_enabled:
            return False, "SLACK_BUSINESS_ALERTS_ENABLED=false"
        if not settings.slack_webhook_alerts:
            return False, "SLACK_WEBHOOK_ALERTS is empty"
        return True, "enabled"

    if not settings.error_alerts_enabled:
        return False, "ERROR_ALERTS_ENABLED=false"
    if not settings.error_webhook:
        return False, "SLACK_WEBHOOK_ERRORS and SLACK_WEBHOOK_ALERTS are both empty"
    return True, "enabled"


def delivery_status() -> dict[str, Any]:
    """Human-readable view of what Slack would do right now."""
    business_ok, business_reason = channel_state(SlackChannel.BUSINESS)
    error_ok, error_reason = channel_state(SlackChannel.ERROR)
    return {
        "slack_enabled": settings.slack_enabled,
        "business_alerts": {
            "deliverable": business_ok,
            "reason": business_reason,
            "webhook_configured": bool(settings.slack_webhook_alerts),
        },
        "error_alerts": {
            "deliverable": error_ok,
            "reason": error_reason,
            "webhook_configured": bool(settings.error_webhook),
        },
        "log_suppressed_messages": settings.slack_log_suppressed_messages,
        "suppressed_since_start": suppressed_counts(),
    }


_ISSUE_EMOJI = {
    IssueType.INTENT_SHIFT: ":arrows_counterclockwise:",
    IssueType.SERP_FEATURE_CHANGE: ":sparkles:",
    IssueType.NEW_COMPETITOR: ":crossed_swords:",
    IssueType.CONTENT_FRESHNESS: ":clock3:",
    IssueType.ALGORITHM_UPDATE: ":cyclone:",
    IssueType.NO_SIGNIFICANT_CHANGE: ":white_circle:",
    IssueType.UNKNOWN: ":grey_question:",
}


def _log_suppressed(channel: SlackChannel, reason: str, payload: dict[str, Any]) -> None:
    summary = payload.get("text") or "(no fallback text)"
    if not settings.slack_log_suppressed_messages:
        logger.info("Slack %s message suppressed (%s): %s", channel.value, reason, summary)
        return

    # The full payload, so a test run with Slack off can still verify exactly
    # what would have been delivered.
    try:
        rendered = json.dumps(payload, indent=2, default=str)
    except (TypeError, ValueError):
        rendered = repr(payload)
    logger.info(
        "Slack %s message suppressed (%s).\nSummary: %s\nPayload:\n%s",
        channel.value,
        reason,
        summary,
        rendered,
    )


async def _post(
    webhook_url: str,
    payload: dict[str, Any],
    *,
    channel: SlackChannel = SlackChannel.ERROR,
) -> bool:
    """Deliver one message. Returns True only on confirmed delivery.

    Returning False for a suppressed message is deliberate: callers use the
    return value to set ``slack_sent``, and recording an undelivered alert as
    sent would make the "Resend" action unavailable for exactly the messages that
    need it.
    """
    deliverable, reason = channel_state(channel)
    if not deliverable:
        _suppressed_counts[channel] += 1
        _log_suppressed(channel, reason, payload)
        return False

    if not webhook_url:
        # Should be unreachable via channel_state, but a wrong explicit URL
        # argument must not turn into a confusing httpx error.
        logger.warning("Slack webhook not configured; message dropped")
        return False

    try:
        async with httpx.AsyncClient(timeout=SLACK_TIMEOUT_SECONDS) as client:
            response = await client.post(webhook_url, json=payload)
        if response.status_code >= 400:
            logger.error(
                "Slack rejected the message: HTTP %s %s",
                response.status_code,
                response.text[:300],
            )
            return False
        return True
    except httpx.HTTPError as exc:
        logger.error("Slack delivery failed: %s", exc)
        return False


def _rank_movement(previous_rank: int | None, current_rank: int | None) -> str:
    if previous_rank is None and current_rank is None:
        return "not ranking"
    if previous_rank is None:
        return f"newly ranking at #{current_rank}"
    if current_rank is None:
        return f"dropped out of results (was #{previous_rank})"
    delta = current_rank - previous_rank
    direction = "down" if delta > 0 else "up"
    return f"#{previous_rank} -> #{current_rank} ({direction} {abs(delta)})"


async def send_intent_shift_alert(
    *,
    keyword: str,
    url: str,
    client_name: str | None,
    project_name: str | None,
    previous_rank: int | None,
    current_rank: int | None,
    issue_type: IssueType,
    ai_diagnosis: str,
    actionable_advice: str,
    confidence: float | None,
    competitor_signals: list[dict[str, Any]] | None = None,
    model_used: str | None = None,
) -> bool:
    """Post the business alert. Returns True only on confirmed delivery."""
    emoji = _ISSUE_EMOJI.get(issue_type, ":grey_question:")
    scope = " / ".join(part for part in (client_name, project_name) if part) or "-"
    confidence_text = f"{confidence:.0%}" if confidence is not None else "n/a"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} Ranking drop: {issue_type.value.replace('_', ' ').title()}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Keyword*\n`{keyword}`"},
                {"type": "mrkdwn", "text": f"*Movement*\n{_rank_movement(previous_rank, current_rank)}"},
                {"type": "mrkdwn", "text": f"*Account*\n{scope}"},
                {"type": "mrkdwn", "text": f"*Confidence*\n{confidence_text}"},
            ],
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*URL*\n<{url}>"}},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Diagnosis*\n{ai_diagnosis[:2800]}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Recommended action*\n{actionable_advice[:2800]}"},
        },
    ]

    if competitor_signals:
        lines = []
        for signal in competitor_signals[:5]:
            domain = signal.get("domain") or ""
            title = signal.get("title") or domain or "unknown"
            sig_url = signal.get("url") or ""
            note = signal.get("note") or signal.get("reason") or ""
            is_new = signal.get("is_new_entrant")

            title_link = f"*<{sig_url}|{title}>*" if sig_url else f"*{title}*"
            domain_badge = f"`{domain}` " if domain else ""
            new_badge = "*[NEW ENTRANT]* " if is_new else ""

            lines.append(f"- {domain_badge}{title_link} {new_badge}— {note}".strip())
        if lines:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Competitor signals*\n" + "\n".join(lines)[:2800]},
                }
            )

    if model_used:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Analyzed by `{model_used}`"}],
            }
        )

    return await _post(
        settings.slack_webhook_alerts,
        {
            # Fallback text for notifications and clients that ignore blocks.
            "text": f"Ranking drop for '{keyword}': {issue_type.value}",
            "blocks": blocks,
        },
        channel=SlackChannel.BUSINESS,
    )


async def send_system_failure_alert(
    *,
    task_name: str,
    error: str,
    target_url: str | None = None,
    keyword: str | None = None,
    context: dict[str, Any] | None = None,
) -> bool:
    """Unclassified fallback notification.

    Prefer ``services.error_alerts.report_error``, which classifies the failure,
    attaches remediation guidance and throttles duplicates. This remains for
    callers that have only a message and no exception object.
    """
    fields = [
        {"type": "mrkdwn", "text": f"*Task*\n`{task_name}`"},
        {"type": "mrkdwn", "text": f"*Environment*\n{settings.app_env}"},
    ]
    if target_url:
        fields.append({"type": "mrkdwn", "text": f"*URL*\n{target_url[:200]}"})
    if keyword:
        fields.append({"type": "mrkdwn", "text": f"*Keyword*\n`{keyword}`"})

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":rotating_light: Background task failed"},
        },
        {"type": "section", "fields": fields},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Error*\n```{error[:2500]}```"},
        },
    ]

    if context:
        rendered = "\n".join(f"{key}: {value}" for key, value in context.items())
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Context*\n```{rendered[:2000]}```"},
            }
        )

    return await _post(
        settings.error_webhook,
        {"text": f"Task {task_name} failed: {error[:200]}", "blocks": blocks},
        channel=SlackChannel.ERROR,
    )


_SEVERITY_STYLE = {
    "CRITICAL": (":rotating_light:", "CRITICAL"),
    "WARNING": (":warning:", "Warning"),
    "INFO": (":information_source:", "Info"),
}


async def send_classified_error_alert(
    *,
    profile: Any,
    error: str,
    source: str,
    target_url: str | None = None,
    keyword: str | None = None,
    context: dict[str, Any] | None = None,
    traceback_text: str | None = None,
    suppressed_since_last: int = 0,
) -> bool:
    """Send an operator-facing alert that says what broke and what to do.

    ``profile`` is a ``services.error_alerts.ErrorProfile``. It is typed loosely
    here to keep this module free of an import cycle.
    """
    emoji, severity_label = _SEVERITY_STYLE.get(
        str(profile.severity), (":rotating_light:", str(profile.severity))
    )

    fields = [
        {"type": "mrkdwn", "text": f"*Severity*\n{severity_label}"},
        {"type": "mrkdwn", "text": f"*Category*\n`{profile.category}`"},
        {"type": "mrkdwn", "text": f"*Source*\n`{source}`"},
        {"type": "mrkdwn", "text": f"*Environment*\n{settings.app_env}"},
    ]
    if keyword:
        fields.append({"type": "mrkdwn", "text": f"*Keyword*\n`{keyword}`"})
    if target_url:
        fields.append({"type": "mrkdwn", "text": f"*URL*\n{target_url[:200]}"})

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} {profile.title}"},
        },
        {"type": "section", "fields": fields},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*What to do*\n{profile.remediation}"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Error*\n```{error[:1500]}```"},
        },
    ]

    if context:
        rendered = "\n".join(f"{key}: {value}" for key, value in context.items())
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Context*\n```{rendered[:1500]}```"},
            }
        )

    if traceback_text:
        # Tail, not head: the actual failure is at the bottom of a traceback.
        tail = traceback_text.strip()[-1200:]
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Traceback (tail)*\n```{tail}```"},
            }
        )

    footer = "Alerts for this category are muted for a short window to prevent flooding."
    if suppressed_since_last > 0:
        footer = (
            f"{suppressed_since_last} identical failure(s) were suppressed since the "
            f"last alert. {footer}"
        )
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": footer}]})

    return await _post(
        settings.error_webhook,
        {
            "text": f"[{severity_label}] {profile.title} ({profile.category})",
            "blocks": blocks,
        },
        channel=SlackChannel.ERROR,
    )


async def send_recovery_notice(
    *, subsystem: str, detail: str | None = None
) -> bool:
    """Confirm a previously alerted subsystem is healthy again.

    Closing the loop matters: without it an operator cannot tell whether silence
    means recovery or means the alerting itself broke.
    """
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":white_check_mark: Recovered: {subsystem}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Subsystem*\n{subsystem}"},
                {"type": "mrkdwn", "text": f"*Environment*\n{settings.app_env}"},
            ],
        },
    ]
    if detail:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": detail[:1500]}}
        )

    return await _post(
        settings.error_webhook,
        {"text": f"Recovered: {subsystem}", "blocks": blocks},
        channel=SlackChannel.ERROR,
    )
