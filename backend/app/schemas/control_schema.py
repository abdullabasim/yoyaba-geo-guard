"""Service control (kill switch) schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.service_control import ServiceKey
from app.schemas.common import ORMModel


class ServiceControlResponse(ORMModel):
    id: int
    service_key: ServiceKey
    is_enabled: bool
    paused_reason: str | None
    paused_by: str | None
    paused_at: datetime | None
    updated_at: datetime
    #: Populated from SERVICE_METADATA so the UI needs no duplicate copy.
    display_name: str = ""
    summary: str = ""
    impact: str = ""


class ServiceControlUpdate(BaseModel):
    is_enabled: bool
    #: Required in the UI when pausing: an undocumented switch flip becomes an
    #: archaeology problem days later.
    reason: str | None = Field(default=None, max_length=1000)


class ServiceControlSummary(BaseModel):
    total: int
    enabled: int
    paused: int
    #: True when the master SCHEDULER switch is off, which supersedes the rest.
    scheduler_paused: bool
    paused_keys: list[ServiceKey] = Field(default_factory=list)


class ContainerStatus(BaseModel):
    """Read-only liveness view of one deployment process.

    Derived from observable evidence (recent task activity, database and Redis
    reachability), NOT from the Docker API. Controlling containers from the
    browser would require mounting the Docker socket into the backend, which
    would hand the web application root on the host.
    """

    name: str
    role: str
    status: str
    detail: str
    controllable: bool = False


class SystemStatusResponse(BaseModel):
    controls: list[ServiceControlResponse]
    summary: ServiceControlSummary
    containers: list[ContainerStatus]
