"""Ranking history endpoints for the analytics chart."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep
from app.crud.keyword_crud import keyword_crud
from app.crud.ranking_crud import ranking_crud
from app.schemas.ranking_schema import (
    RankingsHistoryResponse,
    RankSeries,
    SnapshotComparison,
)

router = APIRouter(prefix="/rankings", tags=["rankings"])


@router.get("/keyword/{keyword_id}", response_model=list[RankingsHistoryResponse])
async def list_history(
    keyword_id: int, session: SessionDep, pagination: PaginationDep, _: CurrentUser
):
    keyword = await keyword_crud.get(session, keyword_id)
    if keyword is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    return await ranking_crud.list_for_keyword(
        session, keyword_id, skip=pagination.skip, limit=pagination.limit
    )


@router.get("/keyword/{keyword_id}/series", response_model=RankSeries)
async def get_series(
    keyword_id: int,
    session: SessionDep,
    _: CurrentUser,
    days: int = Query(default=90, ge=1, le=730),
):
    """Chronological rank points. The chart reverses the y-axis so 1 is on top."""
    series = await ranking_crud.get_series(session, keyword_id, days=days)
    if series is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keyword not found")
    return series


@router.get("/{history_id}", response_model=RankingsHistoryResponse)
async def get_history_entry(history_id: int, session: SessionDep, _: CurrentUser):
    entry = await ranking_crud.get(session, history_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found"
        )
    return entry


@router.get("/{history_id}/comparison", response_model=SnapshotComparison)
async def get_comparison(history_id: int, session: SessionDep, _: CurrentUser):
    """Side-by-side SERP snapshots plus which domains entered or left."""
    comparison = await ranking_crud.get_comparison(session, history_id)
    if comparison is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="History entry not found"
        )
    return comparison
