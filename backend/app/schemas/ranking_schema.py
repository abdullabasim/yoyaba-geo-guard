"""Ranking history schemas (analytics chart + SERP snapshots)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SerpResultItem(BaseModel):
    """One organic result inside ``top_10_serp_snapshot``."""

    position: int
    title: str | None = None
    url: str | None = None
    domain: str | None = None
    description: str | None = None


class RankingsHistoryResponse(ORMModel):
    id: int
    keyword_id: int
    current_rank: int | None
    previous_rank: int | None
    top_10_serp_snapshot: list[dict] = Field(default_factory=list)
    total_results_checked: int | None
    serp_url: str | None
    check_date: datetime


class RankPoint(BaseModel):
    """Single point for the reversed-axis line chart."""

    check_date: datetime
    rank: int | None
    history_id: int


class RankSeries(BaseModel):
    keyword_id: int
    keyword_text: str
    url: str
    location_code: int
    language_code: str
    points: list[RankPoint]
    best_rank: int | None = None
    worst_rank: int | None = None
    latest_rank: int | None = None


class SnapshotComparison(BaseModel):
    """Feeds the "what changed in the SERP" side-by-side view."""

    keyword_text: str
    previous_check_date: datetime | None
    current_check_date: datetime
    previous_rank: int | None
    current_rank: int | None
    previous_snapshot: list[SerpResultItem]
    current_snapshot: list[SerpResultItem]
    entered_domains: list[str]
    exited_domains: list[str]
