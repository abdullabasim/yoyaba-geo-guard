"""Keyword — the search term tracked for a TargetURL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import ActiveMixin, Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.rankings_history import RankingsHistory
    from app.models.target_url import TargetURL

# DataForSEO location code for the United States.
DEFAULT_LOCATION_CODE = 2840
DEFAULT_LANGUAGE_CODE = "en"


class Keyword(Base, TimestampMixin, ActiveMixin):
    __tablename__ = "keywords"
    __table_args__ = (
        # The same term twice for one URL/market would double the API spend.
        UniqueConstraint(
            "target_url_id",
            "keyword_text",
            "location_code",
            "language_code",
            name="uq_keyword_per_url_and_market",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    target_url_id: Mapped[int] = mapped_column(
        ForeignKey("target_urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    keyword_text: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    location_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_LOCATION_CODE,
        server_default=str(DEFAULT_LOCATION_CODE),
    )
    language_code: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default=DEFAULT_LANGUAGE_CODE,
        server_default=DEFAULT_LANGUAGE_CODE,
    )

    target_url: Mapped["TargetURL"] = relationship(back_populates="keywords")
    rankings: Mapped[list["RankingsHistory"]] = relationship(
        back_populates="keyword",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RankingsHistory.check_date.desc()",
    )

    def __repr__(self) -> str:
        return f"<Keyword id={self.id} text={self.keyword_text!r}>"
