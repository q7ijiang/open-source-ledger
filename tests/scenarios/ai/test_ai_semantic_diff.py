from __future__ import annotations

import json
from pathlib import Path

from ai_layer.config import AIConfig
from ai_layer.provider import MockAIProvider
from ai_layer.schemas import normalize_model_analysis
from ai_layer.service import AIService

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "ai"
    / "semantic_diffs"
    / "license_semantic_tightening.json"
)


def _analysis(source: dict, response: dict, config: AIConfig) -> dict:
    service = AIService(config, MockAIProvider(response))
    raw = service.provider.complete("", "", config)
    return normalize_model_analysis(json.loads(raw), source, config.public_dict())


def test_same_license_name_can_have_semantic_tightening() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    config = AIConfig(enabled=True, provider="mock", model="mock-qwen")
    before = _analysis(fixture["before_source"], fixture["before_response"], config)
    after = _analysis(fixture["after_source"], fixture["after_response"], config)
    service = AIService(config, MockAIProvider([]))

    result = service.compare_models([before], [after])

    assert result["status"] == "ok"
    assert len(result["changes"]) == 1
    change = result["changes"][0]
    assert change["model_id"] == "example/semantic-demo"
    assert change["dimension"] == "commercial_use"
    assert change["change_type"] == "tightened"
    assert change["before_state"] == "allowed"
    assert change["after_state"] == "prohibited"
    assert result["fact_policy"]["ai_may_change_delta"] is False


def test_semantic_diff_distinguishes_missing_ai_profiles_from_no_change() -> None:
    config = AIConfig(enabled=True, provider="mock", model="mock-qwen")
    result = AIService(config, MockAIProvider([])).compare_models([], [])

    assert result["status"] == "no_profile"
    assert result["ai_available"] is False
    assert result["before_profile_count"] == 0
    assert result["after_profile_count"] == 0


def test_semantic_diff_reports_new_and_removed_claim_evidence() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    config = AIConfig(enabled=True, provider="mock", model="mock-qwen")
    before = _analysis(fixture["before_source"], fixture["before_response"], config)
    after = _analysis(fixture["after_source"], fixture["after_response"], config)
    service = AIService(config, MockAIProvider([]))

    added = service.compare_models([], [after])
    removed = service.compare_models([before], [])

    assert {change["change_type"] for change in added["changes"]} == {"evidence_added"}
    assert added["changes"][0]["before_state"] == "not_found"
    assert added["changes"][0]["after_state"] == "prohibited"
    assert {change["change_type"] for change in removed["changes"]} == {"evidence_removed"}
    assert removed["changes"][0]["review_priority"] == "high"
    assert removed["changes"][0]["after_state"] == "not_found"


def test_semantic_diff_detects_changed_evidence_for_unchanged_state() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    config = AIConfig(enabled=True, provider="mock", model="mock-qwen")
    before = _analysis(fixture["before_source"], fixture["before_response"], config)
    after = _analysis(fixture["after_source"], fixture["after_response"], config)
    after["claims"][0]["state"] = "allowed"
    after["claims"][0]["state_zh"] = "允许"

    result = AIService(config, MockAIProvider([])).compare_models([before], [after])

    assert len(result["changes"]) == 1
    assert result["changes"][0]["change_type"] == "evidence_changed"
    assert result["changes"][0]["review_priority"] == "medium"
    assert result["changes"][0]["before_quote"] != result["changes"][0]["after_quote"]
