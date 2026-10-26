from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import bom_adapter
import export_bom
import main
import render_graph
import report_enhanced
from ai_layer.config import AIConfig
from ai_layer.provider import MockAIProvider
from ai_layer.schemas import normalize_model_analysis
from ai_layer.service import AIService
from ai_layer.service import analysis_bundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ai"


def _load(relative: str) -> dict:
    return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _analysis(source: dict, response: dict) -> dict:
    config = AIConfig(enabled=True, provider="mock", model="mock-qwen")
    provider = MockAIProvider(response)
    raw = json.loads(provider.complete("", "", config))
    return normalize_model_analysis(raw, source, config.public_dict())


def _asset(model_id: str, analysis: dict) -> dict:
    ns, name = model_id.split("/", 1)
    canonical_id = f"model:modelscope/{ns}/{name}@master"
    return {
        "entity_key": f"model:modelscope/{ns}/{name}",
        "canonical_id": canonical_id,
        "asset_type": "model",
        "name": model_id,
        "version": "master",
        "purls": [f"pkg:modelscope/{ns}/{name}@master"],
        "license": analysis["subject"]["license_fact"],
        "evidence_chain": [
            {
                "evidence_level": "A",
                "source_api": "modelscope",
                "source_url": f"https://www.modelscope.cn/api/v1/models/{ns}/{name}",
                "source_field": "Data.LicenseName",
                "retrieved_at": "2026-10-26T00:00:00Z",
                "status": "ok",
                "raw_value": analysis["subject"]["license_fact"],
            }
        ],
        "snapshot_id": f"modelscope-{ns}__{name}",
        "source_file": f"https://www.modelscope.cn/api/v1/models/{ns}/{name}",
        "ai_analysis": analysis,
    }


def test_ai_analysis_round_trips_through_bom(tmp_path: Path) -> None:
    source = _load("source_bundles/qwen_research_source_bundle.json")
    analysis = _analysis(source, _load("model_profiles/qwen_research_ai_response.json"))
    project_context = {
        "analysis_type": "project_context",
        "status": "ok",
        "uses": [{"use_type": "remote_api", "evidence": {"source_path": "app.py", "quote": "demo"}}],
    }
    asset = _asset("example/qwen-research-demo", analysis)
    asset["ai_project_context"] = project_context
    assets_path = tmp_path / "assets.json"
    edges_path = tmp_path / "edges.json"
    bom_path = tmp_path / "bom.json"
    _write_json(assets_path, [asset])
    _write_json(edges_path, [])

    export_bom.export_bom(assets_path, edges_path, bom_path)
    bom = json.loads(bom_path.read_text(encoding="utf-8"))
    properties = {item["name"]: item["value"] for item in bom["components"][0]["properties"]}
    assert properties["open-source-ledger:ai_evidence_level"] == "C"
    assert "open-source-ledger:ai_analysis_json" in properties

    converted = bom_adapter.convert_bom(bom, source_file=str(bom_path), snapshot_id="t0")
    assert converted[0]["ai_analysis"]["claims"][0]["evidence"]["quote"] == (
        "该模型仅限研究用途，不得用于商业目的。"
    )
    assert converted[0]["ai_project_context"] == project_context


def test_diff_uses_frozen_bom_ai_profiles_and_writes_sidecar(tmp_path: Path) -> None:
    semantic = _load("semantic_diffs/license_semantic_tightening.json")
    before_analysis = _analysis(semantic["before_source"], semantic["before_response"])
    after_analysis = _analysis(semantic["after_source"], semantic["after_response"])
    before_asset = _asset(semantic["model_id"], before_analysis)
    after_asset = _asset(semantic["model_id"], after_analysis)

    before_assets = tmp_path / "before_assets.json"
    before_edges = tmp_path / "before_edges.json"
    after_assets = tmp_path / "after_assets.json"
    after_edges = tmp_path / "after_edges.json"
    before_bom = tmp_path / "before_bom.json"
    after_bom = tmp_path / "after_bom.json"
    _write_json(before_assets, [before_asset])
    _write_json(before_edges, [])
    _write_json(after_assets, [after_asset])
    _write_json(after_edges, [])
    export_bom.export_bom(before_assets, before_edges, before_bom)
    export_bom.export_bom(after_assets, after_edges, after_bom)

    config = AIConfig(enabled=True, provider="mock", model="mock-qwen")
    service = AIService(config, MockAIProvider([]))
    report_path = tmp_path / "report.md"
    main.run_diff(before_bom, after_bom, report_path, ai_service=service)

    report = report_path.read_text(encoding="utf-8")
    assert "AI 语义差异（C 级，待人工确认）" in report
    assert "允许 → 禁止" in report
    assert "Hugging Face" not in report
    assert "PyPI / npm" not in report
    sidecar = tmp_path / "report.ai.json"
    assert sidecar.exists()
    sidecar_data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_data["semantic_diff"]["changes"][0]["change_type"] == "tightened"


