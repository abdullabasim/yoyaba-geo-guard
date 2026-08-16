"""Bulk CSV upload schemas.

The frontend parses the CSV in the browser (papaparse) and posts normalized
rows here. A raw-file endpoint is also provided for very large files.

Expected CSV columns (header row required, case-insensitive):

    client_name, project_name, url, keyword, location_code,
    language_code, check_interval, execution_time, timezone

``location_code``, ``language_code``, ``check_interval``, ``execution_time``
and ``timezone`` are optional and fall back to the model defaults.
"""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CheckInterval
from app.models.keyword import DEFAULT_LANGUAGE_CODE, DEFAULT_LOCATION_CODE

CSV_COLUMNS = [
    "client_name",
    "project_name",
    "url",
    "keyword",
    "location_code",
    "language_code",
    "check_interval",
    "execution_time",
    "timezone",
]

MAX_BULK_ROWS = 5000


class BulkRow(BaseModel):
    client_name: str = Field(min_length=1, max_length=255)
    project_name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=8, max_length=2048)
    keyword: str = Field(min_length=1, max_length=512)
    location_code: int = Field(default=DEFAULT_LOCATION_CODE, ge=1)
    language_code: str = Field(default=DEFAULT_LANGUAGE_CODE, min_length=2, max_length=8)
    check_interval: CheckInterval = CheckInterval.DAILY
    execution_time: time = time(hour=3, minute=0)
    timezone: str = "UTC"

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return cleaned

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str) -> str:
        return " ".join(value.split()).lower()


class BulkUploadRequest(BaseModel):
    rows: list[BulkRow] = Field(min_length=1, max_length=MAX_BULK_ROWS)
    # When true, existing clients/projects/urls are reused instead of erroring.
    upsert_parents: bool = True


class BulkUploadResponse(BaseModel):
    clients_created: int = 0
    projects_created: int = 0
    urls_created: int = 0
    keywords_created: int = 0
    rows_processed: int = 0
    rows_skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class CsvTemplateResponse(BaseModel):
    columns: list[str]
    example_rows: list[dict[str, str]]
