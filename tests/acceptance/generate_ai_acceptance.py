# -*- coding: utf-8 -*-
"""Generate an offline acceptance package for the AI evidence layer."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TESTS_DIR.parent
FIXTURES = TESTS_DIR / "fixtures" / "ai"
PROJECT_FIXTURE = TESTS_DIR / "fixtures" / "acceptance" / "project"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import export_bom
import evidence_enricher
import main
import modelscope_lineage
import render_diff
import render_graph
from ai_layer.config import AIConfig
from ai_layer.provider import MockAIProvider
from ai_layer.schemas import (
    collect_project_evidence,
    normalize_model_analysis,
    normalize_project_context,
)
from ai_layer.service import AIService, analysis_bundle


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _analysis(source: dict, response: dict, config: AIConfig) -> dict:
    provider = MockAIProvider(response)
    raw = json.loads(provider.complete("", "", config))
    return normalize_model_analysis(raw, source, config.public_dict())


def _asset(model_id: str, analysis: dict) -> dict:
    ns, name = model_id.split("/", 1)
    return {
        "entity_key": f"model:modelscope/{ns}/{name}",
        "canonical_id": f"model:modelscope/{ns}/{name}@master",
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


def _write_snapshot(
    output_dir: Path,
    assets: list[dict],
    edges: list[dict],
) -> tuple[dict, Path, Path, Path]:
    assets_path = output_dir / "assets.json"
    edges_path = output_dir / "edges.json"
    graph_path = output_dir / "graph.json"
    _write_json(assets_path, assets)
    _write_json(edges_path, edges)
    modelscope_lineage.write_graph(assets, edges, graph_path)
    try:
        main._enrich_risk_fields(assets_path, edges_path, graph_path)
    except Exception:
        pass
    main._attach_ai_to_graph(graph_path, _load(assets_path))
    graph = _load(graph_path)
    return graph, assets_path, edges_path, graph_path


def _render_graph(graph_path: Path, html_path: Path, title: str) -> None:
    previous = sys.argv
    try:
        sys.argv = [
            "render_graph.py",
            "--input",
            str(graph_path),
            "--output",
            str(html_path),
            "--title",
            title,
        ]
        render_graph.main()
    finally:
        sys.argv = previous


def _render_diff(before_bom: Path, after_bom: Path, html_path: Path) -> None:
    previous = sys.argv
    try:
        sys.argv = [
            "render_diff.py",
            "--before",
            str(before_bom),
            "--after",
            str(after_bom),
            "--output",
            str(html_path),
        ]
        render_diff.main()
    finally:
        sys.argv = previous


def generate_model(output_root: Path, config: AIConfig) -> None:
    output_dir = output_root / "model"
    source_bundle = _load(FIXTURES / "source_bundles" / "qwen_research_source_bundle.json")
    analysis = _analysis(
        source_bundle,
        _load(FIXTURES / "model_profiles" / "qwen_research_ai_response.json"),
        config,
    )
    asset = _asset(source_bundle["model_id"], analysis)
    _, assets_path, edges_path, graph_path = _write_snapshot(output_dir, [asset], [])
    _write_json(output_dir / "source_bundles" / "qwen_research_source_bundle.json", source_bundle)
    bundle = analysis_bundle(config, model_analyses=[analysis])
    _write_json(output_dir / "ai_analysis.json", bundle)
    export_bom.export_bom(assets_path, edges_path, output_dir / "bom.json")
    report = main._render_modelscope_report(source_bundle["model_id"], output_dir, 0.0, bundle)
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    _render_graph(graph_path, output_dir / "lineage.html", "AI 模型模式验收")


def generate_project(output_root: Path, config: AIConfig) -> None:
    output_dir = output_root / "project"
    source_bundle = _load(FIXTURES / "source_bundles" / "qwen_research_source_bundle.json")
    model_analysis = _analysis(
        source_bundle,
        _load(FIXTURES / "model_profiles" / "qwen_research_ai_response.json"),
        config,
    )
    raw_project = json.loads(
        MockAIProvider(
            _load(FIXTURES / "project_contexts" / "remote_api_ai_response.json")
        ).complete("", "", config)
    )

    project_context = normalize_project_context(
        raw_project,
        PROJECT_FIXTURE,
        collect_project_evidence(PROJECT_FIXTURE),
        config.public_dict(),
    )
    asset = _asset(source_bundle["model_id"], model_analysis)
    asset["ai_project_context"] = project_context
    graph, assets_path, edges_path, graph_path = _write_snapshot(output_dir, [asset], [])
    _write_json(output_dir / "source_bundles" / "qwen_research_source_bundle.json", source_bundle)
    bundle = analysis_bundle(
        config,
        model_analyses=[model_analysis],
        project_context=project_context,
    )
    _write_json(output_dir / "ai_analysis.json", bundle)
    export_bom.export_bom(assets_path, edges_path, output_dir / "bom.json")
    models = [
        {
            "model": source_bundle["model_id"],
            "ns": source_bundle["model_id"].split("/", 1)[0],
            "name": source_bundle["model_id"].split("/", 1)[1],
            "sources": ["app.py"],
        }
    ]
    report = main._render_modelscope_project_report(
        PROJECT_FIXTURE,
        models,
        graph,
        0.0,
        False,
        bundle,
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    _render_graph(graph_path, output_dir / "lineage.html", "AI 项目模式验收")


def generate_diff(output_root: Path, config: AIConfig) -> None:
    output_dir = output_root / "diff"
    fixture = _load(FIXTURES / "semantic_diffs" / "license_semantic_tightening.json")
    before_analysis = _analysis(fixture["before_source"], fixture["before_response"], config)
    after_analysis = _analysis(fixture["after_source"], fixture["after_response"], config)
    before_asset = _asset(fixture["model_id"], before_analysis)
    after_asset = _asset(fixture["model_id"], after_analysis)

    before_assets = output_dir / "before_assets.json"
    before_edges = output_dir / "before_edges.json"
    after_assets = output_dir / "after_assets.json"
    after_edges = output_dir / "after_edges.json"
    before_bom = output_dir / "t0_bom.json"
    after_bom = output_dir / "t1_bom.json"
    _write_json(before_assets, [before_asset])
    _write_json(before_edges, [])
    _write_json(after_assets, [after_asset])
    _write_json(after_edges, [])
    export_bom.export_bom(before_assets, before_edges, before_bom)
    export_bom.export_bom(after_assets, after_edges, after_bom)

    service = AIService(config, MockAIProvider([]))
    main.run_diff(before_bom, after_bom, output_dir / "report.md", ai_service=service)
    _render_diff(before_bom, after_bom, output_dir / "diff.html")


def _write_acceptance_readme(output_root: Path) -> None:
    content = """# AI 能力离线验收包

