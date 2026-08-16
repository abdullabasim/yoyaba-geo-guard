"""Enumerations persisted as native PostgreSQL enum types."""

from __future__ import annotations

from enum import StrEnum


class CheckInterval(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @property
    def days(self) -> int:
        """Minimum age of ``last_checked_at`` before a URL is due again."""
        return {
            CheckInterval.DAILY: 1,
            CheckInterval.WEEKLY: 7,
            CheckInterval.MONTHLY: 30,
        }[self]


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class IssueType(StrEnum):
    """Classification returned by the LLM for a ranking drop."""

    INTENT_SHIFT = "INTENT_SHIFT"
    SERP_FEATURE_CHANGE = "SERP_FEATURE_CHANGE"
    NEW_COMPETITOR = "NEW_COMPETITOR"
    CONTENT_FRESHNESS = "CONTENT_FRESHNESS"
    ALGORITHM_UPDATE = "ALGORITHM_UPDATE"
    NO_SIGNIFICANT_CHANGE = "NO_SIGNIFICANT_CHANGE"
    UNKNOWN = "UNKNOWN"
