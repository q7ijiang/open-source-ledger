#!/usr/bin/env python3
"""扫描 CycloneDX SBOM，定位包含重复组件的候选样本。"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = Path(r"D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms")
DEFAULT_OUTPUT_PATH = BASE_DIR / "outputs" / "duplicate_candidates.json"


def clean_text(value: Any) -> str | None:
    """把字段转为去除首尾空白的文本，空值返回 None。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_purl(component: dict[str, Any]) -> str | None:
    """提取组件的 purl；仅在 purl 缺失时回退到以 pkg: 开头的 bom-ref。"""

    purl = clean_text(component.get("purl"))
    if purl:
        return purl

    bom_ref = clean_text(component.get("bom-ref"))
    if bom_ref and bom_ref.startswith("pkg:"):
        return bom_ref
    return None


def flatten_components(components: Iterable[Any]) -> Iterable[tuple[int, dict[str, Any]]]:
    """深度优先展开顶层与嵌套 components，并返回原始顺序索引。"""

    sequence = 0
    stack: list[tuple[Any, int | None]] = [
        (component, None) for component in reversed(list(components))
    ]

    while stack:
        raw_component, _ = stack.pop()
        if not isinstance(raw_component, dict):
            continue

        yield sequence, raw_component
        sequence += 1

        nested = raw_component.get("components")
        if isinstance(nested, list):
            for child in reversed(nested):
                stack.append((child, None))


def component_label(component: dict[str, Any], index: int) -> dict[str, Any]:
    """生成用于候选报告的精简组件描述。"""

    return {
        "组件序号": index,
        "name": clean_text(component.get("name")),
        "version": clean_text(component.get("version")),
        "purl": extract_purl(component),
        "bom-ref": clean_text(component.get("bom-ref")),
    }


