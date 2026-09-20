#!/usr/bin/env python3
"""用现有 entity_resolver.py 验证 Wild SBOMs 的跨生态候选。"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "outputs"
CANDIDATE_PATH = OUTPUT_DIR / "cross_ecosystem_candidates.json"
VALIDATION_PATH = OUTPUT_DIR / "wild_sboms_merge_validation.json"
ADAPTER_PATH = BASE_DIR / "test-project" / "bom_adapter.py"
RESOLVER_PATH = BASE_DIR / "entity_resolver.py"
SAMPLE_SEED = 20260918


def load_module(module_name: str, module_path: Path) -> Any:
    """按文件路径加载模块，避免依赖当前工作目录。"""

    specification = importlib.util.spec_from_file_location(module_name, module_path)
    if specification is None or specification.loader is None:
        raise ImportError(f"无法加载模块：{module_path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 和两个空格缩进输出 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def counter_json(counter: Counter) -> dict[str, int]:
    """把 Counter 转为按键排序的普通字典。"""

    return {str(key): count for key, count in sorted(counter.items(), key=lambda x: str(x[0]))}


def purl_log_list(value: Any) -> list[str]:
    """把日志中的单 purl 或 purl 数组统一转换为列表。"""

    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def is_cross_ecosystem_log(entry: dict[str, Any]) -> bool:
    """判断一条配对日志是否属于跨 purl 生态。"""

    left_types = set(entry.get("kept_purl_types") or [])
    right_types = set(entry.get("merged_purl_types") or [])
    return bool(left_types and right_types and left_types.isdisjoint(right_types))


def pair_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    """生成严格模式与放宽模式共用的配对键。"""

    return (
        entry.get("name"),
        tuple(entry.get("kept_purl_types") or []),
        tuple(entry.get("merged_purl_types") or []),
        str(entry.get("kept_purl")),
        str(entry.get("merged_purl")),
        entry.get("kept_version"),
        entry.get("merged_version"),
    )


def narrow_conditions(entry: dict[str, Any], resolver: Any) -> dict[str, bool]:
    """计算窄例外四个必要条件以及允许生态集合条件。"""

    left_version = entry.get("kept_version")
    right_version = entry.get("merged_version")
    left_types = set(entry.get("kept_purl_types") or [])
    right_types = set(entry.get("merged_purl_types") or [])
    combined_types = left_types | right_types
    return {
        "双方asset_type均为model": (
            entry.get("asset_type_left") == "model"
            and entry.get("asset_type_right") == "model"
        ),
        "版本一致且非空": (
            left_version is not None
            and right_version is not None
            and left_version == right_version
        ),
        "存在共同有效路径": bool(entry.get("common_valid_locations")),
        "purl生态在允许集合": (
            bool(combined_types)
            and combined_types <= resolver.MODEL_ALIAS_PURL_TYPES
        ),
    }


def primary_non_narrow_reason(
    entry: dict[str, Any],
    conditions: dict[str, bool],
) -> str:
    """为未触发窄例外或已由其他信号合并的配对给出一级原因。"""

    if not conditions["双方asset_type均为model"]:
        return "asset_type非model"
    if not conditions["版本一致且非空"]:
        return "版本不一致或缺失"
    if not conditions["存在共同有效路径"]:
        return "无共同有效路径"
    if not conditions["purl生态在允许集合"]:
        return "purl生态不在允许集合"
    if entry.get("status") == "merged":
        return "窄例外条件满足但由其他高置信信号先合并"
    return "其他"


def relaxed_model_alias_bridge(
    left: dict[str, Any],
    right: dict[str, Any],
    left_types: set[str],
    right_types: set[str],
    left_version: str | None,
    right_version: str | None,
    common_locations: set[str],
) -> bool:
    """放宽模式：仅移除 asset_type=model 限制，其余窄例外条件保持不变。"""

    del left, right
    if not common_locations:
        return False
    if left_version is None or right_version is None or left_version != right_version:
        return False
    combined_types = left_types | right_types
    if not combined_types:
        return False
    return (
        left_types.isdisjoint(right_types)
        and combined_types <= {"npm", "pypi", "huggingface"}
    )


def compact_relaxed_pair(entry: dict[str, Any], source_file: Path) -> dict[str, Any]:
    """整理自动合并对的审计信息。"""

    return {
        "文件": str(source_file.resolve()),
        "name": entry.get("name"),
        "组件A": {
            "purl": purl_log_list(entry.get("kept_purl")),
            "purl类型": entry.get("kept_purl_types") or [],
            "version": entry.get("kept_version"),
            "asset_type": entry.get("asset_type_left"),
        },
        "组件B": {
            "purl": purl_log_list(entry.get("merged_purl")),
            "purl类型": entry.get("merged_purl_types") or [],
            "version": entry.get("merged_version"),
            "asset_type": entry.get("asset_type_right"),
        },
        "共同有效路径": entry.get("common_valid_locations") or [],
        "共同哈希": entry.get("common_hashes") or {},
        "共同URL": entry.get("common_urls") or [],
        "共同作者": entry.get("common_authors") or [],
        "合并依据": entry.get("basis"),
        "置信度": entry.get("confidence"),
    }


def analyze_candidate(
    candidate: dict[str, Any],
    adapter: Any,
    resolver: Any,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """对一个候选文件执行严格模式和放宽模式并返回统计与新增合并对。"""

    path = Path(candidate["路径"])
    bom = adapter.load_json(path)
    assets = adapter.convert_bom(
        bom=bom,
        source_file=str(path.resolve()),
        snapshot_id=f"wild-sboms:{path.stem}",
    )

    _, strict_log = resolver.deduplicate_assets(assets)

    original_bridge = resolver.is_model_alias_bridge
    try:
        resolver.is_model_alias_bridge = relaxed_model_alias_bridge
        _, relaxed_log = resolver.deduplicate_assets(assets)
    finally:
        resolver.is_model_alias_bridge = original_bridge

    strict_cross = [entry for entry in strict_log if is_cross_ecosystem_log(entry)]
    relaxed_cross = [entry for entry in relaxed_log if is_cross_ecosystem_log(entry)]

    if len(strict_cross) != len(relaxed_cross):
        raise RuntimeError(
            f"严格与放宽模式的跨生态配对数不一致：{path}，"
            f"{len(strict_cross)} != {len(relaxed_cross)}"
        )

    strict_by_key = {pair_key(entry): entry for entry in strict_cross}
    relaxed_by_key = {pair_key(entry): entry for entry in relaxed_cross}
    if strict_by_key.keys() != relaxed_by_key.keys():
        raise RuntimeError(f"严格与放宽模式的配对键不一致：{path}")

    narrow_triggered = 0
    strict_merged = 0
    strict_status_counts: Counter[str] = Counter()
    strict_basis_counts: Counter[str] = Counter()
    condition_failure_counts: Counter[str] = Counter()
    primary_reason_counts: Counter[str] = Counter()
    relaxed_merged_cross = 0
    relaxed_basis_counts: Counter[str] = Counter()
    new_relaxed_pairs: list[dict[str, Any]] = []
    strict_merged_pairs: list[dict[str, Any]] = []

    for entry in strict_cross:
        key = pair_key(entry)
        relaxed_entry = relaxed_by_key[key]
        conditions = narrow_conditions(entry, resolver)

        strict_status_counts[str(entry.get("status"))] += 1
        if entry.get("status") == "merged":
            strict_merged += 1
            strict_basis_counts[str(entry.get("basis"))] += 1
            strict_merged_pairs.append(compact_relaxed_pair(entry, path))
        if entry.get("basis") == "模型别名跨生态+同名+同版本+相同有效文件位置":
            narrow_triggered += 1

        for name, satisfied in conditions.items():
            if not satisfied:
                condition_failure_counts[name] += 1
        if entry.get("basis") != "模型别名跨生态+同名+同版本+相同有效文件位置":
            primary_reason_counts[primary_non_narrow_reason(entry, conditions)] += 1

        if relaxed_entry.get("status") == "merged":
            relaxed_merged_cross += 1
            relaxed_basis_counts[str(relaxed_entry.get("basis"))] += 1

        if entry.get("status") != "merged" and relaxed_entry.get("status") == "merged":
            new_relaxed_pairs.append(compact_relaxed_pair(relaxed_entry, path))

    result = {
        "文件": str(path.resolve()),
        "文件名": path.name,
        "组件数": len(assets),
        "严格模式": {
            "跨生态配对数": len(strict_cross),
            "自动合并对数": strict_merged,
            "窄例外触发对数": narrow_triggered,
            "状态分布": counter_json(strict_status_counts),
            "合并依据分布": counter_json(strict_basis_counts),
            "必要条件未满足次数": counter_json(condition_failure_counts),
            "未触发窄例外的一级原因": counter_json(primary_reason_counts),
        },
        "放宽模式": {
            "跨生态配对数": len(relaxed_cross),
            "自动合并对数": relaxed_merged_cross,
            "合并依据分布": counter_json(relaxed_basis_counts),
            "相比严格模式新增合并对数": len(new_relaxed_pairs),
        },
    }
    return result, new_relaxed_pairs, strict_cross, strict_merged_pairs


def aggregate_counters(
    file_results: list[dict[str, Any]],
    section: str,
    key: str,
) -> dict[str, int]:
    """汇总各文件下指定嵌套字段的 Counter 风格字典。"""

    total: Counter[str] = Counter()
    for item in file_results:
        total.update(item[section].get(key, {}))
    return counter_json(total)


def main() -> int:
    """遍历候选文件，执行严格模式和放宽模式并输出验证结果。"""

    adapter = load_module("wild_sboms_bom_adapter", ADAPTER_PATH)
    resolver = load_module("wild_sboms_entity_resolver", RESOLVER_PATH)
    candidate_data = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidates = candidate_data["候选文件"]

    started_at = time.perf_counter()
    file_results: list[dict[str, Any]] = []
    all_new_relaxed_pairs: list[dict[str, Any]] = []
    all_strict_merged_pairs: list[dict[str, Any]] = []
    strict_cross_pair_total = 0
    failures: list[dict[str, Any]] = []

    for position, candidate in enumerate(candidates, start=1):
        try:
            result, new_pairs, strict_cross, strict_merged_pairs = analyze_candidate(
                candidate,
                adapter,
                resolver,
            )
        except Exception as exc:
            failures.append(
                {
                    "文件": candidate["路径"],
                    "错误": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        file_results.append(result)
        all_new_relaxed_pairs.extend(new_pairs)
        all_strict_merged_pairs.extend(strict_merged_pairs)
        strict_cross_pair_total += len(strict_cross)

        if position % 100 == 0:
            print(
                f"已验证 {position}/{len(candidates)} 个候选文件，"
                f"放宽模式新增合并 {len(all_new_relaxed_pairs)} 对",
                flush=True,
            )

    strict_merged_total = sum(
        item["严格模式"]["自动合并对数"] for item in file_results
    )
    narrow_total = sum(
        item["严格模式"]["窄例外触发对数"] for item in file_results
    )
    relaxed_merged_total = sum(
        item["放宽模式"]["自动合并对数"] for item in file_results
    )

    generator = random.Random(SAMPLE_SEED)
    sampled_new_pairs = (
        generator.sample(all_new_relaxed_pairs, 20)
        if len(all_new_relaxed_pairs) > 20
        else list(all_new_relaxed_pairs)
    )
    verification_pool = (
        all_new_relaxed_pairs
        if all_new_relaxed_pairs
        else all_strict_merged_pairs
    )
    sampled_verification_pairs = (
        generator.sample(verification_pool, 20)
        if len(verification_pool) > 20
        else list(verification_pool)
    )

    result = {
        "候选文件": str(CANDIDATE_PATH.resolve()),
        "候选文件数": len(candidates),
        "验证成功文件数": len(file_results),
        "验证失败文件数": len(failures),
        "验证失败文件": failures,
        "严格模式": {
            "跨生态配对总数": strict_cross_pair_total,
            "自动合并对数": strict_merged_total,
            "窄例外触发对数": narrow_total,
            "其他信号合并对数": strict_merged_total - narrow_total,
            "自动合并对": all_strict_merged_pairs,
            "状态分布": aggregate_counters(file_results, "严格模式", "状态分布"),
            "合并依据分布": aggregate_counters(
                file_results, "严格模式", "合并依据分布"
            ),
            "必要条件未满足次数": aggregate_counters(
                file_results, "严格模式", "必要条件未满足次数"
            ),
            "未触发窄例外的一级原因": aggregate_counters(
                file_results, "严格模式", "未触发窄例外的一级原因"
            ),
        },
        "放宽模式": {
            "跨生态配对总数": strict_cross_pair_total,
            "自动合并对数": relaxed_merged_total,
            "相比严格模式新增合并对数": len(all_new_relaxed_pairs),
            "新增合并文件数": len(
                {item["文件"] for item in all_new_relaxed_pairs}
            ),
            "新增合并对": all_new_relaxed_pairs,
            "合并依据分布": aggregate_counters(
                file_results, "放宽模式", "合并依据分布"
            ),
        },
        "随机抽样种子": SAMPLE_SEED,
        "随机抽样新增合并对": sampled_new_pairs,
        "第三方核验候选池": (
            "放宽模式新增合并对" if all_new_relaxed_pairs else "严格模式已有跨生态合并对"
        ),
        "第三方核验候选池大小": len(verification_pool),
        "第三方核验实际抽样数": len(sampled_verification_pairs),
        "随机抽样核验对": sampled_verification_pairs,
        "逐文件结果": file_results,
        "验证耗时秒": round(time.perf_counter() - started_at, 3),
    }
    write_json(VALIDATION_PATH, result)

    print(f"验证完成：{len(file_results)} 个候选文件")
    print(f"严格模式跨生态配对：{strict_cross_pair_total} 对")
    print(f"严格模式窄例外触发：{narrow_total} 对")
    print(f"放宽模式新增合并：{len(all_new_relaxed_pairs)} 对")
    print(f"验证失败：{len(failures)} 个")
    print(f"输出：{VALIDATION_PATH}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
