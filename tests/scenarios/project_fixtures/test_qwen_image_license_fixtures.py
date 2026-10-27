from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import bom_adapter
from ai_layer.schemas import sha256_text
from modelscope_lineage import _model_id


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "projects"
    / "qwen_image_license_tightening"
)
TARGET = "Qwen/Qwen-Image-2.1"
TURBO = "Qwen/Qwen-Image-2.1-Turbo"
FP8 = "unsloth/Qwen-Image-2.1-Turbo-FP8"
DOCUMENT_MODEL = "OpenGVLab/InternVL3-8B-Instruct"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _document(bundle: dict, path: str) -> dict:
    return next(item for item in bundle["documents"] if item["path"] == path)


def _asset(assets: list[dict], name: str) -> dict:
    return next(
        item
        for item in assets
        if item.get("name") == name and not item.get("aggregate")
    )


def _component(bom: dict, name: str) -> dict:
    return next(item for item in bom["components"] if item.get("name") == name)


def _properties(component: dict) -> dict[str, str]:
    return {item["name"]: item["value"] for item in component.get("properties", [])}


def _html_data(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"const DATA = (\{.*?\});\s*\n", text, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


def test_fixture_tree_and_project_refs_are_portable() -> None:
    assert (FIXTURE_ROOT / "README.md").is_file()
    assert (FIXTURE_ROOT / "direct" / "README.md").is_file()
    assert (FIXTURE_ROOT / "upstream" / "README.md").is_file()

    direct_config = _json(FIXTURE_ROOT / "direct" / "project" / "config.json")
    upstream_config = _json(
        FIXTURE_ROOT / "upstream" / "project" / "config" / "model_catalog.json"
    )
    assert direct_config["model_id"] == TARGET
    assert upstream_config["image_generation"]["model_id"] == FP8
    assert (
        upstream_config["document_understanding"]["model_id"] == DOCUMENT_MODEL
    )


def test_historical_evidence_does_not_claim_an_apache_license_file() -> None:
    bundle = _json(
        FIXTURE_ROOT
        / "evidence"
        / "qwen-image-2.1.historical-apache.json"
    )
    readme = _document(bundle, "README.md")

    assert bundle["historical_reconstruction"] is True
    assert [item["path"] for item in bundle["documents"]] == ["README.md"]
    assert "license: Apache License 2.0" in readme["content"]
    assert readme["sha256"] == hashlib.sha256(
        readme["content"].encode("utf-8")
    ).hexdigest()
    assert bundle["facts"]["license"]["source_field"] == (
        "README.md:front_matter.license"
    )
    assert "not a retained copy" in bundle["historical_boundary"]

    current = _json(
        FIXTURE_ROOT / "evidence" / "qwen-image-2.1.current.json"
    )
    license_doc = _document(current, "LICENSE")
    assert current["facts"]["license"]["value"] == "qwen-research"
    assert license_doc["sha256"] == (
        "8dc973f024ff95966bea25866efa443fd16776dcb1001e681e3d467ea572b28d"
    )
    assert "Qwen RESEARCH LICENSE AGREEMENT" in license_doc["content"]


def test_scenarios_keep_real_history_and_counterfactual_replay_separate() -> None:
    direct = _json(FIXTURE_ROOT / "direct" / "scenario.json")
    upstream = _json(FIXTURE_ROOT / "upstream" / "scenario.json")

    assert direct["historical_reconstruction"] is True
    assert direct["simulation"] is False
    assert upstream["historical_reconstruction"] is True
    assert upstream["simulation"] is True
    assert "反事实重放" in upstream["simulation_reason"]

    direct_t0 = _asset(
        _json(FIXTURE_ROOT / "direct" / "t0_assets.json"),
        TARGET,
    )
    direct_t1 = _asset(
        _json(FIXTURE_ROOT / "direct" / "t1_assets.json"),
        TARGET,
    )
    assert direct_t0["license"] == "Apache License 2.0"
    assert direct_t0["historical_reconstruction"] is True
    assert direct_t1["license"] == "qwen-research"

    upstream_t0 = _asset(
        _json(FIXTURE_ROOT / "upstream" / "t0_assets.json"),
        TARGET,
    )
    upstream_t1 = _asset(
        _json(FIXTURE_ROOT / "upstream" / "t1_assets.json"),
        TARGET,
    )
    assert upstream_t0["license"] == "Apache License 2.0"
    assert upstream_t0["simulation"] is True
    assert upstream_t0["historical_commit"].startswith("72900d")
    assert upstream_t1["license"] == "qwen-research"


def test_upstream_bom_preserves_real_lineage_and_replay_metadata() -> None:
    bom = _json(FIXTURE_ROOT / "upstream" / "t0_bom.json")
    target = _component(bom, TARGET)
    properties = _properties(target)
    fp8 = _component(bom, FP8)
    turbo = _component(bom, TURBO)

    assert properties["open-source-ledger:simulation"].lower() == "true"
    assert properties["open-source-ledger:historical_reconstruction"].lower() == "true"
    assert properties["open-source-ledger:historical_commit"].startswith("72900d")
    assert target["licenses"][0]["license"] == {"id": "Apache-2.0"}

    fp8_ancestors = {
        item["ref"] for item in fp8.get("pedigree", {}).get("ancestors", [])
    }
    turbo_ancestors = {
        item["ref"] for item in turbo.get("pedigree", {}).get("ancestors", [])
    }
    assert "model:modelscope/Qwen/Qwen-Image-2.1-Turbo@master" in fp8_ancestors
    assert "model:modelscope/Qwen/Qwen-Image-2.1@master" in fp8_ancestors
    assert "model:modelscope/Qwen/Qwen-Image-2.1@master" in turbo_ancestors

    converted = bom_adapter.convert_bom(
        bom,
        source_file=str(FIXTURE_ROOT / "upstream" / "t0_bom.json"),
        snapshot_id="t0",
    )
    converted_target = _asset(converted, TARGET)
    assert converted_target["historical_reconstruction"] is True
    assert converted_target["simulation"] is True


def test_ai_claims_are_quote_verified_and_confidence_is_decomposed() -> None:
    current_bundle = _json(
        FIXTURE_ROOT / "evidence" / "qwen-image-2.1.current.json"
    )
    license_doc = _document(current_bundle, "LICENSE")
    bundle = _json(FIXTURE_ROOT / "upstream" / "ai_analysis.json")
    analyses = [
        item
        for item in bundle["model_analyses"]
        if item["subject"]["model_id"] == TARGET
    ]
    current_analysis = max(analyses, key=lambda item: len(item.get("claims", [])))
    claims = {
        item["dimension"]: item
        for item in current_analysis.get("claims", [])
    }
    commercial = claims["commercial_use"]

    assert commercial["state"] == "prohibited"
    assert commercial["evidence_level"] == "C"
    assert commercial["human_review"] == "pending"
    assert commercial["confidence"] == 0.86
    assert commercial["confidence_factors"] == {
        "base": 0.48,
        "license_file": 0.15,
        "exact_quote": 0.1,
        "restriction_wording": 0.08,
        "source_sha256": 0.03,
        "quote_context": 0.02,
    }
    quote = commercial["evidence"]["quote"]
    assert quote in license_doc["content"]
    assert commercial["evidence"]["quote_sha256"] == sha256_text(quote)
    assert commercial["evidence"]["file_sha256"] == license_doc["sha256"]
    assert "training_other_models" in claims

    context = bundle["project_context"]
    assert context["status"] == "ok"
    assert context["uses"][0]["use_type"] == "local_inference"
    assert context["uses"][0]["confidence"] == 0.83
    assert context["uses"][0]["human_review"] == "pending"

    changes = {
        item["dimension"]: item
        for item in bundle["semantic_diff"]["changes"]
    }
    assert bundle["semantic_diff"]["simulation"] is True
    assert (changes["commercial_use"]["before_state"], changes["commercial_use"]["after_state"]) == (
        "unknown",
        "prohibited",
    )
    assert changes["commercial_use"]["before_confidence"] == 0.59
    assert changes["commercial_use"]["after_confidence"] == 0.86
    assert changes["commercial_use"]["after_source_path"] == "LICENSE"
    assert changes["commercial_use"]["after_quote_sha256"] == sha256_text(quote)


def test_reports_and_html_expose_ai_evidence_and_path_certificates() -> None:
    report = (
        FIXTURE_ROOT / "upstream" / "diff_report.md"
    ).read_text(encoding="utf-8")
    assert "共生成 **2** 张路径证书" in report
    assert "Qwen/Qwen-Image-2.1-Turbo@master" in report
    assert "AI 置信度（t0 → t1）" in report
    assert "0.59 → 0.86" in report
    assert "### AI 置信度构成" in report
    assert "source_sha256 +0.03" in report

    data = _html_data(FIXTURE_ROOT / "upstream" / "diff_graph.html")
    assert data["ai_diff"]["simulation"] is True
    changes = {
        item["dimension"]: item
        for item in data["ai_diff"]["changes"]
    }
    assert changes["commercial_use"]["after_confidence"] == 0.86
    assert changes["commercial_use"]["after_source_path"] == "LICENSE"
    target_nodes = [
        item
        for item in data["nodes_t1"]
        if item.get("name") == TARGET
    ]
    assert target_nodes
    current_profiles = [
        item["ai_analysis"]
        for item in target_nodes
        if item.get("ai_analysis")
        and len(item["ai_analysis"].get("claims", [])) == 7
    ]
    assert current_profiles
    assert current_profiles[0]["claims"][0]["human_review"] == "pending"


def test_generated_text_has_no_machine_specific_paths() -> None:
    suffixes = {".json", ".md", ".html"}
    forbidden = (
        re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE),
        re.compile(r"/Users/[^/\s]+/"),
        re.compile(r"file://", re.IGNORECASE),
    )
    for path in FIXTURE_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        text = path.read_text(encoding="utf-8")
        assert not any(pattern.search(text) for pattern in forbidden), path


def test_null_lineage_reference_is_ignored() -> None:
    assert _model_id(None) is None
    assert _model_id({"Name": None}) is None
    assert _model_id("Qwen/Qwen-Image-2.1") == "Qwen/Qwen-Image-2.1"
