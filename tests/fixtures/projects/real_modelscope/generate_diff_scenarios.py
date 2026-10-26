# -*- coding: utf-8 -*-
"""Create controlled what-if Diff snapshots from a real Project t0 snapshot."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bom_adapter
import build_graph
import export_bom
import networkx as nx
import main as ledger_main
import acceptance_ai
from ai_layer.schemas import semantic_diff


SNAPSHOT_ROOT = ROOT / "tests" / "fixtures" / "projects" / "real_modelscope" / "snapshots" / "full"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _make_diff_report_portable(path: Path) -> None:
    """Keep generated Diff reports portable across machines."""
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for prefix in (str(ROOT) + "\\", ROOT.as_posix() + "/"):
        text = text.replace(prefix, "")
    path.write_text(text, encoding="utf-8")


def _render_diff_outputs(
    output_dir: Path,
    title: str,
    ai_bundle: dict[str, Any] | None = None,
) -> None:
    before = output_dir / "t0_bom.json"
    after = output_dir / "t1_bom.json"
    report_path = output_dir / "diff_report.md"
    ledger_main.run_diff(before, after, report_path)
    if ai_bundle is not None:
        acceptance_ai.append_ai_report(report_path, ai_bundle)
    _make_diff_report_portable(report_path)
    render = subprocess.run(
        [
            sys.executable,
            str(ROOT / "render_diff.py"),
            "--before",
            str(before),
            "--after",
            str(after),
            "--output",
            str(output_dir / "diff_graph.html"),
            "--report",
            str(report_path),
            "--title",
            title,
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
            "render_diff.py failed: " + (render.stderr or render.stdout).strip()
        )


def _asset_by_name(assets: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for asset in assets:
        if asset.get("name") == name and not asset.get("aggregate"):
            return asset
    raise KeyError(f"model not found in snapshot: {name}")


def _reverse_reachable(graph: Any, target: str) -> list[str]:
    reversed_graph = graph.reverse(copy=True)
    nodes = set(nx.descendants(reversed_graph, target))
    nodes.add(target)
    return sorted(nodes)


def _mutate_license_asset(asset: dict[str, Any], target_license: str, reason: str) -> None:
    original = asset.get("license")
    asset["simulation"] = True
    asset["simulation_reason"] = reason
    asset["simulation_original_license"] = original
    asset["simulation_target_license"] = target_license
    asset["license"] = target_license
    evidence = asset.setdefault("evidence_chain", [])
    evidence.insert(
        0,
        {
            "evidence_level": "C",
            "source_api": "simulation",
            "source_url": None,
            "source_field": "fixture.simulation.license",
            "retrieved_at": _now(),
            "status": "simulated",
            "raw_value": target_license,
            "original_value": original,
            "simulation": True,
        },
    )


def _scenario_readme(
    name: str,
    target_model: str,
    target_id: str,
    original_license: str | None,
    target_license: str,
    affected_names: list[str],
    source_snapshot: Path,
) -> str:
    affected = "\n".join(f"- `{value}`" for value in affected_names)
    return f"""# {name}

This is a controlled what-if scenario. It is not a ModelScope claim that the
license changed in the real world.

- Base snapshot: `{source_snapshot.as_posix()}`
- Mutated model: `{target_model}`
- Canonical ID: `{target_id}`
- Original license: `{original_license or "(unknown)"}`
- Simulated license: `{target_license}`
- Simulation metadata: `simulation=true`
- AI overlay: `tests/fixtures/projects/real_modelscope/ai_acceptance/`

Expected downstream set in the frozen project subgraph:

{affected}

The t1 assets retain the original lineage edges. The mutation is represented by
a C-level simulation evidence entry and never overwrites the original A-level
ModelScope evidence.

