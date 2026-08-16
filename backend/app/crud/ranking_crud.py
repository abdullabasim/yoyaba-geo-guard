"""RankingsHistory CRUD — writes observations, reads chart series."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword import Keyword
from app.models.rankings_history import RankingsHistory
from app.models.target_url import TargetURL
from app.schemas.ranking_schema import (
    RankPoint,
    RankSeries,
    SerpResultItem,
    SnapshotComparison,
)


class CRUDRanking:
    async def get(self, session: AsyncSession, history_id: int) -> RankingsHistory | None:
        return await session.get(RankingsHistory, history_id)

    async def get_latest_for_keyword(
        self, session: AsyncSession, keyword_id: int, *, before_id: int | None = None
    ) -> RankingsHistory | None:
        stmt = (
            select(RankingsHistory)
            .where(RankingsHistory.keyword_id == keyword_id)
            .order_by(RankingsHistory.check_date.desc(), RankingsHistory.id.desc())
            .limit(1)
        )
        if before_id is not None:
            stmt = stmt.where(RankingsHistory.id < before_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_observation(
        self,
        session: AsyncSession,
        *,
        keyword_id: int,
        current_rank: int | None,
        previous_rank: int | None,
        snapshot: list[dict[str, Any]],
        total_results_checked: int | None = None,
        serp_url: str | None = None,
    ) -> RankingsHistory:
        row = RankingsHistory(
            keyword_id=keyword_id,
            current_rank=current_rank,
            previous_rank=previous_rank,
            top_10_serp_snapshot=snapshot,
            total_results_checked=total_results_checked,
            serp_url=serp_url,
            check_date=datetime.now(UTC),
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def list_for_keyword(
        self,
        session: AsyncSession,
        keyword_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[RankingsHistory]:
        result = await session.execute(
            select(RankingsHistory)
            .where(RankingsHistory.keyword_id == keyword_id)
            .order_by(RankingsHistory.check_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_series(
        self, session: AsyncSession, keyword_id: int, *, days: int = 90
    ) -> RankSeries | None:
        """Chronological points for the reversed-axis chart."""
        since = datetime.now(UTC) - timedelta(days=days)

        meta = await session.execute(
            select(Keyword, TargetURL.url)
            .join(TargetURL, TargetURL.id == Keyword.target_url_id)
            .where(Keyword.id == keyword_id)
            .limit(1)
        )
        row = meta.first()
        if row is None:
            return None
        keyword, url = row

        result = await session.execute(
            select(
                RankingsHistory.id,
                RankingsHistory.check_date,
                RankingsHistory.current_rank,
            )
            .where(
                RankingsHistory.keyword_id == keyword_id,
                RankingsHistory.check_date >= since,
            )
            .order_by(RankingsHistory.check_date.asc())
        )
        points = [
            RankPoint(history_id=history_id, check_date=check_date, rank=rank)
            for history_id, check_date, rank in result.all()
        ]

        ranked = [p.rank for p in points if p.rank is not None]
        return RankSeries(
            keyword_id=keyword.id,
            keyword_text=keyword.keyword_text,
            url=url,
            location_code=keyword.location_code,
            language_code=keyword.language_code,
            points=points,
            best_rank=min(ranked) if ranked else None,
            worst_rank=max(ranked) if ranked else None,
            latest_rank=points[-1].rank if points else None,
        )

    async def get_comparison(
        self, session: AsyncSession, history_id: int
    ) -> SnapshotComparison | None:
        """Current observation vs. the one before it, with domain churn."""
        current = await session.get(RankingsHistory, history_id)
        if current is None:
            return None

        keyword = await session.get(Keyword, current.keyword_id)
        previous = await self.get_latest_for_keyword(
            session, current.keyword_id, before_id=current.id
        )

        current_items = [SerpResultItem(**item) for item in current.top_10_serp_snapshot]
        previous_items = (
            [SerpResultItem(**item) for item in previous.top_10_serp_snapshot]
            if previous is not None
            else []
        )

        current_domains = {i.domain for i in current_items if i.domain}
        previous_domains = {i.domain for i in previous_items if i.domain}

        return SnapshotComparison(
            keyword_text=keyword.keyword_text if keyword else "",
            previous_check_date=previous.check_date if previous else None,
            current_check_date=current.check_date,
            previous_rank=current.previous_rank,
            current_rank=current.current_rank,
            previous_snapshot=previous_items,
            current_snapshot=current_items,
            entered_domains=sorted(current_domains - previous_domains),
            exited_domains=sorted(previous_domains - current_domains),
        )


ranking_crud = CRUDRanking()
