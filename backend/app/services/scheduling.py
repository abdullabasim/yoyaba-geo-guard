"""Scheduling helpers shared by Celery Beat and the diagnostics endpoint."""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.crud.keyword_crud import keyword_crud
from app.crud.url_crud import target_url_crud
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


async def collect_due_work(session: AsyncSession) -> list[tuple[int, int, str, str]]:
    """Return ``(target_url_id, keyword_id, url, keyword_text)`` for due checks.

    Expands each due URL into one work item per active keyword, because the
    provider is billed per keyword and each keyword needs its own log row.
    """
    due_urls = await target_url_crud.list_due(
        session, window_minutes=settings.due_window_minutes
    )

    work: list[tuple[int, int, str, str]] = []
    for url_obj in due_urls:
        keywords = await keyword_crud.list_active_for_url(session, url_obj.id)
        for keyword in keywords:
            work.append((url_obj.id, keyword.id, url_obj.url, keyword.keyword_text))

    if work:
        logger.info(
            "Dispatching %s keyword checks across %s URLs", len(work), len(due_urls)
        )
    return work


def should_trigger_analysis(
    previous_rank: int | None,
    current_rank: int | None,
    threshold: int | None = None,
) -> bool:
    """Decide whether a movement warrants an LLM call.

    A NULL on either side is not comparable and never triggers analysis.
    Uses the per-URL or per-project threshold if provided, falling back to global settings.
    """
    if previous_rank is None or current_rank is None:
        return False
    effective_threshold = threshold if threshold is not None else settings.rank_drop_threshold
    return (current_rank - previous_rank) >= effective_threshold


WorkItem = tuple[int, int, str, str]  # (target_url_id, keyword_id, url, keyword_text)


def chunk_work(
    work: list[WorkItem], batch_size: int | None = None
) -> list[list[WorkItem]]:
    """Split a flat work list into chunks of ``batch_size``.

    Each chunk becomes one ``fetch_serp_batch_task`` Celery task, which sends
    all its keywords in a single DataForSEO API call.
    """
    size = batch_size or settings.dataforseo_batch_size
    if size <= 0:
        size = 1
    return [work[i : i + size] for i in range(0, len(work), size)]