def test_report_without_ai_keeps_modelscope_evidence_scope() -> None:
    report = report_enhanced.render_report([], [], None, None)
    assert "ModelScope 官方 API" in report
    assert "Hugging Face" not in report
    assert "lockfile" not in report


def test_markdown_ai_section_exposes_confidence_formula() -> None:
    source = _load("source_bundles/qwen_research_source_bundle.json")
    analysis = _analysis(source, _load("model_profiles/qwen_research_ai_response.json"))
    config = AIConfig(enabled=True, provider="mock", model="mock-qwen")
    bundle = analysis_bundle(config, model_analyses=[analysis])
    report = "\n".join(main._render_ai_sections(bundle))

    assert "置信度构成" in report
    assert "LICENSE 文件 +0.15" in report
    assert "基础 +0.48" in report
    assert "置信度因子" in report
    assert "不是模型自报概率" in report
    assert "最终分数限制在 0.05 至 0.89" in report


def test_render_graph_embeds_ai_details_and_valid_javascript(
    tmp_path: Path, monkeypatch
) -> None:
    source = _load("source_bundles/qwen_research_source_bundle.json")
    analysis = _analysis(source, _load("model_profiles/qwen_research_ai_response.json"))
    asset = _asset("example/qwen-research-demo", analysis)
    asset["id"] = asset["canonical_id"]
    asset["decision"] = "UNDETERMINED"
    graph_path = tmp_path / "graph.json"
    html_path = tmp_path / "lineage.html"
    _write_json(
        graph_path,
        {
            "nodes": [asset],
            "edges": [],
            "overall_decision": "UNDETERMINED",
            "overall_decision_zh": "待确认",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["render_graph.py", "--input", str(graph_path), "--output", str(html_path)],
    )
    render_graph.main()

    html = html_path.read_text(encoding="utf-8")
    assert "AI 语义证据（C 级，不改变规则判定）" in html
    assert "置信度" in html
    assert "置信度构成" in html
    assert "function confidenceFactorText" in html
    assert "LICENSE 文件" in html
    assert "证据缺口" in html
    assert "该模型仅限研究用途，不得用于商业目的。" in html

    node = shutil.which("node")
    if node:
        scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, re.DOTALL)
        inline_script = "\n".join(script for script in scripts if script.strip())
        script_path = tmp_path / "render_graph.inline.js"
        script_path.write_text(inline_script, encoding="utf-8")
        checked = subprocess.run(
            [node, "--check", str(script_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert checked.returncode == 0, checked.stderr


def test_model_report_falls_back_to_first_concrete_asset(tmp_path: Path) -> None:
    source = _load("source_bundles/qwen_research_source_bundle.json")
    analysis = _analysis(source, _load("model_profiles/qwen_research_ai_response.json"))
    asset = _asset("example/qwen-research-demo", analysis)
    asset["id"] = asset["canonical_id"]
    assets_path = tmp_path / "assets.json"
    graph_path = tmp_path / "graph.json"
    _write_json(assets_path, [asset])
    _write_json(
        graph_path,
        {"nodes": [asset], "edges": [], "overall_decision": "UNDETERMINED"},
    )

    report = main._render_modelscope_report(
        "example/qwen-research-demo",
        tmp_path,
        0.0,
        graph_path=graph_path,
    )

    assert "example/qwen-research-demo" in report
    assert "（未识别）" not in report
