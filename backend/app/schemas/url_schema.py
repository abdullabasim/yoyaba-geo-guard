"""TargetURL schemas, including the dynamic scheduling payload."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CheckInterval
from app.schemas.common import ORMModel


def _validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown IANA timezone: {value!r}") from exc
    return value


class TargetURLBase(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    check_interval: CheckInterval = CheckInterval.DAILY
    execution_time: time = time(hour=3, minute=0)
    timezone: str = "UTC"
    rank_drop_threshold: int | None = Field(default=None, ge=1, le=50)
    dataforseo_depth: int | None = Field(default=None, ge=10, le=100)
    is_active: bool = True
    #: Default True so a new URL follows its project unless told otherwise.
    inherit_schedule: bool = True

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return cleaned

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_known(cls, value: str) -> str:
        return _validate_timezone(value)


class TargetURLCreate(TargetURLBase):
    project_id: int
    initial_keywords: list[str] = Field(default_factory=list)


class TargetURLUpdate(BaseModel):
    url: str | None = Field(default=None, min_length=8, max_length=2048)
    check_interval: CheckInterval | None = None
    execution_time: time | None = None
    timezone: str | None = None
    rank_drop_threshold: int | None = Field(default=None, ge=1, le=50)
    dataforseo_depth: int | None = Field(default=None, ge=10, le=100)
    is_active: bool | None = None
    inherit_schedule: bool | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_known(cls, value: str | None) -> str | None:
        return None if value is None else _validate_timezone(value)


class ScheduleUpdate(BaseModel):
    """Body of the dedicated per-URL scheduling form.

    Setting ``inherit_schedule`` true makes the other three fields inert: the
    project default wins. They are still stored so that turning inheritance off
    later restores a real schedule instead of a blank one.
    """

    check_interval: CheckInterval
    execution_time: time
    timezone: str = "UTC"
    rank_drop_threshold: int | None = Field(default=None, ge=1, le=50)
    dataforseo_depth: int | None = Field(default=None, ge=10, le=100)
    inherit_schedule: bool = False

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_known(cls, value: str) -> str:
        return _validate_timezone(value)


class InheritScheduleUpdate(BaseModel):
    inherit_schedule: bool


class TargetURLResponse(ORMModel):
    id: int
    project_id: int
    url: str
    check_interval: CheckInterval
    execution_time: time
    timezone: str
    rank_drop_threshold: int | None
    dataforseo_depth: int | None
    inherit_schedule: bool
    last_checked_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TargetURLWithStats(TargetURLResponse):
    project_name: str | None = None
    client_name: str | None = None
    keyword_count: int = 0
    active_keyword_count: int = 0
    # The schedule the scheduler will actually obey. Shown in the UI so an
    # inheriting URL never displays its own stale columns as if they applied.
    effective_check_interval: CheckInterval | None = None
    effective_execution_time: time | None = None
    effective_timezone: str | None = None
    effective_rank_drop_threshold: int | None = None
    effective_dataforseo_depth: int | None = None