本目录由 `tests/acceptance/generate_ai_acceptance.py` 从固定夹具重新生成，全程不访问网络。
测试模型为 `example/qwen-research-demo`，事实许可证名为 `qwen-research`，不代表真实模型的法律结论。

## 验收入口

- [模型模式](model/lineage.html)：打开后点击模型节点，查看商业使用禁止、0.86 置信度、C 级证据、原文引文和待人工确认状态。
- [项目模式](project/lineage.html)：点击模型节点，查看项目通过远程 API 使用模型，以及 `app.py` 中的逐字依据。
- [Diff 模式](diff/diff.html)：查看相同许可证名下“允许商用 → 禁止商用”的语义收紧，以及 t0/t1 原文。

## 预期结果

| 模式 | 预期 |
|---|---|
| Model | `commercial_use=prohibited`；`confidence=0.86`；`evidence_level=C`；`human_review=pending` |
| Model gaps | 训练其他模型、微调版本再分发、商用授权申请方式三项证据不足 |
| Project | `remote_api`；引文来自项目 `app.py`；C 级、待人工确认 |
| Diff | `allowed → prohibited`；复核优先级 `high`；规则 Delta 不被 AI 改写 |

原始报告分别位于 `model/report.md`、`project/report.md` 和 `diff/report.md`；结构化结果位于各目录的 `ai_analysis.json` 或 `report.ai.json`。机器可读清单见 `acceptance_manifest.json`。
"""
    (output_root / "README.md").write_text(content, encoding="utf-8")


def _offline_enrichment(assets: list[dict], _timeout: float) -> tuple[list[dict], dict]:
    """验收包只验证固定证据，不触发 evidence_enricher 的在线补全。"""
    return assets, {"enabled": False, "reason": "offline acceptance fixture"}


def _prepare_output_root(output_root: Path) -> None:
    """只清理本生成器拥有的条目，保留用户在同级放置的其他文件。"""
    output_root.mkdir(parents=True, exist_ok=True)
    for name in ("model", "project", "diff"):
        target = output_root / name
        if target.is_dir():
            shutil.rmtree(target)
    for name in ("README.md", "manifest.json", "acceptance_manifest.json"):
        target = output_root / name
        if target.is_file():
            target.unlink()


def build_manifest(output_root: Path) -> dict:
    files = [
        path.relative_to(output_root).as_posix()
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path.name != "acceptance_manifest.json"
    ]
    manifest = {
        "schema_version": "ai-acceptance/v1",
        "network_used": False,
        "source": "tests/fixtures/ai",
        "name": "qwen-research",
        "ai_evidence_level": "C",
        "human_review_required": True,
        "expected": {
            "model": {"commercial_use": "prohibited", "confidence": 0.86, "evidence_level": "C", "human_review": "pending"},
            "project": {"use_type": "remote_api", "evidence_level": "C", "human_review": "pending"},
            "diff": {"before": "allowed", "after": "prohibited", "review_priority": "high"},
        },
        "files": files,
    }
    _write_json(output_root / "acceptance_manifest.json", manifest)
    return manifest


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 AI 能力离线验收包")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "outputs" / "ai_acceptance",
        help="验收输出目录（默认为仓库 outputs/ai_acceptance）",
    )
    args = parser.parse_args(argv)
    output_root = args.output.resolve()
    _prepare_output_root(output_root)
    config = AIConfig(enabled=True, provider="mock", model="mock-qwen", base_url="offline://mock")

    generate_model(output_root, config)
    generate_project(output_root, config)
    original_enrich_assets = evidence_enricher.enrich_assets
    try:
        evidence_enricher.enrich_assets = _offline_enrichment
        generate_diff(output_root, config)
    finally:
        evidence_enricher.enrich_assets = original_enrich_assets
    _write_acceptance_readme(output_root)
    manifest = build_manifest(output_root)
    print(f"AI 离线验收包已生成：{output_root}")
    print(f"模型/项目/Diff 产物共 {len(manifest['files'])} 个文件；未访问网络。")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main_cli())
