# -*- coding: utf-8 -*-
"""Attach explicit, reproducible AI acceptance evidence to project fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ai_layer.config import AIConfig
from ai_layer.schemas import collect_project_evidence, normalize_model_analysis, normalize_project_context
from ai_layer.service import analysis_bundle

FIXTURE_DIR = Path(__file__).resolve().parent / "ai_acceptance"
AI_MODEL_IDS = (
    "Qwen/Qwen2.5-7B",
    "Qwen/Qwen2.5-7B-Instruct-AWQ",
)
AI_CONFIG = AIConfig(
    enabled=True,
    provider="mock",
    model="frozen-acceptance-fixture",
    base_url="offline://acceptance",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"fixture must contain a JSON object: {path}")
    return value


def _load_template(name: str, model_id: str) -> dict[str, Any]:
    path = FIXTURE_DIR / name
    text = path.read_text(encoding="utf-8").replace("__TARGET_MODEL__", model_id)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError(f"fixture must contain a JSON object: {path}")
    return value


def build_analysis(model_id: str, phase: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if phase not in {"before", "after"}:
        raise ValueError(f"unsupported acceptance AI phase: {phase}")
    source_bundle = _load_template(f"{phase}_source_bundle.json", model_id)
    response = _load_json(FIXTURE_DIR / f"{phase}_response.json")
    analysis = normalize_model_analysis(response, source_bundle, AI_CONFIG.public_dict())
    analysis["simulation"] = True
    analysis["simulation_note"] = source_bundle.get("simulation_note")
    subject = analysis.setdefault("subject", {})
    subject["fact_source"] = "acceptance-fixture simulation"
    return analysis, source_bundle


def attach_profiles(
    assets: list[dict[str, Any]],
    model_ids: Iterable[str],
    phase: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Attach frozen profiles to models already present in the live snapshot."""

    requested = set(model_ids)
    attached_models: set[str] = set()
    analyses: list[dict[str, Any]] = []
    source_dir = output_dir / "source_bundles"
    for asset in assets:
        model_id = str(asset.get("name") or "")
        if asset.get("aggregate") or model_id not in requested:
            continue
        analysis, source_bundle = build_analysis(model_id, phase)
        asset["ai_analysis"] = analysis
        analyses.append(analysis)
        attached_models.add(model_id)
        safe_name = model_id.replace("/", "__")
        destination = source_dir / f"{safe_name}.{phase}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(source_bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    bundle = analysis_bundle(AI_CONFIG, model_analyses=analyses)
    bundle["simulation"] = True
    bundle["simulation_note"] = (
        "验收模拟：AI 画像只用于验证证据展示、语义 Diff 与置信度构成，"
        "不代表目标模型当前 ModelScope 许可证事实。"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "ai_analysis.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    missing = requested - attached_models
    if missing:
        raise ValueError(
            "acceptance AI model identities were not found in the snapshot: "
            + ", ".join(sorted(missing))
        )
    return bundle


def attach_project_context(
    assets: list[dict[str, Any]],
    project_path: Path,
    bundle: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    response = _load_json(FIXTURE_DIR / "project_context_response.json")
    evidence = collect_project_evidence(project_path)
    context = normalize_project_context(
        response, project_path, evidence, AI_CONFIG.public_dict()
    )
    context["simulation"] = True
    context["simulation_note"] = (
        "验收模拟：项目上下文只用于验证逐字代码引用和 C 级证据展示。"
    )
    for asset in assets:
        if not asset.get("aggregate"):
            asset["ai_project_context"] = context
    bundle["project_context"] = context
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "project_context.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "ai_analysis.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return context


def append_ai_report(report_path: Path, bundle: dict[str, Any]) -> None:
    """Insert frozen AI evidence before the report disclaimer."""

    if not report_path.exists():
        return
    import main as ledger_main

    content = report_path.read_text(encoding="utf-8").rstrip()
    marker = "## AI 语义证据"
    disclaimer = "## 免责声明"
    if marker in content:
        content = content[: content.index(marker)].rstrip()
    ai_lines = ledger_main._render_ai_sections(bundle)
    if not ai_lines:
        return
    ai_text = "\n".join(ai_lines).strip()
    if disclaimer in content:
        prefix, suffix = content.split(disclaimer, 1)
        content = (
            prefix.rstrip()
            + "\n\n"
            + ai_text
            + "\n\n"
            + disclaimer
            + suffix
        )
    else:
        content = content + "\n\n" + ai_text
    report_path.write_text(content.rstrip() + "\n", encoding="utf-8")