def analyze_components(
    components: Iterable[Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """统计同名组件对，并返回汇总与重复组详情。"""

    indexed_components = list(flatten_components(components))
    by_name: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)

    for index, component in indexed_components:
        name = clean_text(component.get("name"))
        if name:
            by_name[name].append((index, component))

    same_name_different_purl = 0
    same_name_same_purl = 0
    duplicate_groups: list[dict[str, Any]] = []

    for name, entries in by_name.items():
        if len(entries) < 2:
            continue

        different_purl_pairs: list[tuple[dict[str, Any], dict[str, Any], str, str]] = []
        same_purl_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for left, right in itertools.combinations(entries, 2):
            left_index, left_component = left
            right_index, right_component = right
            left_purl = extract_purl(left_component)
            right_purl = extract_purl(right_component)

            if left_purl is None or right_purl is None:
                continue

            if left_purl == right_purl:
                same_purl_groups[left_purl].extend(
                    [
                        component_label(left_component, left_index),
                        component_label(right_component, right_index),
                    ]
                )
            else:
                same_name_different_purl += 1
                different_purl_pairs.append(
                    (
                        component_label(left_component, left_index),
                        component_label(right_component, right_index),
                        left_purl,
                        right_purl,
                    )
                )

        same_purl_pairs: list[dict[str, Any]] = []
        for purl, labels in same_purl_groups.items():
            unique_labels = {
                (
                    label["组件序号"],
                    label["version"],
                    label["bom-ref"],
                ): label
                for label in labels
            }
            ordered_labels = sorted(
                unique_labels.values(), key=lambda item: item["组件序号"]
            )
            for left, right in itertools.combinations(ordered_labels, 2):
                same_name_same_purl += 1
                same_purl_pairs.append(
                    {
                        "purl": purl,
                        "组件A": left,
                        "组件B": right,
                    }
                )

        if different_purl_pairs or same_purl_pairs:
            duplicate_groups.append(
                {
                    "name": name,
                    "同名不同purl对数": len(different_purl_pairs),
                    "同名同purl对数": len(same_purl_pairs),
                    "同名不同purl对": [
                        {
                            "组件A": left,
                            "组件B": right,
                        }
                        for left, right, _, _ in different_purl_pairs
                    ],
                    "同名同purl对": same_purl_pairs,
                }
            )

    summary = {
        "同名不同purl对数": same_name_different_purl,
        "同名同purl对数": same_name_same_purl,
        "重复组数": len(duplicate_groups),
        "组件总数": len(indexed_components),
    }
    return summary, duplicate_groups


def infer_project(file_path: Path) -> str:
    """从 Syft/Trivy 文件命名中提取项目名。"""

    parts = file_path.stem.split("_")
    if len(parts) >= 3 and parts[0] == "sbom":
        return parts[2]
    return file_path.parent.name


def load_components(path: Path) -> tuple[list[Any] | None, str | None]:
    """读取 CycloneDX 文件中的顶层 components；结构不符时返回原因。"""

    try:
        with path.open("r", encoding="utf-8") as input_file:
            document = json.load(input_file)
    except json.JSONDecodeError as exc:
        return None, f"JSON 解析失败：{exc.msg}（位置 {exc.pos}）"
    except UnicodeDecodeError as exc:
        return None, f"UTF-8 解码失败：{exc}"
    except OSError as exc:
        return None, f"文件读取失败：{exc}"

    if not isinstance(document, dict):
        return None, "根节点不是 JSON 对象"
    if document.get("bomFormat") != "CycloneDX":
        return None, "bomFormat 不是 CycloneDX"
    components = document.get("components")
    if not isinstance(components, list):
        return None, "顶层 components 不是数组"
    return components, None


def scan_file(path: Path, timeout_seconds: float) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """扫描单个文件；返回候选记录和异常记录，二者最多一个非空。"""

    started_at = time.perf_counter()
    components, error = load_components(path)

    if error is not None:
        return None, {
            "路径": str(path.resolve()),
            "原因": error,
            "耗时秒": round(time.perf_counter() - started_at, 6),
        }

    assert components is not None
    summary, duplicate_groups = analyze_components(components)
    elapsed = time.perf_counter() - started_at

    if elapsed > timeout_seconds:
        return None, {
            "路径": str(path.resolve()),
            "原因": f"单文件解析及分析超过 {timeout_seconds:g} 秒，按要求跳过",
            "耗时秒": round(elapsed, 6),
        }

    if summary["同名不同purl对数"] == 0 and summary["同名同purl对数"] == 0:
        return None, None

    duplicate_types: list[str] = []
    if summary["同名不同purl对数"]:
        duplicate_types.append("同名不同purl")
    if summary["同名同purl对数"]:
        duplicate_types.append("同名同purl")

    return (
        {
            "路径": str(path.resolve()),
            "文件名": path.name,
            "项目": infer_project(path),
            "重复对数": summary["同名不同purl对数"] + summary["同名同purl对数"],
            "同名不同purl对数": summary["同名不同purl对数"],
            "同名同purl对数": summary["同名同purl对数"],
            "重复类型": duplicate_types,
            "组件总数": summary["组件总数"],
            "重复组数": summary["重复组数"],
            "重复组": duplicate_groups,
            "耗时秒": round(elapsed, 6),
        },
        None,
    )


def scan_directory(
    input_dir: Path, timeout_seconds: float, max_files: int | None
) -> dict[str, Any]:
    """递归扫描目录并汇总候选文件、失败文件及耗时。"""

    all_files = sorted(input_dir.rglob("*.json"))
    selected_files = all_files[:max_files] if max_files is not None else all_files
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    started_at = time.perf_counter()

    for position, path in enumerate(selected_files, start=1):
        candidate, skipped_file = scan_file(path, timeout_seconds)
        if candidate is not None:
            candidates.append(candidate)
        if skipped_file is not None:
            skipped.append(skipped_file)

        if position % 100 == 0:
            print(f"已扫描 {position}/{len(selected_files)} 个文件，当前候选 {len(candidates)} 个")

    candidates.sort(
        key=lambda item: (
            item["同名不同purl对数"],
            item["同名同purl对数"],
            item["重复对数"],
            item["文件名"],
        ),
        reverse=True,
    )

    category_counts = Counter()
    for candidate in candidates:
        for duplicate_type in candidate["重复类型"]:
            category_counts[duplicate_type] += 1

    return {
        "扫描目录": str(input_dir.resolve()),
        "JSON文件总数": len(all_files),
        "实际扫描文件数": len(selected_files),
        "是否仅扫描部分文件": max_files is not None and len(selected_files) < len(all_files),
        "扫描上限": max_files,
        "单文件超时秒": timeout_seconds,
        "扫描耗时秒": round(time.perf_counter() - started_at, 3),
        "候选文件数": len(candidates),
        "同名不同purl文件数": category_counts["同名不同purl"],
        "同名同purl文件数": category_counts["同名同purl"],
        "两种重复类型均存在的文件数": sum(
            1
            for candidate in candidates
            if len(candidate["重复类型"]) == 2
        ),
        "跳过文件数": len(skipped),
        "跳过文件": skipped,
        "候选文件": candidates,
    }


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 和两空格缩进写出 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(value, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="扫描重复组件候选 SBOM")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=1.0,
        help="单文件解析及分析超过该秒数时跳过，默认 1 秒",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="最多扫描多少个 JSON 文件；默认扫描全部",
    )
    return parser.parse_args()


def main() -> None:
    """执行完整扫描并打印中文汇总。"""

    args = parse_args()
    if args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds 必须大于 0")
    if args.max_files is not None and args.max_files <= 0:
        raise ValueError("--max-files 必须大于 0")
    if not args.input_dir.is_dir():
        raise NotADirectoryError(f"扫描目录不存在或不是目录：{args.input_dir}")

    result = scan_directory(
        input_dir=args.input_dir,
        timeout_seconds=args.timeout_seconds,
        max_files=args.max_files,
    )
    write_json(args.output, result)

    print(f"JSON 文件总数：{result['JSON文件总数']}")
    print(f"实际扫描文件数：{result['实际扫描文件数']}")
    print(f"候选文件数：{result['候选文件数']}")
    print(f"含同名不同 purl 的文件数：{result['同名不同purl文件数']}")
    print(f"含同名同 purl 的文件数：{result['同名同purl文件数']}")
    print(f"跳过文件数：{result['跳过文件数']}")
    print(f"扫描耗时：{result['扫描耗时秒']} 秒")
    print(f"候选输出：{args.output}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
