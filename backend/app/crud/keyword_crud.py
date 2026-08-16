"""Keyword CRUD with latest-rank joins."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.keyword import Keyword
from app.models.rankings_history import RankingsHistory
from app.models.target_url import TargetURL
from app.schemas.keyword_schema import (
    KeywordCreate,
    KeywordUpdate,
    KeywordWithLatestRank,
)


class CRUDKeyword(CRUDBase[Keyword, KeywordCreate, KeywordUpdate]):
    async def list_with_latest_rank(
        self,
        session: AsyncSession,
        *,
        target_url_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[KeywordWithLatestRank]:
        # DISTINCT ON is the cheapest way to get the newest row per keyword and
        # is served directly by ix_rankings_history_keyword_date.
        latest = (
            select(
                RankingsHistory.keyword_id,
                RankingsHistory.current_rank,
                RankingsHistory.previous_rank,
                RankingsHistory.check_date,
            )
            .distinct(RankingsHistory.keyword_id)
            .order_by(RankingsHistory.keyword_id, RankingsHistory.check_date.desc())
            .subquery()
        )

        stmt = (
            select(
                Keyword,
                TargetURL.url.label("url"),
                latest.c.current_rank,
                latest.c.previous_rank,
                latest.c.check_date,
            )
            .join(TargetURL, TargetURL.id == Keyword.target_url_id)
            .outerjoin(latest, latest.c.keyword_id == Keyword.id)
            .order_by(Keyword.id.desc())
        )
        if target_url_id is not None:
            stmt = stmt.where(Keyword.target_url_id == target_url_id)
        result = await session.execute(stmt.offset(skip).limit(limit))

        items: list[KeywordWithLatestRank] = []
        for keyword, url, current_rank, previous_rank, check_date in result.all():
            items.append(
                KeywordWithLatestRank(
                    id=keyword.id,
                    target_url_id=keyword.target_url_id,
                    keyword_text=keyword.keyword_text,
                    location_code=keyword.location_code,
                    language_code=keyword.language_code,
                    is_active=keyword.is_active,
                    created_at=keyword.created_at,
                    updated_at=keyword.updated_at,
                    url=url,
                    current_rank=current_rank,
                    previous_rank=previous_rank,
                    last_check_date=check_date,
                )
            )
        return items

    async def find_existing(
        self,
        session: AsyncSession,
        *,
        target_url_id: int,
        keyword_text: str,
        location_code: int,
        language_code: str,
    ) -> Keyword | None:
        result = await session.execute(
            select(Keyword)
            .where(
                Keyword.target_url_id == target_url_id,
                Keyword.keyword_text == keyword_text,
                Keyword.location_code == location_code,
                Keyword.language_code == language_code,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_active_for_url(
        self, session: AsyncSession, target_url_id: int
    ) -> list[Keyword]:
        result = await session.execute(
            select(Keyword).where(
                Keyword.target_url_id == target_url_id,
                Keyword.is_active.is_(True),
            )
        )
        return list(result.scalars().all())


keyword_crud = CRUDKeyword(Keyword)
