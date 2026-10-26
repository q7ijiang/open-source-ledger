from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import bom_adapter


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "projects"
    / "real_modelscope"
)
FULL_SNAPSHOT = FIXTURE_ROOT / "snapshots" / "full"
SCENARIOS = FULL_SNAPSHOT / "scenarios"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _component(bom: dict, name: str) -> dict:
    return next(
        component
        for component in bom["components"]
        if component.get("name") == name
    )


def _html_data(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"const DATA = (\{.*?\});\s*\n", text, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


def test_full_real_project_snapshot_has_expected_lineage_coverage() -> None:
    manifest = _load_json(FULL_SNAPSHOT / "scan_manifest.json")
    validation = manifest["validation"]

    assert manifest["live_api"] is True
    assert manifest["simulation"] is False
    assert manifest["ai_acceptance_simulation"] is True
    assert manifest["stage"] == "full"
    assert len(manifest["direct_models"]) == 7
    assert manifest["model_count"] == 18
    assert manifest["edge_count"] == 22
    assert validation["status"] == "pass"
    assert validation["direct_model_precision"] == 1.0
    assert validation["direct_model_recall"] == 1.0
    assert validation["observed_max_upstream_depth"] == 3
    assert validation["downstream_model_nodes"] == []
    assert all(
        item["found"] for item in validation["required_lineage_paths"]
    )


def test_full_snapshot_contains_rich_real_upstream_branches() -> None:
    manifest = _load_json(FULL_SNAPSHOT / "scan_manifest.json")
    models = {item["model_id"]: item for item in manifest["models"]}

    assert {
        "OpenGVLab/InternVL3-8B-Instruct",
        "OpenGVLab/InternVL3-8B-Pretrained",
        "OpenGVLab/InternViT-300M-448px-V2_5",
        "OpenGVLab/InternViT-300M-448px",
        "Qwen/Qwen2.5-Math-7B-Instruct",
        "Qwen/Qwen2.5-Math-7B",
        "Qwen/Qwen2.5-7B",
    }.issubset(models)
    assert models["OpenGVLab/InternVL3-8B-Instruct"]["max_depth_seen"] == 3
    assert models["Qwen/Qwen2.5-Math-7B-Instruct"]["max_depth_seen"] == 2
    assert all(
        item["lineage_role"] != "downstream" for item in models.values()
    )


def test_what_if_scenarios_are_explicitly_marked_as_simulated() -> None:
    manifest = _load_json(SCENARIOS / "manifest.json")

    assert manifest["simulation"] is True
    assert {item["name"] for item in manifest["scenarios"]} == {
        "direct_license_change",
        "upstream_license_change",
    }

    for item in manifest["scenarios"]:
        scenario_dir = SCENARIOS / item["path"]
        scenario = _load_json(scenario_dir / "scenario.json")
        assert scenario["simulation"] is True
        assert scenario["ai_acceptance_simulation"] is True
        assert scenario["source_snapshot"].endswith("snapshots/full/t0_bom.json")
        assert _sha256(scenario_dir / "t0_bom.json") == _sha256(
            FULL_SNAPSHOT / "t0_bom.json"
        )
        assert (scenario_dir / "README.md").is_file()
        assert (scenario_dir / "diff_report.md").is_file()
        assert (scenario_dir / "diff_graph.html").is_file()


def test_upstream_scenario_reaches_all_project_model_families() -> None:
    scenario = _load_json(SCENARIOS / "upstream_license_change" / "scenario.json")
    affected = set(scenario["expected_affected_models"])

    assert scenario["mutated_model"] == "Qwen/Qwen2.5-7B"
    assert {
        "Qwen/Qwen2.5-7B-Instruct-AWQ",
        "Qwen/Qwen2.5-Coder-7B-Instruct-AWQ",
        "Qwen/Qwen2.5-Math-7B-Instruct",
        "OpenGVLab/InternVL3-8B-Instruct",
    }.issubset(affected)


def test_simulated_bom_round_trip_preserves_provenance_and_original_evidence(
) -> None:
    scenario_dir = SCENARIOS / "upstream_license_change"
    bom = _load_json(scenario_dir / "t1_bom.json")
    component = _component(bom, "Qwen/Qwen2.5-7B")
    properties = {
        item["name"]: item["value"] for item in component.get("properties", [])
    }
    license_entry = component["licenses"][0]

    assert license_entry["license"] == {"name": "qwen-research"}
    assert license_entry["evidence_level"] == "C"
    assert properties["open-source-ledger:simulation"].lower() == "true"
    assert (
        properties["open-source-ledger:simulation_original_license"]
        == "Apache-2.0"
    )
    assert (
        properties["open-source-ledger:simulation_target_license"]
        == "qwen-research"
    )
    assert any(
        item["evidence_level"] == "A"
        and item["source_field"] in {"Data.License", "Data.LicenseName"}
        and str(item.get("raw_value", "")).lower() == "apache-2.0"
        for item in license_entry["evidence_chain"]
    )

    converted = bom_adapter.convert_bom(
        bom,
        source_file=str(scenario_dir / "t1_bom.json"),
        snapshot_id="t1",
    )
    target = next(
        asset for asset in converted if asset.get("name") == "Qwen/Qwen2.5-7B"
    )
    assert target["simulation"] is True
    assert target["simulation_original_license"] == "Apache-2.0"
    assert target["simulation_target_license"] == "qwen-research"
    assert any(
        item["evidence_level"] == "A"
        for item in target.get("evidence_chain", [])
    )


def test_acceptance_graphs_expose_frozen_ai_evidence_and_stable_diff_layout() -> None:
    project_html = (FULL_SNAPSHOT / "project_graph.html").read_text(encoding="utf-8")
    assert project_html.count('id="risk-grid"') == 1
    assert project_html.count('id="compliance"') == 1
    project = _html_data(FULL_SNAPSHOT / "project_graph.html")
    profiles = [node["ai_analysis"] for node in project["nodes"] if node.get("ai_analysis")]
    assert len(profiles) == 2
    assert all(profile["simulation"] is True for profile in profiles)
    assert any(
        claim["state"] == "allowed" and claim["confidence"] == 0.78
        for profile in profiles for claim in profile.get("claims", [])
    )
    project_contexts = [
        node["ai_project_context"]
        for node in project["nodes"]
        if node.get("ai_project_context")
    ]
    assert len(project_contexts) == 18
    assert len({item["subject"]["project_path"] for item in project_contexts}) == 1
    assert project_contexts[0]["simulation"] is True
    assert project_contexts[0]["uses"][0]["use_type"] == "remote_api"
    assert 'id="download-report"' in project_html
    report = (FULL_SNAPSHOT / "project_report.md").read_text(encoding="utf-8")
    assert "项目使用上下文" in report
    assert "置信度构成" in report
    assert "验收模拟" in report

    scenario_dir = SCENARIOS / "upstream_license_change"
    diff = _html_data(scenario_dir / "diff_graph.html")
    assert diff["ai_diff"]["simulation"] is True
    assert len(diff["ai_diff"]["changes"]) == 1
    change = diff["ai_diff"]["changes"][0]
    assert (change["before_state"], change["after_state"]) == (
        "allowed",
        "prohibited",
    )
    t1_by_id = {node["id"]: node for node in diff["nodes_t1"]}
    for node in diff["nodes_t0"]:
        counterpart = t1_by_id[node["id"]]
        assert (node["x"], node["y"]) == (counterpart["x"], counterpart["y"])
    assert all(
        edge.get("edge_type") != "expanded_from"
        for edge in [*diff["edges_t0"], *diff["edges_t1"]]
    )
