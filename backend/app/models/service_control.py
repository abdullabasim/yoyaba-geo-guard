"""Runtime kill switches for individual pipeline subsystems.

One row per switch, keyed by ``ServiceKey``. The worker reads these on every
task, so flipping a switch in the UI takes effect on the next task without a
restart and without shell access.

This is deliberately NOT container control. Stopping Docker services from the
browser would require mounting the Docker socket into the backend, which grants
the web application root on the host. Pausing the *work* achieves the operational
goal with none of that exposure.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ServiceKey(StrEnum):
    """Every independently pausable part of the pipeline."""

    #: Master switch. When off, Beat dispatches nothing at all.
    SCHEDULER = "SCHEDULER"
    #: Task A. When off, no SERP calls are made and nothing is billed.
    SERP_FETCH = "SERP_FETCH"
    #: Task B. When off, drops are still recorded but never analyzed.
    AI_ANALYSIS = "AI_ANALYSIS"
    #: Business alerts. When off, alerts are stored but not delivered.
    SLACK_ALERTS = "SLACK_ALERTS"
    #: Operator error alerts. Separate from business alerts on purpose.
    ERROR_ALERTS = "ERROR_ALERTS"
    #: The periodic dependency probe.
    HEALTH_MONITOR = "HEALTH_MONITOR"


#: Human-facing metadata. Kept beside the enum so the UI and the seeder agree.
SERVICE_METADATA: dict[ServiceKey, tuple[str, str, str]] = {
    ServiceKey.SCHEDULER: (
        "Scheduler",
        "Master switch for all scheduled work",
        "When paused, Celery Beat dispatches nothing. Manual 'Run now' still "
        "works, so this stops automation without blocking deliberate checks.",
    ),
    ServiceKey.SERP_FETCH: (
        "SERP fetching",
        "Rank checks against the SERP provider",
        "When paused, no SERP request is made and nothing is billed. Use this "
        "first when controlling provider spend.",
    ),
    ServiceKey.AI_ANALYSIS: (
        "AI analysis",
        "LLM intent-shift diagnosis",
        "When paused, ranking drops are still recorded but not analyzed. "
        "Snapshots are retained, so affected drops can be re-analyzed later.",
    ),
    ServiceKey.SLACK_ALERTS: (
        "Slack business alerts",
        "Intent-shift notifications to the client channel",
        "When paused, alerts are still written to the database but not "
        "delivered. Use 'Resend' on the Alerts page to deliver them afterwards.",
    ),
    ServiceKey.ERROR_ALERTS: (
        "Slack error alerts",
        "Operator notifications about failures",
        "When paused, failures are still logged and visible in the Task Monitor "
        "but nobody is notified. Pausing this during a known incident stops "
        "noise; leaving it off means the next real outage is silent.",
    ),
    ServiceKey.HEALTH_MONITOR: (
        "Health monitor",
        "Periodic database, Redis and credential probe",
        "When paused, outages are only noticed when a task happens to run and "
        "fail. This is the check that catches problems on an idle night.",
    ),
}


class ServiceControl(Base):
    """Persisted on/off state for one subsystem."""

    __tablename__ = "service_controls"

    id: Mapped[int] = mapped_column(primary_key=True)

    service_key: Mapped[ServiceKey] = mapped_column(
        SAEnum(ServiceKey, name="service_key", native_enum=True, validate_strings=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        unique=True,
        index=True,
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    #: Why it was paused. Prevents the "who turned this off and why" archaeology
    #: that always follows an undocumented switch flip.
    paused_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    paused_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def display_name(self) -> str:
        return SERVICE_METADATA[self.service_key][0]

    @property
    def summary(self) -> str:
        return SERVICE_METADATA[self.service_key][1]

    @property
    def impact(self) -> str:
        return SERVICE_METADATA[self.service_key][2]

    def __repr__(self) -> str:
        state = "enabled" if self.is_enabled else "PAUSED"
        return f"<ServiceControl {self.service_key.value} {state}>"
