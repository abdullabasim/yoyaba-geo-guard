"""Client schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ClientBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class ClientResponse(ORMModel):
    id: int
    name: str
    company_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClientWithStats(ClientResponse):
    """Used by the management table so counts do not need N+1 requests."""

    project_count: int = 0
    active_project_count: int = 0
