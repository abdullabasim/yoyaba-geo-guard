"""Keyword endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep, SuperUser
from app.crud.keyword_crud import keyword_crud
from app.crud.url_crud import target_url_crud
from app.schemas.common import ActiveToggle, MessageResponse, Page
from app.schemas.keyword_schema import (
    KeywordCreate,
    KeywordResponse,
    KeywordUpdate,
    KeywordWithLatestRank,
)

router = APIRouter(prefix="/keywords", tags=["keywords"])


@router.get("", response_model=Page[KeywordWithLatestRank])
async def list_keywords(
    session: SessionDep,
    pagination: PaginationDep,
    _: CurrentUser,
    target_url_id: int | None = Query(default=None),
):
    items = await keyword_crud.list_with_latest_rank(
        session,
        target_url_id=target_url_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    total = await keyword_crud.count(
        session, filters={"target_url_id": target_url_id} if target_url_id else None
    )
    return Page[KeywordWithLatestRank](
        items=items, total=total, skip=pagination.skip, limit=pagination.limit
    )


@router.post("", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword(payload: KeywordCreate, session: SessionDep, _: SuperUser):
    parent = await target_url_crud.get(session, payload.target_url_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Target URL does not exist"
        )
    existing = await keyword_crud.find_existing(
        session,
        target_url_id=payload.target_url_id,
        keyword_text=payload.keyword_text,
        location_code=payload.location_code,
        language_code=payload.language_code,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Keyword already tracked for this URL and market",
        )
    return await keyword_crud.create(session, payload)


@router.get("/{keyword_id}", response_model=KeywordResponse)
async def get_keyword(keyword_id: int, session: SessionDep, _: CurrentUser):
    keyword = await keyword_crud.get(session, keyword_id)
    if keyword is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    return keyword


@router.patch("/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(
    keyword_id: int, payload: KeywordUpdate, session: SessionDep, _: SuperUser
):
    keyword = await keyword_crud.get(session, keyword_id)
    if keyword is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    return await keyword_crud.update(session, keyword, payload)


@router.patch("/{keyword_id}/toggle", response_model=KeywordResponse)
async def toggle_keyword(
    keyword_id: int, payload: ActiveToggle, session: SessionDep, _: SuperUser
):
    keyword = await keyword_crud.get(session, keyword_id)
    if keyword is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    return await keyword_crud.set_active(session, keyword, payload.is_active)


@router.delete("/{keyword_id}", response_model=MessageResponse)
async def delete_keyword(keyword_id: int, session: SessionDep, _: SuperUser):
    deleted = await keyword_crud.remove(session, keyword_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    return MessageResponse(detail="Keyword deleted")
