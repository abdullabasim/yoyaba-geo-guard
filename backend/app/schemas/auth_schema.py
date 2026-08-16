"""Authentication request/response schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field, computed_field

from app.core.config import settings
from app.schemas.common import ORMModel


class UserRole(StrEnum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(ORMModel):
    id: int
    email: str
    full_name: str | None
    is_active: bool
    is_superuser: bool
    created_at: datetime

    @computed_field
    @property
    def role(self) -> UserRole:
        return UserRole.READ_WRITE if self.is_superuser else UserRole.READ_ONLY

    @computed_field
    @property
    def is_main_account(self) -> bool:
        main_email = (settings.first_admin_email or "admin@yoyaba.com").strip().lower()
        return self.id == 1 or self.email.strip().lower() == main_email


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole = UserRole.READ_WRITE


class UserUpdate(BaseModel):
    email: EmailStr | None = Field(default=None)
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
