"""Keyword schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.keyword import DEFAULT_LANGUAGE_CODE, DEFAULT_LOCATION_CODE
from app.schemas.common import ORMModel


class KeywordBase(BaseModel):
    keyword_text: str = Field(min_length=1, max_length=512)
    location_code: int = Field(default=DEFAULT_LOCATION_CODE, ge=1)
    language_code: str = Field(default=DEFAULT_LANGUAGE_CODE, min_length=2, max_length=8)
    is_active: bool = True

    @field_validator("keyword_text")
    @classmethod
    def normalize_keyword(cls, value: str) -> str:
        # Collapse whitespace so " blue  widgets " and "blue widgets" collide
        # on the unique constraint instead of creating duplicate API spend.
        return " ".join(value.split()).lower()

    @field_validator("language_code")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        return value.strip().lower()


class KeywordCreate(KeywordBase):
    target_url_id: int


class KeywordUpdate(BaseModel):
    keyword_text: str | None = Field(default=None, min_length=1, max_length=512)
    location_code: int | None = Field(default=None, ge=1)
    language_code: str | None = Field(default=None, min_length=2, max_length=8)
    is_active: bool | None = None


class KeywordResponse(ORMModel):
    id: int
    target_url_id: int
    keyword_text: str
    location_code: int
    language_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KeywordWithLatestRank(KeywordResponse):
    url: str | None = None
    current_rank: int | None = None
    previous_rank: int | None = None
    last_check_date: datetime | None = None
