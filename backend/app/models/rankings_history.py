"""RankingsHistory — one SERP observation for a keyword.

``current_rank`` is nullable on purpose: a page that is not present in the
fetched result set is recorded as NULL, never as 0 or 101. Every comparison in
the codebase treats NULL explicitly so "fell out of the results" is never
silently read as "rank 0, a huge improvement".
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.ai_alert import AIAlert
    from app.models.keyword import Keyword


class RankingsHistory(Base):
    __tablename__ = "rankings_history"
    __table_args__ = (
        # Serves both "latest row for keyword" and the analytics chart range.
        Index("ix_rankings_history_keyword_date", "keyword_id", "check_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # List of {position, title, url, domain, description} for the top 10.
    top_10_serp_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    total_results_checked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    serp_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    check_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    keyword: Mapped["Keyword"] = relationship(back_populates="rankings")
    alerts: Mapped[list["AIAlert"]] = relationship(
        back_populates="history",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def rank_delta(self) -> int | None:
        """Positive means the page moved down (worse). None when incomparable."""
        if self.current_rank is None or self.previous_rank is None:
            return None
        return self.current_rank - self.previous_rank

    def __repr__(self) -> str:
        return (
            f"<RankingsHistory id={self.id} keyword_id={self.keyword_id} "
            f"rank={self.current_rank}>"
        )
