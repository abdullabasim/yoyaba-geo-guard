"""TargetURL — a monitored page with its own schedule."""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import ActiveMixin, Base, TimestampMixin
from app.models.enums import CheckInterval

if TYPE_CHECKING:
    from app.models.keyword import Keyword
    from app.models.project import Project


class TargetURL(Base, TimestampMixin, ActiveMixin):
    __tablename__ = "target_urls"
    __table_args__ = (
        # Beat's due-check query filters on exactly these columns.
        Index("ix_target_urls_due_lookup", "is_active", "execution_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    check_interval: Mapped[CheckInterval] = mapped_column(
        SAEnum(CheckInterval, name="check_interval", native_enum=True, validate_strings=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=CheckInterval.DAILY,
        server_default=CheckInterval.DAILY.value,
    )
    # Stored as a naive wall-clock time interpreted in ``timezone`` below.
    execution_time: Mapped[time] = mapped_column(
        Time(timezone=False),
        nullable=False,
        server_default="03:00:00",
    )
    # IANA name. Kept explicit so a stored 03:00 is never ambiguous.
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC", server_default="UTC"
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # When true, the three schedule columns above are ignored in favour of the
    # parent project's defaults. The columns are still populated so that turning
    # inheritance off restores a sensible schedule rather than a blank one.
    inherit_schedule: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    rank_drop_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataforseo_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="target_urls")
    keywords: Mapped[list["Keyword"]] = relationship(
        back_populates="target_url",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # ------------------------------------------------------------------
    # Effective schedule
    #
    # Every scheduling decision must go through these, never the raw columns.
    # Reading ``execution_time`` directly on an inheriting URL yields a stale
    # value and the check fires at the wrong hour.
    # ------------------------------------------------------------------
    def effective_interval(self, project: "Project | None" = None) -> CheckInterval:
        if not self.inherit_schedule:
            return self.check_interval
        source = project
        if source is None:
            try:
                source = self.project
            except Exception:
                source = None
        if source is not None:
            return source.default_check_interval
        return self.check_interval

    def effective_execution_time(self, project: "Project | None" = None) -> time:
        if not self.inherit_schedule:
            return self.execution_time
        source = project
        if source is None:
            try:
                source = self.project
            except Exception:
                source = None
        if source is not None:
            return source.default_execution_time
        return self.execution_time

    def effective_timezone(self, project: "Project | None" = None) -> str:
        if not self.inherit_schedule:
            return self.timezone
        source = project
        if source is None:
            try:
                source = self.project
            except Exception:
                source = None
        if source is not None:
            return source.default_timezone
        return self.timezone

    def effective_rank_drop_threshold(self, project: "Project | None" = None) -> int:
        if self.rank_drop_threshold is not None:
            return self.rank_drop_threshold
        source = project
        if source is None:
            try:
                source = self.project
            except Exception:
                source = None
        if source is not None:
            val = getattr(source, "rank_drop_threshold", None)
            if val is not None:
                return val
        return 3

    def effective_dataforseo_depth(self, project: "Project | None" = None) -> int:
        if self.dataforseo_depth is not None:
            return self.dataforseo_depth
        source = project
        if source is None:
            try:
                source = self.project
            except Exception:
                source = None
        if source is not None:
            val = getattr(source, "dataforseo_depth", None)
            if val is not None:
                return val
        # Fallback to the environment default if neither URL nor project specifies it.
        from app.core.config import settings
        return settings.dataforseo_depth

    def __repr__(self) -> str:
        return f"<TargetURL id={self.id} url={self.url!r}>"
