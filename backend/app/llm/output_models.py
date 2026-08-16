"""Pydantic models for structured LLM output.

These are the contract the model must satisfy. Nothing downstream reads raw
model text: ``intent_analyzer`` validates into ``IntentShiftAnalysis`` first and
retries with the validation error fed back to the model when it fails.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import IssueType


class CompetitorSignal(BaseModel):
    """A specific competitor observation the model used as evidence."""

    model_config = ConfigDict(extra="ignore")

    domain: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=500)
    url: str | None = Field(default=None, max_length=2048)
    note: str = Field(max_length=1000, description="Why this result matters")
    is_new_entrant: bool = False


class IntentShiftAnalysis(BaseModel):
    """The full structured verdict for one ranking drop."""

    model_config = ConfigDict(extra="ignore")

    issue_type: IssueType
    intent_shift_detected: bool
    confidence: float = Field(ge=0.0, le=1.0)
    ai_diagnosis: str = Field(min_length=20, max_length=10000)
    actionable_advice: str = Field(min_length=20, max_length=10000)
    competitor_signals: list[CompetitorSignal] = Field(default_factory=list, max_length=20)
    detected_intent_before: str | None = Field(default=None, max_length=200)
    detected_intent_after: str | None = Field(default=None, max_length=200)

    @field_validator("issue_type", mode="before")
    @classmethod
    def coerce_issue_type(cls, value: object) -> object:
        """Accept loose casing/spacing from the model instead of failing.

        Truly unrecognized values become UNKNOWN rather than raising, so one odd
        label does not waste all three retries.
        """
        if isinstance(value, str):
            normalized = value.strip().upper().replace(" ", "_").replace("-", "_")
            valid = {member.value for member in IssueType}
            return normalized if normalized in valid else IssueType.UNKNOWN.value
        return value

    @field_validator("ai_diagnosis", "actionable_advice", mode="before")
    @classmethod
    def stringify_text(cls, value: object) -> object:
        """Flatten a list of bullet points into text if the model returns one."""
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        return value


class LLMAnalysisOutcome(BaseModel):
    """Wrapper carrying provenance alongside the analysis."""

    analysis: IntentShiftAnalysis
    model_used: str
    attempts: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
