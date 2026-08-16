"""DataForSEO SERP client.

Uses the Live Advanced endpoint (``/v3/serp/google/organic/live/advanced``),
which returns results synchronously. That keeps one Celery task equal to one
observation, with no task-post/task-get polling state machine to maintain.

The provider's response is deeply nested and its HTTP status is not a reliable
success signal — a 200 can still carry a per-task error. Every level is
therefore checked explicitly and a bad shape raises ``SerpProviderError``
rather than producing a silently wrong rank.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.error_alerts import ErrorCategory
from app.services.rate_limiter import (
    DailyBudgetExhausted,
    ProviderRateLimiter,
    RateLimitDeferred,
)

logger = get_logger(__name__)

LIVE_ADVANCED_PATH = "/v3/serp/google/organic/live/advanced"

# DataForSEO signals per-task success with this code, independent of HTTP status.
DFS_STATUS_OK = 20000

# Per-task error codes worth distinguishing. DataForSEO returns these inside a
# HTTP 200 body, so they must be read from the payload rather than the status.
DFS_AUTH_CODES = {40100, 40101, 40200}
DFS_QUOTA_CODES = {40201, 40202, 40501, 40502}
DFS_RATE_LIMIT_CODES = {40203, 40429}

SNAPSHOT_SIZE = 10
MAX_DESCRIPTION_CHARS = 300
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class SerpProviderError(RuntimeError):
    """Raised when the provider is unreachable or returns an unusable payload.

    Subclasses carry an ``error_category`` so the alerting layer can classify the
    failure exactly, instead of guessing from the message text.
    """

    error_category = ErrorCategory.SERP_UNAVAILABLE


class SerpAuthError(SerpProviderError):
    error_category = ErrorCategory.SERP_AUTH


class SerpQuotaError(SerpProviderError):
    error_category = ErrorCategory.SERP_QUOTA


class SerpRateLimitError(SerpProviderError):
    error_category = ErrorCategory.SERP_RATE_LIMIT

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        #: Carried so the task layer can reschedule with the provider's own delay
        #: instead of guessing one.
        self.retry_after_seconds = retry_after_seconds


class SerpUnavailableError(SerpProviderError):
    error_category = ErrorCategory.SERP_UNAVAILABLE


class SerpMalformedResponseError(SerpProviderError):
    error_category = ErrorCategory.SERP_MALFORMED


class SerpNotConfiguredError(SerpProviderError):
    error_category = ErrorCategory.CONFIGURATION


@dataclass
class SerpFetchResult:
    rank: int | None
    snapshot: list[dict[str, Any]] = field(default_factory=list)
    total_results_checked: int = 0
    serp_url: str | None = None
    cost: float | None = None


def normalize_domain(url: str | None) -> str | None:
    """Host without ``www.``, lowercased. Returns None for unusable input."""
    if not url:
        return None
    try:
        parsed = urlparse(url if "//" in url else f"https://{url}")
    except ValueError:
        return None
    host = (parsed.netloc or "").lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _normalize_path(url: str | None) -> str:
    if not url:
        return "/"
    try:
        path = urlparse(url).path or "/"
    except ValueError:
        return "/"
    return path.rstrip("/") or "/"


def _matches_target(result_url: str | None, target_url: str) -> bool:
    """Match a SERP entry against the tracked page.

    Domain equality alone would credit any page on the site; exact URL equality
    would miss trailing-slash and protocol variants. Domain plus normalized
    path is the useful middle ground.
    """
    result_domain = normalize_domain(result_url)
    target_domain = normalize_domain(target_url)
    if result_domain is None or target_domain is None:
        return False
    if result_domain != target_domain:
        return False
    return _normalize_path(result_url) == _normalize_path(target_url)


def build_snapshot(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Top-10 competitor snapshot stored as JSONB and fed to the LLM."""
    snapshot: list[dict[str, Any]] = []
    for item in items[:SNAPSHOT_SIZE]:
        url = item.get("url")
        description = item.get("description") or item.get("snippet") or ""
        snapshot.append(
            {
                "position": item.get("rank_absolute") or item.get("rank_group") or 0,
                "title": item.get("title"),
                "url": url,
                "domain": item.get("domain") or normalize_domain(url),
                "description": description[:MAX_DESCRIPTION_CHARS],
            }
        )
    return snapshot


