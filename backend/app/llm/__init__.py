"""The LLM boundary.

All OpenAI interaction, prompt text, structured-output models and LangSmith
tracing live entirely within this package. The worker imports nothing but
``detect_intent_shift`` and
never talk to the LLM provider directly.
"""

from app.llm.client import (
    LLMAuthError,
    LLMError,
    LLMNotConfiguredError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
    close_llm_client,
    complete_json,
    get_llm_client,
    traced,
    tracing_active,
    translate_provider_error,
)
from app.llm.intent_analyzer import IntentAnalysisError, detect_intent_shift
from app.llm.output_models import (
    CompetitorSignal,
    IntentShiftAnalysis,
    LLMAnalysisOutcome,
)
from app.llm.prompts import PROMPT_VERSION, SYSTEM_PROMPT

__all__ = [
    "PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "CompetitorSignal",
    "IntentAnalysisError",
    "IntentShiftAnalysis",
    "LLMAnalysisOutcome",
    "LLMAuthError",
    "LLMError",
    "LLMNotConfiguredError",
    "LLMQuotaError",
    "LLMRateLimitError",
    "LLMResponseError",
    "LLMTimeoutError",
    "LLMUnavailableError",
    "close_llm_client",
    "complete_json",
    "detect_intent_shift",
    "get_llm_client",
    "traced",
    "tracing_active",
    "translate_provider_error",
]
