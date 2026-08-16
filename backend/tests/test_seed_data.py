"""Demo seed data integrity.

The seed is the first thing anyone sees, and it writes directly to the same
tables as real data. These tests guard the two things that would matter:
the generated history must obey the same NULL-rank rules as production data, and
seeding must be structurally valid without touching a database or the network.
"""

from __future__ import annotations

import random

from app.core.seed import (
    COMPETITOR_POOL,
    DEMO_DATA,
    HISTORY_DAYS,
    RANDOM_SEED,
    _build_snapshot,
    _generate_history,
    _topic_for_url,
)
from app.models.enums import CheckInterval


class TestDemoDefinition:
    def test_urls_are_absolute_https(self):
        for client in DEMO_DATA:
            for project in client.projects:
                for url in project.urls:
                    assert url.url.startswith("https://"), url.url
                    # A bare domain would make the "page not found in results"
                    # path fire for every keyword.
                    assert url.url.count("/") >= 3, url.url

    def test_every_url_has_at_least_one_keyword(self):
        for client in DEMO_DATA:
            for project in client.projects:
                for url in project.urls:
                    assert url.keywords, f"{url.url} has no keywords"

    def test_urls_are_unique(self):
        seen = [
            url.url
            for client in DEMO_DATA
            for project in client.projects
            for url in project.urls
        ]
        assert len(seen) == len(set(seen))

    def test_demo_covers_both_inheritance_modes(self):
        """The seed must demonstrate the feature, not just one side of it."""
        modes = {
            url.inherit_schedule
            for client in DEMO_DATA
            for project in client.projects
            for url in project.urls
        }
        assert modes == {True, False}

    def test_demo_includes_an_inactive_client_and_project(self):
        """Proves a disabled parent halts descendants without deleting anything."""
        assert any(not client.is_active for client in DEMO_DATA)
        assert any(
            project.name == "Paused Experiment"
            for client in DEMO_DATA
            for project in client.projects
        )

    def test_demo_includes_a_not_ranking_keyword(self):
        """Exercises the NULL-rank path, which is where rank bugs hide."""
        assert any(
            keyword.start_rank is None
            for client in DEMO_DATA
            for project in client.projects
            for url in project.urls
            for keyword in url.keywords
        )

    def test_demo_includes_engineered_drops(self):
        drops = [
            keyword.drop
            for client in DEMO_DATA
            for project in client.projects
            for url in project.urls
            for keyword in url.keywords
            if keyword.drop
        ]
        # Without a drop the analytics chart and the AI trigger show nothing.
        assert len(drops) >= 3
        assert all(drop >= 3 for drop in drops), "a drop below the threshold triggers nothing"

    def test_intervals_are_valid_enum_members(self):
        for client in DEMO_DATA:
            for project in client.projects:
                assert isinstance(project.default_check_interval, CheckInterval)
                for url in project.urls:
                    assert isinstance(url.check_interval, CheckInterval)


class TestSnapshotGeneration:
    def test_snapshot_has_exactly_ten_unique_positions(self):
        rng = random.Random(RANDOM_SEED)
        snapshot = _build_snapshot("https://example.com/page", 4, rng)
        assert len(snapshot) == 10
        assert [row["position"] for row in snapshot] == list(range(1, 11))

    def test_tracked_page_appears_at_its_rank(self):
        rng = random.Random(RANDOM_SEED)
        url = "https://developer.mozilla.org/en-US/docs/Web/CSS/flex"
        snapshot = _build_snapshot(url, 3, rng)
        assert snapshot[2]["url"] == url

    def test_absent_page_is_not_in_the_snapshot(self):
        rng = random.Random(RANDOM_SEED)
        url = "https://example.com/page"
        snapshot = _build_snapshot(url, None, rng)
        assert all(row["url"] != url for row in snapshot)

    def test_topic_selection_is_relevant(self):
        assert _topic_for_url("https://docs.python.org/3/library/asyncio-task.html") == "python"
        assert _topic_for_url("https://developer.mozilla.org/en-US/docs/Web/CSS/flex") == "docs"
        assert _topic_for_url("https://ahrefs.com/blog/seo-statistics/") == "analytics"
        assert _topic_for_url("https://slack.com/pricing") == "saas"

    def test_every_topic_pool_can_fill_a_snapshot(self):
        # Fewer than 10 entries would repeat domains inside one snapshot.
        for topic, pool in COMPETITOR_POOL.items():
            assert len(pool) >= 10, topic


