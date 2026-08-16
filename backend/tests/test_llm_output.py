"""Validation tests for the structured LLM output contract.

These assert that the ``IntentShiftAnalysis`` coercions actually save retries,
and that genuinely bad output still fails so the retry loop engages.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.client import LLMResponseError, extract_json_object
from app.llm.output_models import IntentShiftAnalysis
from app.models.enums import IssueType

VALID = {
    "issue_type": "INTENT_SHIFT",
    "intent_shift_detected": True,
    "confidence": 0.82,
    "ai_diagnosis": "The top ten moved from informational guides to commercial listings.",
    "actionable_advice": "Rebuild the page as a comparison table with pricing tiers.",
}


class TestIntentShiftAnalysis:
    def test_valid_payload(self):
        analysis = IntentShiftAnalysis.model_validate(VALID)
        assert analysis.issue_type is IssueType.INTENT_SHIFT
        assert analysis.competitor_signals == []

    def test_loose_issue_type_casing_is_coerced(self):
        analysis = IntentShiftAnalysis.model_validate({**VALID, "issue_type": "intent shift"})
        assert analysis.issue_type is IssueType.INTENT_SHIFT

    def test_unknown_issue_type_falls_back_instead_of_failing(self):
        # Wasting all three retries on one odd label would be expensive.
        analysis = IntentShiftAnalysis.model_validate({**VALID, "issue_type": "VIBES"})
        assert analysis.issue_type is IssueType.UNKNOWN

    def test_bullet_list_text_is_flattened(self):
        analysis = IntentShiftAnalysis.model_validate(
            {**VALID, "actionable_advice": ["Add a pricing table.", "Add FAQ schema."]}
        )
        assert "Add a pricing table." in analysis.actionable_advice
        assert "\n" in analysis.actionable_advice

    def test_confidence_out_of_range_fails(self):
        with pytest.raises(ValidationError):
            IntentShiftAnalysis.model_validate({**VALID, "confidence": 1.7})

    def test_too_short_diagnosis_fails(self):
        with pytest.raises(ValidationError):
            IntentShiftAnalysis.model_validate({**VALID, "ai_diagnosis": "dropped"})

    def test_missing_required_field_fails(self):
        payload = {key: value for key, value in VALID.items() if key != "confidence"}
        with pytest.raises(ValidationError):
            IntentShiftAnalysis.model_validate(payload)

    def test_extra_keys_are_ignored(self):
        analysis = IntentShiftAnalysis.model_validate({**VALID, "invented_field": 1})
        assert analysis.confidence == 0.82


class TestExtractJsonObject:
    def test_plain_json(self):
        assert extract_json_object('{"a": 1}') == {"a": 1}

    def test_markdown_fenced_json(self):
        assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}

    def test_json_wrapped_in_prose(self):
        raw = 'Here is my analysis:\n{"a": 1}\nLet me know if you need more.'
        assert extract_json_object(raw) == {"a": 1}

    def test_no_json_raises(self):
        with pytest.raises(LLMResponseError, match="no JSON object"):
            extract_json_object("I cannot answer that.")

    def test_array_is_rejected(self):
        with pytest.raises(LLMResponseError):
            extract_json_object("[1, 2, 3]")
