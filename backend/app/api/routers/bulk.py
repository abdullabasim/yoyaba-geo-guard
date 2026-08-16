"""Bulk CSV ingestion.

Two entry points:

* ``POST /bulk/rows``  — the frontend parses the CSV with papaparse and posts
  validated JSON rows. Preferred, because validation errors are reported per
  row before anything touches the database.
* ``POST /bulk/csv``   — raw multipart upload, parsed server-side. For files
  too large to parse comfortably in the browser.

Both share one importer that creates the Client -> Project -> TargetURL ->
Keyword chain, reusing existing parents instead of duplicating them.
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, SessionDep, SuperUser
from app.crud.client_crud import client_crud
from app.crud.keyword_crud import keyword_crud
from app.crud.project_crud import project_crud
from app.crud.url_crud import target_url_crud
from app.schemas.bulk_schema import (
    CSV_COLUMNS,
    MAX_BULK_ROWS,
    BulkRow,
    BulkUploadRequest,
    BulkUploadResponse,
    CsvTemplateResponse,
)
from app.schemas.client_schema import ClientCreate
from app.schemas.keyword_schema import KeywordCreate
from app.schemas.project_schema import ProjectCreate
from app.schemas.url_schema import TargetURLCreate

router = APIRouter(prefix="/bulk", tags=["bulk"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


async def _import_rows(
    session: AsyncSession, rows: list[BulkRow]
) -> BulkUploadResponse:
    response = BulkUploadResponse()

    # Caches keep a 5000-row file from issuing 5000 redundant parent lookups.
    client_cache: dict[str, int] = {}
    project_cache: dict[tuple[int, str], int] = {}
    url_cache: dict[tuple[int, str], int] = {}

    for index, row in enumerate(rows, start=1):
        try:
            # Savepoint per row: a failed flush would otherwise poison the
            # session and abort every subsequent row in the file.
            async with session.begin_nested():
                client_id = client_cache.get(row.client_name)
                if client_id is None:
                    client = await client_crud.get_by_name(session, row.client_name)
                    if client is None:
                        client = await client_crud.create(
                            session, ClientCreate(name=row.client_name)
                        )
                        response.clients_created += 1
                    client_id = client.id
                    client_cache[row.client_name] = client_id

                project_key = (client_id, row.project_name)
                project_id = project_cache.get(project_key)
                if project_id is None:
                    project = await project_crud.get_by_name_for_client(
                        session, client_id, row.project_name
                    )
                    if project is None:
                        project = await project_crud.create(
                            session,
                            ProjectCreate(client_id=client_id, name=row.project_name),
                        )
                        response.projects_created += 1
                    project_id = project.id
                    project_cache[project_key] = project_id

                url_key = (project_id, row.url)
                url_id = url_cache.get(url_key)
                if url_id is None:
                    url_obj = await target_url_crud.get_by_url_for_project(
                        session, project_id, row.url
                    )
                    if url_obj is None:
                        url_obj = await target_url_crud.create(
                            session,
                            {
                                "project_id": project_id,
                                "url": row.url,
                                "check_interval": row.check_interval,
                                "execution_time": row.execution_time,
                                "timezone": row.timezone,
                            }
                        )
                        response.urls_created += 1
                    url_id = url_obj.id
                    url_cache[url_key] = url_id

                existing_keyword = await keyword_crud.find_existing(
                    session,
                    target_url_id=url_id,
                    keyword_text=row.keyword,
                    location_code=row.location_code,
                    language_code=row.language_code,
                )
                if existing_keyword is not None:
                    response.rows_skipped += 1
                else:
                    await keyword_crud.create(
                        session,
                        KeywordCreate(
                            target_url_id=url_id,
                            keyword_text=row.keyword,
                            location_code=row.location_code,
                            language_code=row.language_code,
                        ),
                    )
                    response.keywords_created += 1

            response.rows_processed += 1

        except Exception as exc:
            # One bad row must not discard the whole file. The savepoint is
            # rolled back and the row is reported; the rest continues.
            response.rows_skipped += 1
            response.errors.append(f"row {index}: {type(exc).__name__}: {exc}")

            # Ids cached during the rolled-back savepoint may not exist.
            client_cache.clear()
            project_cache.clear()
            url_cache.clear()

    return response


@router.get("/template", response_model=CsvTemplateResponse)
async def get_csv_template(_: CurrentUser):
    """Column contract for the upload UI and the downloadable sample."""
    return CsvTemplateResponse(
        columns=CSV_COLUMNS,
        example_rows=[
            {
                "client_name": "Acme Inc",
                "project_name": "Acme Blog",
                "url": "https://acme.example.com/pricing",
                "keyword": "project management pricing",
                "location_code": "2840",
                "language_code": "en",
                "check_interval": "daily",
                "execution_time": "03:00",
                "timezone": "UTC",
            },
            {
                "client_name": "Acme Inc",
                "project_name": "Acme Blog",
                "url": "https://acme.example.com/pricing",
                "keyword": "best project tool",
                "location_code": "2840",
                "language_code": "en",
                "check_interval": "weekly",
                "execution_time": "04:30",
                "timezone": "Europe/Berlin",
            },
        ],
    )


@router.post("/rows", response_model=BulkUploadResponse)
async def bulk_insert_rows(
    payload: BulkUploadRequest, session: SessionDep, _: SuperUser
):
    return await _import_rows(session, payload.rows)


@router.post("/csv", response_model=BulkUploadResponse)
async def bulk_insert_csv(
    session: SessionDep, _: SuperUser, file: UploadFile = File(...)
):
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded",
        ) from None

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="CSV has no header row"
        )

    header_map = {name.strip().lower(): name for name in reader.fieldnames}
    missing = [
        column
        for column in ("client_name", "project_name", "url", "keyword")
        if column not in header_map
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required columns: {', '.join(missing)}",
        )

    rows: list[BulkRow] = []
    errors: list[str] = []
    for line_number, raw_row in enumerate(reader, start=2):
        if len(rows) >= MAX_BULK_ROWS:
            errors.append(f"stopped at row limit {MAX_BULK_ROWS}")
            break

        values = {
            column: (raw_row.get(source) or "").strip()
            for column, source in header_map.items()
            if column in CSV_COLUMNS
        }
        # Drop empties so Pydantic applies the declared defaults.
        values = {key: value for key, value in values.items() if value}

        if not values.get("url"):
            continue

        try:
            rows.append(BulkRow(**values))
        except ValidationError as exc:
            errors.append(f"line {line_number}: {exc.errors()[0].get('msg', 'invalid')}")

    if not rows:
        return BulkUploadResponse(errors=errors or ["no valid rows found"])

    response = await _import_rows(session, rows)
    response.errors = errors + response.errors
    return response
