"""Runtime kill-switch reads and writes.

Read path is cached in-process for ``CACHE_TTL_SECONDS``, because every task
consults these switches and an uncached read would add a database round trip to
work that is otherwise pure. The TTL is short enough that flipping a switch in
the UI takes effect within seconds without a restart.

Fail-safe direction: if the switch cannot be read at all, the subsystem is
treated as **enabled**. A database blip must not silently stop all monitoring —
the customer-visible failure of "we stopped checking your rankings and nobody
noticed" is worse than the alternative.
"""

from __future__ import annotations

import time as time_module
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session_scope
from app.core.logging import get_logger
from app.models.service_control import (
    SERVICE_METADATA,
    ServiceControl,
    ServiceKey,
)

logger = get_logger(__name__)

CACHE_TTL_SECONDS = 10.0


@dataclass
class _CacheEntry:
    values: dict[ServiceKey, bool]
    fetched_at: float


_cache: _CacheEntry | None = None


def invalidate_cache() -> None:
    """Drop the cache so the next read hits the database.

    Called after a write inside the same process. Other processes pick the change
    up when their own TTL expires, which is why the TTL is seconds and not
    minutes.
    """
    global _cache
    _cache = None


async def _load_all(session: AsyncSession) -> dict[ServiceKey, bool]:
    result = await session.execute(
        select(ServiceControl.service_key, ServiceControl.is_enabled)
    )
    stored = {key: bool(enabled) for key, enabled in result.all()}
    # A switch with no row is enabled: absence must never mean "paused".
    return {key: stored.get(key, True) for key in ServiceKey}


async def get_all_states(*, use_cache: bool = True) -> dict[ServiceKey, bool]:
    global _cache

    if use_cache and _cache is not None:
        if time_module.monotonic() - _cache.fetched_at < CACHE_TTL_SECONDS:
            return dict(_cache.values)

    try:
        async with session_scope() as session:
            values = await _load_all(session)
        _cache = _CacheEntry(values=values, fetched_at=time_module.monotonic())
        return dict(values)
    except Exception as exc:
        logger.error("Could not read service controls (%s); assuming enabled", exc)
        if _cache is not None:
            # A stale answer beats an arbitrary one.
            return dict(_cache.values)
        return {key: True for key in ServiceKey}


async def is_enabled(key: ServiceKey, *, use_cache: bool = True) -> bool:
    states = await get_all_states(use_cache=use_cache)
    return states.get(key, True)


async def list_controls(session: AsyncSession) -> list[ServiceControl]:
    """Full rows for the UI, creating any switch that has no row yet."""
    result = await session.execute(select(ServiceControl))
    existing = {row.service_key: row for row in result.scalars().all()}

    created = False
    for key in ServiceKey:
        if key not in existing:
            row = ServiceControl(service_key=key, is_enabled=True)
            session.add(row)
            existing[key] = row
            created = True
    if created:
        await session.flush()
        invalidate_cache()

    # Enum declaration order is the order an operator reads them in: master
    # switch first, then the individual stages.
    return [existing[key] for key in ServiceKey]


async def set_enabled(
    session: AsyncSession,
    key: ServiceKey,
    *,
    enabled: bool,
    reason: str | None = None,
    actor: str | None = None,
) -> ServiceControl:
    result = await session.execute(
        select(ServiceControl).where(ServiceControl.service_key == key).limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = ServiceControl(service_key=key)
        session.add(row)

    row.is_enabled = enabled
    if enabled:
        row.paused_reason = None
        row.paused_by = None
        row.paused_at = None
    else:
        row.paused_reason = reason
        row.paused_by = actor
        row.paused_at = datetime.now(UTC)

    await session.flush()
    await session.refresh(row)
    invalidate_cache()

    logger.warning(
        "Service control %s set to %s by %s (%s)",
        key.value,
        "enabled" if enabled else "PAUSED",
        actor or "unknown",
        reason or "no reason given",
    )
    return row


def describe(key: ServiceKey) -> tuple[str, str, str]:
    """(display name, summary, impact) for the UI."""
    return SERVICE_METADATA[key]
