#!/usr/bin/env python3
"""扫描 Wild SBOMs，找出同一文件内同名但 purl 生态不同的组件对。"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = Path(r"D:\datasets\wild-sboms\cyclonedx-json")
DEFAULT_OUTPUT_PATH = BASE_DIR / "outputs" / "cross_ecosystem_candidates.json"
PURL_PATTERN = re.compile(r"^pkg:([^/]+)/(.+)$", re.IGNORECASE)


def clean_text(value: Any) -> str | None:
    """把输入转换为去首尾空白的字符串；空值返回 None。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_list(value: Any) -> list[Any]:
    """把单值、数组和空值统一转换为列表。"""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def extract_purls(component: dict[str, Any]) -> list[str]:
    """提取组件 purl；缺少 purl 时兼容以 pkg: 开头的 bom-ref。"""

    purls: list[str] = []
    for raw_purl in as_list(component.get("purl")):
        purl = clean_text(raw_purl)
        if purl and purl not in purls:
            purls.append(purl)

    bom_ref = clean_text(component.get("bom-ref"))
    if bom_ref and bom_ref.startswith("pkg:") and bom_ref not in purls:
        purls.append(bom_ref)
    return purls


def parse_purl(purl: str) -> dict[str, str | None] | None:
    """解析 purl 的生态、命名空间、名称和版本。"""

    match = PURL_PATTERN.match(purl.strip())
    if not match:
        return None

    purl_type = match.group(1).lower()
    coordinate = match.group(2).split("#", 1)[0].split("?", 1)[0]
    if "@" in coordinate:
        package_coordinate, version = coordinate.rsplit("@", 1)
    else:
        package_coordinate, version = coordinate, None

    package_coordinate = unquote(package_coordinate)
    if "/" in package_coordinate:
        namespace, name = package_coordinate.rsplit("/", 1)
    else:
        namespace, name = None, package_coordinate

    return {
        "type": purl_type,
        "namespace": namespace,
        "name": unquote(name),
        "version": unquote(version) if version else None,
        "purl": purl,
    }


def flatten_components(components: Iterable[Any]) -> Iterable[tuple[int, dict[str, Any]]]:
    """深度优先展开顶层和嵌套 components，并保留稳定顺序。"""

    sequence = 0
    stack: list[Any] = list(reversed(list(components)))
    while stack:
        raw_component = stack.pop()
        if not isinstance(raw_component, dict):
            continue

        yield sequence, raw_component
        sequence += 1

        nested = raw_component.get("components")
        if isinstance(nested, list):
            stack.extend(reversed(nested))


def asset_type_for(component: dict[str, Any]) -> str:
    """沿用现有 BOM 适配器的组件类型映射。"""

    component_type = clean_text(component.get("type")) or ""
    if component_type in {"machine-learning-model", "model"}:
        return "model"
    if component_type in {"data", "dataset"}:
        return "dataset"
    if component_type == "repository":
        return "repository"
    return "package"


def component_purl_entries(
    component_index: int,
    component: dict[str, Any],
) -> list[dict[str, Any]]:
    """把一个组件展开为带 purl 类型信息的候选记录。"""

    name = clean_text(component.get("name"))
    if not name:
        return []

    entries: list[dict[str, Any]] = []
    for purl in extract_purls(component):
        parsed = parse_purl(purl)
        if parsed is None:
            continue
        entries.append(
            {
                "组件序号": component_index,
                "name": name,
                "version": clean_text(component.get("version")) or parsed["version"],
                "purl": purl,
                "purl类型": parsed["type"],
                "asset_type": asset_type_for(component),
                "bom-ref": clean_text(component.get("bom-ref")),
            }
        )
    return entries


def component_signature(entry: dict[str, Any]) -> tuple[Any, ...]:
    """生成组件去重键，避免相同安装记录产生重复组件对。"""

    return (
        entry.get("name"),
        entry.get("version"),
        entry.get("purl"),
        entry.get("bom-ref"),
    )