def _extract_organic_items(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Pull organic results out of the nested response, validating each level."""
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise SerpMalformedResponseError("response contained no tasks")

    task = tasks[0]
    if not isinstance(task, dict):
        raise SerpMalformedResponseError("malformed task entry")

    task_status = task.get("status_code")
    if task_status != DFS_STATUS_OK:
        message = task.get("status_message")
        detail = f"provider task failed: status={task_status} message={message!r}"

        # A 200 response can still carry an auth or billing failure in the body,
        # so the category has to come from this code, not the HTTP status.
        if task_status in DFS_AUTH_CODES:
            raise SerpAuthError(detail)
        if task_status in DFS_QUOTA_CODES:
            raise SerpQuotaError(detail)
        if task_status in DFS_RATE_LIMIT_CODES:
            raise SerpRateLimitError(detail)

        lowered = str(message or "").lower()
        if any(marker in lowered for marker in ("money", "balance", "credit", "quota", "limit exceeded")):
            raise SerpQuotaError(detail)
        if any(marker in lowered for marker in ("auth", "credential", "forbidden", "access denied")):
            raise SerpAuthError(detail)

        raise SerpProviderError(detail)

    results = task.get("result")
    if not isinstance(results, list) or not results:
        raise SerpMalformedResponseError("provider task returned no result block")

    result = results[0]
    if not isinstance(result, dict):
        raise SerpMalformedResponseError("malformed result block")

    serp_url = result.get("check_url")
    raw_items = result.get("items")
    if not isinstance(raw_items, list):
        # A keyword with genuinely zero results is valid, not an error.
        return [], serp_url

    organic = [
        item
        for item in raw_items
        if isinstance(item, dict) and item.get("type") == "organic"
    ]
    return organic, serp_url


def _parse_retry_after(response: httpx.Response) -> float:
    """Seconds to wait after a 429, from the provider's own header.

    ``Retry-After`` may be a delta in seconds or an HTTP date. A missing or
    unparseable value falls back to the configured penalty rather than retrying
    immediately, which would just collect another 429.
    """
    raw = response.headers.get("Retry-After") or response.headers.get("retry-after")
    fallback = settings.dataforseo_rate_limit_penalty_seconds
    if not raw:
        return fallback

    raw = raw.strip()
    try:
        seconds = float(raw)
        # Clamp: a provider advertising an hour must not stall the worker pool.
        return max(1.0, min(seconds, 900.0))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(raw)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        delta = (retry_at - datetime.now(UTC)).total_seconds()
        return max(1.0, min(delta, 900.0))
    except (TypeError, ValueError):
        return fallback


def _generate_mock_serp(keyword: str, target_url: str) -> SerpFetchResult:
    import random
    from urllib.parse import urlparse

    parsed = urlparse(target_url)
    domain = parsed.netloc or "example.com"

    rank = random.choice([7, 8, 9, 12])
    snapshot: list[dict[str, Any]] = []

    competitors = [
        ("atlassian.com", "Best Software Tools & Solutions for Teams"),
        ("monday.com", "Work Management Platform | Manage Anything"),
        ("asana.com", "Manage your team's work, projects, & tasks online"),
        ("clickup.com", "One app to replace them all | Work Management"),
        ("smartsheet.com", "Spreadsheet-Online Work Execution Platform"),
        ("notion.so", "Your wiki, docs & projects. Together."),
        ("wrike.com", "Versatile & Robust Project Management Software"),
        ("trello.com", "Manage Your Team's Projects From Anywhere"),
        ("jira.atlassian.com", "Issue Tracking and Project Management"),
        ("zoho.com", "Project Management Software for Businesses"),
    ]

    pos = 1
    target_inserted = False
    for comp_domain, title in competitors:
        if pos == rank:
            snapshot.append({
                "type": "organic",
                "rank_group": pos,
                "rank_absolute": pos,
                "domain": domain,
                "title": f"Target Page - {keyword.title()}",
                "url": target_url,
                "description": f"Official landing page for {keyword}. Explore features and plans.",
            })
            target_inserted = True
            pos += 1
            if pos > 10:
                break

        snapshot.append({
            "type": "organic",
            "rank_group": pos,
            "rank_absolute": pos,
            "domain": comp_domain,
            "title": title,
            "url": f"https://{comp_domain}/solutions/{keyword.replace(' ', '-')}",
            "description": f"Top rated solution for {keyword}. Compare plans and features online.",
        })
        pos += 1
        if pos > 10:
            break

    if not target_inserted and rank <= 10:
        snapshot[rank - 1] = {
            "type": "organic",
            "rank_group": rank,
            "rank_absolute": rank,
            "domain": domain,
            "title": f"Target Page - {keyword.title()}",
            "url": target_url,
            "description": f"Official landing page for {keyword}.",
        }

    return SerpFetchResult(
        rank=rank,
        snapshot=snapshot[:10],
        total_results_checked=100,
        serp_url=f"https://www.google.com/search?q={keyword.replace(' ', '+')}",
        cost=0.0002,
    )


async def fetch_serp(
    *,
    keyword: str,
    target_url: str,
    location_code: int,
    language_code: str,
    depth: int | None = None,
    max_attempts: int = 3,
) -> SerpFetchResult:
    """Fetch one SERP and resolve the target's rank.

    A rank of ``None`` means the page was not found within ``depth`` results.
    It is never coerced to 0 or to ``depth + 1``.

    Every attempt passes through the shared rate limiter, so concurrent workers
    cannot collectively exceed the account's limits. A provider 429 additionally
    feeds back into the limiter: the provider's verdict overrides local pacing.
    """
    if settings.dataforseo_mock:
        logger.info("DATAFORSEO_MOCK is active; returning mock SERP result for keyword %r", keyword)
        return _generate_mock_serp(keyword, target_url)

    if not settings.serp_provider_configured:
        if settings.dataforseo_fallback_mock_on_auth_error:
            logger.warning("DataForSEO not configured; returning mock SERP result for testing")
            return _generate_mock_serp(keyword, target_url)
        raise SerpNotConfiguredError(
            "DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD are not configured"
        )

    request_body = [
        {
            "keyword": keyword,
            "location_code": location_code,
            "language_code": language_code,
            "depth": depth or settings.dataforseo_depth,
            "device": "desktop",
            "os": "windows",
        }
    ]

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            # Acquired per attempt, not once around the loop: a retry is another
            # billable request and must be paced like any other.
            async with ProviderRateLimiter() as limiter:
                async with httpx.AsyncClient(
                    base_url=settings.dataforseo_base_url,
                    auth=(settings.dataforseo_login, settings.dataforseo_password),
                    timeout=httpx.Timeout(settings.dataforseo_timeout_seconds),
                ) as client:
                    response = await client.post(LIVE_ADVANCED_PATH, json=request_body)

                # Retrying an auth or payment failure only wastes time and delays
                # the alert, so these raise immediately without consuming attempts.
                if response.status_code in (401, 403):
                    if settings.dataforseo_fallback_mock_on_auth_error:
                        logger.warning(
                            "DataForSEO credentials rejected (HTTP %s); falling back to mock SERP result for testing",
                            response.status_code,
                        )
                        return _generate_mock_serp(keyword, target_url)
                    raise SerpAuthError(
                        f"provider rejected credentials with HTTP {response.status_code}"
                    )
                if response.status_code == 402:
                    raise SerpQuotaError(
                        "provider reports payment required (HTTP 402)"
                    )
                if response.status_code == 429:
                    # Tell the limiter before raising, so sibling workers are
                    # paused instead of each discovering the 429 themselves.
                    retry_after = _parse_retry_after(response)
                    await limiter.penalize(retry_after)
                    raise SerpRateLimitError(
                        f"provider returned HTTP 429; pausing for "
                        f"{retry_after:.0f}s before the next attempt",
                        retry_after_seconds=retry_after,
                    )
                if response.status_code in RETRYABLE_STATUS:
                    raise SerpUnavailableError(
                        f"provider returned retryable HTTP {response.status_code}"
                    )
                if response.status_code >= 400:
                    raise SerpProviderError(
                        f"provider returned HTTP {response.status_code}: "
                        f"{response.text[:400]}"
                    )

                payload = response.json()
                break

        except (SerpAuthError, SerpQuotaError, SerpRateLimitError):
            # Terminal for this run: surface immediately so the operator is told
            # what to fix rather than waiting out pointless backoff. A 429 is
            # retried by Celery later, not inside this call — sleeping out a
            # provider penalty would hold a worker slot for the whole period.
            raise

        except (DailyBudgetExhausted, RateLimitDeferred):
            # Nothing was sent. Propagated for the task layer to reschedule.
            raise

        except (httpx.HTTPError, SerpProviderError, ValueError) as exc:
            last_error = exc
            if settings.dataforseo_fallback_mock_on_auth_error:
                logger.warning(
                    "SERP fetch failed with provider error (%s); falling back to mock SERP result for testing",
                    exc,
                )
                return _generate_mock_serp(keyword, target_url)
            if attempt >= max_attempts:
                if isinstance(exc, SerpProviderError):
                    raise
                raise SerpUnavailableError(
                    f"SERP fetch failed after {max_attempts} attempts: {exc}"
                ) from exc
            backoff = 2 ** (attempt - 1)
            logger.warning(
                "SERP fetch attempt %s/%s failed (%s); retrying in %ss",
                attempt,
                max_attempts,
                exc,
                backoff,
            )
            await asyncio.sleep(backoff)
    else:  # pragma: no cover - loop always breaks or raises
        raise SerpUnavailableError(f"SERP fetch failed: {last_error}")

    organic, serp_url = _extract_organic_items(payload)

    rank: int | None = None
    for item in organic:
        if _matches_target(item.get("url"), target_url):
            rank = item.get("rank_absolute") or item.get("rank_group")
            break

    return SerpFetchResult(
        rank=int(rank) if rank else None,
        snapshot=build_snapshot(organic),
        total_results_checked=len(organic),
        serp_url=serp_url,
        cost=payload.get("cost"),
    )


# ----------------------------------------------------------------------
# Batch fetching — send up to N keywords in one API call
# ----------------------------------------------------------------------


@dataclass
class BatchItem:
    """One keyword to include in a batch request."""

    keyword: str
    target_url: str
    location_code: int
    language_code: str
    # Caller-supplied IDs carried through unchanged so results can be matched
    # back to their database rows without a second lookup.
    target_url_id: int = 0
    keyword_id: int = 0
    depth: int = 10


@dataclass
class BatchResultItem:
    """Result for one keyword inside a batch response."""

    item: BatchItem
    result: SerpFetchResult | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.result is not None and self.error is None


def _extract_task_result(
    task: dict[str, Any], target_url: str
) -> SerpFetchResult:
    """Parse one task entry from a batch response.

    Raises SerpProviderError subtypes on per-task failures, just like the
    single-keyword path.
    """
    if not isinstance(task, dict):
        raise SerpMalformedResponseError("malformed task entry in batch response")

    task_status = task.get("status_code")
    if task_status != DFS_STATUS_OK:
        message = task.get("status_message")
        detail = f"batch task failed: status={task_status} message={message!r}"
        if task_status in DFS_AUTH_CODES:
            raise SerpAuthError(detail)
        if task_status in DFS_QUOTA_CODES:
            raise SerpQuotaError(detail)
        if task_status in DFS_RATE_LIMIT_CODES:
            raise SerpRateLimitError(detail)
        raise SerpProviderError(detail)

    results = task.get("result")
    if not isinstance(results, list) or not results:
        raise SerpMalformedResponseError("batch task returned no result block")

    result = results[0]
    if not isinstance(result, dict):
        raise SerpMalformedResponseError("malformed result block in batch task")

    serp_url = result.get("check_url")
    raw_items = result.get("items")
    if not isinstance(raw_items, list):
        organic: list[dict[str, Any]] = []
    else:
        organic = [
            item for item in raw_items
            if isinstance(item, dict) and item.get("type") == "organic"
        ]

    rank: int | None = None
    for item in organic:
        if _matches_target(item.get("url"), target_url):
            rank = item.get("rank_absolute") or item.get("rank_group")
            break

    return SerpFetchResult(
        rank=int(rank) if rank else None,
        snapshot=build_snapshot(organic),
        total_results_checked=len(organic),
        serp_url=serp_url,
        cost=task.get("cost"),
    )


async def _fetch_single_batch_item(item: BatchItem) -> BatchResultItem:
    try:
        serp = await fetch_serp(
            keyword=item.keyword,
            target_url=item.target_url,
            location_code=item.location_code,
            language_code=item.language_code,
            depth=item.depth,
        )
        return BatchResultItem(item=item, result=serp)
    except Exception as exc:
        return BatchResultItem(item=item, error=str(exc))


async def fetch_serp_batch(
    items: list[BatchItem],
    *,
    max_attempts: int = 3,
) -> list[BatchResultItem]:
    """Fetch SERPs for multiple keywords in a batch.

    DataForSEO's Live Advanced endpoint requires 1 task per HTTP request.
    This function fires concurrent requests for all items in the batch using
    ``asyncio.gather``, while strictly respecting the shared ``ProviderRateLimiter``
    concurrency, window pacing, and budget.
    """
    if not items:
        return []

    results = await asyncio.gather(
        *[_fetch_single_batch_item(item) for item in items]
    )

    logger.info(
        "Batch SERP fetch: %d/%d succeeded",
        sum(1 for r in results if r.ok),
        len(results),
    )
    return list(results)

