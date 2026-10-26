# -*- coding: utf-8 -*-
"""Generate live ModelScope Project snapshots for the repository fixtures.

The script deliberately invokes the same Project pipeline as ``main.py``. It does
not hand-write assets or BOM files, so the resulting t0 snapshot exercises the
real scanner, ModelScope adapter, lineage merge, BOM export and report renderer.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as ledger_main
import networkx as nx

import acceptance_ai
import export_bom


STAGES = {
    "smoke": ROOT / "tests" / "fixtures" / "projects" / "real_modelscope" / "smoke_project",
    "full": ROOT / "tests" / "fixtures" / "projects" / "real_modelscope" / "full_project",
}


EXPECTED = {
    "smoke": {
        "direct_models": ["Qwen/Qwen2.5-7B-Instruct-AWQ"],
        "required_paths": [
            ("Qwen/Qwen2.5-7B-Instruct-AWQ", "Qwen/Qwen2.5-7B"),
        ],
        "minimum_max_depth": 2,
    },
    "full": {
        "direct_models": [
            "Qwen/Qwen2.5-14B-Instruct-AWQ",
            "Qwen/Qwen2.5-7B-Instruct-AWQ",
            "Qwen/Qwen2.5-Coder-7B-Instruct-AWQ",
            "OpenGVLab/InternVL3-8B-Instruct",
            "Qwen/Qwen2.5-Math-7B-Instruct",
            "LLM-Research/gemma-3-4b-it",
            "BAAI/bge-m3",
        ],
        "required_paths": [
            (
                "Qwen/Qwen2.5-Coder-7B-Instruct-AWQ",
                "Qwen/Qwen2.5-7B",
            ),
            (
                "OpenGVLab/InternVL3-8B-Instruct",
                "OpenGVLab/InternViT-300M-448px",
            ),
            (
                "OpenGVLab/InternVL3-8B-Instruct",
                "Qwen/Qwen2.5-7B",
            ),
            (
                "Qwen/Qwen2.5-Math-7B-Instruct",
                "Qwen/Qwen2.5-7B",
            ),
            (
                "LLM-Research/gemma-3-4b-it",
                "google/gemma-3-4b-pt",
            ),
        ],
        "minimum_max_depth": 3,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _project_output_dir(artifacts_dir: Path, project_path: Path) -> Path:
    return ledger_main._project_output_dir(artifacts_dir, project_path)


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _make_snapshot_portable(report_dir: Path, report_paths: list[Path]) -> None:
    """Remove machine-specific repository prefixes from committed snapshot text."""
    run_context_path = report_dir / "run_context.json"
    if run_context_path.exists():
        run_context = json.loads(run_context_path.read_text(encoding="utf-8"))
        for key in ("project_path", "artifacts_dir", "cache_dir", "graph_path"):
            value = run_context.get(key)
            if isinstance(value, str) and value.strip():
                run_context[key] = _display_path(Path(value))
        _write_json(run_context_path, run_context)

    prefixes = (str(ROOT) + "\\", ROOT.as_posix() + "/")
    for path in report_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for prefix in prefixes:
            text = text.replace(prefix, "")
        path.write_text(text, encoding="utf-8")


def _validate_snapshot(
    stage: str,
    direct_models: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = EXPECTED[stage]
    expected_direct = set(expected["direct_models"])
    detected_direct = {str(item.get("model") or "") for item in direct_models}
    true_positive = len(expected_direct & detected_direct)
    precision = true_positive / len(detected_direct) if detected_direct else 0.0
    recall = true_positive / len(expected_direct) if expected_direct else 1.0

    graph = nx.DiGraph()
    model_names = {
        str(asset.get("canonical_id")): str(asset.get("name"))
        for asset in assets
        if asset.get("canonical_id") and not asset.get("aggregate")
    }
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source and target and source != target:
            graph.add_edge(source, target)

    ids_by_name: dict[str, str] = {}
    for canonical_id, name in model_names.items():
        ids_by_name.setdefault(name, canonical_id)

    path_results = []
    for source_name, target_name in expected["required_paths"]:
        source_id = ids_by_name.get(source_name)
        target_id = ids_by_name.get(target_name)
        found = bool(
            source_id
            and target_id
            and source_id in graph
            and target_id in graph
            and nx.has_path(graph, source_id, target_id)
        )
        path_results.append(
            {"from": source_name, "to": target_name, "found": found}
        )

    max_depth = max(
        (int(asset.get("max_depth_seen") or 0) for asset in assets),
        default=0,
    )
    downstream_nodes = [
        str(asset.get("name") or "")
        for asset in assets
        if asset.get("lineage_role") == "downstream"
    ]
    passed = (
        precision == 1.0
        and recall == 1.0
        and all(item["found"] for item in path_results)
        and max_depth >= int(expected["minimum_max_depth"])
        and not downstream_nodes
    )
    return {
        "status": "pass" if passed else "fail",
        "direct_model_precision": precision,
        "direct_model_recall": recall,
        "expected_direct_models": sorted(expected_direct),
        "detected_direct_models": sorted(detected_direct),
        "missing_direct_models": sorted(expected_direct - detected_direct),
        "unexpected_direct_models": sorted(detected_direct - expected_direct),
        "required_lineage_paths": path_results,
        "observed_max_upstream_depth": max_depth,
        "downstream_model_nodes": downstream_nodes,
    }


def _render_validation_report(stage: str, validation: dict[str, Any]) -> str:
    path_rows = [
        f"| `{item['from']}` | `{item['to']}` | {'PASS' if item['found'] else 'FAIL'} |"
        for item in validation["required_lineage_paths"]
    ]
    return "\n".join(
        [
            f"# Real ModelScope {stage} validation",
            "",
            f"- Overall: **{validation['status'].upper()}**",
            f"- Direct model precision: **{validation['direct_model_precision']:.3f}**",
            f"- Direct model recall: **{validation['direct_model_recall']:.3f}**",
            f"- Maximum upstream depth observed: **{validation['observed_max_upstream_depth']}**",
            f"- Downstream model nodes included: **{len(validation['downstream_model_nodes'])}**",
            "",
            "## Required lineage paths",
            "",
            "| From | To (ancestor) | Result |",
            "| --- | --- | --- |",
            *path_rows,
            "",
            "This report validates the frozen live snapshot. It does not claim "
            "that any license changed.",
            "",
        ]
    )


def _scan_manifest(
    project_path: Path,
    assets: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    graph: dict[str, Any],
    stage: str,
    direct: list[dict[str, Any]],
    validation: dict[str, Any],
) -> dict[str, Any]:
    models = []
    for asset in assets:
        if asset.get("aggregate") or not str(asset.get("name") or ""):
            continue
        models.append(
            {
                "model_id": asset.get("name"),
                "canonical_id": asset.get("canonical_id"),
                "license": asset.get("license"),
                "lineage_role": asset.get("lineage_role"),
                "lineage_status": asset.get("lineage_status"),
                "lineage_complete": asset.get("lineage_complete"),
                "lineage_depth": asset.get("lineage_depth"),
                "resolved_upstream_count": asset.get("resolved_upstream_count"),
                "max_depth_seen": asset.get("max_depth_seen"),
                "source_file": asset.get("source_file"),
                "evidence_chain": asset.get("evidence_chain") or [],
            }
        )
    return {
        "schema_version": "real-modelscope-project-snapshot/v1",
        "stage": stage,
        "generated_at": _utc_now(),
        "live_api": True,
        "project_path": project_path.relative_to(ROOT).as_posix(),
        "direct_models": direct,
        "validation": validation,
        "model_count": len(models),
        "edge_count": len(edges),
        "graph_node_count": graph.get("node_count", 0),
        "models": sorted(models, key=lambda item: str(item["model_id"])),
        "source": "ModelScope official API",
        "simulation": False,
        "ai_acceptance_simulation": stage == "full",
    }


def generate(
    stage: str,
    output_dir: Path | None = None,
    reuse_existing: bool = False,
) -> Path:
    project_path = STAGES[stage]
    destination = (output_dir or project_path.parent / "snapshots" / stage).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    artifacts_dir = destination / "artifacts"
    cache_dir = destination / "cache"
    output_dir_for_main = destination

    report_path = output_dir_for_main / "project_report.md"
    bom_path = output_dir_for_main / "t0_bom.json"
    graph_path = output_dir_for_main / "t0_graph.json"

    args = Namespace(
        project=project_path,
        output=report_path,
        artifacts_dir=artifacts_dir,
        cache_dir=cache_dir,
        bom_output=bom_path,
        graph_output=graph_path,
        max_upstream_depth=None,
        max_upstream_nodes=128,
        ai_mode=False,
        ai_max_models=20,
    )
    if not reuse_existing:
        ledger_main.run_project(args)

    if reuse_existing:
        report_dir = destination
        assets_path = output_dir_for_main / "t0_assets.json"
        edges_path = output_dir_for_main / "t0_edges.json"
    else:
        report_dir = _project_output_dir(artifacts_dir, project_path)
        _make_snapshot_portable(
            report_dir,
            [report_path, report_dir / "report.md"],
        )
        assets_path = report_dir / "assets.json"
        edges_path = report_dir / "edges.json"
    if not assets_path.exists() or not edges_path.exists():
        raise RuntimeError(f"Project pipeline did not write assets/edges: {report_dir}")

    if not reuse_existing:
        shutil.copy2(assets_path, output_dir_for_main / "t0_assets.json")
        shutil.copy2(edges_path, output_dir_for_main / "t0_edges.json")
    assets = json.loads(assets_path.read_text(encoding="utf-8"))
    edges = json.loads(edges_path.read_text(encoding="utf-8"))
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    ai_bundle = None
    if stage == "full":
        ai_bundle = acceptance_ai.attach_profiles(
            assets,
            acceptance_ai.AI_MODEL_IDS,
            "before",
            output_dir_for_main,
        )
        acceptance_ai.attach_project_context(
            assets,
            project_path,
            ai_bundle,
            output_dir_for_main,
        )
        _write_json(assets_path, assets)
        _write_json(output_dir_for_main / "t0_assets.json", assets)
        ledger_main._attach_ai_to_graph(graph_path, assets)
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        export_bom.export_bom(assets_path, edges_path, bom_path)
        acceptance_ai.append_ai_report(report_path, ai_bundle)
        acceptance_ai.append_ai_report(report_dir / "report.md", ai_bundle)
    direct = ledger_main._scan_project_models(project_path)
    validation = _validate_snapshot(stage, direct, assets, edges)
    _write_json(
        output_dir_for_main / "scan_manifest.json",
        _scan_manifest(project_path, assets, edges, graph, stage, direct, validation),
    )
    (output_dir_for_main / "validation_report.md").write_text(
        _render_validation_report(stage, validation),
        encoding="utf-8",
    )
    if validation["status"] != "pass":
        raise RuntimeError(
            f"Live snapshot validation failed for stage {stage}: {validation}"
        )
    render = subprocess.run(
        [
            sys.executable,
            str(ROOT / "render_graph.py"),
            "--input",
            str(graph_path),
            "--output",
            str(destination / "project_graph.html"),
            "--report",
            str(report_path),
            "--title",
            f"{stage} - real ModelScope project",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if render.returncode != 0:
        raise RuntimeError(
            "render_graph.py failed: " + (render.stderr or render.stdout).strip()
        )
    print(f"Snapshot generated: {destination}")
    return destination


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate live ModelScope Project snapshots")
    parser.add_argument("--stage", choices=tuple(STAGES), required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse frozen t0 assets/edges/graph and refresh AI evidence plus HTML.",
    )
    args = parser.parse_args(argv)
    generate(args.stage, args.output, reuse_existing=args.reuse_existing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
