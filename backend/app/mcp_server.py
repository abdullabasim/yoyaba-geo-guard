"""Model Context Protocol server exposing ranking history to LLM clients.

Runs as its own process (``python -m app.mcp_server``). Default transport is
stdio, for editor/agent clients that spawn the server directly; ``--transport
http`` serves over HTTP for the compose deployment.

Read-only by design: an LLM client can query history but cannot mutate the
database.
"""

from __future__ import annotations

import argparse
import re
from typing import Any

import httpx

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import session_scope
from app.core.logging import get_logger
from app.models.ai_alert import AIAlert
from app.models.client import Client
from app.models.keyword import Keyword
from app.models.project import Project
from app.models.rankings_history import RankingsHistory
from app.models.target_url import TargetURL
from app.services.dataforseo import normalize_domain

logger = get_logger(__name__)

mcp = FastMCP(settings.mcp_server_name)

MAX_HISTORY_ROWS = 200


@mcp.tool()
async def get_ranking_history(
    url: str, keyword: str, limit: int | str = 50
) -> dict[str, Any]:
    """Return the ranking history for one URL and keyword.

    Args:
        url: The tracked page URL. Matched on domain plus path, so protocol and
            trailing-slash variants resolve to the same record.
        keyword: The tracked search term. Case and extra whitespace are ignored.
        limit: Maximum number of observations, newest first (max 200).

    Returns a JSON object with the resolved entity, the observation list
    (rank, previous rank, top-10 snapshot, timestamp) and any AI alerts.
    """
    limit = int(limit)
    limit = max(1, min(limit, MAX_HISTORY_ROWS))
    normalized_keyword = " ".join(keyword.split()).lower()
    target_domain = normalize_domain(url)

    async with session_scope() as session:
        stmt = (
            select(Keyword, TargetURL, Project, Client)
            .join(TargetURL, TargetURL.id == Keyword.target_url_id)
            .join(Project, Project.id == TargetURL.project_id)
            .join(Client, Client.id == Project.client_id)
            .where(func.lower(Keyword.keyword_text) == normalized_keyword)
        )
        result = await session.execute(stmt)
        candidates = result.all()

        match = None
        for keyword_row, url_row, project_row, client_row in candidates:
            if normalize_domain(url_row.url) == target_domain:
                match = (keyword_row, url_row, project_row, client_row)
                break

        if match is None:
            return {
                "found": False,
                "message": (
                    f"No tracked keyword {keyword!r} found for a URL on domain "
                    f"{target_domain!r}."
                ),
                "candidates_for_keyword": [row[1].url for row in candidates][:10],
            }

        keyword_row, url_row, project_row, client_row = match

        history_result = await session.execute(
            select(RankingsHistory)
            .where(RankingsHistory.keyword_id == keyword_row.id)
            .order_by(RankingsHistory.check_date.desc())
            .limit(limit)
        )
        history = list(history_result.scalars().all())

        alerts: list[dict[str, Any]] = []
        if history:
            alert_result = await session.execute(
                select(AIAlert)
                .where(AIAlert.history_id.in_([row.id for row in history]))
                .order_by(AIAlert.created_at.desc())
            )
            alerts = [
                {
                    "history_id": alert.history_id,
                    "issue_type": str(alert.issue_type),
                    "ai_diagnosis": alert.ai_diagnosis,
                    "actionable_advice": alert.actionable_advice,
                    "confidence": alert.confidence,
                    "created_at": alert.created_at.isoformat(),
                }
                for alert in alert_result.scalars().all()
            ]

        ranks = [row.current_rank for row in history if row.current_rank is not None]

        return {
            "found": True,
            "client": client_row.name,
            "project": project_row.name,
            "url": url_row.url,
            "keyword": keyword_row.keyword_text,
            "location_code": keyword_row.location_code,
            "language_code": keyword_row.language_code,
            "check_interval": str(url_row.check_interval),
            "is_active": bool(
                url_row.is_active
                and keyword_row.is_active
                and project_row.is_active
                and client_row.is_active
            ),
            "last_checked_at": (
                url_row.last_checked_at.isoformat() if url_row.last_checked_at else None
            ),
            "observation_count": len(history),
            "best_rank": min(ranks) if ranks else None,
            "worst_rank": max(ranks) if ranks else None,
            "latest_rank": history[0].current_rank if history else None,
            "history": [
                {
                    "history_id": row.id,
                    "check_date": row.check_date.isoformat(),
                    "current_rank": row.current_rank,
                    "previous_rank": row.previous_rank,
                    "rank_delta": row.rank_delta,
                    "total_results_checked": row.total_results_checked,
                    "top_10_serp_snapshot": row.top_10_serp_snapshot,
                }
                for row in history
            ],
            "ai_alerts": alerts,
        }


@mcp.tool()
async def fetch_page_content(url: str) -> str:
    """Fetch and extract visible text from a URL for content analysis.
    
    Args:
        url: The web page URL to fetch.
        
    Returns:
        The extracted text content of the page, stripped of HTML tags, or an error message.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Provide a standard User-Agent so we don't get blocked as easily
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            # Simple regex to strip HTML scripts, styles, and tags
            html = response.text
            # Remove script and style blocks entirely
            html = re.sub(r'<(script|style)[^>]*>[\s\S]*?</\1>', ' ', html, flags=re.IGNORECASE)
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', html)
            # Normalize whitespace
            text = ' '.join(text.split())
            
            # Truncate extremely aggressively to avoid blowing up the LLM context window 
            # and to stay under Groq free tier TPM limits (12k TPM)
            return text[:800]
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return f"Failed to fetch content from {url}: {e}"


@mcp.tool()
async def list_tracked_urls(client_name: str | None = None) -> dict[str, Any]:
    """List tracked URLs with their keywords, optionally filtered by client."""
    async with session_scope() as session:
        stmt = (
            select(TargetURL, Project, Client)
            .join(Project, Project.id == TargetURL.project_id)
            .join(Client, Client.id == Project.client_id)
            .order_by(Client.name, Project.name, TargetURL.url)
        )
        if client_name:
            stmt = stmt.where(func.lower(Client.name) == client_name.strip().lower())
        result = await session.execute(stmt)

        items: list[dict[str, Any]] = []
        for url_row, project_row, client_row in result.all():
            keyword_result = await session.execute(
                select(Keyword.keyword_text, Keyword.is_active).where(
                    Keyword.target_url_id == url_row.id
                )
            )
            items.append(
                {
                    "client": client_row.name,
                    "project": project_row.name,
                    "url": url_row.url,
                    "check_interval": str(url_row.check_interval),
                    "execution_time": url_row.execution_time.isoformat(),
                    "timezone": url_row.timezone,
                    "is_active": bool(
                        url_row.is_active and project_row.is_active and client_row.is_active
                    ),
                    "keywords": [
                        {"keyword": text, "is_active": active}
                        for text, active in keyword_result.all()
                    ],
                }
            )

        return {"count": len(items), "urls": items}


def main() -> None:
    parser = argparse.ArgumentParser(description="YOYABA GEO Guard MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="stdio for locally spawned clients, http for the compose service",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8110)
    args = parser.parse_args()

    if args.transport == "stdio":
        logger.info("Starting MCP server on stdio")
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        transport = "sse"
        logger.info("Starting MCP server (%s) on %s:%s", transport, args.host, args.port)
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()
