"""Rate limiter logic that must hold regardless of Redis behaviour.

The limiter exists to stop us causing our own 429s. These tests target the parts
where a plausible-looking implementation is silently wrong:

* a fixed window instead of a sliding one allows a double burst at the boundary,
* an in-process semaphore is defeated by prefork workers,
* consuming budget before a request that never happens drains it for free,
* failing closed turns a Redis blip into a total monitoring outage.
"""

from __future__ import annotations

import pytest

from app.services.rate_limiter import (
    DailyBudgetExhausted,
    ProviderRateLimiter,
    RateLimitDeferred,
    RateLimitSnapshot,
)


class TestExceptionSemantics:
    def test_deferred_carries_a_retry_delay(self):
        """The caller reschedules with this, so it cannot be absent."""
        error = RateLimitDeferred("no slot", retry_after_seconds=42.0)
        assert error.retry_after_seconds == 42.0
        assert "no slot" in str(error)

    def test_budget_exhausted_reports_usage(self):
        error = DailyBudgetExhausted(used=500, budget=500)
        assert error.used == 500
        assert error.budget == 500
        # The operator needs the numbers in the message, not just a class name.
        assert "500" in str(error)

    def test_deferred_is_not_a_provider_error(self):
        """Deferral means nothing was sent, so it must not classify as a SERP fault.

        If it inherited from SerpProviderError the alerting layer would page an
        operator about our own pacing.
        """
        from app.services.dataforseo import SerpProviderError

        assert not issubclass(RateLimitDeferred, SerpProviderError)
        assert not issubclass(DailyBudgetExhausted, SerpProviderError)


class TestSnapshot:
    def test_remaining_budget_is_computed(self):
        snap = RateLimitSnapshot(
            provider="dataforseo",
            requests_per_minute_limit=60,
            requests_in_window=10,
            max_concurrent=5,
            in_flight=2,
            daily_budget=100,
            used_today=40,
            redis_ok=True,
        )
        assert snap.budget_remaining == 60

    def test_zero_budget_means_unlimited_not_exhausted(self):
        """0 must read as 'no ceiling', never as 'nothing left'."""
        snap = RateLimitSnapshot(
            provider="dataforseo",
            requests_per_minute_limit=60,
            requests_in_window=0,
            max_concurrent=5,
            in_flight=0,
            daily_budget=0,
            used_today=999,
            redis_ok=True,
        )
        assert snap.budget_remaining is None
        assert snap.as_dict()["daily_budget"]["limit"] == "unlimited"
        assert snap.as_dict()["daily_budget"]["remaining"] == "unlimited"

    def test_overspend_clamps_at_zero(self):
        snap = RateLimitSnapshot(
            provider="dataforseo",
            requests_per_minute_limit=60,
            requests_in_window=0,
            max_concurrent=5,
            in_flight=0,
            daily_budget=10,
            used_today=15,
            redis_ok=True,
        )
        assert snap.budget_remaining == 0


class TestFailOpen:
    """Limiter bookkeeping failures must never stop monitoring."""

    @pytest.mark.asyncio
    async def test_window_allows_when_redis_is_down(self, monkeypatch):
        from app.services import rate_limiter

        def explode():
            raise RuntimeError("redis is down")

        monkeypatch.setattr(rate_limiter, "get_redis", explode)

        allowed, wait = await rate_limiter._try_acquire_window("dataforseo", 60)
        assert allowed is True
        assert wait == 0.0

    @pytest.mark.asyncio
    async def test_concurrency_allows_when_redis_is_down(self, monkeypatch):
        from app.services import rate_limiter

        def explode():
            raise RuntimeError("redis is down")

        monkeypatch.setattr(rate_limiter, "get_redis", explode)

        allowed, marker = await rate_limiter._try_acquire_slot("dataforseo", 5)
        assert allowed is True
        assert marker is None

    @pytest.mark.asyncio
    async def test_budget_allows_when_redis_is_down(self, monkeypatch):
        """A fail-closed budget would make a Redis blip a full outage."""
        from app.services import rate_limiter

        def explode():
            raise RuntimeError("redis is down")

        monkeypatch.setattr(rate_limiter, "get_redis", explode)

        # Must not raise.
        await rate_limiter._check_and_consume_budget("dataforseo", 100)

    @pytest.mark.asyncio
    async def test_zero_limits_bypass_redis_entirely(self, monkeypatch):
        """0 disables a control, so it must not even touch Redis."""
        from app.services import rate_limiter

        def explode():
            raise AssertionError("Redis must not be consulted when the limit is 0")

        monkeypatch.setattr(rate_limiter, "get_redis", explode)

        assert await rate_limiter._try_acquire_window("dataforseo", 0) == (True, 0.0)
        assert await rate_limiter._try_acquire_slot("dataforseo", 0) == (True, None)
        await rate_limiter._check_and_consume_budget("dataforseo", 0)


