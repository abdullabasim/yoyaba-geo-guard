"""Client CRUD with project counts for the management table."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.client import Client
from app.models.project import Project
from app.schemas.client_schema import ClientCreate, ClientUpdate, ClientWithStats


class CRUDClient(CRUDBase[Client, ClientCreate, ClientUpdate]):
    async def list_with_stats(
        self, session: AsyncSession, *, skip: int = 0, limit: int = 50
    ) -> list[ClientWithStats]:
        active_count = func.count(Project.id).filter(Project.is_active.is_(True))
        stmt = (
            select(
                Client,
                func.count(Project.id).label("project_count"),
                active_count.label("active_project_count"),
            )
            .outerjoin(Project, Project.client_id == Client.id)
            .group_by(Client.id)
            .order_by(Client.id.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        items: list[ClientWithStats] = []
        for client, project_count, active_project_count in result.all():
            items.append(
                ClientWithStats(
                    **{
                        "id": client.id,
                        "name": client.name,
                        "company_name": client.company_name,
                        "is_active": client.is_active,
                        "created_at": client.created_at,
                        "updated_at": client.updated_at,
                        "project_count": int(project_count or 0),
                        "active_project_count": int(active_project_count or 0),
                    }
                )
            )
        return items

    async def get_by_name(self, session: AsyncSession, name: str) -> Client | None:
        result = await session.execute(select(Client).where(Client.name == name).limit(1))
        return result.scalar_one_or_none()


client_crud = CRUDClient(Client)
