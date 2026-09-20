#!/usr/bin/env python3
"""只读检查 MSU CycloneDX SBOM 中的实体对齐辅助信号。"""

from __future__ import annotations

import argparse
import json
import sys
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


DEFAULT_INPUT_DIR = Path(r"D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms")
BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = BASE_DIR / "work" / "msu_signal_scan.json"
HASH_ALGORITHMS = {"sha256", "sha1", "sha512", "sha384", "sha224", "md5"}
LAYER_PREFIXES = ("sha1:", "sha224:", "sha256:", "sha384:", "sha512:", "md5:")


def clean_text(value: Any) -> str | None:
    """把值转换为去首尾空白的文本；空值返回 None。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def flatten_components(components: Iterable[Any]) -> Iterable[dict[str, Any]]:
    """深度优先展开顶层与嵌套 components。"""

    for raw_component in components:
        if not isinstance(raw_component, dict):
            continue
        yield raw_component
        nested = raw_component.get("components")
        if isinstance(nested, list):
            yield from flatten_components(nested)


def normalize_hash_algorithm(value: Any) -> str | None:
    """统一 CycloneDX 哈希算法名称。"""

    algorithm = clean_text(value)
    if not algorithm:
        return None
    normalized = algorithm.lower().replace("-", "").replace("_", "")
    aliases = {
        "sha256": "sha256",
        "sha1": "sha1",
        "sha512": "sha512",
        "sha384": "sha384",
        "sha224": "sha224",
        "md5": "md5",
    }
    return aliases.get(normalized)


def extract_hashes(component: dict[str, Any]) -> dict[str, set[str]]:
    """提取组件自身及 evidence 中常见位置的哈希值。"""

    result: dict[str, set[str]] = {}
    candidates: list[dict[str, Any]] = []

    raw_hashes = component.get("hashes")
    if isinstance(raw_hashes, list):
        candidates.extend(item for item in raw_hashes if isinstance(item, dict))

    evidence = component.get("evidence")
    if isinstance(evidence, dict):
        for key in ("hashes", "fileHashes"):
            raw = evidence.get(key)
            if isinstance(raw, list):
                candidates.extend(item for item in raw if isinstance(item, dict))

    for item in candidates:
        algorithm = normalize_hash_algorithm(
            item.get("alg") or item.get("algorithm") or item.get("hashAlgorithm")
        )
        digest = clean_text(item.get("content") or item.get("value") or item.get("hash"))
        if algorithm and digest:
            result.setdefault(algorithm, set()).add(digest.lower())
    return result


def external_reference_types(component: dict[str, Any]) -> Counter:
    """统计组件 externalReferences 的 type 分布。"""

    counter: Counter = Counter()
    references = component.get("externalReferences")
    if not isinstance(references, list):
        return counter
    for reference in references:
        if not isinstance(reference, dict):
            continue
        reference_type = clean_text(reference.get("type"))
        if reference_type:
            counter[reference_type.lower()] += 1
    return counter


def extract_external_urls(component: dict[str, Any]) -> set[str]:
    """提取 website、distribution、vcs 与 repository 类 URL。"""

    urls: set[str] = set()
    references = component.get("externalReferences")
    if not isinstance(references, list):
        return urls
    wanted = {"website", "distribution", "vcs", "repository", "source-distribution"}
    for reference in references:
        if not isinstance(reference, dict):
            continue
        reference_type = (clean_text(reference.get("type")) or "").lower()
        url = clean_text(reference.get("url"))
        if reference_type in wanted and url:
            urls.add(url)
    return urls


def extract_authors(component: dict[str, Any]) -> set[str]:
    """提取 author、publisher、supplier、maintainers 等作者型字段。"""

    authors: set[str] = set()
    for key in ("author", "publisher"):
        value = clean_text(component.get(key))
        if value:
            authors.add(value)

    supplier = component.get("supplier")
    if isinstance(supplier, dict):
        supplier_name = clean_text(supplier.get("name"))
        if supplier_name:
            authors.add(supplier_name)

    maintainers = component.get("maintainers")
    if isinstance(maintainers, list):
        for maintainer in maintainers:
            if isinstance(maintainer, dict):
                name = clean_text(maintainer.get("name"))
            else:
                name = clean_text(maintainer)
            if name:
                authors.add(name)

    evidence = component.get("evidence")
    if isinstance(evidence, dict):
        for key in ("author", "authors", "maintainer", "maintainers"):
            raw_value = evidence.get(key)
            values = raw_value if isinstance(raw_value, list) else [raw_value]
            for value in values:
                if isinstance(value, dict):
                    value = value.get("name")
                text = clean_text(value)
                if text:
                    authors.add(text)

    return authors


def property_location_values(component: dict[str, Any]) -> tuple[set[str], set[str]]:
    """从 properties 中拆出具体文件路径与 layerID。"""

    file_locations: set[str] = set()
    layer_locations: set[str] = set()
    properties = component.get("properties")
    if not isinstance(properties, list):
        return file_locations, layer_locations

    for raw_property in properties:
        if not isinstance(raw_property, dict):
            continue
        name = clean_text(raw_property.get("name")) or ""
        value = clean_text(raw_property.get("value"))
        if not value:
            continue
        lower_name = name.lower()
        if "layer" in lower_name or value.lower().startswith(LAYER_PREFIXES):
            layer_locations.add(value)
            continue
        if any(token in lower_name for token in ("location", "path", "filepath")):
            file_locations.add(value)
    return file_locations, layer_locations


def occurrence_locations(component: dict[str, Any]) -> set[str]:
    """提取标准 evidence.occurrences 中的文件位置。"""

    locations: set[str] = set()
    evidence = component.get("evidence")
    if not isinstance(evidence, dict):
        return locations
    occurrences = evidence.get("occurrences")
    if not isinstance(occurrences, list):
        return locations
    for occurrence in occurrences:
        if not isinstance(occurrence, dict):
            continue
        location = clean_text(occurrence.get("location"))
        if location:
            locations.add(location)
    return locations


def inspect_component(component: dict[str, Any], summary: dict[str, Any]) -> None:
    """检查单个组件并累加字段可用性统计。"""

    hashes = extract_hashes(component)
    refs = external_reference_types(component)
    urls = extract_external_urls(component)
    authors = extract_authors(component)
    property_files, property_layers = property_location_values(component)
    occurrence_files = occurrence_locations(component)
    file_locations = property_files | occurrence_files

    summary["组件总数"] += 1
    if hashes:
        summary["有哈希组件数"] += 1
    for algorithm in hashes:
        summary["哈希算法组件数"][algorithm] += 1
    if urls:
        summary["有homepage或仓库URL组件数"] += 1
    if authors:
        summary["有author或maintainer组件数"] += 1
    if file_locations:
        summary["有A级文件路径组件数"] += 1
    if property_layers:
        summary["有B级layerID组件数"] += 1
    if not file_locations and not property_layers:
        summary["C级无位置组件数"] += 1

    summary["externalReference类型组件数"].update(refs.keys())
    summary["作者字段来源组件数"]["author"] += int(bool(clean_text(component.get("author"))))
    summary["作者字段来源组件数"]["publisher"] += int(bool(clean_text(component.get("publisher"))))
    summary["作者字段来源组件数"]["supplier"] += int(
        isinstance(component.get("supplier"), dict)
    )
    summary["作者字段来源组件数"]["maintainers"] += int(
        isinstance(component.get("maintainers"), list)
    )
    summary["原始字段组件数"]["hashes"] += int(isinstance(component.get("hashes"), list))
    summary["原始字段组件数"]["externalReferences"] += int(
        isinstance(component.get("externalReferences"), list)
    )
    summary["原始字段组件数"]["author"] += int("author" in component)


def new_summary(path: Path | None = None) -> dict[str, Any]:
    """创建一个文件级或目录级统计对象。"""

    summary: dict[str, Any] = {
        "文件": str(path.resolve()) if path is not None else None,
        "组件总数": 0,
        "有哈希组件数": 0,
        "哈希算法组件数": Counter(),
        "有homepage或仓库URL组件数": 0,
        "有author或maintainer组件数": 0,
        "有A级文件路径组件数": 0,
        "有B级layerID组件数": 0,
        "C级无位置组件数": 0,
        "externalReference类型组件数": Counter(),
        "作者字段来源组件数": Counter(),
        "原始字段组件数": Counter(),
    }
    return summary


def merge_summary(target: dict[str, Any], source: dict[str, Any]) -> None:
    """把一个文件的统计并入目录级统计。"""

    scalar_keys = (
        "组件总数",
        "有哈希组件数",
        "有homepage或仓库URL组件数",
        "有author或maintainer组件数",
        "有A级文件路径组件数",
        "有B级layerID组件数",
        "C级无位置组件数",
    )
    for key in scalar_keys:
        target[key] += source[key]
    for key in (
        "哈希算法组件数",
        "externalReference类型组件数",
        "作者字段来源组件数",
        "原始字段组件数",
    ):
        target[key].update(source[key])


def jsonable_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """把 Counter 转成可序列化字典。"""

    return {
        key: (dict(sorted(value.items())) if isinstance(value, Counter) else value)
        for key, value in summary.items()
    }


def inspect_file(path: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """解析并检查一个文件，出错时返回可读原因。"""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, {"文件": str(path.resolve()), "错误": str(exc)}

    if not isinstance(document, dict) or document.get("bomFormat") != "CycloneDX":
        return None, {"文件": str(path.resolve()), "错误": "不是 CycloneDX JSON"}

    components = document.get("components")
    if not isinstance(components, list):
        return None, {"文件": str(path.resolve()), "错误": "顶层 components 不是数组"}

    summary = new_summary(path)
    for component in flatten_components(components):
        inspect_component(component, summary)
    return summary, None


def select_sample_files(files: list[Path], count: int = 5) -> list[Path]:
    """按排序后的均匀位置抽取样本，确保覆盖整个文件名区间。"""

    if len(files) <= count:
        return files
    indices = [round(index * (len(files) - 1) / (count - 1)) for index in range(count)]
    return [files[index] for index in indices]


def main() -> None:
    """运行抽样或全量扫描并输出 JSON 统计。"""

    parser = argparse.ArgumentParser(description="检查 MSU SBOM 对齐信号")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--sample", type=int, default=0, help="大于 0 时仅均匀抽取指定数量")
    args = parser.parse_args()

    files = sorted(args.input_dir.rglob("*.json"))
    selected_files = (
        select_sample_files(files, args.sample) if args.sample > 0 else files
    )
    started_at = time.perf_counter()
    aggregate = new_summary()
    file_summaries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for position, path in enumerate(selected_files, start=1):
        summary, error = inspect_file(path)
        if error is not None:
            errors.append(error)
            continue
        assert summary is not None
        file_summaries.append(jsonable_summary(summary))
        merge_summary(aggregate, summary)
        if position % 100 == 0:
            print(f"已检查 {position}/{len(selected_files)} 个文件")

    document = {
        "输入目录": str(args.input_dir.resolve()),
        "发现JSON文件数": len(files),
        "实际检查文件数": len(selected_files),
        "抽样模式": args.sample > 0,
        "抽样数量": args.sample if args.sample > 0 else None,
        "检查耗时秒": round(time.perf_counter() - started_at, 6),
        "解析失败数": len(errors),
        "文件级可用性": {
            "含哈希文件数": sum(
                item["有哈希组件数"] > 0 for item in file_summaries
            ),
            "含homepage或仓库URL文件数": sum(
                item["有homepage或仓库URL组件数"] > 0
                for item in file_summaries
            ),
            "含author或maintainer文件数": sum(
                item["有author或maintainer组件数"] > 0
                for item in file_summaries
            ),
            "含A级文件路径文件数": sum(
                item["有A级文件路径组件数"] > 0
                for item in file_summaries
            ),
            "含B级layerID文件数": sum(
                item["有B级layerID组件数"] > 0
                for item in file_summaries
            ),
        },
        "汇总": jsonable_summary(aggregate),
        "文件统计": file_summaries,
        "错误": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(document["汇总"], ensure_ascii=False, indent=2))
    print(f"结果输出：{args.output.resolve()}")


if __name__ == "__main__":
    # 在 Windows 终端中显式使用 UTF-8，避免中文统计键乱码。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