class TestHistoryGeneration:
    def test_history_length_matches_configuration(self):
        rng = random.Random(RANDOM_SEED)
        seed_keyword = DEMO_DATA[0].projects[0].urls[0].keywords[0]
        rows = _generate_history(1, "https://example.com/page", seed_keyword, rng)
        assert len(rows) == HISTORY_DAYS

    def test_first_row_has_no_previous_rank(self):
        """previous_rank must be NULL on the first observation, not 0."""
        rng = random.Random(RANDOM_SEED)
        seed_keyword = DEMO_DATA[0].projects[0].urls[0].keywords[0]
        rows = _generate_history(1, "https://example.com/page", seed_keyword, rng)
        assert rows[0].previous_rank is None

    def test_previous_rank_chains_correctly(self):
        rng = random.Random(RANDOM_SEED)
        seed_keyword = DEMO_DATA[0].projects[0].urls[0].keywords[0]
        rows = _generate_history(1, "https://example.com/page", seed_keyword, rng)
        for earlier, later in zip(rows, rows[1:]):
            assert later.previous_rank == earlier.current_rank

    def test_not_ranking_keyword_stays_null_throughout(self):
        """A NULL rank must never become 0 or 101 anywhere in the series."""
        rng = random.Random(RANDOM_SEED)
        from app.core.seed import SeedKeyword

        rows = _generate_history(
            1, "https://example.com/page", SeedKeyword("x", start_rank=None), rng
        )
        assert all(row.current_rank is None for row in rows)

    def test_engineered_drop_is_visible_in_the_series(self):
        from app.core.seed import SeedKeyword

        rng = random.Random(RANDOM_SEED)
        rows = _generate_history(
            1,
            "https://example.com/page",
            SeedKeyword("x", start_rank=4, drop=8),
            rng,
        )
        ranks = [row.current_rank for row in rows if row.current_rank is not None]
        # The drop must be large enough to exceed the default threshold.
        biggest_jump = max(
            later - earlier for earlier, later in zip(ranks, ranks[1:])
        )
        assert biggest_jump >= 3

    def test_ranks_never_go_below_one(self):
        from app.core.seed import SeedKeyword

        rng = random.Random(RANDOM_SEED)
        rows = _generate_history(
            1, "https://example.com/page", SeedKeyword("x", start_rank=1), rng
        )
        assert all(row.current_rank >= 1 for row in rows if row.current_rank is not None)

    def test_check_dates_are_chronological_and_in_the_past(self):
        from datetime import UTC, datetime

        from app.core.seed import SeedKeyword

        rng = random.Random(RANDOM_SEED)
        rows = _generate_history(
            1, "https://example.com/page", SeedKeyword("x", start_rank=5), rng
        )
        dates = [row.check_date for row in rows]
        assert dates == sorted(dates)
        assert all(date < datetime.now(UTC) for date in dates)

    def test_generation_is_deterministic(self):
        """Same seed, same history — otherwise demo screenshots drift."""
        from app.core.seed import SeedKeyword

        first = _generate_history(
            1, "https://example.com/p", SeedKeyword("x", start_rank=6, drop=5),
            random.Random(RANDOM_SEED),
        )
        second = _generate_history(
            1, "https://example.com/p", SeedKeyword("x", start_rank=6, drop=5),
            random.Random(RANDOM_SEED),
        )
        assert [row.current_rank for row in first] == [row.current_rank for row in second]