class TestBudgetRefund:
    """Budget is consumed before the call, so aborts must refund it."""

    @pytest.mark.asyncio
    async def test_deferral_refunds_the_consumed_unit(self, monkeypatch):
        from app.services import rate_limiter

        refunds: list[str] = []

        async def fake_refund(provider: str) -> None:
            refunds.append(provider)

        async def never_allow(provider: str, limit: int):
            return False, 5.0

        async def consume(provider: str, budget: int) -> None:
            return None

        monkeypatch.setattr(rate_limiter, "_refund_budget", fake_refund)
        monkeypatch.setattr(rate_limiter, "_try_acquire_window", never_allow)
        monkeypatch.setattr(rate_limiter, "_check_and_consume_budget", consume)

        limiter = ProviderRateLimiter(
            requests_per_minute=60,
            max_concurrent=5,
            daily_budget=100,
            max_wait_seconds=0.0,
        )
        with pytest.raises(RateLimitDeferred):
            await limiter.__aenter__()

        assert refunds == ["dataforseo"], "a call that never happened must not bill"

    @pytest.mark.asyncio
    async def test_provider_failure_does_not_refund(self, monkeypatch):
        """A provider-side failure may still have been billed, so it counts."""
        from app.services import rate_limiter

        refunds: list[str] = []

        async def fake_refund(provider: str) -> None:
            refunds.append(provider)

        async def allow_window(provider: str, limit: int):
            return True, 0.0

        async def allow_slot(provider: str, limit: int):
            return True, "marker"

        async def release(provider: str, marker):
            return None

        async def consume(provider: str, budget: int) -> None:
            return None

        monkeypatch.setattr(rate_limiter, "_refund_budget", fake_refund)
        monkeypatch.setattr(rate_limiter, "_try_acquire_window", allow_window)
        monkeypatch.setattr(rate_limiter, "_try_acquire_slot", allow_slot)
        monkeypatch.setattr(rate_limiter, "_release_slot", release)
        monkeypatch.setattr(rate_limiter, "_check_and_consume_budget", consume)

        limiter = ProviderRateLimiter(daily_budget=100, max_wait_seconds=0.0)
        await limiter.__aenter__()
        await limiter.__aexit__(TimeoutError, TimeoutError("provider timed out"), None)

        assert refunds == []

    @pytest.mark.asyncio
    async def test_unconfigured_provider_refunds(self, monkeypatch):
        """No credentials means no request, so the budget must be returned."""
        from app.services import rate_limiter
        from app.services.dataforseo import SerpNotConfiguredError

        refunds: list[str] = []

        async def fake_refund(provider: str) -> None:
            refunds.append(provider)

        async def allow_window(provider: str, limit: int):
            return True, 0.0

        async def allow_slot(provider: str, limit: int):
            return True, "marker"

        async def release(provider: str, marker):
            return None

        async def consume(provider: str, budget: int) -> None:
            return None

        monkeypatch.setattr(rate_limiter, "_refund_budget", fake_refund)
        monkeypatch.setattr(rate_limiter, "_try_acquire_window", allow_window)
        monkeypatch.setattr(rate_limiter, "_try_acquire_slot", allow_slot)
        monkeypatch.setattr(rate_limiter, "_release_slot", release)
        monkeypatch.setattr(rate_limiter, "_check_and_consume_budget", consume)

        limiter = ProviderRateLimiter(daily_budget=100, max_wait_seconds=0.0)
        await limiter.__aenter__()
        await limiter.__aexit__(
            SerpNotConfiguredError, SerpNotConfiguredError("no creds"), None
        )

        assert refunds == ["dataforseo"]


