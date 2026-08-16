"""AIAlert CRUD."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_alert import AIAlert
from app.models.client import Client
from app.models.enums import IssueType
from app.models.keyword import Keyword
from app.models.project import Project
from app.models.rankings_history import RankingsHistory
from app.models.target_url import TargetURL
from app.schemas.alert_schema import AIAlertDetail, AIAlertStats


class CRUDAlert:
    async def get(self, session: AsyncSession, alert_id: int) -> AIAlert | None:
        return await session.get(AIAlert, alert_id)

    async def create(
        self,
        session: AsyncSession,
        *,
        history_id: int,
        issue_type: IssueType,
        ai_diagnosis: str,
        actionable_advice: str,
        confidence: float | None = None,
        competitor_signals: list[dict[str, Any]] | None = None,
        model_used: str | None = None,
    ) -> AIAlert:
        alert = AIAlert(
            history_id=history_id,
            issue_type=issue_type,
            ai_diagnosis=ai_diagnosis,
            actionable_advice=actionable_advice,
            confidence=confidence,
            competitor_signals=competitor_signals,
            model_used=model_used,
        )
        session.add(alert)
        await session.flush()
        await session.refresh(alert)
        return alert

    async def mark_slack_sent(
        self, session: AsyncSession, alert_id: int, sent: bool = True
    ) -> None:
        alert = await session.get(AIAlert, alert_id)
        if alert is not None:
            alert.slack_sent = sent
            session.add(alert)
            await session.flush()

    async def list_detailed(
        self,
        session: AsyncSession,
        *,
        alert_id: int | None = None,
        issue_type: IssueType | None = None,
        client_id: int | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 50,
    ) -> list[AIAlertDetail]:
        stmt = (
            select(
                AIAlert,
                Keyword.keyword_text,
                TargetURL.url,
                Project.name.label("project_name"),
                Client.name.label("client_name"),
                RankingsHistory.current_rank,
                RankingsHistory.previous_rank,
                RankingsHistory.check_date,
            )
            .join(RankingsHistory, RankingsHistory.id == AIAlert.history_id)
            .join(Keyword, Keyword.id == RankingsHistory.keyword_id)
            .join(TargetURL, TargetURL.id == Keyword.target_url_id)
            .join(Project, Project.id == TargetURL.project_id)
            .join(Client, Client.id == Project.client_id)
        )
        if alert_id is not None:
            stmt = stmt.where(AIAlert.id == alert_id)
        if issue_type is not None:
            stmt = stmt.where(AIAlert.issue_type == issue_type)
        if client_id is not None:
            stmt = stmt.where(Client.id == client_id)

        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Keyword.keyword_text.ilike(pattern),
                    TargetURL.url.ilike(pattern),
                    Client.name.ilike(pattern),
                    Project.name.ilike(pattern),
                    AIAlert.ai_diagnosis.ilike(pattern),
                    AIAlert.actionable_advice.ilike(pattern),
                )
            )

        is_asc = sort_order.lower() == "asc"
        sort_column_map = {
            "created_at": AIAlert.created_at,
            "keyword": Keyword.keyword_text,
            "url": TargetURL.url,
            "confidence": AIAlert.confidence,
            "issue_type": AIAlert.issue_type,
            "client": Client.name,
            "project": Project.name,
        }
        target_col = sort_column_map.get(sort_by, AIAlert.created_at)
        stmt = stmt.order_by(target_col.asc() if is_asc else target_col.desc())

        result = await session.execute(stmt.offset(skip).limit(limit))

        items: list[AIAlertDetail] = []
        for row in result.all():
            (
                alert,
                keyword_text,
                url,
                project_name,
                client_name,
                current_rank,
                previous_rank,
                check_date,
            ) = row
            items.append(
                AIAlertDetail(
                    id=alert.id,
                    history_id=alert.history_id,
                    issue_type=alert.issue_type,
                    ai_diagnosis=alert.ai_diagnosis,
                    actionable_advice=alert.actionable_advice,
                    confidence=alert.confidence,
                    competitor_signals=alert.competitor_signals,
                    model_used=alert.model_used,
                    slack_sent=alert.slack_sent,
                    created_at=alert.created_at,
                    keyword_text=keyword_text,
                    url=url,
                    project_name=project_name,
                    client_name=client_name,
                    current_rank=current_rank,
                    previous_rank=previous_rank,
                    check_date=check_date,
                )
            )
        return items

    async def count(
        self,
        session: AsyncSession,
        *,
        issue_type: IssueType | None = None,
        client_id: int | None = None,
        search: str | None = None,
    ) -> int:
        stmt = (
            select(func.count(AIAlert.id))
            .select_from(AIAlert)
            .join(RankingsHistory, RankingsHistory.id == AIAlert.history_id)
            .join(Keyword, Keyword.id == RankingsHistory.keyword_id)
            .join(TargetURL, TargetURL.id == Keyword.target_url_id)
            .join(Project, Project.id == TargetURL.project_id)
            .join(Client, Client.id == Project.client_id)
        )
        if issue_type is not None:
            stmt = stmt.where(AIAlert.issue_type == issue_type)
        if client_id is not None:
            stmt = stmt.where(Client.id == client_id)
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Keyword.keyword_text.ilike(pattern),
                    TargetURL.url.ilike(pattern),
                    Client.name.ilike(pattern),
                    Project.name.ilike(pattern),
                    AIAlert.ai_diagnosis.ilike(pattern),
                    AIAlert.actionable_advice.ilike(pattern),
                )
            )
        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def get_stats(
        self, session: AsyncSession, *, window_days: int = 30
    ) -> AIAlertStats:
        since = datetime.now(UTC) - timedelta(days=window_days)

        by_type = await session.execute(
            select(AIAlert.issue_type, func.count())
            .where(AIAlert.created_at >= since)
            .group_by(AIAlert.issue_type)
        )
        counts = {str(issue_type): int(count) for issue_type, count in by_type.all()}

        unsent = await session.execute(
            select(func.count())
            .select_from(AIAlert)
            .where(AIAlert.created_at >= since, AIAlert.slack_sent.is_(False))
        )

        return AIAlertStats(
            total=sum(counts.values()),
            by_issue_type=counts,
            unsent=int(unsent.scalar_one()),
            window_days=window_days,
        )


alert_crud = CRUDAlert()
