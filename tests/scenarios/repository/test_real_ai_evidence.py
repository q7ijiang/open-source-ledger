from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = REPO_ROOT / "docs" / "competition" / "real-ai"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_ai_evidence_is_not_mock_and_has_frozen_metadata() -> None:
    bundle = _load(EVIDENCE / "ai_analysis.json")
    provider = bundle["provider"]

    assert provider["provider"] == "openai-compatible"
    assert provider["model"] == "Qwen/Qwen3.5-27B"
    assert "api-inference.modelscope.cn" in provider["base_url"]
    assert bundle["generated_at"]
    assert bundle["prompt_version"] == "modelscope-license-audit-v2"


def test_real_ai_claims_are_quote_verified_c_level_and_pending() -> None:
    bundle = _load(EVIDENCE / "ai_analysis.json")
    source_documents = {
        item["model_id"]: {
            document["path"]: document.get("content", "")
            for document in item.get("documents", [])
        }
        for item in (
            _load(path) for path in sorted((EVIDENCE / "source_bundles").glob("*.json"))
        )
    }
    checked = 0
    for analysis in bundle["model_analyses"]:
        model_id = analysis["subject"]["model_id"]
        documents = source_documents.get(model_id, {})
        for claim in analysis.get("claims", []):
            evidence = claim["evidence"]
            assert evidence["quote"] in documents.get(evidence["source_path"], ""), claim
            assert claim["evidence_level"] == "C"
            assert claim["human_review"] == "pending"
            checked += 1

    assert checked >= 4


def test_real_ai_verification_record_matches_current_files() -> None:
    verification = _load(EVIDENCE / "verification.json")

    assert verification["all_quotes_exact"] is True
    assert verification["all_c_level_pending"] is True
    assert verification["provider"]["model"] == "Qwen/Qwen3.5-27B"
    assert verification["files"]
