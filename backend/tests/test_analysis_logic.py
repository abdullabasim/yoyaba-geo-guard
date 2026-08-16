"""Unit tests for the pure decision logic.

These cover the two places where a silent mistake would be expensive: the
rank-drop trigger rule and the SERP response parser. Neither needs a database,
a network connection or an API key.

Run with:  cd backend && pytest
"""

from __future__ import annotations

import pytest

from app.services.dataforseo import (
    SerpMalformedResponseError,
    SerpQuotaError,
    _extract_organic_items,
    _matches_target,
    build_snapshot,
    normalize_domain,
)
from app.services.scheduling import should_trigger_analysis


class TestShouldTriggerAnalysis:
    def test_drop_at_threshold_triggers(self):
        assert should_trigger_analysis(3, 6) is True

    def test_drop_below_threshold_does_not_trigger(self):
        assert should_trigger_analysis(3, 5) is False

    def test_improvement_does_not_trigger(self):
        assert should_trigger_analysis(8, 2) is False

    def test_missing_previous_never_triggers(self):
        assert should_trigger_analysis(None, 40) is False

    def test_falling_out_of_results_never_triggers(self):
        # None must not be read as a numeric rank in either direction.
        assert should_trigger_analysis(4, None) is False

    def test_both_missing_never_triggers(self):
        assert should_trigger_analysis(None, None) is False


class TestNormalizeDomain:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("https://www.example.com/page", "example.com"),
            ("http://example.com", "example.com"),
            ("https://EXAMPLE.com:8080/x", "example.com"),
            ("example.com/path", "example.com"),
            (None, None),
            ("", None),
        ],
    )
    def test_normalization(self, value, expected):
        assert normalize_domain(value) == expected


class TestMatchesTarget:
    def test_same_page_with_trailing_slash(self):
        assert _matches_target("https://a.com/pricing/", "https://a.com/pricing") is True

    def test_protocol_and_www_variants(self):
        assert _matches_target("http://www.a.com/pricing", "https://a.com/pricing") is True

    def test_different_page_on_same_domain(self):
        assert _matches_target("https://a.com/blog", "https://a.com/pricing") is False

    def test_different_domain(self):
        assert _matches_target("https://b.com/pricing", "https://a.com/pricing") is False


class TestBuildSnapshot:
    def test_caps_at_ten_and_maps_fields(self):
        items = [
            {
                "rank_absolute": i,
                "title": f"Title {i}",
                "url": f"https://site{i}.com/p",
                "domain": f"site{i}.com",
                "description": "x" * 500,
            }
            for i in range(1, 15)
        ]
        snapshot = build_snapshot(items)
        assert len(snapshot) == 10
        assert snapshot[0]["position"] == 1
        assert snapshot[0]["domain"] == "site1.com"
        assert len(snapshot[0]["description"]) == 300

    def test_derives_domain_when_absent(self):
        snapshot = build_snapshot(
            [{"rank_absolute": 1, "url": "https://www.derived.com/x"}]
        )
        assert snapshot[0]["domain"] == "derived.com"


class TestExtractOrganicItems:
    def test_filters_non_organic_types(self):
        payload = {
            "tasks": [
                {
                    "status_code": 20000,
                    "result": [
                        {
                            "check_url": "https://google.com/search?q=x",
                            "items": [
                                {"type": "paid", "url": "https://ad.com"},
                                {"type": "organic", "url": "https://real.com"},
                                {"type": "video", "url": "https://vid.com"},
                            ],
                        }
                    ],
                }
            ]
        }
        organic, serp_url = _extract_organic_items(payload)
        assert len(organic) == 1
        assert organic[0]["url"] == "https://real.com"
        assert serp_url == "https://google.com/search?q=x"

    def test_provider_error_code_raises(self):
        payload = {
            "tasks": [{"status_code": 40501, "status_message": "quota exceeded"}]
        }
        # A quota failure must be typed, so the alert can say "top up the balance"
        # rather than "something went wrong".
        with pytest.raises(SerpQuotaError, match="quota exceeded"):
            _extract_organic_items(payload)

    def test_missing_tasks_raises(self):
        with pytest.raises(SerpMalformedResponseError, match="no tasks"):
            _extract_organic_items({})

    def test_zero_results_is_not_an_error(self):
        payload = {
            "tasks": [{"status_code": 20000, "result": [{"check_url": "u"}]}]
        }
        organic, serp_url = _extract_organic_items(payload)
        assert organic == []
        assert serp_url == "u"
