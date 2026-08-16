"""AIAlert — the LLM diagnosis attached to a ranking observation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import IssueType

if TYPE_CHECKING:
    from app.models.rankings_history import RankingsHistory


class AIAlert(Base):
    __tablename__ = "ai_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    history_id: Mapped[int] = mapped_column(
        ForeignKey("rankings_history.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issue_type: Mapped[IssueType] = mapped_column(
        SAEnum(IssueType, name="issue_type", native_enum=True, validate_strings=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=IssueType.UNKNOWN,
        server_default=IssueType.UNKNOWN.value,
        index=True,
    )
    ai_diagnosis: Mapped[str] = mapped_column(Text, nullable=False)
    actionable_advice: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Competitor URLs/titles the model cited as evidence.
    competitor_signals: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    slack_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    history: Mapped["RankingsHistory"] = relationship(back_populates="alerts")

    def __repr__(self) -> str:
        return f"<AIAlert id={self.id} issue={self.issue_type}>"
