"""User CRUD and first-admin seeding."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth_schema import UserCreate, UserRole, UserUpdate

logger = get_logger(__name__)


class CRUDUser:
    async def get(self, session: AsyncSession, user_id: int) -> User | None:
        return await session.get(User, user_id)

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        result = await session.execute(
            select(User).where(func.lower(User.email) == email.strip().lower()).limit(1)
        )
        return result.scalar_one_or_none()

    async def list(self, session: AsyncSession, *, skip: int = 0, limit: int = 50) -> list[User]:
        result = await session.execute(
            select(User).order_by(User.id.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self, session: AsyncSession) -> int:
        result = await session.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())

    async def create(self, session: AsyncSession, payload: UserCreate) -> User:
        is_super = getattr(payload, 'is_superuser', None)
        if is_super is None:
            is_super = payload.role == UserRole.READ_WRITE

        user = User(
            email=payload.email.strip().lower(),
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            is_superuser=is_super,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    async def update(self, session: AsyncSession, user: User, payload: UserUpdate) -> User:
        if payload.email is not None:
            user.email = payload.email.strip().lower()
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.password:
            user.password_hash = hash_password(payload.password)
        if payload.role is not None:
            user.is_superuser = payload.role == UserRole.READ_WRITE
        if payload.is_active is not None:
            user.is_active = payload.is_active

        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    async def set_active(self, session: AsyncSession, user: User, is_active: bool) -> User:
        user.is_active = is_active
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    async def remove(self, session: AsyncSession, user_id: int) -> bool:
        user = await self.get(session, user_id)
        if user is None:
            return False
        await session.delete(user)
        await session.flush()
        return True

    async def authenticate(
        self, session: AsyncSession, email: str, password: str
    ) -> User | None:
        user = await self.get_by_email(session, email)
        if user is None:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def change_password(
        self, session: AsyncSession, user: User, new_password: str
    ) -> None:
        user.password_hash = hash_password(new_password)
        session.add(user)
        await session.flush()

    async def ensure_first_admin(self, session: AsyncSession) -> None:
        """Seed one superuser so a fresh deployment is loginable.

        Runs on API startup. Does nothing once any user exists, so it can never
        resurrect or overwrite a deleted or rotated admin account.
        """
        result = await session.execute(select(func.count()).select_from(User))
        if int(result.scalar_one()) > 0:
            return

        if not settings.first_admin_email or not settings.first_admin_password:
            logger.warning("No users exist and FIRST_ADMIN_* is unset; login is impossible")
            return

        await self.create(
            session,
            UserCreate(
                email=settings.first_admin_email,
                password=settings.first_admin_password,
                full_name="Initial Admin",
                role=UserRole.READ_WRITE,
            ),
        )
        logger.info("Seeded initial admin user %s", settings.first_admin_email)


user_crud = CRUDUser()
