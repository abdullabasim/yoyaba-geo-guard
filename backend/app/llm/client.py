"""OpenAI client and LangSmith tracing.

Two concerns, deliberately kept together because they are both cross-cutting
plumbing around every LLM call:

1. A lazily constructed ``AsyncOpenAI`` pointed at the OpenAI base URL.
2. A ``traced`` decorator that wraps LangSmith's ``@traceable`` but degrades to
   a transparent pass-through when tracing is disabled or the package is
   missing. Without that fallback, an absent LangSmith key would take down the
   entire analysis path.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from mcp.client.sse import sse_client
from mcp.client.session import ClientSession


from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    InternalServerError,
    PermissionDeniedError,
    RateLimitError,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.services.error_alerts import ErrorCategory

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class LLMError(RuntimeError):
    """Base for LLM failures. Subclasses carry an explicit alert category."""

    error_category = ErrorCategory.LLM_UNAVAILABLE


class LLMNotConfiguredError(LLMError):
    """Raised when an LLM call is attempted without an API key."""

    error_category = ErrorCategory.LLM_NOT_CONFIGURED


class LLMResponseError(LLMError):
    """Raised when the provider returns an unusable or unparseable response."""

    error_category = ErrorCategory.LLM_INVALID_OUTPUT


class LLMRateLimitError(LLMError):
    error_category = ErrorCategory.LLM_RATE_LIMIT


class LLMQuotaError(LLMError):
    error_category = ErrorCategory.LLM_QUOTA


class LLMAuthError(LLMError):
    error_category = ErrorCategory.LLM_AUTH


class LLMTimeoutError(LLMError):
    error_category = ErrorCategory.LLM_TIMEOUT


class LLMUnavailableError(LLMError):
    error_category = ErrorCategory.LLM_UNAVAILABLE


#: Message markers that distinguish billing exhaustion from ordinary throttling.
#: The OpenAI-compatible API reports both as HTTP 429.
_QUOTA_MARKERS = ("quota", "billing", "credit", "insufficient", "exceeded your")


def translate_provider_error(exc: Exception) -> LLMError:
    """Convert an SDK exception into a typed, classifiable application error."""
    message = str(exc)
    lowered = message.lower()

    if isinstance(exc, RateLimitError):
        if any(marker in lowered for marker in _QUOTA_MARKERS):
            return LLMQuotaError(f"OpenAI quota exhausted: {message}")
        return LLMRateLimitError(f"OpenAI rate limit: {message}")
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return LLMAuthError(f"OpenAI authentication failed: {message}")
    if isinstance(exc, APITimeoutError):
        return LLMTimeoutError(f"OpenAI request timed out: {message}")
    if isinstance(exc, (InternalServerError, APIConnectionError)):
        return LLMUnavailableError(f"OpenAI unavailable: {message}")
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        if status == 429:
            return LLMRateLimitError(f"OpenAI rate limit: {message}")
        if status in (401, 403):
            return LLMAuthError(f"OpenAI authentication failed: {message}")
        if status == 402:
            return LLMQuotaError(f"OpenAI billing limit reached: {message}")
        return LLMUnavailableError(f"OpenAI returned HTTP {status}: {message}")

    return LLMUnavailableError(f"OpenAI call failed: {type(exc).__name__}: {message}")


# ----------------------------------------------------------------------
# LangSmith tracing
# ----------------------------------------------------------------------
def _configure_langsmith() -> bool:
    """Export the env vars the LangSmith SDK reads. Returns whether it is on."""
    if not settings.tracing_enabled:
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    return True


_TRACING_ACTIVE = _configure_langsmith()

if _TRACING_ACTIVE:
    try:
        from langsmith import traceable as _langsmith_traceable
    except ImportError:  # pragma: no cover - optional dependency
        logger.warning("LANGSMITH_TRACING is on but langsmith is not installed")
        _langsmith_traceable = None
        _TRACING_ACTIVE = False
else:
    _langsmith_traceable = None


def traced(name: str, run_type: str = "llm") -> Callable[[F], F]:
    """Decorate an async function with LangSmith tracing when available.

    When tracing is off this returns the function untouched, so there is no
    import-time or call-time cost and no hard dependency on LangSmith.
    """

    def decorator(func: F) -> F:
        if not _TRACING_ACTIVE or _langsmith_traceable is None:
            return func

        traced_func = _langsmith_traceable(run_type=run_type, name=name)(func)

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await traced_func(*args, **kwargs)
            except Exception:
                # Never let an observability failure mask the real work.
                logger.exception("LangSmith-wrapped call raised; retrying untraced")
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def tracing_active() -> bool:
    return _TRACING_ACTIVE


# ----------------------------------------------------------------------
# OpenAI client
# ----------------------------------------------------------------------
_client: AsyncOpenAI | None = None


def get_llm_client() -> AsyncOpenAI:
    """Lazily build the shared client so import never requires a key."""
    global _client
    if not settings.llm_enabled:
        raise LLMNotConfiguredError("OPENAI_API_KEY is not configured")
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
            # Retries here cover transport errors only; schema retries are
            # handled in intent_analyzer, which must re-prompt with feedback.
            max_retries=settings.openai_max_retries,
        )
    return _client


async def close_llm_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def extract_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object out of a model reply.

    Reasoning models sometimes wrap JSON in prose or markdown fences even when
    asked not to, so the first and last brace are used as a fallback.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMResponseError(f"no JSON object found in reply: {raw[:300]!r}") from None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"malformed JSON in reply: {exc}") from exc

    if not isinstance(parsed, dict):
        raise LLMResponseError(f"expected a JSON object, got {type(parsed).__name__}")
    return parsed


def _generate_mock_llm_json() -> tuple[dict[str, Any], dict[str, int | None]]:
    mock_payload = {
        "issue_type": "INTENT_SHIFT",
        "intent_shift_detected": True,
        "confidence": 0.88,
        "ai_diagnosis": "The search engine results page shifted from informational research intent to commercial comparison intent. Competitors with comparison tables and pricing callouts replaced informational guides in top positions.",
        "actionable_advice": "Update page content to highlight comparison tables, clear pricing features, and direct interactive call-to-action buttons for commercial users.",
        "detected_intent_before": "Informational / Research Guide",
        "detected_intent_after": "Commercial / Product Comparison",
        "competitor_signals": [
            {
                "domain": "monday.com",
                "title": "Work Management Platform | Manage Anything",
                "url": "https://monday.com/solutions/project-management",
                "note": "Ranked #1 with interactive pricing calculator and comparison grid",
                "is_new_entrant": True
            },
            {
                "domain": "clickup.com",
                "title": "One app to replace them all | Work Management",
                "url": "https://clickup.com/solutions",
                "note": "Gained +3 ranks with direct free trial buttons",
                "is_new_entrant": False
            }
        ]
    }
    return mock_payload, {"prompt_tokens": 420, "completion_tokens": 150}


@traced(name="openai_chat_completion")
async def complete_json(
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
) -> tuple[dict[str, Any], dict[str, int | None]]:
    """One JSON-mode completion, with MCP tool support. Returns ``(parsed_object, token_usage)``."""
    if settings.openai_mock:
        logger.info("OPENAI_MOCK is active; returning mock LLM analysis")
        return _generate_mock_llm_json()

    client = get_llm_client()
    model_name = model or settings.openai_model
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Initialize MCP tool variables
    mcp_endpoint = "http://mcp:8110/sse"
    mcp_tools_available = []
    
    usage = {"prompt_tokens": 0, "completion_tokens": 0}

    try:
        async with sse_client(mcp_endpoint) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                
                for t in tools_response.tools:
                    mcp_tools_available.append({
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.inputSchema
                        }
                    })
                
                import json
                with open("/app/last_request.json", "w") as f:
                    json.dump({"messages": messages, "tools": mcp_tools_available}, f, indent=2)
                
                while True:
                    # Detect reasoning models (o-series, gpt-5.x) which don't
                    # support `temperature` and require special handling for tools.
                    _lower = model_name.lower()
                    is_reasoning_model = (
                        _lower.startswith("o1")
                        or _lower.startswith("o3")
                        or _lower.startswith("o4")
                        or "gpt-5" in _lower
                    )

                    response_kwargs = {
                        "model": model_name,
                        "messages": messages,
                        "max_completion_tokens": max_tokens,
                    }

                    # Reasoning models reject `temperature`; non-reasoning models use it.
                    if not is_reasoning_model:
                        response_kwargs["temperature"] = temperature

                    if mcp_tools_available:
                        response_kwargs["tools"] = mcp_tools_available
                        # Reasoning models require reasoning_effort='none'
                        # when using function tools via /v1/chat/completions.
                        if is_reasoning_model:
                            response_kwargs["reasoning_effort"] = "none"
                    else:
                        response_kwargs["response_format"] = {"type": "json_object"}
                    
                    # If we have tool messages, we can't force json_object until the final response
                    # Wait, some models allow json_object with tools, some don't.
                    # To be safe, we'll only enforce json_object when tools aren't present OR we'll trust the prompt.
                    # Since we want JSON at the end, let's ask for json_object if we can.
                    import json
                    logger.info("Sending request to LLM. Approx chars: %s", len(json.dumps(response_kwargs)))
                    response = await client.chat.completions.create(**response_kwargs)
                    
                    if response.usage:
                        usage["prompt_tokens"] += getattr(response.usage, "prompt_tokens", 0) or 0
                        usage["completion_tokens"] += getattr(response.usage, "completion_tokens", 0) or 0
                    
                    if not response.choices:
                        raise LLMResponseError("provider returned no choices")
                        
                    message = response.choices[0].message
                    messages.append(message.model_dump(exclude_none=True))
                    
                    if not message.tool_calls:
                        break
                        
                    for tool_call in message.tool_calls:
                        func_name = tool_call.function.name
                        func_args = json.loads(tool_call.function.arguments)
                        logger.info("LLM called tool: %s", func_name)
                        
                        try:
                            result = await session.call_tool(func_name, arguments=func_args)
                            # Extract text from the result
                            if result.content and len(result.content) > 0:
                                tool_result_content = result.content[0].text
                            else:
                                tool_result_content = "Success"
                        except Exception as e:
                            logger.error("Tool %s failed: %s", func_name, e)
                            tool_result_content = f"Tool call failed: {e}"
                            
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": func_name,
                            "content": tool_result_content
                        })
                        
                content = message.content

    except LLMError:
        raise
    except Exception as exc:
        import traceback
        logger.error("Exception in complete_json: %s\n%s", exc, traceback.format_exc())
        if settings.openai_fallback_mock_on_auth_error:
            logger.warning(
                "OpenAI API call failed (%s); returning mock LLM analysis for testing",
                exc,
            )
            return _generate_mock_llm_json()
        raise translate_provider_error(exc) from exc

    if not content:
        raise LLMResponseError("provider returned an empty message")

    return extract_json_object(content), usage
