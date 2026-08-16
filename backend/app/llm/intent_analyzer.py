"""Intent-shift analysis: the only entry point the worker calls.

Resilience model: JSON mode guarantees syntactically valid JSON but not a valid
*shape*. So every reply is validated into ``IntentShiftAnalysis``, and on
``ValidationError`` the call is retried up to ``OPENAI_MAX_RETRIES`` times with
exponential backoff, re-prompting with the exact validator output appended so
the model can correct itself instead of repeating the same mistake.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.client import (
    LLMError,
    LLMNotConfiguredError,
    LLMResponseError,
    complete_json,
    traced,
)
from app.llm.output_models import IntentShiftAnalysis, LLMAnalysisOutcome
from app.llm.prompts import (
    SYSTEM_PROMPT,
    build_analysis_prompt,
    build_retry_prompt,
)
from app.services.error_alerts import ErrorCategory

logger = get_logger(__name__)


class IntentAnalysisError(RuntimeError):
    """Raised when no schema-valid analysis could be produced after all retries."""

    error_category = ErrorCategory.LLM_INVALID_OUTPUT


def _format_datetime(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M UTC") if value else None


@traced(name="detect_intent_shift", run_type="chain")
async def detect_intent_shift(
    *,
    keyword: str,
    target_url: str,
    previous_rank: int | None,
    current_rank: int | None,
    previous_snapshot: list[dict[str, Any]],
    current_snapshot: list[dict[str, Any]],
    previous_check_date: datetime | None = None,
    current_check_date: datetime | None = None,
    location_code: int | None = None,
    language_code: str | None = None,
) -> LLMAnalysisOutcome:
    """Diagnose a ranking drop, returning a schema-valid analysis.

    Raises ``IntentAnalysisError`` when the model cannot produce valid output,
    or ``LLMNotConfiguredError`` when no API key is configured. Both are handled
    by the calling task, which records FAILED and alerts admins.
    """
    if not settings.llm_enabled:
        raise LLMNotConfiguredError("OPENAI_API_KEY is not configured")

    base_prompt = build_analysis_prompt(
        keyword=keyword,
        target_url=target_url,
        previous_rank=previous_rank,
        current_rank=current_rank,
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        previous_check_date=_format_datetime(previous_check_date),
        current_check_date=_format_datetime(current_check_date),
        location_code=location_code,
        language_code=language_code,
    )

    max_attempts = max(1, settings.openai_max_retries)
    prompt = base_prompt
    last_error: str = "unknown error"

    for attempt in range(1, max_attempts + 1):
        try:
            payload, usage = await complete_json(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
            )
            analysis = IntentShiftAnalysis.model_validate(payload)

            return LLMAnalysisOutcome(
                analysis=analysis,
                model_used=settings.openai_model,
                attempts=attempt,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )

        except (ValidationError, LLMResponseError) as exc:
            last_error = str(exc)
            logger.warning(
                "LLM analysis attempt %s/%s produced invalid output for '%s': %s",
                attempt,
                max_attempts,
                keyword,
                last_error[:500],
            )
            if attempt >= max_attempts:
                break
            prompt = build_retry_prompt(base_prompt, last_error)
            await asyncio.sleep(2 ** (attempt - 1))

        except LLMError:
            # Rate limits, dead keys, timeouts and outages are infrastructure
            # problems, not schema problems. Re-prompting cannot fix them, and
            # wrapping them would erase the category the alerting layer needs to
            # tell the operator what to actually do.
            raise

        except Exception as exc:
            raise IntentAnalysisError(
                f"LLM call failed for keyword '{keyword}': {type(exc).__name__}: {exc}"
            ) from exc

    raise IntentAnalysisError(
        f"LLM produced no schema-valid analysis for keyword '{keyword}' "
        f"after {max_attempts} attempts. Last error: {last_error[:500]}"
    )
