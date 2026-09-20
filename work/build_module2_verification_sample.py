#!/usr/bin/env python3
"""重建 MSU 模块 2 的全部合并对，并为第三方核验抽取固定随机样本。"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import unquote


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = Path(r"D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms")
ADAPTER_PATH = BASE_DIR / "test-project" / "bom_adapter.py"
RESOLVER_PATH = BASE_DIR / "entity_resolver.py"
ALL_PAIRS_PATH = BASE_DIR / "work" / "module2_all_merged_pairs.json"
SAMPLE_PATH = BASE_DIR / "work" / "module2_verification_sample_50.json"
SAMPLE_COUNT = 50
RANDOM_SEED = 20260918


def load_module(module_name: str, module_path: Path) -> Any:
    """按文件路径加载解析器或对齐器。"""

    specification = importlib.util.spec_from_file_location(module_name, module_path)
    if specification is None or specification.loader is None:
        raise ImportError(f"无法加载模块：{module_path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 写出核验输入文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def as_list(value: Any) -> list[Any]:
    """把单值或列表统一为列表。"""

    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def purl_type(resolver: Any, purl: str) -> str | None:
    """提取 purl 的生态类型。"""

    return resolver.purl_type(purl)


def canonical_purls(resolver: Any, entry: dict[str, Any], side: str) -> list[str]:
    """提取一侧日志中的规范 purl，同时保留原始 purl。"""

    raw_values = as_list(entry.get(f"{side}_purl"))
    purls: list[str] = []
    for raw_value in raw_values:
        purl = str(raw_value).strip()
        if purl and purl not in purls:
            purls.append(purl)
    return purls


def canonical_key(canonical_purl: str) -> str:
    """生成用于判断两个 purl 是否只是限定参数不同的键。"""

    return unquote(canonical_purl.split("#", 1)[0].split("?", 1)[0]).lower()


def compact_pair(entry: dict[str, Any], index: int, resolver: Any) -> dict[str, Any]:
    """把完整配对日志压缩成第三方核验输入。"""

    purls_a = canonical_purls(resolver, entry, "kept")
    purls_b = canonical_purls(resolver, entry, "merged")
    canonical_a = [resolver.canonical_purl(item) for item in purls_a]
    canonical_b = [resolver.canonical_purl(item) for item in purls_b]
    types_a = sorted(
        {value for item in purls_a if (value := purl_type(resolver, item))}
    )
    types_b = sorted(
        {value for item in purls_b if (value := purl_type(resolver, item))}
    )
    keys_a = {canonical_key(item) for item in canonical_a}
    keys_b = {canonical_key(item) for item in canonical_b}
    return {
        "核验编号": index,
        "原始SBOM": entry.get("kept_source_file"),
        "name": entry.get("name"),
        "version": entry.get("kept_version"),
        "被合并版本": entry.get("merged_version"),
        "purlA": purls_a,
        "purlB": purls_b,
        "规范purlA": canonical_a,
        "规范purlB": canonical_b,
        "purl类型A": types_a,
        "purl类型B": types_b,
        "规范purl主体相同": bool(keys_a & keys_b),
        "合并依据": entry.get("basis"),
        "置信度": entry.get("confidence"),
        "共同哈希": entry.get("common_hashes", {}),
        "共同URL": entry.get("common_urls", []),
        "共同作者": entry.get("common_authors", []),
        "共同A级位置": entry.get("common_valid_locations", []),
        "源位置等级A": entry.get("kept_location_level"),
        "源位置等级B": entry.get("merged_location_level"),
    }


def main() -> None:
    """扫描全部 SBOM，收集合并对并抽取 50 对。"""

    adapter = load_module("msu_verify_bom_adapter", ADAPTER_PATH)
    resolver = load_module("msu_verify_entity_resolver", RESOLVER_PATH)
    files = sorted(INPUT_DIR.rglob("*.json"))
    merged_pairs: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    started_at = time.perf_counter()

    for position, path in enumerate(files, start=1):
        try:
            bom = adapter.load_json(path)
            assets = adapter.convert_bom(
                bom=bom,
                source_file=str(path.resolve()),
                snapshot_id=f"third-party-verification:{position}",
            )
            _, merge_log = resolver.deduplicate_assets(assets)
        except Exception as exc:
            errors.append(
                {
                    "文件": str(path.resolve()),
                    "错误": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        for entry in merge_log:
            if entry.get("status") != "merged":
                continue
            merged_pairs.append(
                compact_pair(entry, len(merged_pairs) + 1, resolver)
            )

        if position % 100 == 0:
            print(f"已扫描 {position}/{len(files)}，累计合并对 {len(merged_pairs)}")

    type_combination_counts = Counter(
        "->".join(pair["purl类型A"]) + "::" + "->".join(pair["purl类型B"])
        for pair in merged_pairs
    )
    basis_counts = Counter(pair["合并依据"] for pair in merged_pairs)
    body_same_counts = Counter(pair["规范purl主体相同"] for pair in merged_pairs)

    all_document = {
        "输入目录": str(INPUT_DIR.resolve()),
        "文件总数": len(files),
        "解析失败数": len(errors),
        "错误": errors,
        "合并对数": len(merged_pairs),
        "purl类型组合分布": dict(sorted(type_combination_counts.items())),
        "合并依据分布": dict(sorted(basis_counts.items())),
        "规范purl主体相同分布": {
            str(key): count for key, count in sorted(body_same_counts.items())
        },
        "合并对": merged_pairs,
    }
    write_json(ALL_PAIRS_PATH, all_document)

    generator = random.Random(RANDOM_SEED)
    sampled = (
        generator.sample(merged_pairs, SAMPLE_COUNT)
        if len(merged_pairs) > SAMPLE_COUNT
        else list(merged_pairs)
    )
    sample_document = {
        "输入目录": str(INPUT_DIR.resolve()),
        "总体合并对数": len(merged_pairs),
        "抽样数量": len(sampled),
        "抽样方式": f"固定随机种子 {RANDOM_SEED}，从全部合并对中无放回随机抽取",
        "purl类型组合分布": dict(sorted(type_combination_counts.items())),
        "合并依据总体分布": dict(sorted(basis_counts.items())),
        "合并对": sampled,
    }
    write_json(SAMPLE_PATH, sample_document)

    print(
        json.dumps(
            {
                "合并对数": len(merged_pairs),
                "purl类型组合分布": dict(sorted(type_combination_counts.items())),
                "合并依据分布": dict(sorted(basis_counts.items())),
                "规范purl主体相同": dict(body_same_counts),
                "抽样数量": len(sampled),
                "耗时秒": round(time.perf_counter() - started_at, 6),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"全部合并对：{ALL_PAIRS_PATH}")
    print(f"核验样本：{SAMPLE_PATH}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
