#!/usr/bin/env python3
"""对 Hugging Face 模型 BOM 运行模块 1、2 并输出结构化验证数据。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BOM_DIR = ROOT / "outputs" / "hf_models_bom"
WORK_DIR = ROOT / "work" / "hf_models_module_validation"
ADAPTER = ROOT / "outputs" / "bom_adapter.py"
RESOLVER = ROOT / "entity_resolver.py"
OUTPUT_JSON = ROOT / "work" / "hf_models_validation_data.json"

# 文件名到 Hugging Face 仓库标识的映射，用于报告中还原模型来源。
MODEL_REFS = {
    "bert-base-uncased_bom.json": "google-bert/bert-base-uncased",
    "all-MiniLM-L6-v2_bom.json": "sentence-transformers/all-MiniLM-L6-v2",
    "stsb-roberta-base_bom.json": "cross-encoder/stsb-roberta-base",
    "nli-deberta-v3-base_bom.json": "cross-encoder/nli-deberta-v3-base",
    "SmolLM2-135M-Instruct_bom.json": "HuggingFaceTB/SmolLM2-135M-Instruct",
    "Qwen2.5-0.5B-Instruct_bom.json": "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen2.5-0.5B-Instruct-GGUF_bom.json": "bartowski/Qwen2.5-0.5B-Instruct-GGUF",
    "Llama-2-7b-chat-hf_bom.json": "meta-llama/Llama-2-7b-chat-hf",
    "Llama-2-7B-Chat-GGUF_bom.json": "TheBloke/Llama-2-7B-Chat-GGUF",
}


def load_json(path: Path) -> Any:
    """读取 UTF-8 JSON。"""

    with path.open("r", encoding="utf-8") as input_file:
        return json.load(input_file)


def write_json(path: Path, value: Any) -> None:
    """按 UTF-8 和两空格缩进写入 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(value, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def run_python(script: Path, args: list[str]) -> tuple[float, subprocess.CompletedProcess[str]]:
    """运行现有 Python 模块并计时，确保使用统一 UTF-8。"""

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    command = [sys.executable, str(script), *args]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"命令失败：{' '.join(command)}\n"
            f"stdout：{completed.stdout}\n"
            f"stderr：{completed.stderr}"
        )
    return elapsed, completed


def flatten_components(
    components: list[Any], prefix: str = "components"
) -> list[tuple[str, dict[str, Any]]]:
    """深度优先展开组件，保留嵌套路径。"""

    flattened: list[tuple[str, dict[str, Any]]] = []
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            continue
        component_path = f"{prefix}[{index}]"
        flattened.append((component_path, component))
        nested = component.get("components")
        if isinstance(nested, list):
            flattened.extend(
                flatten_components(nested, f"{component_path}/components")
            )
    return flattened


def component_kind(component: dict[str, Any]) -> str:
    """把 CycloneDX 类型映射到项目的 asset_type。"""

    component_type = str(component.get("type") or "")
    if component_type in {"machine-learning-model", "model"}:
        return "model"
    if component_type in {"data", "dataset"}:
        return "dataset"
    return "package"


def model_reference(component: dict[str, Any]) -> dict[str, Any]:
    """提取模型名、版本和 purl。"""

    return {
        "name": component.get("name"),
        "version": component.get("version"),
        "purl": component.get("purl") or component.get("bom-ref"),
    }


def ancestor_chains(component: dict[str, Any]) -> list[list[dict[str, Any]]]:
    """把嵌套 pedigree 展开为一条条祖先链。"""

    ancestors = component.get("pedigree", {}).get("ancestors")
    if not isinstance(ancestors, list) or not ancestors:
        return []

    chains: list[list[dict[str, Any]]] = []
    for ancestor in ancestors:
        if not isinstance(ancestor, dict):
            continue
        nested = ancestor_chains(ancestor)
        if nested:
            for chain in nested:
                chains.append([model_reference(ancestor), *chain])
        else:
            chains.append([model_reference(ancestor)])
    return chains


def dataset_entries(component: dict[str, Any]) -> list[dict[str, Any]]:
    """提取 modelCard 中声明的数据集引用和名称。"""

    datasets = (
        component.get("modelCard", {})
        .get("modelParameters", {})
        .get("datasets")
    )
    if not isinstance(datasets, list):
        return []
    result: list[dict[str, Any]] = []
    for dataset in datasets:
        if isinstance(dataset, dict):
            result.append(
                {
                    "ref": dataset.get("ref"),
                    "name": dataset.get("name"),
                }
            )
        else:
            result.append({"ref": None, "name": str(dataset)})
    return result


def extract_purl_types(asset: dict[str, Any]) -> set[str]:
    """从资产 purl 中提取生态类型。"""

    values = asset.get("purls")
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        values = []
    result: set[str] = set()
    for value in values:
        text = str(value or "")
        if text.startswith("pkg:") and "/" in text:
            result.add(text[4:].split("/", 1)[0].lower())
    return result


def raw_bom_summary(bom: dict[str, Any]) -> dict[str, Any]:
    """统计原始 BOM 中与血缘直接相关的字段。"""

    flattened = flatten_components(bom.get("components", []))
    model_rows: list[dict[str, Any]] = []
    model_count = 0
    ancestor_count = 0
    dataset_count = 0

    for _, component in flattened:
        if component_kind(component) != "model":
            continue
        model_count += 1
        chains = ancestor_chains(component)
        datasets = dataset_entries(component)
        if chains:
            ancestor_count += 1
        if datasets:
            dataset_count += 1
        model_rows.append(
            {
                **model_reference(component),
                "pedigree_notes": component.get("pedigree", {}).get("notes"),
                "ancestor_chains": chains,
                "datasets": datasets,
            }
        )

    return {
        "component_count": len(flattened),
        "model_component_count": model_count,
        "models_with_ancestors": ancestor_count,
        "models_with_datasets": dataset_count,
        "models": model_rows,
    }


