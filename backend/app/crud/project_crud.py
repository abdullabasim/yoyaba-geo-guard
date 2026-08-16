"""Project CRUD with client name and URL counts."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.client import Client
from app.models.project import Project
from app.models.target_url import TargetURL
from app.schemas.project_schema import ProjectCreate, ProjectUpdate, ProjectWithStats


class CRUDProject(CRUDBase[Project, ProjectCreate, ProjectUpdate]):
    async def list_with_stats(
        self,
        session: AsyncSession,
        *,
        client_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ProjectWithStats]:
        active_urls = func.count(TargetURL.id).filter(TargetURL.is_active.is_(True))
        inheriting_urls = func.count(TargetURL.id).filter(
            TargetURL.inherit_schedule.is_(True)
        )
        stmt = (
            select(
                Project,
                Client.name.label("client_name"),
                func.count(TargetURL.id).label("url_count"),
                active_urls.label("active_url_count"),
                inheriting_urls.label("inheriting_url_count"),
            )
            .join(Client, Client.id == Project.client_id)
            .outerjoin(TargetURL, TargetURL.project_id == Project.id)
            .group_by(Project.id, Client.name)
            .order_by(Project.id.desc())
        )
        if client_id is not None:
            stmt = stmt.where(Project.client_id == client_id)
        result = await session.execute(stmt.offset(skip).limit(limit))

        items: list[ProjectWithStats] = []
        for row in result.all():
            (
                project,
                client_name,
                url_count,
                active_url_count,
                inheriting_url_count,
            ) = row
            items.append(
                ProjectWithStats(
                    id=project.id,
                    client_id=project.client_id,
                    name=project.name,
                    description=project.description,
                    is_active=project.is_active,
                    default_check_interval=project.default_check_interval,
                    default_execution_time=project.default_execution_time,
                    default_timezone=project.default_timezone,
                    created_at=project.created_at,
                    updated_at=project.updated_at,
                    client_name=client_name,
                    url_count=int(url_count or 0),
                    active_url_count=int(active_url_count or 0),
                    inheriting_url_count=int(inheriting_url_count or 0),
                )
            )
        return items

    async def get_by_name_for_client(
        self, session: AsyncSession, client_id: int, name: str
    ) -> Project | None:
        result = await session.execute(
            select(Project)
            .where(Project.client_id == client_id, Project.name == name)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_schedule_modes(
        self, session: AsyncSession, project_id: int
    ) -> tuple[int, int]:
        """``(inheriting, overriding)`` URL counts for the project.

        Surfaced in the UI so an operator editing the project default can see
        how many URLs the change will actually move.
        """
        result = await session.execute(
            select(
                func.count(TargetURL.id).filter(TargetURL.inherit_schedule.is_(True)),
                func.count(TargetURL.id).filter(TargetURL.inherit_schedule.is_(False)),
            ).where(TargetURL.project_id == project_id)
        )
        inheriting, overriding = result.one()
        return int(inheriting or 0), int(overriding or 0)

    async def force_inherit_all_urls(
        self, session: AsyncSession, project_id: int
    ) -> int:
        """Make every URL in the project follow the project default.

        Destructive: per-URL schedules stop being honoured. Only called when the
        caller explicitly set ``apply_to_all_urls``.
        """
        result = await session.execute(
            update(TargetURL)
            .where(TargetURL.project_id == project_id)
            .values(inherit_schedule=True)
        )
        await session.flush()
        return int(result.rowcount or 0)


project_crud = CRUDProject(Project)
