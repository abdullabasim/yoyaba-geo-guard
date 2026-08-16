"""Schedule inheritance and kill-switch behaviour.

These target the two ways this feature can silently do the wrong thing:

1. Reading a URL's own schedule columns while it is inheriting — the check then
   fires at an hour nobody configured.
2. A kill switch that fails closed — a database blip would stop all monitoring
   with no alert, which is the worst possible failure for a monitoring product.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest

from app.crud.url_crud import CRUDTargetURL
from app.models.enums import CheckInterval
from app.models.project import Project
from app.models.service_control import SERVICE_METADATA, ServiceKey
from app.models.target_url import TargetURL


def make_project(
    *,
    interval: CheckInterval = CheckInterval.DAILY,
    execution_time: time = time(hour=3),
    timezone: str = "UTC",
) -> Project:
    project = Project()
    project.name = "Test project"
    project.default_check_interval = interval
    project.default_execution_time = execution_time
    project.default_timezone = timezone
    return project


def make_url(
    project: Project,
    *,
    inherit: bool,
    interval: CheckInterval = CheckInterval.WEEKLY,
    execution_time: time = time(hour=17, minute=45),
    timezone: str = "Asia/Tokyo",
) -> TargetURL:
    url_obj = TargetURL()
    url_obj.url = "https://example.com/pricing"
    url_obj.inherit_schedule = inherit
    url_obj.check_interval = interval
    url_obj.execution_time = execution_time
    url_obj.timezone = timezone
    url_obj.project = project
    return url_obj


class TestEffectiveSchedule:
    def test_inheriting_url_uses_project_default(self):
        project = make_project(
            interval=CheckInterval.MONTHLY,
            execution_time=time(hour=6, minute=30),
            timezone="Europe/Berlin",
        )
        url_obj = make_url(project, inherit=True)

        assert url_obj.effective_interval() is CheckInterval.MONTHLY
        assert url_obj.effective_execution_time() == time(hour=6, minute=30)
        assert url_obj.effective_timezone() == "Europe/Berlin"

    def test_overriding_url_keeps_its_own_schedule(self):
        project = make_project(
            interval=CheckInterval.MONTHLY,
            execution_time=time(hour=6, minute=30),
            timezone="Europe/Berlin",
        )
        url_obj = make_url(project, inherit=False)

        assert url_obj.effective_interval() is CheckInterval.WEEKLY
        assert url_obj.effective_execution_time() == time(hour=17, minute=45)
        assert url_obj.effective_timezone() == "Asia/Tokyo"

    def test_own_columns_are_preserved_while_inheriting(self):
        """Inheritance must not destroy the URL's own values.

        Turning inheritance off later has to restore a real schedule rather than
        a blank one, so the columns stay populated.
        """
        project = make_project()
        url_obj = make_url(project, inherit=True)

        assert url_obj.check_interval is CheckInterval.WEEKLY
        assert url_obj.execution_time == time(hour=17, minute=45)

        url_obj.inherit_schedule = False
        assert url_obj.effective_execution_time() == time(hour=17, minute=45)

    def test_missing_project_falls_back_to_own_columns(self):
        """A detached URL must still yield a schedule, never raise."""
        url_obj = TargetURL()
        url_obj.inherit_schedule = True
        url_obj.check_interval = CheckInterval.DAILY
        url_obj.execution_time = time(hour=9)
        url_obj.timezone = "UTC"

        assert url_obj.effective_interval(None) is CheckInterval.DAILY
        assert url_obj.effective_execution_time(None) == time(hour=9)

    def test_explicit_project_argument_avoids_lazy_load(self):
        """Passing the project explicitly is what the async due-query relies on.

        A lazy relationship access inside the async scheduler would raise, so the
        helpers must accept a project that was eagerly loaded.
        """
        project = make_project(execution_time=time(hour=1, minute=15))
        url_obj = TargetURL()
        url_obj.inherit_schedule = True
        url_obj.check_interval = CheckInterval.WEEKLY
        url_obj.execution_time = time(hour=20)
        url_obj.timezone = "UTC"

        assert url_obj.effective_execution_time(project) == time(hour=1, minute=15)


class TestDueDetection:
    """``_is_due`` must read the effective schedule, not the raw columns."""

    def setup_method(self):
        self.crud = CRUDTargetURL(TargetURL)

    def test_inheriting_url_is_due_at_project_time(self):
        project = make_project(execution_time=time(hour=3), timezone="UTC")
        url_obj = make_url(
            project, inherit=True, execution_time=time(hour=17), timezone="UTC"
        )
        url_obj.last_checked_at = datetime(2026, 8, 14, 3, 5, tzinfo=UTC)

        at_project_time = datetime(2026, 8, 15, 3, 5, tzinfo=UTC)
        assert self.crud._is_due(url_obj, at_project_time, 30) is True

        # Its own 17:00 must be ignored while inheriting.
        at_own_time = datetime(2026, 8, 15, 17, 5, tzinfo=UTC)
        assert self.crud._is_due(url_obj, at_own_time, 30) is False

    def test_overriding_url_is_due_at_its_own_time(self):
        project = make_project(execution_time=time(hour=3), timezone="UTC")
        url_obj = make_url(
            project,
            inherit=False,
            interval=CheckInterval.DAILY,
            execution_time=time(hour=17),
            timezone="UTC",
        )
        url_obj.last_checked_at = datetime(2026, 8, 14, 17, 5, tzinfo=UTC)

        assert (
            self.crud._is_due(url_obj, datetime(2026, 8, 15, 17, 5, tzinfo=UTC), 30)
            is True
        )
        assert (
            self.crud._is_due(url_obj, datetime(2026, 8, 15, 3, 5, tzinfo=UTC), 30)
            is False
        )

    def test_never_checked_url_is_due_immediately(self):
        project = make_project()
        url_obj = make_url(project, inherit=True)
        url_obj.last_checked_at = None
        assert self.crud._is_due(url_obj, datetime(2026, 8, 15, 12, 0, tzinfo=UTC), 30)

    def test_interval_not_elapsed_is_not_due(self):
        project = make_project(interval=CheckInterval.WEEKLY, execution_time=time(hour=3))
        url_obj = make_url(project, inherit=True)
        now = datetime(2026, 8, 15, 3, 5, tzinfo=UTC)
        url_obj.last_checked_at = now - timedelta(days=2)
        assert self.crud._is_due(url_obj, now, 30) is False

    def test_missed_window_waits_rather_than_bursting(self):
        """Outside the window the run is skipped, not queued up.

        Otherwise a worker outage would release a burst of stale checks and bill
        the provider for all of them at once.
        """
        project = make_project(execution_time=time(hour=3), timezone="UTC")
        url_obj = make_url(project, inherit=True)
        url_obj.last_checked_at = datetime(2026, 8, 14, 3, 5, tzinfo=UTC)

        long_after = datetime(2026, 8, 15, 9, 0, tzinfo=UTC)
        assert self.crud._is_due(url_obj, long_after, 30) is False

    def test_unknown_timezone_falls_back_to_utc(self):
        project = make_project(execution_time=time(hour=3), timezone="Mars/Olympus_Mons")
        url_obj = make_url(project, inherit=True)
        url_obj.last_checked_at = datetime(2026, 8, 14, 3, 5, tzinfo=UTC)

        # Must not raise, and must behave as UTC.
        assert self.crud._is_due(url_obj, datetime(2026, 8, 15, 3, 5, tzinfo=UTC), 30)


class TestServiceControlMetadata:
    def test_every_service_key_has_operator_metadata(self):
        """The UI renders these strings; a missing entry would KeyError at runtime."""
        for key in ServiceKey:
            assert key in SERVICE_METADATA
            name, summary, impact = SERVICE_METADATA[key]
            assert name and summary and impact
            # The impact text is what stops someone pausing a subsystem without
            # understanding the consequence.
            assert len(impact) > 40

    def test_scheduler_is_the_master_switch(self):
        assert ServiceKey.SCHEDULER in ServiceKey
        # Enum order drives display order: the master switch must come first.
        assert list(ServiceKey)[0] is ServiceKey.SCHEDULER


class TestControlsFailOpen:
    """A switch that cannot be read must not stop the pipeline."""

    @pytest.mark.asyncio
    async def test_unreadable_switch_defaults_to_enabled(self, monkeypatch):
        from app.services import controls

        controls.invalidate_cache()

        def explode(*args, **kwargs):
            raise RuntimeError("database is down")

        monkeypatch.setattr(controls, "session_scope", explode)

        states = await controls.get_all_states(use_cache=False)
        assert all(states.values()), "a read failure must not pause anything"
        assert await controls.is_enabled(ServiceKey.SERP_FETCH) is True

    @pytest.mark.asyncio
    async def test_stale_cache_preferred_over_arbitrary_default(self, monkeypatch):
        """A previously known state beats guessing when the database goes away."""
        import time as time_module

        from app.services import controls

        controls._cache = controls._CacheEntry(
            values={key: True for key in ServiceKey} | {ServiceKey.AI_ANALYSIS: False},
            fetched_at=time_module.monotonic() - (controls.CACHE_TTL_SECONDS + 5),
        )

        def explode(*args, **kwargs):
            raise RuntimeError("database is down")

        monkeypatch.setattr(controls, "session_scope", explode)

        states = await controls.get_all_states(use_cache=False)
        assert states[ServiceKey.AI_ANALYSIS] is False
        controls.invalidate_cache()