def module2_summary(
    assets: list[dict[str, Any]], merge_log: list[dict[str, Any]]
) -> dict[str, Any]:
    """汇总同名 purl 检查、窄例外和合并置信度。"""

    model_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for asset in assets:
        if asset.get("asset_type") == "model":
            model_groups[str(asset.get("name") or "")].append(asset)

    same_name_diff_purl: list[dict[str, Any]] = []
    same_name_diff_type: list[dict[str, Any]] = []
    for name, group in model_groups.items():
        if len(group) < 2:
            continue
        purls = sorted(
            {
                str(purl)
                for asset in group
                for purl in (
                    asset.get("purls")
                    if isinstance(asset.get("purls"), list)
                    else [asset.get("purl")]
                )
                if purl
            }
        )
        purl_types = sorted(
            set().union(*(extract_purl_types(asset) for asset in group))
        )
        if len(purls) > 1:
            same_name_diff_purl.append(
                {"name": name, "purls": purls, "purl_types": purl_types}
            )
        if len(purl_types) > 1:
            same_name_diff_type.append(
                {"name": name, "purls": purls, "purl_types": purl_types}
            )

    merged = [entry for entry in merge_log if entry.get("status") == "merged"]
    review = [
        entry for entry in merge_log if entry.get("status") == "needs_review"
    ]
    skipped = [
        entry
        for entry in merge_log
        if entry.get("status") not in {"merged", "needs_review"}
    ]
    narrow = [
        entry for entry in merged if "窄例外" in str(entry.get("basis") or "")
    ]

    return {
        "same_name_pair_count": len(merge_log),
        "same_name_diff_purl_model_groups": same_name_diff_purl,
        "same_name_diff_purl_type_groups": same_name_diff_type,
        "narrow_exception_triggered": len(narrow),
        "narrow_exception_entries": narrow,
        "merged_pair_count": len(merged),
        "needs_review_pair_count": len(review),
        "skipped_pair_count": len(skipped),
        "confidence_distribution": dict(
            Counter(str(entry.get("confidence")) for entry in merged)
        ),
        "skip_reason_distribution": dict(
            Counter(str(entry.get("status")) for entry in skipped)
        ),
    }


def narrow_exception_reason(summary: dict[str, Any]) -> str:
    """解释窄例外未触发或已触发的原因。"""

    if summary["narrow_exception_triggered"]:
        return "已触发模型跨生态别名窄例外。"
    if summary["same_name_pair_count"] == 0:
        return "不存在同名模型组件，实体解析器未形成任何候选对。"
    if not summary["same_name_diff_purl_type_groups"]:
        return "存在同名模型组件，但没有覆盖 npm/pypi/huggingface 的不同 purl 生态组合。"
    return "存在跨生态候选，但缺少共同有效文件路径或版本不一致，未满足窄例外全部条件。"


def main() -> None:
    """执行逐模型验证并写出结构化结果。"""

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for bom_path in sorted(BOM_DIR.glob("*_bom.json")):
        stem = bom_path.stem.replace("_bom", "")
        bom = load_json(bom_path)
        raw_summary = raw_bom_summary(bom)

        assets_path = WORK_DIR / f"{stem}_assets.json"
        dedup_path = WORK_DIR / f"{stem}_deduplicated.json"
        log_path = WORK_DIR / f"{stem}_merge_log.json"

        adapter_seconds, adapter_result = run_python(
            ADAPTER,
            [
                "--input",
                str(bom_path),
                "--output",
                str(assets_path),
                "--snapshot-id",
                f"hf-{stem}",
            ],
        )
        assets = load_json(assets_path)
        resolver_seconds, resolver_result = run_python(
            RESOLVER,
            [
                "--input",
                str(assets_path),
                "--output",
                str(dedup_path),
                "--log",
                str(log_path),
            ],
        )
        merge_log = load_json(log_path)
        module2 = module2_summary(assets, merge_log)

        rows.append(
            {
                "file": bom_path.name,
                "huggingface_repo": MODEL_REFS.get(
                    bom_path.name, bom_path.stem.replace("_bom", "")
                ),
                "module1": {
                    "parsed_component_count": len(assets),
                    "model_asset_count": sum(
                        1 for asset in assets if asset.get("asset_type") == "model"
                    ),
                    "models_with_pedigree_ancestors": raw_summary[
                        "models_with_ancestors"
                    ],
                    "models_with_modelcard_datasets": raw_summary[
                        "models_with_datasets"
                    ],
                    "elapsed_seconds": round(adapter_seconds, 6),
                    "stdout": adapter_result.stdout.strip().splitlines(),
                },
                "raw_bom": raw_summary,
                "module2": {
                    **module2,
                    "elapsed_seconds": round(resolver_seconds, 6),
                    "narrow_exception_reason": narrow_exception_reason(module2),
                    "stdout": resolver_result.stdout.strip().splitlines(),
                },
                "paths": {
                    "assets": str(assets_path),
                    "deduplicated": str(dedup_path),
                    "merge_log": str(log_path),
                },
            }
        )

    write_json(OUTPUT_JSON, rows)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
