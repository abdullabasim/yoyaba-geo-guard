"""Shared schema building blocks."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for response schemas read out of SQLAlchemy instances."""

    model_config = ConfigDict(from_attributes=True)


class ActiveToggle(BaseModel):
    """Body of the PATCH /{id}/toggle endpoints used by the UI switches."""

    is_active: bool


class PaginationParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)


class Page(BaseModel, Generic[T]):
    """Envelope so the frontend can render totals without a second request."""

    items: list[T]
    total: int
    skip: int
    limit: int


class MessageResponse(BaseModel):
    detail: str


class BulkResult(BaseModel):
    created: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
