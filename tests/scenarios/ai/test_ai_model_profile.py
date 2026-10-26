from __future__ import annotations

import json
from pathlib import Path

from ai_layer.config import AIConfig
from ai_layer.provider import MockAIProvider
from ai_layer.service import AIService

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ai"


def _load(relative: str) -> dict:
    return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))


def _service(response: dict) -> AIService:
    config = AIConfig(enabled=True, provider="mock", model="mock-qwen")
    return AIService(config, MockAIProvider(response))


def test_model_profile_preserves_exact_quotes_and_confidence() -> None:
    source_bundle = _load("source_bundles/qwen_research_source_bundle.json")
    analysis = _service(_load("model_profiles/qwen_research_ai_response.json")).analyze_model_source(
        source_bundle
    )

    assert analysis["status"] == "ok"
    assert analysis["subject"]["license_fact"] == "qwen-research"
    claims = {claim["dimension"]: claim for claim in analysis["claims"]}
    assert claims["commercial_use"]["state"] == "prohibited"
    assert claims["commercial_use"]["confidence"] == 0.86
    assert claims["commercial_use"]["evidence_level"] == "C"
    assert claims["commercial_use"]["human_review"] == "pending"
    assert claims["commercial_use"]["evidence"]["quote"] == "该模型仅限研究用途，不得用于商业目的。"
    assert claims["notice"]["confidence"] == 0.59
    assert {gap["dimension"] for gap in analysis["gaps"]} == {
        "training_other_models",
        "fine_tuned_redistribution",
        "commercial_license_request",
    }
    assert analysis["fact_policy"]["ai_may_change_license"] is False
    assert analysis["fact_policy"]["ai_may_change_decision"] is False




def test_model_profile_rejects_non_exact_quote() -> None:
    source_bundle = _load("source_bundles/qwen_research_source_bundle.json")
    response = _load("model_profiles/qwen_research_ai_response.json")
    response["claims"][0]["evidence"]["quote"] = "该模型不得商用。"

    analysis = _service(response).analyze_model_source(source_bundle)

    assert all(claim["dimension"] != "commercial_use" for claim in analysis["claims"])
    commercial_gap = next(gap for gap in analysis["gaps"] if gap["dimension"] == "commercial_use")
    assert "精确命中" in commercial_gap["reason"]


def test_missing_ai_endpoint_degrades_without_network_or_exception() -> None:
    source_bundle = _load("source_bundles/qwen_research_source_bundle.json")
    config = AIConfig(
        enabled=True,
        provider="openai-compatible",
        model="open-weight-model",
        base_url="",
    )

    analysis = AIService(config).analyze_model_source(source_bundle)

    assert analysis["status"] == "unavailable"
    assert "AI_BASE_URL" in analysis["reason"]
    assert analysis["fact_policy"]["ai_may_change_decision"] is False

def test_fixture_hashes_match_document_content() -> None:
    from ai_layer.schemas import sha256_text

    source_bundle = _load("source_bundles/qwen_research_source_bundle.json")
    for document in source_bundle["documents"]:
        assert document["sha256"] == sha256_text(document["content"])

    semantic = _load("semantic_diffs/license_semantic_tightening.json")
    for key in ("before_source", "after_source"):
        document = semantic[key]["documents"][0]
        assert document["sha256"] == sha256_text(document["content"])
