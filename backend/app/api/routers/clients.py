"""Client endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep, SuperUser
from app.crud.client_crud import client_crud
from app.schemas.client_schema import (
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    ClientWithStats,
)
from app.schemas.common import ActiveToggle, MessageResponse, Page

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=Page[ClientWithStats])
async def list_clients(session: SessionDep, pagination: PaginationDep, _: CurrentUser):
    items = await client_crud.list_with_stats(
        session, skip=pagination.skip, limit=pagination.limit
    )
    total = await client_crud.count(session)
    return Page[ClientWithStats](
        items=items, total=total, skip=pagination.skip, limit=pagination.limit
    )


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(payload: ClientCreate, session: SessionDep, _: SuperUser):
    return await client_crud.create(session, payload)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, session: SessionDep, _: CurrentUser):
    client = await client_crud.get(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int, payload: ClientUpdate, session: SessionDep, _: SuperUser
):
    client = await client_crud.get(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return await client_crud.update(session, client, payload)


@router.patch("/{client_id}/toggle", response_model=ClientResponse)
async def toggle_client(
    client_id: int, payload: ActiveToggle, session: SessionDep, _: SuperUser
):
    """Pause or resume a client. Disabling stops all descendant executions."""
    client = await client_crud.get(session, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return await client_crud.set_active(session, client, payload.is_active)


@router.delete("/{client_id}", response_model=MessageResponse)
async def delete_client(client_id: int, session: SessionDep, _: SuperUser):
    """Cascades to projects, URLs, keywords, history and alerts."""
    deleted = await client_crud.remove(session, client_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return MessageResponse(detail="Client deleted")
