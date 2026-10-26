from __future__ import annotations

import json
from pathlib import Path

from ai_layer.config import AIConfig
from ai_layer.schemas import normalize_model_analysis

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "ai"
    / "multi_evidence"
    / "case.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _normalize(response_key: str) -> dict:
    fixture = _fixture()
    config = AIConfig(enabled=True, provider="mock", model="mock")
    return normalize_model_analysis(
        fixture[response_key],
        fixture["source_bundle"],
        config.public_dict(),
    )


def test_same_dimension_keeps_multiple_exact_evidences() -> None:
    analysis = _normalize("response")

    assert analysis["status"] == "ok"
    assert len(analysis["claims"]) == 1
    claim = analysis["claims"][0]
    assert claim["dimension"] == "commercial_use"
    assert claim["evidence_count"] == 2
    assert {item["source_path"] for item in claim["evidences"]} == {
        "LICENSE",
        "README.md",
    }
    assert claim["cross_document_support"] is True
    assert claim["conditions"][0]["quote"]
    assert claim["confidence"] <= 0.89


def test_cross_document_state_conflict_requires_human_review() -> None:
    analysis = _normalize("conflicting_response")

    assert analysis["status"] == "conflict"
    assert analysis["conflicts"]
    assert analysis["claims"][0]["conflict"] is True
    assert analysis["claims"][0]["human_review"] == "pending"
