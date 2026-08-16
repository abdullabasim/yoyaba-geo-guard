"""TargetURL CRUD, including the Celery Beat due-check query.

The due query is the single most correctness-sensitive piece of the system:
it decides whether the paid SERP API gets called. It enforces three rules.

1. Every ancestor must be enabled — Client, Project and TargetURL all
   ``is_active=True``. Pausing a client silently pauses all its spend.
2. The URL's local wall-clock ``execution_time`` (interpreted in its own
   ``timezone``) must fall inside the current dispatch window.
3. ``last_checked_at`` must be older than the interval. This is what makes the
   query idempotent: a Beat restart, a duplicate tick, or an overlapping worker
   will not re-fetch the same URL and burn credits twice.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.crud.base import CRUDBase
from app.models.client import Client
from app.models.keyword import Keyword
from app.models.project import Project
from app.models.target_url import TargetURL
from app.schemas.url_schema import TargetURLCreate, TargetURLUpdate, TargetURLWithStats


class CRUDTargetURL(CRUDBase[TargetURL, TargetURLCreate, TargetURLUpdate]):
    async def list_with_stats(
        self,
        session: AsyncSession,
        *,
        project_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[TargetURLWithStats]:
        active_keywords = func.count(Keyword.id).filter(Keyword.is_active.is_(True))
        stmt = (
            select(
                TargetURL,
                Project,
                Client.name.label("client_name"),
                func.count(Keyword.id).label("keyword_count"),
                active_keywords.label("active_keyword_count"),
            )
            .join(Project, Project.id == TargetURL.project_id)
            .join(Client, Client.id == Project.client_id)
            .outerjoin(Keyword, Keyword.target_url_id == TargetURL.id)
            .group_by(TargetURL.id, Project.id, Client.name)
            .order_by(TargetURL.id.desc())
        )
        if project_id is not None:
            stmt = stmt.where(TargetURL.project_id == project_id)
        result = await session.execute(stmt.offset(skip).limit(limit))

        items: list[TargetURLWithStats] = []
        for row in result.all():
            url_obj, project, client_name, keyword_count, active_keyword_count = row
            items.append(
                TargetURLWithStats(
                    id=url_obj.id,
                    project_id=url_obj.project_id,
                    url=url_obj.url,
                    check_interval=url_obj.check_interval,
                    execution_time=url_obj.execution_time,
                    timezone=url_obj.timezone,
                    rank_drop_threshold=url_obj.rank_drop_threshold,
                    dataforseo_depth=url_obj.dataforseo_depth,
                    inherit_schedule=url_obj.inherit_schedule,
                    last_checked_at=url_obj.last_checked_at,
                    is_active=url_obj.is_active,
                    created_at=url_obj.created_at,
                    updated_at=url_obj.updated_at,
                    project_name=project.name,
                    client_name=client_name,
                    keyword_count=int(keyword_count or 0),
                    active_keyword_count=int(active_keyword_count or 0),
                    # What the scheduler will actually use, so the UI never shows
                    # a schedule that differs from the one being obeyed.
                    effective_check_interval=url_obj.effective_interval(project),
                    effective_execution_time=url_obj.effective_execution_time(project),
                    effective_timezone=url_obj.effective_timezone(project),
                    effective_rank_drop_threshold=url_obj.effective_rank_drop_threshold(project),
                    effective_dataforseo_depth=url_obj.effective_dataforseo_depth(project),
                )
            )
        return items

    async def get_with_keywords(
        self, session: AsyncSession, url_id: int
    ) -> TargetURL | None:
        result = await session.execute(
            select(TargetURL)
            .options(selectinload(TargetURL.keywords))
            .where(TargetURL.id == url_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_url_for_project(
        self, session: AsyncSession, project_id: int, url: str
    ) -> TargetURL | None:
        result = await session.execute(
            select(TargetURL)
            .where(TargetURL.project_id == project_id, TargetURL.url == url)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_due(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
        window_minutes: int = 30,
        limit: int = 500,
    ) -> list[TargetURL]:
        """Return active URLs whose scheduled time has arrived.

        Timezone handling is done in Python rather than SQL: ``execution_time``
        is a naive wall clock plus an IANA name, and converting that inside
        Postgres for every row would defeat the index and mishandle DST.
        The SQL pass narrows to active rows whose interval has elapsed; the
        Python pass applies the per-row timezone window.

        The project is eagerly loaded because an inheriting URL takes its
        schedule from the project; a lazy load here would raise in async context.
        """
        reference = now or datetime.now(UTC)

        stmt = (
            select(TargetURL)
            .join(Project, Project.id == TargetURL.project_id)
            .join(Client, Client.id == Project.client_id)
            .options(
                selectinload(TargetURL.keywords),
                joinedload(TargetURL.project),
            )
            .where(
                TargetURL.is_active.is_(True),
                Project.is_active.is_(True),
                Client.is_active.is_(True),
                # Only URLs that actually have something to check.
                TargetURL.keywords.any(Keyword.is_active.is_(True)),
            )
            .order_by(TargetURL.last_checked_at.asc().nullsfirst())
            .limit(limit)
        )
        result = await session.execute(stmt)
        candidates = list(result.scalars().unique().all())

        due: list[TargetURL] = []
        for url_obj in candidates:
            if self._is_due(url_obj, reference, window_minutes):
                due.append(url_obj)
        return due

    @staticmethod
    def _is_due(url_obj: TargetURL, reference: datetime, window_minutes: int) -> bool:
        # Always resolve through the effective_* helpers. Reading the raw columns
        # on an inheriting URL yields a stale schedule and fires the check at the
        # wrong hour.
        interval_days = url_obj.effective_interval().days
        scheduled_time = url_obj.effective_execution_time()
        zone_name = url_obj.effective_timezone()

        # Never checked: run at the next window rather than waiting a full cycle.
        if url_obj.last_checked_at is None:
            return True

        last_checked = url_obj.last_checked_at
        if last_checked.tzinfo is None:
            last_checked = last_checked.replace(tzinfo=UTC)

        # Interval not yet elapsed. A small tolerance stops a check that ran a
        # few minutes early from being pushed a whole day later.
        elapsed = reference - last_checked
        if elapsed < timedelta(days=interval_days) - timedelta(minutes=window_minutes):
            return False

        try:
            local_zone = ZoneInfo(zone_name)
        except Exception:
            local_zone = UTC

        local_now = reference.astimezone(local_zone)
        scheduled_today = local_now.replace(
            hour=scheduled_time.hour,
            minute=scheduled_time.minute,
            second=0,
            microsecond=0,
        )

        # Due once the scheduled moment has passed, up to the window length.
        # Beyond the window the run is treated as missed and waits for the next
        # occurrence, so a worker outage cannot cause a burst of stale checks.
        delta = local_now - scheduled_today
        return timedelta(0) <= delta <= timedelta(minutes=window_minutes)

    async def mark_checked(
        self, session: AsyncSession, url_id: int, when: datetime | None = None
    ) -> None:
        url_obj = await session.get(TargetURL, url_id)
        if url_obj is not None:
            url_obj.last_checked_at = when or datetime.now(UTC)
            session.add(url_obj)
            await session.flush()


target_url_crud = CRUDTargetURL(TargetURL)
