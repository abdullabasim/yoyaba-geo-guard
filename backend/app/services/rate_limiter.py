"""Distributed rate limiting for outbound provider calls.

Why this exists: Beat expands every due URL into one task per keyword and
enqueues them together. With 200 keywords due at 03:00 the worker pool would
fire ~200 provider calls in a few seconds. That earns HTTP 429s, and a 429 costs
more than a delay: the check is deferred, the log fills with failures, and the
operator gets alerted about a problem we caused ourselves.

Three independent controls, in the order they bite:

1. **Requests per minute** \u2014 a sliding window shared by every worker process.
2. **Concurrency** \u2014 how many provider calls may be in flight at once.
3. **Daily budget** \u2014 a hard ceiling on spend, independent of pacing.

All three live in Redis because the limit belongs to the *account*, not to a
process. An in-process ``asyncio.Semaphore`` would be silently defeated by
prefork workers: four processes each honouring "5 concurrent" is 20.

Fail-open vs fail-closed differs per control, deliberately:

* Pacing and concurrency **fail open** \u2014 if Redis is down we allow the call. The
  provider's own 429 remains the backstop, and stalling all monitoring because
  the throttle bookkeeping is unavailable is the worse outcome.
* The daily budget also fails open, because a fail-closed budget would turn a
  Redis outage into a total monitoring outage. The budget is a cost guardrail,
  not a safety interlock; ``SERP_FETCH`` on the control panel is the hard stop.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

#: Sliding-window keys are namespaced per provider so a second provider added
#: later cannot share \u2014 and silently halve \u2014 this one's budget.
WINDOW_KEY = "seo:ratelimit:{provider}:window"
CONCURRENCY_KEY = "seo:ratelimit:{provider}:inflight"
BUDGET_KEY = "seo:ratelimit:{provider}:budget:{day}"

#: An in-flight marker is released in a ``finally``, but a killed worker cannot
#: run one. Every marker therefore carries its own expiry, so a hard crash
#: cannot permanently consume a concurrency slot.
INFLIGHT_TTL_SECONDS = 180

#: Budget counters outlive their day briefly so a check running across midnight
#: still finds the counter it incremented.
BUDGET_TTL_SECONDS = 60 * 60 * 26


class RateLimitDeferred(Exception):
    """No slot became available within the allowed wait.

    Distinct from a provider 429: nothing was sent, so the caller should retry
    later rather than treat it as a provider failure. Carries the delay the
    caller should wait.
    """

    def __init__(self, reason: str, retry_after_seconds: float) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds


class DailyBudgetExhausted(Exception):
    """The configured daily request budget is spent.

    Not a provider error and not retryable today: retrying inside the same day
    would burn task slots against a ceiling that cannot move until midnight.
    """

    def __init__(self, used: int, budget: int) -> None:
        super().__init__(
            f"daily SERP request budget exhausted ({used}/{budget} used today)"
        )
        self.used = used
        self.budget = budget


_client: aioredis.Redis | None = None

# ---------------------------------------------------------------------------
# Sliding window, atomically.
#
# A naive INCR on a per-minute key is a *fixed* window: 60 requests at 10:00:59
# plus 60 at 10:01:00 is 120 within one second, which is exactly the burst that
# triggers a 429. A sorted set of timestamps gives a true sliding window, and the
# whole trim-count-add sequence must be atomic or two workers both observe
# "59 used" and both proceed.
# ---------------------------------------------------------------------------
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now_ms - window_ms)
local used = redis.call('ZCARD', key)

if used < limit then
    redis.call('ZADD', key, now_ms, member)
    redis.call('PEXPIRE', key, window_ms + 1000)
    return {1, used + 1, 0}
end

-- Full: report how long until the oldest entry leaves the window.
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local wait_ms = window_ms
if oldest[2] then
    wait_ms = (tonumber(oldest[2]) + window_ms) - now_ms
    if wait_ms < 0 then wait_ms = 0 end
end
return {0, used, wait_ms}
"""

_sliding_window_script = None


