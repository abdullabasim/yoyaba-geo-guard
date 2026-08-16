"""Async Redis client used for alert de-duplication state.

Deliberately a separate logical database (DB 2) from the Celery broker (DB 0)
and result backend (DB 1), so flushing alert state can never disturb queued
work.

Every function here is failure-tolerant on purpose: this Redis is used to
*suppress* duplicate alerts. If it is unreachable, the correct behaviour is to
let the alert through rather than to swallow it — a noisy alert is recoverable,
a silently dropped one is not.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Lazily build the shared client. Import never opens a connection."""
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.alert_state_redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=3,
            socket_connect_timeout=3,
            health_check_interval=30,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def claim_alert_slot(key: str, ttl_seconds: int) -> tuple[bool, int]:
    """Atomically decide whether an alert may be sent.

    Returns ``(allowed, suppressed_since_last)``. When allowed, the second value
    is how many duplicates were folded into this alert while the previous
    window was open — read *before* the counter is reset, otherwise the figure
    would always be zero.

    ``SET NX`` is the claim: the first caller for a key wins and sends. Later
    callers increment a companion counter instead.

    On any Redis failure this returns ``(True, 0)`` — fail open, never silence.
    """
    counter_key = f"{key}:suppressed"
    try:
        client = get_redis()
        acquired = await client.set(key, "1", ex=ttl_seconds, nx=True)
        if acquired:
            previous = await client.get(counter_key)
            await client.delete(counter_key)
            return True, int(previous) if previous else 0

        suppressed = await client.incr(counter_key)
        # Outlive the claim slightly so the count survives until the next send.
        await client.expire(counter_key, ttl_seconds + 60)
        return False, int(suppressed)
    except Exception as exc:
        logger.warning("Alert throttle unavailable (%s); sending alert anyway", exc)
        return True, 0


async def reset_alert_slot(key: str) -> None:
    """Clear a throttle claim so the next occurrence alerts immediately.

    Used when a subsystem recovers, so a fresh failure is not silenced by a
    stale window from the previous incident.
    """
    try:
        client = get_redis()
        await client.delete(key, f"{key}:suppressed")
    except Exception:
        pass


async def read_suppressed_count(key: str) -> int:
    """Current suppression counter for a key, without mutating it."""
    try:
        client = get_redis()
        value = await client.get(f"{key}:suppressed")
        return int(value) if value else 0
    except Exception:
        return 0


async def ping_redis() -> bool:
    """Liveness probe used by the health monitor task."""
    try:
        client = get_redis()
        return bool(await client.ping())
    except Exception as exc:
        logger.error("Redis ping failed: %s", exc)
        return False
