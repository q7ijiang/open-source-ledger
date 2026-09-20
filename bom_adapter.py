#!/usr/bin/env python3
"""把真实 CycloneDX BOM 转换为统一的资产记录。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_BOM_PATH = BASE_DIR / "sample_bom.json"
DEFAULT_ASSETS_PATH = BASE_DIR / "assets.json"


def load_json(path: Path) -> Any:
    """读取 UTF-8 JSON，并把常见读取错误转换为中文提示。"""

    try:
        with path.open("r", encoding="utf-8") as input_file:
            return json.load(input_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"找不到 BOM 文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"BOM 不是合法 JSON：{path}，位置：{exc.pos}") from exc


def clean_text(value: Any) -> str | None:
    """把字段转换为去首尾空格的文本；空值返回 None。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_list(value: Any) -> list[Any]:
    """把单值或列表统一转换为列表。"""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def asset_type_for(component: dict[str, Any]) -> str:
    """把 CycloneDX 组件类型映射为项目内部资产类型。"""

    component_type = clean_text(component.get("type")) or ""
    if component_type in {"machine-learning-model", "model"}:
        return "model"
    if component_type in {"data", "dataset"}:
        return "dataset"
    if component_type == "repository":
        return "repository"
    return "package"


def extract_licenses(component: dict[str, Any]) -> list[str]:
    """兼容 CycloneDX 的许可证对象、表达式和字符串写法。"""

    names: list[str] = []

    def add_name(raw_license: Any) -> None:
        if isinstance(raw_license, str):
            name = clean_text(raw_license)
        elif isinstance(raw_license, dict):
            license_value = raw_license.get("license")
            if isinstance(license_value, dict):
                name = clean_text(license_value.get("id")) or clean_text(
                    license_value.get("name")
                )
            elif isinstance(license_value, str):
                name = clean_text(license_value)
            else:
                name = (
                    clean_text(raw_license.get("expression"))
                    or clean_text(raw_license.get("id"))
                    or clean_text(raw_license.get("name"))
                )
        else:
            name = None

        if name and name not in names:
            names.append(name)

    for entry in as_list(component.get("licenses")):
        add_name(entry)

    # 兼容少量工具把单许可证放在 license 字段中的非标准写法。
    if not names and component.get("license") is not None:
        add_name(component["license"])

    return names


def extract_purls(component: dict[str, Any]) -> list[str]:
    """提取 purl，并在必要时回退到以 pkg: 开头的 bom-ref。"""

    purls: list[str] = []
    for raw_purl in as_list(component.get("purl")):
        purl = clean_text(raw_purl)
        if purl and purl not in purls:
            purls.append(purl)

    bom_ref = clean_text(component.get("bom-ref"))
    if bom_ref and bom_ref.startswith("pkg:") and bom_ref not in purls:
        purls.append(bom_ref)

    return purls


def is_location_property(property_name: str) -> bool:
    """判断组件属性名是否表示文件或层内出现位置。"""

    normalized = property_name.lower()
    return any(
        token in normalized
        for token in ("location", "occurrence", "filepath", "file_path", "path")
    )


def evidence_entry(
    source_field: str,
    raw_value: Any,
    retrieved_at: str,
    source_url: str | None = None,
) -> dict[str, Any]:
    """按统一结构创建一条证据。"""

    return {
        "evidence_level": "A",
        "source_api": "cyclonedx",
        "source_url": source_url,
        "source_field": source_field,
        "retrieved_at": retrieved_at,
        "status": "ok",
        "raw_value": raw_value,
    }


def extract_evidence_chain(
    component: dict[str, Any], retrieved_at: str
) -> list[dict[str, Any]]:
    """提取许可证、标准 occurrence 和工具位置属性证据。"""

    evidence_chain: list[dict[str, Any]] = []

    for entry in as_list(component.get("licenses")):
        evidence_chain.append(
            evidence_entry(
                "components[].licenses",
                json.dumps(entry, ensure_ascii=False),
                retrieved_at,
            )
        )

    evidence = component.get("evidence")
    if isinstance(evidence, dict):
        for occurrence in as_list(evidence.get("occurrences")):
            if not isinstance(occurrence, dict):
                continue
            location = clean_text(occurrence.get("location"))
            if location:
                evidence_chain.append(
                    evidence_entry(
                        "components[].evidence.occurrences[].location",
                        location,
                        retrieved_at,
                    )
                )

    # Trivy 使用 FilePath，Syft 使用 syft:location:0:path，
    # 两者都不在标准 evidence.occurrences 中，需要从 properties 提取。
    for raw_property in as_list(component.get("properties")):
        if not isinstance(raw_property, dict):
            continue
        property_name = clean_text(raw_property.get("name")) or ""
        if not is_location_property(property_name):
            continue
        raw_value = clean_text(raw_property.get("value"))
        if raw_value:
            evidence_chain.append(
                evidence_entry(
                    f"components[].properties[name={property_name}]",
                    raw_value,
                    retrieved_at,
                    clean_text(raw_property.get("url")),
                )
            )

    return evidence_chain


