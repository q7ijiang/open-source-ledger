# -*- coding: utf-8 -*-
"""从一次真实 Project 扫描构造受控 t0。

输入：
- observed BOM：真实扫描得到的当前快照；
- template BOM：已有的受控 t0 结构（只取目标模型的许可证/历史证据）；
- current source bundle：目标模型的当前 ModelScope 原文；
- historical bundle：历史 README 证据；
- Apache LICENSE：标准 Apache-2.0 全文，仅作为受控替代文本。

输出：
- controlled t0 BOM，目标模型许可证回放为 Apache-2.0；
- 目标模型用真实 AI 重新分析受控 LICENSE/README；
- 其他模型保留 observed BOM 中的真实 AI 画像。
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_layer.config import AIConfig
from ai_layer.service import AIService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _component(bom: dict[str, Any], name: str) -> dict[str, Any]:
    for item in bom.get("components", []):
        if item.get("name") == name:
            return item
    raise KeyError(name)


def _set_property(component: dict[str, Any], name: str, value: str) -> None:
    properties = component.setdefault("properties", [])
    for item in properties:
        if item.get("name") == name:
            item["value"] = value
            return
    properties.append({"name": name, "value": value})


def _controlled_bundle(
    current_bundle: dict[str, Any],
    historical_bundle: dict[str, Any],
    apache_text: str,
) -> dict[str, Any]:
    bundle = copy.deepcopy(current_bundle)
    historical_readme = next(
        (item for item in historical_bundle.get("documents", []) if item.get("path") == "README.md"),
        None,
    )
    if historical_readme is None:
        raise ValueError("historical bundle 没有 README.md")
    bundle["facts"] = {
        **(bundle.get("facts") or {}),
        "license": {
            "value": "Apache License 2.0",
            "source_field": "controlled:historical-readme + apache-2.0",
            "evidence_level": "A",
        },
    }
    bundle["documents"] = [
        {
            "path": "LICENSE",
            "sha256": hashlib.sha256(apache_text.encode("utf-8")).hexdigest(),
            "content": apache_text,
            "controlled_source": True,
            "synthetic_document": True,
            "not_historical_original": True,
            "source_url": "https://www.apache.org/licenses/LICENSE-2.0",
        },
        {
            **copy.deepcopy(historical_readme),
            "controlled_source": True,
            "historical_reconstruction": True,
        },
    ]
    bundle["historical_reconstruction"] = True
    bundle["simulation"] = True
    bundle["simulation_note"] = (
        "Controlled t0: the Apache LICENSE text is a controlled reconstruction, "
        "not the historical ModelScope file."
    )
    return bundle


def build_controlled_t0(
    observed_bom: dict[str, Any],
    template_bom: dict[str, Any],
    target_model: str,
    current_bundle: dict[str, Any],
    historical_bundle: dict[str, Any],
    apache_text: str,
    service: AIService,
) -> dict[str, Any]:
    controlled = copy.deepcopy(observed_bom)
    observed_target = _component(controlled, target_model)
    template_target = _component(template_bom, target_model)

    analysis = service.analyze_model_source(
        _controlled_bundle(current_bundle, historical_bundle, apache_text)
    )
    analysis = {
        **analysis,
        "controlled_source": True,
        "synthetic_document": True,
        "not_historical_original": True,
    }

    observed_target["licenses"] = copy.deepcopy(template_target["licenses"])
    template_props = {
        item.get("name"): item for item in template_target.get("properties", []) if item.get("name")
    }
    for name in (
        "open-source-ledger:simulation",
        "open-source-ledger:simulation_reason",
        "open-source-ledger:simulation_original_license",
        "open-source-ledger:simulation_target_license",
        "open-source-ledger:historical_reconstruction",
        "open-source-ledger:historical_commit",
        "open-source-ledger:historical_source_url",
    ):
        if name in template_props:
            _set_property(observed_target, name, template_props[name]["value"])
    _set_property(observed_target, "open-source-ledger:controlled_baseline", "True")
    _set_property(observed_target, "open-source-ledger:controlled_source", "True")
    _set_property(observed_target, "open-source-ledger:synthetic_document", "True")
    _set_property(observed_target, "open-source-ledger:not_historical_original", "True")
    _set_property(observed_target, "open-source-ledger:decision", "SAFE")
    _set_property(observed_target, "open-source-ledger:decision_zh", "安全（绿）")
    _set_property(observed_target, "open-source-ledger:risk_level", "2")
    _set_property(observed_target, "open-source-ledger:ai_status", str(analysis.get("status") or "unavailable"))
    _set_property(observed_target, "open-source-ledger:ai_evidence_level", "C")
    _set_property(
        observed_target,
        "open-source-ledger:ai_analysis_json",
        json.dumps(analysis, ensure_ascii=False, separators=(",", ":")),
    )

    metadata = controlled.setdefault("metadata", {})
    metadata["controlled_baseline"] = True
    metadata["simulation"] = True
    metadata["not_a_real_license_change"] = True
    metadata["controlled_source"] = "controlled Apache-2.0 reconstruction"
    metadata["controlled_generated_at"] = _now()
    metadata["controlled_target_model"] = target_model
    return controlled


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构造受控 t0 BOM")
    parser.add_argument("--observed-bom", required=True, type=Path)
    parser.add_argument("--template-bom", required=True, type=Path)
    parser.add_argument("--target-model", default="Qwen/Qwen-Image-2.1")
    parser.add_argument("--current-bundle", required=True, type=Path)
    parser.add_argument("--historical-bundle", required=True, type=Path)
    parser.add_argument("--apache-license", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    config = AIConfig.from_env(True)
    if not config.base_url or not config.model or not config.api_key:
        raise SystemExit("AI_BASE_URL / AI_MODEL / AI_API_KEY 不完整，不能生成真实 t0 AI 证据")
    service = AIService(config)
    result = build_controlled_t0(
        _load(args.observed_bom),
        _load(args.template_bom),
        args.target_model,
        _load(args.current_bundle),
        _load(args.historical_bundle),
        args.apache_license.read_text(encoding="utf-8"),
        service,
    )
    _write(args.output, result)
    target = _component(result, args.target_model)
    status = next(
        (item.get("value") for item in target.get("properties", []) if item.get("name") == "open-source-ledger:ai_status"),
        "unknown",
    )
    print(f"controlled t0 已写入：{args.output}")
    print(f"target={args.target_model} ai_status={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