def find_cross_ecosystem_pairs(
    components: Iterable[Any],
) -> tuple[list[dict[str, Any]], int]:
    """返回单文件内所有跨生态同名组件对及组件记录总数。"""

    by_name: dict[str, dict[str, dict[tuple[Any, ...], dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    component_count = 0

    for component_index, component in flatten_components(components):
        component_count += 1
        for entry in component_purl_entries(component_index, component):
            name = str(entry["name"])
            purl_type = str(entry["purl类型"])
            by_name[name][purl_type][component_signature(entry)] = entry

    pairs: list[dict[str, Any]] = []
    seen_pairs: set[tuple[Any, ...]] = set()

    for name, groups_by_type in by_name.items():
        if len(groups_by_type) < 2:
            continue

        purl_types = sorted(groups_by_type)
        for left_type, right_type in itertools.combinations(purl_types, 2):
            left_entries = list(groups_by_type[left_type].values())
            right_entries = list(groups_by_type[right_type].values())
            for left_entry, right_entry in itertools.product(left_entries, right_entries):
                pair_key = (
                    name,
                    left_entry["组件序号"],
                    left_entry["purl"],
                    right_entry["组件序号"],
                    right_entry["purl"],
                )
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                pairs.append(
                    {
                        "name": name,
                        "组件A": left_entry,
                        "组件B": right_entry,
                    }
                )

    pairs.sort(
        key=lambda item: (
            str(item["name"]),
            str(item["组件A"]["purl类型"]),
            str(item["组件B"]["purl类型"]),
            str(item["组件A"]["purl"]),
            str(item["组件B"]["purl"]),
        )
    )
    return pairs, component_count


def load_components(path: Path) -> list[Any]:
    """读取 CycloneDX 顶层 components；结构不符时抛出可读异常。"""

    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("JSON 根节点不是对象")
    if document.get("bomFormat") != "CycloneDX":
        raise ValueError("bomFormat 不是 CycloneDX")
    components = document.get("components")
    if not isinstance(components, list):
        raise ValueError("顶层 components 不是数组")
    return components


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 和两个空格缩进输出 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """扫描目录并写出跨生态候选文件。"""

    parser = argparse.ArgumentParser(description="扫描 Wild SBOMs 跨生态候选")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="最多扫描的文件数；0 表示扫描全部。",
    )
    args = parser.parse_args()

    all_files = sorted(args.input_dir.glob("*.json"))
    selected_files = (
        all_files[: args.max_files] if args.max_files and args.max_files > 0 else all_files
    )
    candidates: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    type_combination_counts: Counter[str] = Counter()
    total_pairs = 0
    total_components = 0
    started_at = time.perf_counter()

    for position, path in enumerate(selected_files, start=1):
        try:
            components = load_components(path)
            pairs, component_count = find_cross_ecosystem_pairs(components)
        except Exception as exc:
            failures.append(
                {
                    "路径": str(path.resolve()),
                    "错误": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        total_components += component_count
        if not pairs:
            continue

        for pair in pairs:
            left_type = str(pair["组件A"]["purl类型"])
            right_type = str(pair["组件B"]["purl类型"])
            type_pair = "::".join(sorted((left_type, right_type)))
            type_combination_counts[type_pair] += 1

        total_pairs += len(pairs)
        candidates.append(
            {
                "路径": str(path.resolve()),
                "文件名": path.name,
                "跨生态对数量": len(pairs),
                "组件对": pairs,
            }
        )

        if position % 500 == 0:
            print(
                f"已扫描 {position}/{len(selected_files)} 个文件，"
                f"候选文件 {len(candidates)} 个，跨生态对 {total_pairs} 对",
                flush=True,
            )

    candidates.sort(
        key=lambda item: (-int(item["跨生态对数量"]), str(item["文件名"]))
    )
    result = {
        "扫描目录": str(args.input_dir.resolve()),
        "JSON文件总数": len(all_files),
        "实际扫描文件数": len(selected_files),
        "是否仅扫描部分文件": len(selected_files) < len(all_files),
        "扫描上限": args.max_files if args.max_files and args.max_files > 0 else None,
        "扫描组件数": total_components,
        "解析失败文件数": len(failures),
        "解析失败文件": failures,
        "候选文件数": len(candidates),
        "跨生态组件对总数": total_pairs,
        "purl类型组合分布": dict(sorted(type_combination_counts.items())),
        "扫描耗时秒": round(time.perf_counter() - started_at, 3),
        "候选文件": candidates,
    }
    write_json(args.output, result)

    print(f"扫描完成：{len(selected_files)} 个文件")
    print(f"候选文件：{len(candidates)} 个")
    print(f"跨生态组件对：{total_pairs} 对")
    print(f"解析失败：{len(failures)} 个")
    print(f"输出：{args.output}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
