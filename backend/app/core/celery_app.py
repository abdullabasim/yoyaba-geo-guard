"""Celery application and Beat schedule.

Task modules are imported eagerly via ``include`` so both the worker and the
API process can enqueue by name without importing the task module themselves.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import schedule

from app.core.config import settings

celery_app = Celery(
    "seo_intent",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Redelivery on worker loss; safe because Task A is idempotent per day.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    # Hard ceilings so a hung provider call cannot occupy a slot forever.
    task_soft_time_limit=300,
    task_time_limit=360,
    result_expires=60 * 60 * 24 * 7,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    "dispatch-due-checks": {
        "task": "app.worker.tasks.dispatch_due_checks",
        "schedule": schedule(run_every=settings.beat_dispatch_interval_seconds),
        "options": {"expires": settings.beat_dispatch_interval_seconds},
    },
    # Independent of workload: an outage is reported within one interval even if
    # no URL happens to be due.
    "monitor-system-health": {
        "task": "app.worker.tasks.monitor_system_health",
        "schedule": schedule(run_every=settings.health_check_interval_seconds),
        "options": {"expires": settings.health_check_interval_seconds},
    },
}
