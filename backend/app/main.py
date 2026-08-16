"""FastAPI application entry point."""

from __future__ import annotations

import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import (
    alerts,
    auth,
    bulk,
    clients,
    controls as controls_router,
    keywords,
    projects,
    rankings,
    system,
    tasks,
    urls,
    users,
)
from app.core.config import settings
from app.core.database import dispose_engine, session_scope
from app.core.logging import get_logger, setup_logging
from app.core.redis_client import close_redis
from app.core.seed import seed_if_empty
from app.crud.user_crud import user_crud
from app.llm.client import close_llm_client, tracing_active
from app.services import controls
from app.services.error_alerts import report_error
from app.services.rate_limiter import close_redis as close_rate_limiter_redis

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(
        "Starting %s (env=%s, llm=%s, serp=%s, tracing=%s)",
        settings.project_name,
        settings.app_env,
        "configured" if settings.llm_enabled else "MISSING KEY",
        "configured" if settings.serp_provider_configured else "MISSING CREDENTIALS",
        "on" if tracing_active() else "off",
    )

    # Logged prominently at WARNING because silence from Slack is otherwise
    # indistinguishable from a broken integration.
    if not settings.slack_enabled:
        logger.warning(
            "SLACK_ENABLED=false — no Slack message will be delivered. Alerts are "
            "still classified, stored and logged. Set SLACK_ENABLED=true and "
            "restart the backend and worker to go live."
        )
    else:
        logger.info(
            "Slack delivery: business=%s, errors=%s",
            "on" if settings.business_alerts_deliverable else "off",
            "on" if settings.error_alerts_deliverable else "off",
        )

    # Seeding must never prevent the API from serving; a failure here is loud
    # in the log but not fatal.
    try:
        async with session_scope() as session:
            await user_crud.ensure_first_admin(session)
    except Exception:
        logger.exception("Initial admin seeding failed")

    # Ensure a row exists for every kill switch, so the control panel is
    # populated on first load rather than after the first task runs.
    try:
        async with session_scope() as session:
            await controls.list_controls(session)
    except Exception:
        logger.exception("Service control initialization failed")

    # Demo data, only into a database with no clients at all.
    if settings.seed_demo_data:
        try:
            async with session_scope() as session:
                counts = await seed_if_empty(session)
            if counts:
                logger.info("Demo data seeded: %s", counts)
        except Exception:
            logger.exception("Demo data seeding failed")

    yield

    await close_llm_client()
    await close_redis()
    # The limiter keeps its own client on a different logical database, so it
    # needs its own close or the connection leaks on reload.
    await close_rate_limiter_redis()
    await dispose_engine()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.project_name,
    version="1.0.0",
    description=(
        "YOYABA B2B Growth Platform: Detects search intent shifts behind organic "
        "ranking drops by comparing Google SERP snapshots before and after drops, "
        "diagnosing root causes with an LLM, and generating structured Slack alerts."
    ),
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Required for the httpOnly auth cookie to be sent cross-origin.
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log every unhandled error. Silent 500s are the enemy here.

    Database failures reaching this handler are also pushed to Slack: without
    that, an outage that only affects interactive requests would never notify
    anyone, since the task pipeline alerts only when a task runs.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)

    if settings.alert_on_api_database_errors:
        from app.services.error_alerts import ErrorCategory, classify_exception

        database_categories = {
            ErrorCategory.DATABASE_CONNECTION,
            ErrorCategory.DATABASE_ERROR,
            ErrorCategory.REDIS_CONNECTION,
        }
        if classify_exception(exc).category in database_categories:
            await report_error(
                exc,
                source="api",
                scope="api_database",
                context={
                    "method": request.method,
                    "path": request.url.path,
                },
                traceback_text="".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                ),
            )

    detail = f"{type(exc).__name__}: {exc}" if settings.debug else "Internal server error"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": detail}
    )


@app.get("/health", tags=["system"])
async def health():
    """Liveness probe used by docker-compose."""
    return {"status": "ok", "environment": settings.app_env}


@app.get("/health/ready", tags=["system"])
async def readiness():
    """Readiness probe: verifies the database actually answers."""
    from sqlalchemy import text

    try:
        async with session_scope() as session:
            await session.execute(text("SELECT 1"))
        database_ok = True
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        database_ok = False

    return JSONResponse(
        status_code=status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ready" if database_ok else "degraded",
            "database": "ok" if database_ok else "unreachable",
            "llm_configured": settings.llm_enabled,
            "serp_configured": settings.serp_provider_configured,
            "tracing": tracing_active(),
            "slack_enabled": settings.slack_enabled,
            "business_alerts_deliverable": settings.business_alerts_deliverable,
            "error_alerts_deliverable": settings.error_alerts_deliverable,
            "error_webhook_configured": bool(settings.error_webhook),
        },
    )


for router in (
    auth.router,
    clients.router,
    projects.router,
    urls.router,
    keywords.router,
    rankings.router,
    alerts.router,
    tasks.router,
    bulk.router,
    users.router,
    controls_router.router,
    system.router,
):
    app.include_router(router, prefix=settings.api_v1_prefix)
