"""Generic async CRUD base.

Routers never build SQL; they call these methods. Each concrete module adds the
joins and aggregates its endpoints need.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    async def get(self, session: AsyncSession, obj_id: int) -> ModelType | None:
        return await session.get(self.model, obj_id)

    async def get_many(
        self,
        session: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
        order_desc: bool = True,
    ) -> list[ModelType]:
        stmt = select(self.model)
        for column, value in (filters or {}).items():
            if value is not None:
                stmt = stmt.where(getattr(self.model, column) == value)
        order_column = getattr(self.model, "id")
        stmt = stmt.order_by(order_column.desc() if order_desc else order_column.asc())
        result = await session.execute(stmt.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def count(
        self, session: AsyncSession, *, filters: dict[str, Any] | None = None
    ) -> int:
        stmt = select(func.count()).select_from(self.model)
        for column, value in (filters or {}).items():
            if value is not None:
                stmt = stmt.where(getattr(self.model, column) == value)
        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def create(
        self, session: AsyncSession, payload: CreateSchemaType | dict[str, Any]
    ) -> ModelType:
        values = payload if isinstance(payload, dict) else payload.model_dump()
        obj = self.model(**values)
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj

    async def update(
        self,
        session: AsyncSession,
        obj: ModelType,
        payload: UpdateSchemaType | dict[str, Any],
    ) -> ModelType:
        values = (
            payload
            if isinstance(payload, dict)
            # exclude_unset keeps a PATCH from nulling untouched columns.
            else payload.model_dump(exclude_unset=True)
        )
        for column, value in values.items():
            setattr(obj, column, value)
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj

    async def set_active(
        self, session: AsyncSession, obj: ModelType, is_active: bool
    ) -> ModelType:
        obj.is_active = is_active  # type: ignore[attr-defined]
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj

    async def remove(self, session: AsyncSession, obj_id: int) -> bool:
        result = await session.execute(delete(self.model).where(self.model.id == obj_id))
        return bool(result.rowcount)
