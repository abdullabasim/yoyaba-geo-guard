"""Project — belongs to a Client, groups target URLs, holds schedule defaults."""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import ActiveMixin, Base, TimestampMixin
from app.models.enums import CheckInterval

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.target_url import TargetURL


class Project(Base, TimestampMixin, ActiveMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # ------------------------------------------------------------------
    # Schedule defaults
    #
    # A URL with ``inherit_schedule=True`` uses these values; one with its own
    # schedule ignores them. Editing the project default therefore reschedules
    # every inheriting URL at once, which is the point, while URLs deliberately
    # staggered across the day keep their own times.
    # ------------------------------------------------------------------
    default_check_interval: Mapped[CheckInterval] = mapped_column(
        SAEnum(CheckInterval, name="check_interval", native_enum=True, validate_strings=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=CheckInterval.DAILY,
        server_default=CheckInterval.DAILY.value,
    )
    default_execution_time: Mapped[time] = mapped_column(
        Time(timezone=False),
        nullable=False,
        server_default="03:00:00",
    )
    default_timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC", server_default="UTC"
    )
    rank_drop_threshold: Mapped[int] = mapped_column(
        Integer,
        default=3,
        server_default="3",
        nullable=False,
    )
    dataforseo_depth: Mapped[int] = mapped_column(
        Integer,
        default=10,
        server_default="10",
        nullable=False,
    )

    client: Mapped["Client"] = relationship(back_populates="projects")
    target_urls: Mapped[list["TargetURL"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"