def flatten_components(
    components: Iterable[Any],
) -> Iterable[tuple[dict[str, Any], str]]:
    """深度优先展开 components 及其嵌套 components。"""

    for index, component in enumerate(components):
        if not isinstance(component, dict):
            continue
        yield component, f"components[{index}]"
        nested = component.get("components")
        if isinstance(nested, list):
            for nested_component, nested_path in flatten_components(nested):
                yield nested_component, f"{nested_path}/components[]"


def find_components(document: dict[str, Any]) -> tuple[list[Any], str]:
    """定位 CycloneDX components，并明确识别 PIQUE 评估结果。"""

    components = document.get("components")
    if isinstance(components, list):
        return components, "components"

    # PIQUE 输出会包含 measures/diagnostics，但没有原始组件字段。
    if any(key in document for key in ("factors", "measures", "diagnostics")):
        raise ValueError(
            "输入是 PIQUE 评估结果，不是原始 CycloneDX BOM；"
            "文件中没有 components，packages 数组也不含组件数据。"
        )

    # 兼容把 CycloneDX 文档包在 bom、sbom 或 document 下的结构。
    for key in ("bom", "sbom", "document", "cyclonedx"):
        nested = document.get(key)
        if isinstance(nested, dict):
            nested_components = nested.get("components")
            if isinstance(nested_components, list):
                return nested_components, f"{key}.components"

    raise ValueError(
        "输入 JSON 中没有可解析的 components 数组；"
        "请确认文件是原始 CycloneDX BOM。"
    )


def convert_component(
    component: dict[str, Any],
    retrieved_at: str,
    source_file: str,
    snapshot_id: str,
) -> dict[str, Any]:
    """把单个 CycloneDX 组件转换为统一资产记录。"""

    asset_type = asset_type_for(component)
    name = clean_text(component.get("name"))
    if not name:
        name = "(未命名组件)"

    licenses = extract_licenses(component)
    return {
        "canonical_id": f"{asset_type}:{name}",
        "asset_type": asset_type,
        "name": name,
        "version": clean_text(component.get("version")) or "",
        "purls": extract_purls(component),
        "license": "; ".join(licenses),
        "evidence_chain": extract_evidence_chain(component, retrieved_at),
        "snapshot_id": snapshot_id,
        "source_file": source_file,
    }


def convert_bom(
    bom: dict[str, Any],
    source_file: str,
    snapshot_id: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """解析 BOM 并返回资产数组。"""

    raw_components, _ = find_components(bom)
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    assets: list[dict[str, Any]] = []

    for component, _ in flatten_components(raw_components):
        assets.append(
            convert_component(
                component,
                retrieved_at,
                source_file,
                snapshot_id,
            )
        )
        if limit is not None and len(assets) >= limit:
            break

    return assets


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 和两空格缩进写出 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(value, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="把 CycloneDX BOM 转换为资产 JSON")
    parser.add_argument("--input", type=Path, default=DEFAULT_BOM_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_ASSETS_PATH)
    parser.add_argument("--snapshot-id", default="basic-20260918")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最多解析的组件数；默认解析全部组件。",
    )
    return parser.parse_args()


def main() -> None:
    """执行 BOM 解析并输出统计。"""

    args = parse_args()
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit 必须大于 0。")

    bom = load_json(args.input)
    if not isinstance(bom, dict):
        raise ValueError(f"BOM 根节点必须是对象：{args.input}")

    try:
        assets = convert_bom(
            bom=bom,
            source_file=str(args.input.resolve()),
            snapshot_id=args.snapshot_id,
            limit=args.limit,
        )
    except ValueError as exc:
        print(f"解析失败：{exc}", file=sys.stderr)
        raise SystemExit(2) from None
    write_json(args.output, assets)

    licenses = {
        item.strip()
        for asset in assets
        for item in str(asset.get("license", "")).split(";")
        if item.strip()
    }
    evidence_count = sum(len(asset.get("evidence_chain", [])) for asset in assets)

    print(f"读取 BOM：{args.input}")
    print(f"组件数：{len(assets)}")
    print(f"许可证种类数：{len(licenses)}")
    print(f"evidence 条数：{evidence_count}")
    print(f"资产输出：{args.output}")


if __name__ == "__main__":
    # 在 Windows 终端中显式使用 UTF-8，避免中文提示乱码。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
