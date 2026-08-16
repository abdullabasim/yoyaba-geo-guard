"""Demo data seeding.

Purpose: a first boot that shows a working product rather than empty tables. The
URLs are real, live pages and the keywords are ones those pages plausibly rank
for, so a "Run now" against a configured SERP provider returns believable
results instead of a guaranteed miss.

Backdated ranking history is generated locally, with no provider calls. That is
deliberate: seeding must be free and offline. The generated series includes one
engineered 5-position drop per project so the analytics chart has a visible
event and the rank-drop trigger has something to fire on.

Idempotent: seeding is skipped entirely when any client already exists, so a
container restart never duplicates or overwrites real data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.client import Client
from app.models.enums import CheckInterval
from app.models.keyword import Keyword
from app.models.project import Project
from app.models.rankings_history import RankingsHistory
from app.models.target_url import TargetURL

logger = get_logger(__name__)

#: Fixed so repeated seeds on fresh databases produce identical demo history.
RANDOM_SEED = 20260815

HISTORY_DAYS = 45


@dataclass
class SeedKeyword:
    text: str
    location_code: int = 2840
    language_code: str = "en"
    #: Where this page starts in the generated history.
    start_rank: int | None = 8
    #: Engineer a drop of this many positions two checks before the end.
    drop: int = 0


@dataclass
class SeedUrl:
    url: str
    keywords: list[SeedKeyword]
    inherit_schedule: bool = True
    check_interval: CheckInterval = CheckInterval.DAILY
    execution_time: time = time(hour=3, minute=0)
    timezone: str = "UTC"


@dataclass
class SeedProject:
    name: str
    description: str
    urls: list[SeedUrl]
    default_check_interval: CheckInterval = CheckInterval.DAILY
    default_execution_time: time = time(hour=3, minute=0)
    default_timezone: str = "UTC"


@dataclass
class SeedClient:
    name: str
    company_name: str
    projects: list[SeedProject]
    is_active: bool = True


#: Competitor domains used to synthesize plausible SERP snapshots. Grouped by
#: topic so a snapshot for a hosting query does not list recipe sites.
COMPETITOR_POOL: dict[str, list[tuple[str, str]]] = {
    "docs": [
        ("developer.mozilla.org", "MDN Web Docs"),
        ("stackoverflow.com", "Stack Overflow discussion"),
        ("github.com", "Open-source implementation on GitHub"),
        ("w3schools.com", "W3Schools tutorial"),
        ("css-tricks.com", "CSS-Tricks guide"),
        ("smashingmagazine.com", "Smashing Magazine article"),
        ("dev.to", "DEV Community post"),
        ("medium.com", "Medium write-up"),
        ("freecodecamp.org", "freeCodeCamp handbook"),
        ("digitalocean.com", "DigitalOcean tutorial"),
    ],
    "saas": [
        ("g2.com", "G2 reviews and comparison"),
        ("capterra.com", "Capterra software listing"),
        ("trustradius.com", "TrustRadius buyer reviews"),
        ("zapier.com", "Zapier blog roundup"),
        ("hubspot.com", "HubSpot marketing guide"),
        ("forbes.com", "Forbes Advisor best-of list"),
        ("pcmag.com", "PCMag editor review"),
        ("techradar.com", "TechRadar buying guide"),
        ("softwareadvice.com", "Software Advice shortlist"),
        ("getapp.com", "GetApp category page"),
    ],
    "python": [
        ("docs.python.org", "Official Python documentation"),
        ("realpython.com", "Real Python tutorial"),
        ("pypi.org", "Package on PyPI"),
        ("fastapi.tiangolo.com", "FastAPI documentation"),
        ("docs.sqlalchemy.org", "SQLAlchemy documentation"),
        ("testdriven.io", "TestDriven.io course article"),
        ("pythonspeed.com", "Python performance notes"),
        ("betterprogramming.pub", "Better Programming article"),
        ("towardsdatascience.com", "Towards Data Science piece"),
        ("stackoverflow.com", "Stack Overflow answer"),
    ],
    "analytics": [
        ("ahrefs.com", "Ahrefs blog study"),
        ("semrush.com", "Semrush guide"),
        ("moz.com", "Moz Whiteboard Friday"),
        ("searchenginejournal.com", "Search Engine Journal news"),
        ("searchengineland.com", "Search Engine Land analysis"),
        ("backlinko.com", "Backlinko guide"),
        ("neilpatel.com", "Neil Patel breakdown"),
        ("similarweb.com", "SimilarWeb data page"),
        ("statista.com", "Statista chart"),
        ("gartner.com", "Gartner research note"),
    ],
}


#: Real, live pages. Chosen because they are stable, public, and genuinely
#: relevant to their keywords, so a real SERP check produces meaningful output.
DEMO_DATA: list[SeedClient] = [
    SeedClient(
        name="Main Client",
        company_name="Main Web Group",
        projects=[
            SeedProject(
                name="Main SEO Monitoring",
                description="Core project tracking top URLs for intent shifts and rank drops.",
                default_check_interval=CheckInterval.DAILY,
                default_execution_time=time(hour=3, minute=0),
                default_timezone="UTC",
                urls=[
                    SeedUrl(
                        url="https://developer.mozilla.org/en-US/docs/Web/CSS/flex",
                        inherit_schedule=False,
                        keywords=[
                            SeedKeyword("flex shorthand css", start_rank=2, drop=8),
                            SeedKeyword("css flexbox examples", start_rank=None),
                        ],
                    ),
                    SeedUrl(
                        url="https://fastapi.tiangolo.com/tutorial/sql-databases/",
                        keywords=[
                            SeedKeyword("fastapi sql databases", start_rank=3, drop=7),
                            SeedKeyword("fastapi tutorials", start_rank=4, drop=6),
                        ],
                    ),
                ],
            ),
        ],
    ),
    SeedClient(
        name="Inactive Client",
        company_name="Archived Group",
        is_active=False,
        projects=[
            SeedProject(
                name="Paused Experiment",
                description="Legacy project",
                urls=[
                    SeedUrl(
                        url="https://example.com/legacy",
                        keywords=[SeedKeyword("legacy keyword")],
                    )
                ]
            )
        ]
    )
]


def _topic_for_url(url: str) -> str:
    if "python.org" in url or "fastapi" in url or "sqlalchemy" in url:
        return "python"
    if "developer.mozilla.org" in url:
        return "docs"
    if "ahrefs" in url or "moz.com" in url:
        return "analytics"
    return "saas"


def _build_snapshot(
    url: str,
    our_rank: int | None,
    rng: random.Random,
    *,
    shift_intent: bool = False,
) -> list[dict[str, Any]]:
    """Synthesize a plausible top-10 snapshot.

    When ``shift_intent`` is set, part of the pool is replaced with
    commercial-intent style results so the before/after comparison shows a real
    composition change rather than a reshuffle.
    """
    topic = _topic_for_url(url)
    pool = list(COMPETITOR_POOL[topic])
    if shift_intent:
        pool = COMPETITOR_POOL["saas"][:6] + pool[:4]
    rng.shuffle(pool)

    snapshot: list[dict[str, Any]] = []
    position = 1
    pool_index = 0

    while position <= 10:
        if our_rank is not None and position == our_rank:
            snapshot.append(
                {
                    "position": position,
                    "title": "Tracked page",
                    "url": url,
                    "domain": url.split("/")[2].removeprefix("www."),
                    "description": "The client page being monitored for this keyword.",
                }
            )
        else:
            domain, title = pool[pool_index % len(pool)]
            pool_index += 1
            snapshot.append(
                {
                    "position": position,
                    "title": title,
                    "url": f"https://{domain}/{topic}-resource-{position}",
                    "domain": domain,
                    "description": (
                        f"{title} covering the topic in depth, with examples and "
                        "reference material."
                    ),
                }
            )
        position += 1

    return snapshot


def _generate_history(
    keyword_id: int,
    url: str,
    seed_keyword: SeedKeyword,
    rng: random.Random,
) -> list[RankingsHistory]:
    """Backdated observations with small drift plus an optional engineered drop."""
    rows: list[RankingsHistory] = []
    now = datetime.now(UTC)

    current = seed_keyword.start_rank
    previous: int | None = None
    # The drop lands two checks from the end so the chart shows the fall and one
    # subsequent observation, which is what the analyzer compares.
    drop_index = HISTORY_DAYS - 3

    for day_offset in range(HISTORY_DAYS, 0, -1):
        index = HISTORY_DAYS - day_offset
        check_date = now - timedelta(days=day_offset, hours=rng.randint(0, 2))

        if current is not None:
            if seed_keyword.drop and index == drop_index:
                current = current + seed_keyword.drop
            elif rng.random() < 0.35:
                # Ordinary day-to-day noise.
                current = max(1, current + rng.choice([-1, 1]))

        shifted = bool(seed_keyword.drop) and index >= drop_index
        rows.append(
            RankingsHistory(
                keyword_id=keyword_id,
                current_rank=current,
                previous_rank=previous,
                top_10_serp_snapshot=_build_snapshot(
                    url, current if (current or 99) <= 10 else None, rng,
                    shift_intent=shifted,
                ),
                total_results_checked=100,
                serp_url="https://www.google.com/search?q=demo",
                check_date=check_date,
            )
        )
        previous = current

    return rows


async def demo_data_exists(session: AsyncSession) -> bool:
    result = await session.execute(select(func.count()).select_from(Client))
    return int(result.scalar_one()) > 0


async def seed_demo_data(
    session: AsyncSession, *, with_history: bool = True
) -> dict[str, int]:
    """Insert the demo hierarchy. Caller must ensure the database is empty.

    Returns per-entity counts for logging and for the API response.
    """
    rng = random.Random(RANDOM_SEED)
    counts = {
        "clients": 0,
        "projects": 0,
        "urls": 0,
        "keywords": 0,
        "history_rows": 0,
    }

    for seed_client in DEMO_DATA:
        client = Client(
            name=seed_client.name,
            company_name=seed_client.company_name,
            is_active=seed_client.is_active,
        )
        session.add(client)
        await session.flush()
        counts["clients"] += 1

        for seed_project in seed_client.projects:
            # The project named "Paused Experiment" exists to demonstrate that a
            # disabled parent halts every descendant.
            project_active = seed_project.name != "Paused Experiment"
            project = Project(
                client_id=client.id,
                name=seed_project.name,
                description=seed_project.description,
                is_active=project_active,
                default_check_interval=seed_project.default_check_interval,
                default_execution_time=seed_project.default_execution_time,
                default_timezone=seed_project.default_timezone,
            )
            session.add(project)
            await session.flush()
            counts["projects"] += 1

            for seed_url in seed_project.urls:
                target = TargetURL(
                    project_id=project.id,
                    url=seed_url.url,
                    check_interval=seed_url.check_interval,
                    execution_time=seed_url.execution_time,
                    timezone=seed_url.timezone,
                    inherit_schedule=seed_url.inherit_schedule,
                    is_active=True,
                    # Backdated so the demo URLs read as genuinely monitored
                    # rather than all appearing to be due at once.
                    last_checked_at=datetime.now(UTC) - timedelta(hours=rng.randint(2, 20)),
                )
                session.add(target)
                await session.flush()
                counts["urls"] += 1

                for seed_keyword in seed_url.keywords:
                    keyword = Keyword(
                        target_url_id=target.id,
                        keyword_text=seed_keyword.text,
                        location_code=seed_keyword.location_code,
                        language_code=seed_keyword.language_code,
                        is_active=True,
                    )
                    session.add(keyword)
                    await session.flush()
                    counts["keywords"] += 1

                    if with_history:
                        rows = _generate_history(
                            keyword.id, seed_url.url, seed_keyword, rng
                        )
                        session.add_all(rows)
                        counts["history_rows"] += len(rows)

    await session.flush()
    logger.info("Seeded demo data: %s", counts)
    return counts


async def seed_if_empty(session: AsyncSession) -> dict[str, int] | None:
    """Seed only when the database has no clients at all.

    Guarding on emptiness rather than on a marker row means a restart against a
    populated database is a no-op, and no real customer data can be touched.
    """
    if await demo_data_exists(session):
        logger.info("Clients already exist; skipping demo seed")
        return None
    return await seed_demo_data(session, with_history=settings.seed_demo_history)