def get_redis() -> aioredis.Redis:
    """Lazily build the client. Import never opens a connection."""
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.rate_limit_redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=3,
            socket_connect_timeout=3,
            health_check_interval=30,
        )
    return _client


async def close_redis() -> None:
    global _client, _sliding_window_script
    if _client is not None:
        await _client.aclose()
        _client = None
    _sliding_window_script = None


def _script(client: aioredis.Redis):
    global _sliding_window_script
    if _sliding_window_script is None:
        _sliding_window_script = client.register_script(_SLIDING_WINDOW_LUA)
    return _sliding_window_script


def _today() -> str:
    return datetime.now(UTC).strftime("%Y%m%d")


@dataclass
class RateLimitSnapshot:
    """Current limiter state, for the diagnostics endpoint."""

    provider: str
    requests_per_minute_limit: int
    requests_in_window: int
    max_concurrent: int
    in_flight: int
    daily_budget: int
    used_today: int
    redis_ok: bool

    @property
    def budget_remaining(self) -> int | None:
        if self.daily_budget <= 0:
            return None
        return max(0, self.daily_budget - self.used_today)

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "redis_ok": self.redis_ok,
            "requests_per_minute": {
                "limit": self.requests_per_minute_limit or "unlimited",
                "used_in_last_60s": self.requests_in_window,
            },
            "concurrency": {
                "limit": self.max_concurrent or "unlimited",
                "in_flight": self.in_flight,
            },
            "daily_budget": {
                "limit": self.daily_budget or "unlimited",
                "used_today": self.used_today,
                "remaining": self.budget_remaining
                if self.daily_budget > 0
                else "unlimited",
            },
        }


async def _try_acquire_window(provider: str, limit: int) -> tuple[bool, float]:
    """``(allowed, wait_seconds)`` for the requests-per-minute window."""
    if limit <= 0:
        return True, 0.0
    try:
        client = get_redis()
        now_ms = int(time.time() * 1000)
        member = f"{now_ms}-{id(asyncio.current_task())}"
        allowed, _used, wait_ms = await _script(client)(
            keys=[WINDOW_KEY.format(provider=provider)],
            args=[now_ms, 60_000, limit, member],
        )
        return bool(int(allowed)), float(wait_ms) / 1000.0
    except Exception as exc:
        logger.warning("Rate limiter unavailable (%s); allowing the request", exc)
        return True, 0.0


async def _try_acquire_slot(provider: str, limit: int) -> tuple[bool, str | None]:
    """``(allowed, marker)`` for the concurrency limiter."""
    if limit <= 0:
        return True, None
    try:
        client = get_redis()
        key = CONCURRENCY_KEY.format(provider=provider)
        marker = f"{time.time():.6f}-{id(asyncio.current_task())}"
        # A sorted set rather than a counter: entries carry timestamps, so slots
        # leaked by a killed worker age out instead of being lost forever.
        now = time.time()
        await client.zremrangebyscore(key, 0, now - INFLIGHT_TTL_SECONDS)
        in_flight = await client.zcard(key)
        if in_flight >= limit:
            return False, None
        await client.zadd(key, {marker: now})
        await client.expire(key, INFLIGHT_TTL_SECONDS * 2)
        return True, marker
    except Exception as exc:
        logger.warning("Concurrency limiter unavailable (%s); allowing", exc)
        return True, None


async def _release_slot(provider: str, marker: str | None) -> None:
    if marker is None:
        return
    try:
        client = get_redis()
        await client.zrem(CONCURRENCY_KEY.format(provider=provider), marker)
    except Exception:
        # The marker's timestamp guarantees it ages out; losing this call only
        # delays reuse of one slot.
        pass


