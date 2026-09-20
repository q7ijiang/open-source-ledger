#!/usr/bin/env python3
"""在候选 SBOM 中查找能够真正触发实体对齐规则的样本。"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = BASE_DIR / "outputs" / "duplicate_candidates.json"
BOM_ADAPTER_PATH = BASE_DIR / "test-project" / "bom_adapter.py"
RESOLVER_PATH = BASE_DIR / "entity_resolver.py"


def load_module(module_name: str, module_path: Path) -> Any:
    """按文件路径加载现有模块，避免改动模块源码或默认参数。"""

    specification = importlib.util.spec_from_file_location(module_name, module_path)
    if specification is None or specification.loader is None:
        raise ImportError(f"无法加载模块：{module_path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def analyze_pair_decisions(assets: list[dict[str, Any]], resolver: Any) -> Counter:
    """复现模块 2 的两两判定，统计实际会生成的合并记录。"""

    indices_by_name: dict[str, list[int]] = {}
    for index, asset in enumerate(assets):
        name = resolver.clean_text(asset.get("name")) or ""
        indices_by_name.setdefault(name, []).append(index)

    decisions: Counter = Counter()
    for indices in indices_by_name.values():
        for left_position, left_index in enumerate(indices):
            for right_index in indices[left_position + 1 :]:
                decision = resolver.evaluate_pair(
                    assets[left_index], assets[right_index]
                )
                if decision is None:
                    continue
                confidence, basis = decision
                decisions[(confidence, basis)] += 1

    return decisions


def main() -> None:
    """逐个候选计算合并次数并输出排名。"""

    adapter = load_module("bom_adapter_for_scan", BOM_ADAPTER_PATH)
    resolver = load_module("entity_resolver_for_scan", RESOLVER_PATH)

    candidate_document = json.loads(CANDIDATES_PATH.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []

    for position, candidate in enumerate(candidate_document["候选文件"], start=1):
        path = Path(candidate["路径"])
        bom = adapter.load_json(path)
        assets = adapter.convert_bom(
            bom=bom,
            source_file=str(path.resolve()),
            snapshot_id=f"scan-{position}",
        )
        decisions = analyze_pair_decisions(assets, resolver)
        results.append(
            {
                "文件名": path.name,
                "项目": candidate["项目"],
                "同名不同purl对数": candidate["同名不同purl对数"],
                "同名同purl对数": candidate["同名同purl对数"],
                "实际合并对数": sum(decisions.values()),
                "置信度与依据": [
                    {
                        "置信度": confidence,
                        "依据": basis,
                        "对数": count,
                    }
                    for (confidence, basis), count in sorted(decisions.items())
                ],
            }
        )

    results.sort(
        key=lambda item: (
            item["实际合并对数"],
            item["同名不同purl对数"],
            item["文件名"],
        ),
        reverse=True,
    )

    print(json.dumps(results[:30], ensure_ascii=False, indent=2))
    print(f"含实际合并的候选数：{sum(1 for item in results if item['实际合并对数'])}")
    print(f"最大实际合并对数：{results[0]['实际合并对数'] if results else 0}")


if __name__ == "__main__":
    main()
