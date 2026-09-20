#!/usr/bin/env python3
"""在 MSU 全量 Docker SBOM 上验证扩展后的实体对齐规则。"""

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
INPUT_DIR = Path(r"D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms")
MAIN_SAMPLE = (
    INPUT_DIR
    / "benchmark-alpine-busybox-ngnix-node-ubuntu"
    / "sbom_syft_node_lts_cdx.json"
)
TRIVY_SAMPLE = (
    INPUT_DIR
    / "benchmark-alpine-busybox-ngnix-node-ubuntu"
    / "sbom_trivy_ubuntu_jammy-20240111_cdx.json"
)
OUTPUT_DIR = BASE_DIR / "outputs"
ADAPTER_PATH = BASE_DIR / "test-project" / "bom_adapter.py"
RESOLVER_PATH = BASE_DIR / "entity_resolver.py"
SAMPLE_SEED = 20260918

# 全量结果会在运行后由脚本写入 outputs；人工结论用独立映射保留审计痕迹。
MANUAL_VERDICTS: dict[str, dict[str, str]] = {
    "sbom_syft_node_jod-bookworm_cdx.json|@npmcli/agent|2.2.2|2.2.2|homepage或repository URL相同|0.95": {
        "结论": "真同一实体",
        "理由": "同名同版本；purl 仅 package-id 限定不同，repository URL 一致，属于同一包的重复安装记录。",
    },
    "sbom_syft_node_22.11.0-bookworm_cdx.json|unique-slug|4.0.0|4.0.0|homepage或repository URL相同|0.95": {
        "结论": "真同一实体",
        "理由": "同名同版本；purl 仅 package-id 限定不同，repository URL 一致，属于同一包的重复安装记录。",
    },
    "sbom_syft_node_iron-bookworm_cdx.json|minipass|3.3.6|3.3.6|homepage或repository URL相同|0.95": {
        "结论": "真同一实体",
        "理由": "同名同版本且作者与 repository URL 均一致，属于同一包的重复安装记录。",
    },
    "sbom_syft_node_22.10.0-bookworm_cdx.json|minipass|3.3.6|3.3.6|homepage或repository URL相同|0.95": {
        "结论": "真同一实体",
        "理由": "同名同版本且作者与 repository URL 均一致，属于同一包的重复安装记录。",
    },
    "sbom_syft_node_23.1-bullseye-slim_cdx.json|minipass-fetch|3.0.5|3.0.5|homepage或repository URL相同|0.95": {
        "结论": "真同一实体",
        "理由": "同名同版本；purl 仅 package-id 限定不同，repository URL 一致，属于同一包的重复安装记录。",
    },
    "sbom_syft_node_20.16.0-alpine3.19_cdx.json|minipass|3.3.6|3.3.6|homepage或repository URL相同|0.95": {
        "结论": "真同一实体",
        "理由": "同名同版本且作者与 repository URL 均一致，属于同一包的重复安装记录。",
    },
    "sbom_syft_node_23.1-bookworm_cdx.json|mkdirp|3.0.1|3.0.1|homepage或repository URL相同|0.95": {
        "结论": "真同一实体",
        "理由": "同名同版本；purl 仅 package-id 限定不同，repository URL 一致，属于同一包的重复安装记录。",
    },
    "sbom_syft_node_jod_cdx.json|unique-slug|4.0.0|4.0.0|homepage或repository URL相同|0.95": {
        "结论": "真同一实体",
        "理由": "同名同版本；purl 仅 package-id 限定不同，repository URL 一致，属于同一包的重复安装记录。",
    },
    "sbom_syft_node_23-bookworm-slim_cdx.json|make-fetch-happen|13.0.1|13.0.1|homepage或repository URL相同|0.95": {
        "结论": "真同一实体",
        "理由": "同名同版本；purl 仅 package-id 限定不同，repository URL 一致，属于同一包的重复安装记录。",
    },
    "sbom_syft_node_22.5-slim_cdx.json|minipass|3.3.6|3.3.6|homepage或repository URL相同|0.95": {
        "结论": "真同一实体",
        "理由": "同名同版本且作者与 repository URL 均一致，属于同一包的重复安装记录。",
    },
}