async def _check_and_consume_budget(provider: str, budget: int) -> None:
    """Raise ``DailyBudgetExhausted`` when today's ceiling is reached."""
    if budget <= 0:
        return
    key = BUDGET_KEY.format(provider=provider, day=_today())
    try:
        client = get_redis()
        used = await client.incr(key)
        if used == 1:
            await client.expire(key, BUDGET_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Daily budget counter unavailable (%s); allowing", exc)
        return

    if used > budget:
        raise DailyBudgetExhausted(used=used - 1, budget=budget)


async def _refund_budget(provider: str) -> None:
    """Return a consumed budget unit when the call never happened.

    The budget is consumed before the request so two workers cannot both pass a
    near-exhausted ceiling. Anything that aborts afterwards must refund, or the
    budget would drain without a single provider call being made.
    """
    try:
        client = get_redis()
        await client.decr(BUDGET_KEY.format(provider=provider, day=_today()))
    except Exception:
        pass


async def consume_budget_batch(provider: str, count: int) -> None:
    """Consume ``count`` budget units for a batch request.

    A batch of N keywords is billed as N tasks by DataForSEO, so the daily
    budget must reflect the true cost. The rate limiter's ``__aenter__``
    already consumed 1 unit; this adds ``count - 1`` more.

    Raises ``DailyBudgetExhausted`` if the extra consumption pushes the
    counter past the limit.
    """
    if count <= 1:
        return
    extra = count - 1  # 1 already consumed by ProviderRateLimiter.__aenter__
    budget = settings.dataforseo_daily_request_budget
    if budget <= 0:
        return
    key = BUDGET_KEY.format(provider=provider, day=_today())
    try:
        client = get_redis()
        used = await client.incrby(key, extra)
    except Exception as exc:
        logger.warning("Batch budget accounting unavailable (%s); allowing", exc)
        return

    if used > budget:
        # Refund the extra we just added so the counter is accurate.
        try:
            await client.decrby(key, extra)
        except Exception:
            pass
        raise DailyBudgetExhausted(used=used - extra, budget=budget)


class ProviderRateLimiter:
    """Async context manager guarding one outbound provider call.

    ```python
    async with ProviderRateLimiter() as limiter:
        response = await client.post(...)
        if response.status_code == 429:
            await limiter.penalize(retry_after)
    ```

    Raises ``DailyBudgetExhausted`` or ``RateLimitDeferred`` instead of blocking
    indefinitely: a Celery task holding a worker slot while it sleeps for ten
    minutes is worse than releasing the slot and retrying.
    """

    def __init__(
        self,
        provider: str = "dataforseo",
        *,
        requests_per_minute: int | None = None,
        max_concurrent: int | None = None,
        daily_budget: int | None = None,
        max_wait_seconds: float | None = None,
    ) -> None:
        self.provider = provider
        self.requests_per_minute = (
            settings.dataforseo_max_requests_per_minute
            if requests_per_minute is None
            else requests_per_minute
        )
        self.max_concurrent = (
            settings.dataforseo_max_concurrent_requests
            if max_concurrent is None
            else max_concurrent
        )
        self.daily_budget = (
            settings.dataforseo_daily_request_budget
            if daily_budget is None
            else daily_budget
        )
        self.max_wait_seconds = (
            settings.dataforseo_rate_limit_max_wait_seconds
            if max_wait_seconds is None
            else max_wait_seconds
        )
        self._slot_marker: str | None = None
        self._budget_consumed = False

    async def __aenter__(self) -> ProviderRateLimiter:
        await _check_and_consume_budget(self.provider, self.daily_budget)
        self._budget_consumed = self.daily_budget > 0

        deadline = time.monotonic() + max(0.0, self.max_wait_seconds)
        attempt = 0

        while True:
            allowed, wait_seconds = await _try_acquire_window(
                self.provider, self.requests_per_minute
            )
            if allowed:
                got_slot, marker = await _try_acquire_slot(
                    self.provider, self.max_concurrent
                )
                if got_slot:
                    self._slot_marker = marker
                    return self
                # Window consumed but no concurrency slot: short poll, since
                # in-flight calls finish on their own.
                wait_seconds = 1.0

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if self._budget_consumed:
                    await _refund_budget(self.provider)
                    self._budget_consumed = False
                raise RateLimitDeferred(
                    f"no {self.provider} rate-limit slot within "
                    f"{self.max_wait_seconds:.0f}s "
                    f"(limit {self.requests_per_minute}/min, "
                    f"{self.max_concurrent} concurrent)",
                    retry_after_seconds=max(wait_seconds, 5.0),
                )

            attempt += 1
            # Jitter: without it, N workers unblocked by the same expiring entry
            # would retry in lockstep and collide again.
            sleep_for = min(max(wait_seconds, 0.25), remaining, 5.0)
            sleep_for += (attempt % 5) * 0.11
            await asyncio.sleep(sleep_for)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        await _release_slot(self.provider, self._slot_marker)
        self._slot_marker = None

        # A request that never reached the provider must not count against the
        # budget. Provider-side failures (timeouts, 5xx) DO count, because the
        # provider may well have billed them.
        if self._budget_consumed and exc_type is not None:
            from app.services.dataforseo import SerpNotConfiguredError

            if issubclass(exc_type, (SerpNotConfiguredError, RateLimitDeferred)):
                await _refund_budget(self.provider)

        return False

    async def penalize(self, retry_after_seconds: float) -> None:
        """Fill the window after a provider 429.

        The provider disagreed with our pacing, so its verdict wins: block local
        traffic for the whole ``Retry-After`` period instead of letting the next
        worker immediately try again and collect another 429.
        """
        if self.requests_per_minute <= 0:
            return
        try:
            client = get_redis()
            key = WINDOW_KEY.format(provider=self.provider)
            now_ms = int(time.time() * 1000)
            # Saturate the window, then hold it for the penalty duration.
            members = {
                f"penalty-{now_ms}-{index}": now_ms
                for index in range(self.requests_per_minute)
            }
            await client.zadd(key, members)
            await client.pexpire(key, int(max(retry_after_seconds, 1.0) * 1000))
            logger.warning(
                "Provider 429: pausing %s calls for %.0fs",
                self.provider,
                retry_after_seconds,
            )
        except Exception as exc:
            logger.warning("Could not record rate-limit penalty (%s)", exc)


async def snapshot(provider: str = "dataforseo") -> RateLimitSnapshot:
    """Read current usage without consuming anything."""
    requests_in_window = 0
    in_flight = 0
    used_today = 0
    redis_ok = True

    try:
        client = get_redis()
        now = time.time()
        now_ms = int(now * 1000)

        await client.zremrangebyscore(
            WINDOW_KEY.format(provider=provider), 0, now_ms - 60_000
        )
        requests_in_window = int(
            await client.zcard(WINDOW_KEY.format(provider=provider)) or 0
        )

        await client.zremrangebyscore(
            CONCURRENCY_KEY.format(provider=provider), 0, now - INFLIGHT_TTL_SECONDS
        )
        in_flight = int(
            await client.zcard(CONCURRENCY_KEY.format(provider=provider)) or 0
        )

        raw_used = await client.get(BUDGET_KEY.format(provider=provider, day=_today()))
        used_today = int(raw_used) if raw_used else 0
    except Exception as exc:
        logger.warning("Rate limiter snapshot unavailable: %s", exc)
        redis_ok = False

    return RateLimitSnapshot(
        provider=provider,
        requests_per_minute_limit=settings.dataforseo_max_requests_per_minute,
        requests_in_window=requests_in_window,
        max_concurrent=settings.dataforseo_max_concurrent_requests,
        in_flight=in_flight,
        daily_budget=settings.dataforseo_daily_request_budget,
        used_today=used_today,
        redis_ok=redis_ok,
    )


async def reset(provider: str = "dataforseo", *, include_budget: bool = False) -> None:
    """Clear limiter state. Used by tests and by a deliberate operator reset."""
    try:
        client = get_redis()
        keys = [
            WINDOW_KEY.format(provider=provider),
            CONCURRENCY_KEY.format(provider=provider),
        ]
        if include_budget:
            keys.append(BUDGET_KEY.format(provider=provider, day=_today()))
        await client.delete(*keys)
    except Exception as exc:
        logger.warning("Could not reset rate limiter state (%s)", exc)
