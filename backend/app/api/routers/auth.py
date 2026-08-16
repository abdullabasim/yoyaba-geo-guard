"""Authentication endpoints.

The token is returned in the body (for scripts) and simultaneously set as an
httpOnly cookie (for the browser), so the frontend never stores a JWT in
localStorage where XSS could read it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import ACCESS_COOKIE_NAME, CurrentUser, SessionDep, SuperUser
from app.core.config import settings
from app.core.security import create_access_token
from app.crud.user_crud import user_crud
from app.schemas.auth_schema import (
    LoginRequest,
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        # Lax still sends the cookie on top-level navigation, which the
        # Next.js middleware relies on for route guarding.
        samesite="lax",
        secure=settings.app_env == "production",
        path="/",
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, session: SessionDep):
    user = await user_crud.authenticate(session, payload.email, payload.password)
    if user is None:
        # Deliberately identical message for unknown email and wrong password.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )

    token = create_access_token(
        subject=str(user.id),
        extra_claims={"email": user.email, "is_superuser": user.is_superuser},
    )
    _set_auth_cookie(response, token)
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    return MessageResponse(detail="Logged out")


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: CurrentUser):
    return current_user


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep, _: SuperUser):
    existing = await user_crud.get_by_email(session, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    return await user_crud.create(session, payload)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: PasswordChange, session: SessionDep, current_user: CurrentUser
):
    verified = await user_crud.authenticate(
        session, current_user.email, payload.current_password
    )
    if verified is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
        )
    await user_crud.change_password(session, current_user, payload.new_password)
    return MessageResponse(detail="Password updated")
