from __future__ import annotations

import json
from pathlib import Path

from ai_layer.config import AIConfig
from ai_layer.provider import MockAIProvider
from ai_layer.service import AIService
from ai_layer.service import attach_project_context
from ai_layer.schemas import collect_project_evidence

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
PROJECT = FIXTURES / "acceptance" / "project"


def _response() -> dict:
    path = FIXTURES / "ai" / "project_contexts" / "remote_api_ai_response.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_project_context_uses_verbatim_project_evidence() -> None:
    provider = MockAIProvider(_response())
    config = AIConfig(enabled=True, provider="mock", model="mock-qwen")
    service = AIService(config, provider)

    result = service.analyze_project_context(PROJECT, [])

    assert result["status"] == "ok"
    assert result["uses"][0]["use_type"] == "remote_api"
    assert result["uses"][0]["confidence"] == 0.83
    assert result["uses"][0]["evidence"]["source_path"] == "app.py"
    assert "client.chat.completions.create" in result["uses"][0]["evidence"]["quote"]
    assert result["fact_policy"]["human_review_required"] is True


def test_project_evidence_redacts_secret_values_before_ai_call() -> None:
    evidence = collect_project_evidence(PROJECT)
    app_source = next(item["content"] for item in evidence if item["path"] == "app.py")
    assert "TEST_ONLY" not in app_source
    assert "api_key=<redacted>" in app_source


def test_project_relative_paths_do_not_leak_absolute_root() -> None:
    evidence = collect_project_evidence(PROJECT)
    assert evidence
    assert all(not Path(item["path"]).is_absolute() for item in evidence)
    assert all(str(REPO_ROOT) not in item["path"] for item in evidence)


def test_project_context_is_attached_to_every_concrete_model() -> None:
    context = {"analysis_type": "project_context", "status": "ok", "uses": []}
    assets = [
        {"canonical_id": "model:a", "name": "a", "asset_type": "model"},
        {"canonical_id": "model:b", "name": "b", "asset_type": "model"},
        {"canonical_id": "model:c", "name": "c", "aggregate": True},
    ]

    attach_project_context(assets, context)

    assert assets[0]["ai_project_context"] == context
    assert assets[1]["ai_project_context"] == context
    assert "ai_project_context" not in assets[2]
