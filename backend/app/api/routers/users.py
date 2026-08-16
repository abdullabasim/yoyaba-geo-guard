"""User management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep, SuperUser
from app.core.config import settings
from app.crud.user_crud import user_crud
from app.models.user import User
from app.schemas.auth_schema import UserCreate, UserResponse, UserRole, UserUpdate
from app.schemas.common import ActiveToggle, MessageResponse, Page

router = APIRouter(prefix="/users", tags=["users"])


def check_is_main_account(user: User) -> bool:
    main_email = (settings.first_admin_email or "admin@yoyaba.com").strip().lower()
    return user.id == 1 or user.email.strip().lower() == main_email


@router.get("", response_model=Page[UserResponse])
async def list_users(session: SessionDep, pagination: PaginationDep, _: CurrentUser):
    items = await user_crud.list(session, skip=pagination.skip, limit=pagination.limit)
    total = await user_crud.count(session)
    return Page[UserResponse](
        items=[UserResponse.model_validate(u) for u in items],
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep, _: SuperUser):
    existing = await user_crud.get_by_email(session, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )
    user = await user_crud.create(session, payload)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, session: SessionDep, _: CurrentUser):
    user = await user_crud.get(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int, payload: UserUpdate, session: SessionDep, _: SuperUser
):
    user = await user_crud.get(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if check_is_main_account(user):
        if payload.role == UserRole.READ_ONLY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The main admin account role cannot be changed to read-only.",
            )
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The main admin account cannot be deactivated.",
            )

    if payload.email and payload.email.strip().lower() != user.email.lower():
        existing = await user_crud.get_by_email(session, payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )

    updated = await user_crud.update(session, user, payload)
    return UserResponse.model_validate(updated)


@router.patch("/{user_id}/toggle", response_model=UserResponse)
async def toggle_user_active(
    user_id: int, payload: ActiveToggle, session: SessionDep, _: SuperUser
):
    user = await user_crud.get(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if check_is_main_account(user) and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The main admin account cannot be deactivated.",
        )

    updated = await user_crud.set_active(session, user, payload.is_active)
    return UserResponse.model_validate(updated)


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int, session: SessionDep, current_user: SuperUser
):
    user = await user_crud.get(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if check_is_main_account(user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The main admin account cannot be deleted.",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own logged-in account.",
        )

    await user_crud.remove(session, user_id)
    return MessageResponse(detail="User deleted")