The AI section is also simulated. It demonstrates quote validation, confidence
factors and semantic tightening, but it is not a claim about the real model's
current ModelScope license.
"""


def build_scenario(
    name: str,
    target_name: str,
    target_license: str,
    reason: str,
    source_assets: Path,
    source_edges: Path,
    source_bom: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_dir = output_root / name
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = json.loads(source_assets.read_text(encoding="utf-8"))
    edges = json.loads(source_edges.read_text(encoding="utf-8"))
    t0_assets = copy.deepcopy(assets)
    t0_edges = copy.deepcopy(edges)
    target = _asset_by_name(assets, target_name)
    target_id = target["canonical_id"]
    original_license = target.get("license")
    _mutate_license_asset(target, target_license, reason)

    acceptance_ai.attach_profiles(
        t0_assets,
        [target_name],
        "before",
        output_dir / "ai" / "before",
    )
    after_bundle = acceptance_ai.attach_profiles(
        assets,
        [target_name],
        "after",
        output_dir / "ai" / "after",
    )
    after_bundle["semantic_diff"] = semantic_diff(
        ledger_main._ai_model_analyses_from_assets(t0_assets),
        ledger_main._ai_model_analyses_from_assets(assets),
    )

    graph = build_graph.build_graph(assets, edges)
    affected_ids = _reverse_reachable(graph, target_id)
    names = {
        asset.get("canonical_id"): asset.get("name")
        for asset in assets
        if asset.get("canonical_id")
    }
    affected_names = [names[item] for item in affected_ids if item in names]

    _write_json(output_dir / "t1_assets.json", assets)
    _write_json(output_dir / "t1_edges.json", edges)
    _write_json(output_dir / "t0_assets.json", t0_assets)
    _write_json(output_dir / "t0_edges.json", t0_edges)
    shutil.copy2(source_bom, output_dir / "t0_bom.json")
    export_bom.export_bom(output_dir / "t1_assets.json", output_dir / "t1_edges.json", output_dir / "t1_bom.json")

    _write_json(output_dir / "ai" / "after" / "ai_analysis.json", after_bundle)

    scenario = {
        "schema_version": "modelscope-what-if-diff/v1",
        "name": name,
        "created_at": _now(),
        "simulation": True,
        "ai_acceptance_simulation": True,
        "simulation_reason": reason,
        "source_snapshot": _display_path(source_bom),
        "mutated_model": target_name,
        "canonical_id": target_id,
        "original_license": original_license,
        "target_license": target_license,
        "expected_affected_models": affected_names,
        "t0": "t0_bom.json",
        "t1": "t1_bom.json",
        "diff_report": "diff_report.md",
        "diff_graph": "diff_graph.html",
    }
    _write_json(output_dir / "scenario.json", scenario)
    (output_dir / "README.md").write_text(
        _scenario_readme(
            name,
            target_name,
            target_id,
            original_license,
            target_license,
            affected_names,
            Path(_display_path(source_bom)),
        ),
        encoding="utf-8",
    )
    _render_diff_outputs(
        output_dir,
        name + " - real project what-if",
        after_bundle,
    )
    return scenario


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate controlled Diff scenarios from a real project snapshot")
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_ROOT)
    parser.add_argument("--output", type=Path, default=SNAPSHOT_ROOT / "scenarios")
    args = parser.parse_args(argv)
    source_bom = args.snapshot / "t0_bom.json"
    source_assets = args.snapshot / "t0_assets.json"
    source_edges = args.snapshot / "t0_edges.json"
    for path in (source_bom, source_assets, source_edges):
        if not path.exists():
            raise FileNotFoundError(f"run generate_live_fixtures.py --stage full first: {path}")

    args.output.mkdir(parents=True, exist_ok=True)
    scenarios = [
        build_scenario(
            "direct_license_change",
            "Qwen/Qwen2.5-7B-Instruct-AWQ",
            "qwen-research",
            "direct_model_license_change",
            source_assets,
            source_edges,
            source_bom,
            args.output,
        ),
        build_scenario(
            "upstream_license_change",
            "Qwen/Qwen2.5-7B",
            "qwen-research",
            "upstream_model_license_change",
            source_assets,
            source_edges,
            source_bom,
            args.output,
        ),
    ]
    _write_json(
        args.output / "manifest.json",
        {
            "schema_version": "modelscope-what-if-manifest/v1",
            "source_snapshot": _display_path(source_bom),
            "simulation": True,
            "scenarios": [
                {"name": item["name"], "path": item["name"], "target": item["mutated_model"]}
                for item in scenarios
            ],
        },
    )
    (args.output / "README.md").write_text(
        "# Real Project What-if Diff Scenarios\n\n"
        "These directories are generated from the live Project t0 snapshot. "
        "`t0_bom.json` is the real snapshot; `t1_bom.json` is a controlled "
        "license mutation with `simulation=true` and a retained original A-level "
        "evidence entry.\n\n"
        "Run Project and Diff with the explicit files in each scenario; do not "
        "treat the mutated t1 as a live ModelScope observation.\n",
        encoding="utf-8",
    )
    print(f"Scenarios generated: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli()) 