def load_module(module_name: str, module_path: Path) -> Any:
    """按文件路径加载模块，避免依赖当前工作目录。"""

    specification = importlib.util.spec_from_file_location(module_name, module_path)
    if specification is None or specification.loader is None:
        raise ImportError(f"无法加载模块：{module_path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 和两空格缩进写出 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def counter_json(counter: Counter) -> dict[str, int]:
    """把 Counter 转换为按置信度或原因排序的普通字典。"""

    return {
        str(key): count
        for key, count in sorted(
            counter.items(),
            key=lambda item: str(item[0]),
        )
    }


def confidence_json(counter: Counter) -> dict[str, int]:
    """把置信度 Counter 按数值倒序输出。"""

    def sort_key(item: tuple[Any, int]) -> float:
        try:
            return -float(item[0])
        except (TypeError, ValueError):
            return float("inf")

    return {str(key): count for key, count in sorted(counter.items(), key=sort_key)}


def purl_display(value: Any) -> str | list[str] | None:
    """让日志中的 purl 保持单值或数组的可读形式。"""

    if isinstance(value, list):
        return value
    if value is None:
        return None
    return str(value)


def compact_merge_entry(entry: dict[str, Any], source_file: Path) -> dict[str, Any]:
    """从完整配对日志中保留人工核对和统计所需字段。"""

    kept_purl = purl_display(entry.get("kept_purl"))
    merged_purl = purl_display(entry.get("merged_purl"))
    return {
        "文件": str(source_file.resolve()),
        "name": entry.get("name"),
        "kept_version": entry.get("kept_version"),
        "merged_version": entry.get("merged_version"),
        "kept_purl": kept_purl,
        "merged_purl": merged_purl,
        "basis": entry.get("basis"),
        "confidence": entry.get("confidence"),
        "common_hashes": entry.get("common_hashes", {}),
        "common_urls": entry.get("common_urls", []),
        "common_authors": entry.get("common_authors", []),
        "common_valid_locations": entry.get("common_valid_locations", []),
        "kept_location_level": entry.get("kept_location_level"),
        "merged_location_level": entry.get("merged_location_level"),
    }


def signal_component_counts(asset: dict[str, Any], resolver: Any) -> dict[str, bool]:
    """判断单个资产是否携带四类扩展信号。"""

    return {
        "has_hash": bool(resolver.extract_hashes(asset)),
        "has_url": bool(resolver.extract_urls(asset)),
        "has_author": bool(resolver.extract_authors(asset)),
        "has_a_location": bool(resolver.extract_evidence_locations(asset)),
        "has_b_layer": bool(resolver.extract_layer_locations(asset)),
    }


def summarize_file(
    path: Path,
    adapter: Any,
    resolver: Any,
    collect_log: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """解析并对齐一个文件，返回逐文件统计与紧凑合并记录。"""

    started_at = time.perf_counter()
    compiled_hash = ""
    try:
        compiled_hash = json.dumps(
            {
                "path": str(path),
                "size": path.stat().st_size,
                "mtime": path.stat().st_mtime,
            },
            ensure_ascii=False,
        )
        bom = adapter.load_json(path)
        assets = adapter.convert_bom(
            bom=bom,
            source_file=str(path.resolve()),
            snapshot_id=f"msu-extended:{path.parent.name}",
        )
        deduplicated, merge_log = resolver.deduplicate_assets(assets)
    except Exception as exc:  # 保留单文件失败，不中断 995 文件批处理。
        return (
            {
                "文件": str(path.resolve()),
                "文件名": path.name,
                "项目": path.parent.name,
                "解析成功": False,
                "错误": f"{type(exc).__name__}: {exc}",
                "指纹": compiled_hash,
                "耗时秒": round(time.perf_counter() - started_at, 6),
            },
            [],
        )

    status_counts = Counter(str(entry.get("status")) for entry in merge_log)
    confidence_counts = Counter(
        entry.get("confidence")
        for entry in merge_log
        if entry.get("status") == "merged"
    )
    basis_counts = Counter(
        str(entry.get("basis"))
        for entry in merge_log
        if entry.get("status") == "merged"
    )
    merged_entries = [
        entry for entry in merge_log if entry.get("status") == "merged"
    ]
    review_entries = [
        entry for entry in merge_log if entry.get("status") == "needs_review"
    ]
    hash_conflict_count = sum(
        1
        for entry in merge_log
        if entry.get("status") == "skipped: hash_conflict"
    )
    url_version_mismatch_count = sum(
        1
        for entry in merge_log
        if entry.get("common_urls")
        and entry.get("kept_version") != entry.get("merged_version")
    )

    component_signals = Counter()
    for asset in assets:
        flags = signal_component_counts(asset, resolver)
        for key, present in flags.items():
            component_signals[key] += int(present)

    compact_entries = [
        compact_merge_entry(entry, path) for entry in merged_entries
    ] if collect_log else []

    return (
        {
            "文件": str(path.resolve()),
            "文件名": path.name,
            "项目": path.parent.name,
            "解析成功": True,
            "组件数": len(assets),
            "去重后组件数": len(deduplicated),
            "同名配对总数": len(merge_log),
            "自动合并对数": len(merged_entries),
            "人工复核对数": len(review_entries),
            "跳过对数": sum(
                1
                for entry in merge_log
                if entry.get("status") not in {"merged", "needs_review"}
            ),
            "置信度分布": confidence_json(confidence_counts),
            "合并依据分布": counter_json(basis_counts),
            "状态分布": counter_json(status_counts),
            "哈希冲突对数": hash_conflict_count,
            "同URL但版本不同被拦截对数": url_version_mismatch_count,
            "有哈希组件数": component_signals["has_hash"],
            "有URL组件数": component_signals["has_url"],
            "有author或maintainer组件数": component_signals["has_author"],
            "有A级路径组件数": component_signals["has_a_location"],
            "有B级layerID组件数": component_signals["has_b_layer"],
            "evidence条数": sum(
                len(asset.get("evidence_chain", []))
                if isinstance(asset.get("evidence_chain"), list)
                else 0
                for asset in assets
            ),
            "耗时秒": round(time.perf_counter() - started_at, 6),
        },
        compact_entries,
    )


def aggregate_results(file_results: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总全部文件的合并、复核、跳过和信号可用性。"""

    successful = [item for item in file_results if item.get("解析成功")]
    failed = [item for item in file_results if not item.get("解析成功")]
    confidence_counts = Counter()
    status_counts = Counter()
    basis_counts = Counter()
    for item in successful:
        confidence_counts.update(
            {
                float(confidence): count
                for confidence, count in item["置信度分布"].items()
            }
        )
        status_counts.update(item["状态分布"])
        basis_counts.update(item["合并依据分布"])

    return {
        "文件总数": len(file_results),
        "解析成功文件数": len(successful),
        "解析失败文件数": len(failed),
        "组件总数": sum(item["组件数"] for item in successful),
        "去重后组件总数": sum(item["去重后组件数"] for item in successful),
        "同名配对总数": sum(item["同名配对总数"] for item in successful),
        "自动合并对数": sum(item["自动合并对数"] for item in successful),
        "人工复核对数": sum(item["人工复核对数"] for item in successful),
        "跳过对数": sum(item["跳过对数"] for item in successful),
        "发生自动合并文件数": sum(
            item["自动合并对数"] > 0 for item in successful
        ),
        "置信度分布": confidence_json(confidence_counts),
        "合并依据分布": counter_json(basis_counts),
        "状态分布": counter_json(status_counts),
        "哈希冲突对数": sum(item["哈希冲突对数"] for item in successful),
        "同URL但版本不同被拦截对数": sum(
            item["同URL但版本不同被拦截对数"] for item in successful
        ),
        "有哈希组件数": sum(item["有哈希组件数"] for item in successful),
        "有URL组件数": sum(item["有URL组件数"] for item in successful),
        "有author或maintainer组件数": sum(
            item["有author或maintainer组件数"] for item in successful
        ),
        "有A级路径组件数": sum(item["有A级路径组件数"] for item in successful),
        "有B级layerID组件数": sum(
            item["有B级layerID组件数"] for item in successful
        ),
        "含哈希文件数": sum(item["有哈希组件数"] > 0 for item in successful),
        "含URL文件数": sum(item["有URL组件数"] > 0 for item in successful),
        "含author或maintainer文件数": sum(
            item["有author或maintainer组件数"] > 0 for item in successful
        ),
        "含A级路径文件数": sum(
            item["有A级路径组件数"] > 0 for item in successful
        ),
        "含B级layerID文件数": sum(
            item["有B级layerID组件数"] > 0 for item in successful
        ),
        "总解析与对齐耗时秒": round(
            sum(item.get("耗时秒", 0) for item in file_results), 6
        ),
        "解析失败样本": failed[:20],
    }


def sample_merged_pairs(
    merged_entries: list[dict[str, Any]],
    count: int = 10,
) -> list[dict[str, Any]]:
    """用固定随机种子抽取合并对，保证结果可复现。"""

    if not merged_entries:
        return []
    generator = random.Random(SAMPLE_SEED)
    selected = (
        generator.sample(merged_entries, count)
        if len(merged_entries) > count
        else list(merged_entries)
    )
    for entry in selected:
        key = "|".join(
            [
                Path(str(entry.get("文件"))).name,
                str(entry.get("name")),
                str(entry.get("kept_version")),
                str(entry.get("merged_version")),
                str(entry.get("basis")),
                str(entry.get("confidence")),
            ]
        )
        verdict = MANUAL_VERDICTS.get(key)
        entry["人工判断"] = verdict or {
            "结论": "待人工核对",
            "理由": "由报告生成者完成逐对核对后填写。",
        }
    return selected


def main() -> None:
    """遍历 995 个 SBOM，写出逐文件结果、重点样本日志和汇总。"""

    adapter = load_module("msu_extended_bom_adapter", ADAPTER_PATH)
    resolver = load_module("msu_extended_entity_resolver", RESOLVER_PATH)
    files = sorted(INPUT_DIR.rglob("*.json"))
    main_sample_resolved = MAIN_SAMPLE.resolve()
    trivy_sample_resolved = TRIVY_SAMPLE.resolve()

    started_at = time.perf_counter()
    file_results: list[dict[str, Any]] = []
    all_merged_entries: list[dict[str, Any]] = []

    for position, path in enumerate(files, start=1):
        resolved_path = path.resolve()
        collect_log = resolved_path in {main_sample_resolved, trivy_sample_resolved}
        result, compact_entries = summarize_file(
            path,
            adapter,
            resolver,
            collect_log=True,
        )
        file_results.append(result)
        all_merged_entries.extend(compact_entries)

        if resolved_path == main_sample_resolved and result.get("解析成功"):
            bom = adapter.load_json(path)
            assets = adapter.convert_bom(
                bom=bom,
                source_file=str(path.resolve()),
                snapshot_id="msu-extended-main-syft-node-lts",
            )
            deduplicated, merge_log = resolver.deduplicate_assets(assets)
            write_json(OUTPUT_DIR / "assets_real_npm_extended.json", assets)
            write_json(
                OUTPUT_DIR / "assets_real_npm_extended_deduplicated.json",
                deduplicated,
            )
            write_json(
                OUTPUT_DIR / "merge_log_real_npm_extended.json",
                merge_log,
            )

        if resolved_path == trivy_sample_resolved and result.get("解析成功"):
            bom = adapter.load_json(path)
            assets = adapter.convert_bom(
                bom=bom,
                source_file=str(path.resolve()),
                snapshot_id="msu-extended-trivy-ubuntu-jammy",
            )
            deduplicated, merge_log = resolver.deduplicate_assets(assets)
            write_json(OUTPUT_DIR / "assets_real_trivy_extended.json", assets)
            write_json(
                OUTPUT_DIR / "assets_real_trivy_extended_deduplicated.json",
                deduplicated,
            )
            write_json(
                OUTPUT_DIR / "merge_log_real_trivy_extended.json",
                merge_log,
            )

        if position % 100 == 0:
            print(f"已完成 {position}/{len(files)} 个文件")

    aggregate = aggregate_results(file_results)
    aggregate["全量批处理耗时秒"] = round(time.perf_counter() - started_at, 6)
    aggregate["输入目录"] = str(INPUT_DIR.resolve())
    aggregate["重点样本"] = {
        "npm_主样本": str(MAIN_SAMPLE.resolve()),
        "trivy_样本": str(TRIVY_SAMPLE.resolve()),
    }

    sampled_pairs = sample_merged_pairs(all_merged_entries)
    write_json(OUTPUT_DIR / "msu_extended_alignment_summary.json", aggregate)
    write_json(OUTPUT_DIR / "msu_extended_file_results.json", file_results)
    write_json(OUTPUT_DIR / "msu_extended_merge_samples.json", sampled_pairs)
    write_json(
        OUTPUT_DIR / "msu_extended_signal_availability.json",
        {
            "组件级": {
                "有哈希组件数": aggregate["有哈希组件数"],
                "有URL组件数": aggregate["有URL组件数"],
                "有author或maintainer组件数": aggregate[
                    "有author或maintainer组件数"
                ],
                "有A级路径组件数": aggregate["有A级路径组件数"],
                "有B级layerID组件数": aggregate["有B级layerID组件数"],
            },
            "文件级": {
                "文件总数": aggregate["文件总数"],
                "含哈希文件数": aggregate["含哈希文件数"],
                "含URL文件数": aggregate["含URL文件数"],
                "含author或maintainer文件数": aggregate[
                    "含author或maintainer文件数"
                ],
                "含A级路径文件数": aggregate["含A级路径文件数"],
                "含B级layerID文件数": aggregate["含B级layerID文件数"],
            },
        },
    )

    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    print(f"抽样合并对：{OUTPUT_DIR / 'msu_extended_merge_samples.json'}")


if __name__ == "__main__":
    # 在 Windows 终端中显式使用 UTF-8，避免中文结果乱码。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
