"""Tests for error classification and alert throttling.

These matter because the alerting path is the one an operator relies on when
everything else is broken. A misclassified error sends useless guidance; a
throttle that fails closed silences a real outage.

No network, no database, no Redis: classification is pure, and the throttle is
exercised against a fake Redis.
"""

from __future__ import annotations

import pytest

from app.llm.client import (
    LLMAuthError,
    LLMNotConfiguredError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.llm.intent_analyzer import IntentAnalysisError
from app.services.dataforseo import (
    SerpAuthError,
    SerpMalformedResponseError,
    SerpProviderError,
    SerpQuotaError,
    SerpRateLimitError,
    _extract_organic_items,
)
from app.services.error_alerts import (
    ErrorCategory,
    Severity,
    build_throttle_key,
    classify_exception,
    throttle_window_seconds,
)


class TestTypedExceptionClassification:
    @pytest.mark.parametrize(
        "exc,expected",
        [
            (SerpAuthError("bad creds"), ErrorCategory.SERP_AUTH),
            (SerpQuotaError("no money"), ErrorCategory.SERP_QUOTA),
            (SerpRateLimitError("429"), ErrorCategory.SERP_RATE_LIMIT),
            (SerpMalformedResponseError("shape"), ErrorCategory.SERP_MALFORMED),
            (SerpProviderError("generic"), ErrorCategory.SERP_UNAVAILABLE),
            (LLMRateLimitError("slow down"), ErrorCategory.LLM_RATE_LIMIT),
            (LLMQuotaError("out of credit"), ErrorCategory.LLM_QUOTA),
            (LLMAuthError("bad key"), ErrorCategory.LLM_AUTH),
            (LLMTimeoutError("too slow"), ErrorCategory.LLM_TIMEOUT),
            (LLMNotConfiguredError("no key"), ErrorCategory.LLM_NOT_CONFIGURED),
            (LLMResponseError("bad json"), ErrorCategory.LLM_INVALID_OUTPUT),
            (IntentAnalysisError("no valid output"), ErrorCategory.LLM_INVALID_OUTPUT),
        ],
    )
    def test_typed_exceptions_classify_exactly(self, exc, expected):
        assert classify_exception(exc).category is expected

    def test_every_category_has_remediation_text(self):
        # An alert without guidance is just a traceback with extra steps.
        for category in ErrorCategory:
            class Typed(RuntimeError):
                error_category = category

            profile = classify_exception(Typed("x"))
            assert profile.remediation
            assert len(profile.remediation) > 40
            assert profile.title


class TestLibraryExceptionClassification:
    def test_sqlalchemy_operational_error_is_connection_failure(self):
        from sqlalchemy.exc import OperationalError

        exc = OperationalError("SELECT 1", {}, Exception("connection refused"))
        assert classify_exception(exc).category is ErrorCategory.DATABASE_CONNECTION

    def test_sqlalchemy_integrity_error_is_generic_database_error(self):
        from sqlalchemy.exc import IntegrityError

        exc = IntegrityError("INSERT", {}, Exception("duplicate key"))
        assert classify_exception(exc).category is ErrorCategory.DATABASE_ERROR

    def test_redis_error_is_redis_connection(self):
        from redis.exceptions import ConnectionError as RedisConnectionError

        assert (
            classify_exception(RedisConnectionError("nope")).category
            is ErrorCategory.REDIS_CONNECTION
        )

    def test_unknown_exception_falls_back_without_raising(self):
        profile = classify_exception(ValueError("something odd"))
        assert profile.category is ErrorCategory.UNKNOWN
        assert profile.severity is Severity.WARNING


class TestSeverityAssignment:
    @pytest.mark.parametrize(
        "category",
        [
            ErrorCategory.SERP_AUTH,
            ErrorCategory.SERP_QUOTA,
            ErrorCategory.LLM_AUTH,
            ErrorCategory.LLM_QUOTA,
            ErrorCategory.LLM_NOT_CONFIGURED,
            ErrorCategory.DATABASE_CONNECTION,
            ErrorCategory.REDIS_CONNECTION,
            ErrorCategory.CONFIGURATION,
        ],
    )
    def test_unrecoverable_failures_are_critical(self, category):
        class Typed(RuntimeError):
            error_category = category

        assert classify_exception(Typed("x")).severity is Severity.CRITICAL

    @pytest.mark.parametrize(
        "category",
        [
            ErrorCategory.SERP_RATE_LIMIT,
            ErrorCategory.LLM_RATE_LIMIT,
            ErrorCategory.LLM_TIMEOUT,
        ],
    )
    def test_transient_failures_are_warnings(self, category):
        class Typed(RuntimeError):
            error_category = category

        assert classify_exception(Typed("x")).severity is Severity.WARNING


class TestThrottleKeys:
    def test_systemic_failures_collapse_across_scopes(self):
        # 200 keywords failing on one dead database must be ONE alert.
        first = build_throttle_key(ErrorCategory.DATABASE_CONNECTION, "keyword-a")
        second = build_throttle_key(ErrorCategory.DATABASE_CONNECTION, "keyword-b")
        assert first == second

    def test_non_systemic_failures_stay_separate_per_scope(self):
        first = build_throttle_key(ErrorCategory.SERP_MALFORMED, "keyword-a")
        second = build_throttle_key(ErrorCategory.SERP_MALFORMED, "keyword-b")
        assert first != second

    def test_different_categories_never_share_a_key(self):
        assert build_throttle_key(ErrorCategory.LLM_AUTH) != build_throttle_key(
            ErrorCategory.LLM_QUOTA
        )

    def test_systemic_windows_are_longer(self):
        systemic = classify_exception(_typed(ErrorCategory.DATABASE_CONNECTION))
        one_off = classify_exception(_typed(ErrorCategory.SERP_MALFORMED))
        assert throttle_window_seconds(systemic) > throttle_window_seconds(one_off)


def _typed(category: ErrorCategory) -> RuntimeError:
    class Typed(RuntimeError):
        error_category = category

    return Typed("x")


class FakeRedis:
    """Minimal SET NX / INCR / EXPIRE / GET / DELETE stand-in."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def incr(self, key):
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])

    async def expire(self, key, ttl):
        return True

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, *keys):
        removed = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                removed += 1
        return removed


class BrokenRedis:
    async def set(self, *args, **kwargs):
        raise ConnectionError("redis is down")

    async def get(self, *args, **kwargs):
        raise ConnectionError("redis is down")

    async def incr(self, *args, **kwargs):
        raise ConnectionError("redis is down")

    async def expire(self, *args, **kwargs):
        raise ConnectionError("redis is down")

    async def delete(self, *args, **kwargs):
        raise ConnectionError("redis is down")


class TestClaimAlertSlot:
    @pytest.fixture(autouse=True)
    def _reset(self):
        from app.core import redis_client

        original = redis_client.get_redis
        yield
        redis_client.get_redis = original

    async def test_first_claim_wins_and_duplicates_are_suppressed(self, monkeypatch):
        from app.core import redis_client

        fake = FakeRedis()
        monkeypatch.setattr(redis_client, "get_redis", lambda: fake)

        allowed, suppressed = await redis_client.claim_alert_slot("k", 60)
        assert allowed is True
        assert suppressed == 0

        for expected in (1, 2, 3):
            allowed, suppressed = await redis_client.claim_alert_slot("k", 60)
            assert allowed is False
            assert suppressed == expected

    async def test_next_allowed_alert_reports_folded_duplicates(self, monkeypatch):
        from app.core import redis_client

        fake = FakeRedis()
        monkeypatch.setattr(redis_client, "get_redis", lambda: fake)

        await redis_client.claim_alert_slot("k", 60)
        await redis_client.claim_alert_slot("k", 60)
        await redis_client.claim_alert_slot("k", 60)

        # Simulate the window expiring.
        del fake.store["k"]

        allowed, suppressed = await redis_client.claim_alert_slot("k", 60)
        assert allowed is True
        # The two suppressed duplicates must be reported, not silently lost.
        assert suppressed == 2

    async def test_throttle_fails_open_when_redis_is_down(self, monkeypatch):
        from app.core import redis_client

        monkeypatch.setattr(redis_client, "get_redis", lambda: BrokenRedis())

        # Duplicate noise is recoverable; a silently dropped alert is not.
        for _ in range(3):
            allowed, suppressed = await redis_client.claim_alert_slot("k", 60)
            assert allowed is True
            assert suppressed == 0


class TestSerpErrorCodeMapping:
    def test_quota_status_code_raises_quota_error(self):
        payload = {"tasks": [{"status_code": 40501, "status_message": "no money"}]}
        with pytest.raises(SerpQuotaError):
            _extract_organic_items(payload)

    def test_auth_status_code_raises_auth_error(self):
        payload = {"tasks": [{"status_code": 40100, "status_message": "unauthorized"}]}
        with pytest.raises(SerpAuthError):
            _extract_organic_items(payload)

    def test_rate_limit_status_code_raises_rate_limit_error(self):
        payload = {"tasks": [{"status_code": 40429, "status_message": "slow down"}]}
        with pytest.raises(SerpRateLimitError):
            _extract_organic_items(payload)

    def test_balance_message_infers_quota_even_for_unknown_code(self):
        payload = {
            "tasks": [{"status_code": 49999, "status_message": "Insufficient balance"}]
        }
        with pytest.raises(SerpQuotaError):
            _extract_organic_items(payload)

    def test_missing_tasks_is_malformed_not_generic(self):
        with pytest.raises(SerpMalformedResponseError):
            _extract_organic_items({})