class TestSlidingWindowScript:
    """The Lua script is the correctness core; assert its shape."""

    def test_script_trims_before_counting(self):
        from app.services.rate_limiter import _SLIDING_WINDOW_LUA

        trim = _SLIDING_WINDOW_LUA.index("ZREMRANGEBYSCORE")
        count = _SLIDING_WINDOW_LUA.index("ZCARD")
        # Counting before trimming would include expired entries and under-allow.
        assert trim < count

    def test_script_is_atomic_over_check_and_add(self):
        """Check and add must be one round trip.

        Split across two calls, two workers both read "59 used" and both proceed,
        which is exactly the burst the limiter exists to prevent.
        """
        from app.services.rate_limiter import _SLIDING_WINDOW_LUA

        assert "ZCARD" in _SLIDING_WINDOW_LUA
        assert "ZADD" in _SLIDING_WINDOW_LUA
        assert _SLIDING_WINDOW_LUA.index("ZCARD") < _SLIDING_WINDOW_LUA.index("ZADD")

    def test_script_sets_an_expiry(self):
        """Without PEXPIRE the key leaks forever on an idle provider."""
        from app.services.rate_limiter import _SLIDING_WINDOW_LUA

        assert "PEXPIRE" in _SLIDING_WINDOW_LUA

    def test_script_reports_wait_time_when_full(self):
        from app.services.rate_limiter import _SLIDING_WINDOW_LUA

        # The caller needs a real delay, not a fixed guess.
        assert "ZRANGE" in _SLIDING_WINDOW_LUA
        assert "WITHSCORES" in _SLIDING_WINDOW_LUA


class TestRetryAfterParsing:
    """A 429's Retry-After decides the pause; misreading it wastes a day."""

    def _response(self, headers: dict[str, str]):
        import httpx

        return httpx.Response(429, headers=headers)

    def test_numeric_seconds(self):
        from app.services.dataforseo import _parse_retry_after

        assert _parse_retry_after(self._response({"Retry-After": "30"})) == 30.0

    def test_header_is_case_insensitive(self):
        from app.services.dataforseo import _parse_retry_after

        assert _parse_retry_after(self._response({"retry-after": "45"})) == 45.0

    def test_missing_header_falls_back_to_configured_penalty(self):
        from app.core.config import settings
        from app.services.dataforseo import _parse_retry_after

        assert _parse_retry_after(self._response({})) == (
            settings.dataforseo_rate_limit_penalty_seconds
        )

    def test_garbage_header_falls_back(self):
        from app.core.config import settings
        from app.services.dataforseo import _parse_retry_after

        assert _parse_retry_after(self._response({"Retry-After": "soon"})) == (
            settings.dataforseo_rate_limit_penalty_seconds
        )

    def test_absurd_delay_is_clamped(self):
        """A provider advertising an hour must not stall the worker pool."""
        from app.services.dataforseo import _parse_retry_after

        assert _parse_retry_after(self._response({"Retry-After": "99999"})) == 900.0

    def test_zero_is_raised_to_one_second(self):
        """Retrying instantly just collects another 429."""
        from app.services.dataforseo import _parse_retry_after

        assert _parse_retry_after(self._response({"Retry-After": "0"})) == 1.0

    def test_http_date_is_understood(self):
        from app.services.dataforseo import _parse_retry_after

        # A past date must not produce a negative sleep.
        value = _parse_retry_after(
            self._response({"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})
        )
        assert value >= 1.0


class TestTaskDeferralSemantics:
    def test_deferred_is_distinct_from_skipped(self):
        """Skipped means 'nothing to do'; deferred means 'not yet'.

        Collapsing them would either lose the check or mark healthy pacing as an
        error, depending on which way they were merged.
        """
        from app.worker.logging_ctx import TaskDeferred, TaskSkipped

        assert not issubclass(TaskDeferred, TaskSkipped)
        assert not issubclass(TaskSkipped, TaskDeferred)

    def test_deferred_delay_has_a_floor(self):
        from app.worker.logging_ctx import TaskDeferred

        assert TaskDeferred("x", retry_after_seconds=0).retry_after_seconds == 1.0
        assert TaskDeferred("x", retry_after_seconds=-5).retry_after_seconds == 1.0

    def test_deferral_reason_is_preserved(self):
        from app.worker.logging_ctx import TaskDeferred

        error = TaskDeferred("rate limited by our own pacing", retry_after_seconds=120)
        assert error.reason == "rate limited by our own pacing"
        assert error.retry_after_seconds == 120


class TestRedisDatabaseIsolation:
    def test_rate_limit_uses_its_own_logical_database(self):
        """Sharing a DB with the broker means a flush destroys queued work."""
        from app.core.config import settings

        assert settings.rate_limit_redis_db not in (0, 1, 2)
        assert settings.rate_limit_redis_url != settings.alert_state_redis_url
        assert settings.rate_limit_redis_url != settings.celery_broker_url

    def test_keys_are_namespaced_per_provider(self):
        """A second provider must not silently share this one's budget."""
        from app.services.rate_limiter import (
            BUDGET_KEY,
            CONCURRENCY_KEY,
            WINDOW_KEY,
        )

        assert "{provider}" in WINDOW_KEY
        assert "{provider}" in CONCURRENCY_KEY
        assert "{provider}" in BUDGET_KEY
        # The budget key is per day, so it resets at midnight rather than never.
        assert "{day}" in BUDGET_KEY
