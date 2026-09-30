# -*- coding: utf-8 -*-
"""从资产 JSON 提取血缘边并输出 edges.json。

优先读取资产记录中已有的 pedigree.ancestors、modelCard.modelParameters.datasets
和 dependencies 字段。对于当前 bom_adapter.py 只保留 source_file、不保留这些
原始字段的情况，会按 source_file 回读原始 CycloneDX BOM，补回关系信息。

输出严格遵循 docs/接口约定.md：每条边包含 source、target、edge_type、
evidence_level、source_field 和 snapshot_id，边端点尽可能使用资产 canonical_id。

用法：
    python extract_edges.py --input outputs/assets.json --output outputs/edges.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = BASE_DIR / "outputs" / "assets.json"
DEFAULT_OUTPUT_PATH = BASE_DIR / "outputs" / "edges.json"

EDGE_TYPES = {"derived_from", "trained_on", "depends_on"}
PURL_PATTERN = re.compile(r"^pkg:([^/]+)/(.+)$", re.IGNORECASE)
ASSET_TYPE_FOR_COMPONENT_TYPE = {
    "machine-learning-model": "model",
    "model": "model",
    "data": "dataset",
    "dataset": "dataset",
    "repository": "repository",
}


def load_json(path: Path) -> Any:
    """读取 UTF-8 JSON，并提供明确的中文错误信息。"""

    try:
        with path.open("r", encoding="utf-8") as input_file:
            return json.load(input_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"找不到文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 格式错误：{path}，位置：{exc.pos}") from exc


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 和两空格缩进写出 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(value, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def clean_text(value: Any) -> str | None:
    """把值转换为去除首尾空白后的文本；空值返回 None。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_list(value: Any) -> list[Any]:
    """把单个值或列表统一为列表。"""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_assets(path: Path) -> list[dict[str, Any]]:
    """读取资产数组，并兼容 {"assets": [...]} / {"nodes": [...]} 包装。"""

    data = load_json(path)
    if isinstance(data, dict):
        data = data.get("assets", data.get("nodes"))
    if not isinstance(data, list):
        raise ValueError(f"资产文件顶层必须是数组，或包含 assets/nodes 数组：{path}")
    if not all(isinstance(asset, dict) for asset in data):
        raise ValueError(f"资产数组中的每一项都必须是对象：{path}")
    return data


def purl_without_version_and_qualifiers(purl: str) -> str:
    """去掉 purl 的版本、qualifier 和 subpath，只保留包身份。"""

    value = clean_text(purl) or ""
    if not value.startswith("pkg:"):
        return value
    value = value.split("#", 1)[0].split("?", 1)[0]
    if "@" in value:
        value = value.rsplit("@", 1)[0]
    return value


def purl_identity(purl: str) -> str | None:
    """生成用于匹配的统一 purl 身份键。"""

    base = purl_without_version_and_qualifiers(purl)
    match = PURL_PATTERN.match(base)
    if not match:
        return None

    purl_type = match.group(1).lower()
    purl_path = unquote(match.group(2)).strip("/")
    if not purl_path:
        return None
    if purl_type in {"pypi", "npm"}:
        purl_path = purl_path.lower()
    return f"{purl_type}/{purl_path}"


def purl_parts(purl: str) -> tuple[str, str, str, str] | None:
    """返回 purl 的 (类型, 命名空间, 名称, 完整路径)。"""

    base = purl_without_version_and_qualifiers(purl)
    match = PURL_PATTERN.match(base)
    if not match:
        return None

    purl_type = match.group(1).lower()
    decoded_path = unquote(match.group(2)).strip("/")
    segments = [segment for segment in decoded_path.split("/") if segment]
    if not segments:
        return None

    name = segments[-1]
    namespace = "/".join(segments[:-1])
    return purl_type, namespace, name, decoded_path


def asset_type_for_reference(reference: str, relation_kind: str) -> str:
    """根据边类型和引用形式推断目标资产类型。"""

    if reference.startswith("model:"):
        return "model"
    if reference.startswith("dataset:"):
        return "dataset"
    if reference.startswith("repository:"):
        return "repository"
    if reference.startswith("package:"):
        return "package"
    if relation_kind == "trained_on":
        return "dataset"

    parts = purl_parts(reference)
    if parts:
        purl_type, _, _, purl_path = parts
        if purl_type in {"pypi", "npm"}:
            return "package"
        lower_path = purl_path.lower()
        if "/datasets/" in f"/{lower_path}" or "huggingface.co/datasets" in lower_path:
            return "dataset"
        if purl_type == "huggingface":
            return "model"
    if relation_kind == "derived_from":
        return "model"
    return "package"


def fallback_canonical_id(reference: str, relation_kind: str) -> str:
    """把尚无对应资产的引用转换为稳定的 canonical_id。"""

    reference = clean_text(reference) or ""
    if ":" in reference and not reference.startswith("pkg:"):
        prefix, _ = reference.split(":", 1)
        if prefix in {"model", "package", "dataset", "repository"}:
            return reference

    asset_type = asset_type_for_reference(reference, relation_kind)
    parts = purl_parts(reference)
    if parts:
        purl_type, namespace, name, _ = parts
        if purl_type == "npm" and namespace.startswith("@"):
            name = f"{namespace}/{name}"
        return f"{asset_type}:{name}"

    leaf_name = reference.rstrip("/").split("/")[-1]
    return f"{asset_type}:{leaf_name or reference}"


class AssetIndex:
    """维护 canonical_id、purl 和名称索引，用于把引用映射到资产。"""

    def __init__(self, assets: Iterable[dict[str, Any]]) -> None:
        self.assets: list[dict[str, Any]] = list(assets)
        self.by_canonical_id: dict[str, dict[str, Any]] = {}
        self.by_purl_identity: dict[str, str] = {}
        self.by_name: dict[str, list[str]] = {}
        self._build()

    def _build(self) -> None:
        for asset in self.assets:
            canonical_id = clean_text(asset.get("canonical_id"))
            if not canonical_id:
                continue
            self.by_canonical_id.setdefault(canonical_id, asset)

            for purl in as_list(asset.get("purls")):
                identity = purl_identity(clean_text(purl) or "")
                if identity:
                    self.by_purl_identity.setdefault(identity, canonical_id)

            name = clean_text(asset.get("name"))
            if name:
                self.by_name.setdefault(name.lower(), []).append(canonical_id)

    def resolve(self, reference: Any, relation_kind: str) -> str | None:
        """把祖先、数据集或依赖引用解析为 canonical_id。"""

        text = clean_text(reference)
        if not text:
            return None

        if text in self.by_canonical_id:
            return text

        identity = purl_identity(text)
        if identity and identity in self.by_purl_identity:
            return self.by_purl_identity[identity]

        parts = purl_parts(text)
        name = parts[2] if parts else text.rstrip("/").split("/")[-1]
        candidates = self.by_name.get(name.lower(), [])
        if len(candidates) == 1:
            return candidates[0]

        canonical_id = fallback_canonical_id(text, relation_kind)
        if canonical_id in self.by_canonical_id:
            return canonical_id
        return canonical_id


def flatten_components(components: Iterable[Any]) -> Iterable[dict[str, Any]]:
    """递归展开 CycloneDX components。"""

    for component in components:
        if not isinstance(component, dict):
            continue
        yield component
        nested = component.get("components")
        if isinstance(nested, list):
            yield from flatten_components(nested)


def find_components(document: dict[str, Any]) -> list[dict[str, Any]]:
    """定位 CycloneDX BOM 中的 components，兼容常见包装。"""

    if isinstance(document.get("components"), list):
        return list(flatten_components(document["components"]))
    for key in ("bom", "sbom", "document", "cyclonedx"):
        nested = document.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("components"), list):
            return list(flatten_components(nested["components"]))
    return []


def component_asset_type(component: dict[str, Any]) -> str:
    """把 CycloneDX 组件类型映射为项目资产类型。"""

    component_type = clean_text(component.get("type")) or ""
    return ASSET_TYPE_FOR_COMPONENT_TYPE.get(component_type, "package")


def component_name(component: dict[str, Any]) -> str | None:
    """读取组件名称；缺失时返回 None。"""

    return clean_text(component.get("name"))


def component_identity_keys(component: dict[str, Any]) -> set[str]:
    """生成组件的 purl 与名称匹配键。"""

    keys: set[str] = set()
    for purl in as_list(component.get("purl")):
        identity = purl_identity(clean_text(purl) or "")
        if identity:
            keys.add(identity)

    bom_ref = clean_text(component.get("bom-ref"))
    if bom_ref:
        bom_ref_identity = purl_identity(bom_ref)
        if bom_ref_identity:
            keys.add(bom_ref_identity)

    name = component_name(component)
    if name:
        keys.add(f"name:{name.lower()}")
    return keys


class BomRelationIndex:
    """缓存原始 BOM 的组件关系与顶层 dependencies。"""

    def __init__(self) -> None:
        self._cache: dict[Path, dict[str, Any]] = {}

    def _load(self, source_path: Path) -> dict[str, Any]:
        resolved = source_path.resolve()
        if resolved not in self._cache:
            document = load_json(resolved)
            if not isinstance(document, dict):
                raise ValueError(f"原始 BOM 顶层必须是对象：{resolved}")

            components = find_components(document)
            component_by_key: dict[str, dict[str, Any]] = {}
            for component in components:
                for key in component_identity_keys(component):
                    component_by_key.setdefault(key, component)

            dependency_by_key: dict[str, list[str]] = {}
            for dependency in as_list(document.get("dependencies")):
                if not isinstance(dependency, dict):
                    continue
                targets = [
                    clean_text(target)
                    for target in as_list(dependency.get("dependsOn"))
                    if clean_text(target)
                ]
                keys: set[str] = set()
                ref_identity = purl_identity(clean_text(dependency.get("ref")) or "")
                if ref_identity:
                    keys.add(ref_identity)
                ref = clean_text(dependency.get("ref"))
                if ref:
                    keys.add(f"name:{ref.lower()}")
                for key in keys:
                    dependency_by_key.setdefault(key, []).extend(targets)

            self._cache[resolved] = {
                "components": component_by_key,
                "dependencies": dependency_by_key,
            }
        return self._cache[resolved]

    def component_for_asset(
        self, asset: dict[str, Any], source_path: Path
    ) -> dict[str, Any] | None:
        """在原 BOM 中定位资产对应的组件。"""

        index = self._load(source_path)
        for purl in as_list(asset.get("purls")):
            identity = purl_identity(clean_text(purl) or "")
            if identity and identity in index["components"]:
                return index["components"][identity]

        name = clean_text(asset.get("name"))
        if name and f"name:{name.lower()}" in index["components"]:
            return index["components"][f"name:{name.lower()}"]
        return None

    def dependencies_for_asset(
        self, asset: dict[str, Any], source_path: Path
    ) -> list[str]:
        """从原 BOM 顶层 dependencies 中读取资产自己的 dependsOn。"""

        index = self._load(source_path)
        targets: list[str] = []
        for purl in as_list(asset.get("purls")):
            identity = purl_identity(clean_text(purl) or "")
            if identity:
                targets.extend(index["dependencies"].get(identity, []))

        component = self.component_for_asset(asset, source_path)
        if component:
            for key in component_identity_keys(component):
                targets.extend(index["dependencies"].get(key, []))
        return targets


def relation_values(value: Any) -> list[str]:
    """兼容字符串、对象和列表形式，提取引用字符串。"""

    values: list[str] = []
    for item in as_list(value):
        if isinstance(item, str):
            reference = clean_text(item)
        elif isinstance(item, dict):
            reference = (
                clean_text(item.get("ref"))
                or clean_text(item.get("purl"))
                or clean_text(item.get("bom-ref"))
                or clean_text(item.get("name"))
            )
        else:
            reference = None
        if reference:
            values.append(reference)
    return values


def direct_relation_values(asset: dict[str, Any], field: str) -> list[str]:
    """从资产内按照字段路径提取引用。"""

    if field == "pedigree.ancestors":
        pedigree = asset.get("pedigree")
        return relation_values(pedigree.get("ancestors") if isinstance(pedigree, dict) else None)
    if field == "modelCard.modelParameters.datasets":
        model_card = asset.get("modelCard")
        parameters = model_card.get("modelParameters") if isinstance(model_card, dict) else None
        return relation_values(parameters.get("datasets") if isinstance(parameters, dict) else None)
    if field == "dependencies":
        return relation_values(asset.get("dependencies"))
    return []


def make_edge(
    source: str,
    target: str,
    edge_type: str,
    evidence_level: str,
    source_field: str,
    snapshot_id: str | None,
) -> dict[str, Any]:
    """按接口约定创建一条血缘边。"""

    return {
        "source": source,
        "target": target,
        "edge_type": edge_type,
        "evidence_level": evidence_level,
        "source_field": source_field,
        "snapshot_id": snapshot_id,
    }


def extract_edges(assets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """从资产列表提取、解析并去重全部血缘边。"""

    asset_index = AssetIndex(assets)
    bom_index = BomRelationIndex()
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    raw_edge_count = 0
    recovered_assets = 0
    unresolved_references = 0

    def add_edges(
        asset: dict[str, Any],
        field: str,
        references: list[str],
        edge_type: str,
        evidence_level: str,
    ) -> None:
        nonlocal raw_edge_count, unresolved_references
        source = clean_text(asset.get("canonical_id"))
        if not source:
            return
        snapshot_id = clean_text(asset.get("snapshot_id"))
        for reference in references:
            target = asset_index.resolve(reference, edge_type)
            if not target:
                continue
            raw_edge_count += 1
            if target not in asset_index.by_canonical_id:
                unresolved_references += 1
            signature = (source, target, edge_type)
            if signature in seen:
                continue
            seen.add(signature)
            edges.append(
                make_edge(
                    source,
                    target,
                    edge_type,
                    evidence_level,
                    field,
                    snapshot_id,
                )
            )

    for asset in assets:
        source = clean_text(asset.get("canonical_id"))
        if not source:
            continue

        ancestor_values = direct_relation_values(asset, "pedigree.ancestors")
        dataset_values = direct_relation_values(
            asset, "modelCard.modelParameters.datasets"
        )
        dependency_values = direct_relation_values(asset, "dependencies")

        source_file = clean_text(asset.get("source_file"))
        source_path = Path(source_file) if source_file else None
        if source_path and source_path.is_file():
            component = bom_index.component_for_asset(asset, source_path)
            if component:
                ancestry = component.get("pedigree")
                ancestors = (
                    ancestry.get("ancestors")
                    if isinstance(ancestry, dict)
                    else None
                )
                model_card = component.get("modelCard")
                parameters = (
                    model_card.get("modelParameters")
                    if isinstance(model_card, dict)
                    else None
                )
                datasets = (
                    parameters.get("datasets")
                    if isinstance(parameters, dict)
                    else None
                )
                recovered_ancestors = relation_values(ancestors)
                recovered_datasets = relation_values(datasets)
                if recovered_ancestors or recovered_datasets:
                    recovered_assets += 1
                ancestor_values.extend(recovered_ancestors)
                dataset_values.extend(recovered_datasets)

            dependency_values.extend(
                bom_index.dependencies_for_asset(asset, source_path)
            )

        add_edges(
            asset,
            "pedigree.ancestors",
            ancestor_values,
            "derived_from",
            "A",
        )
        add_edges(
            asset,
            "modelCard.modelParameters.datasets",
            dataset_values,
            "trained_on",
            "A",
        )
        add_edges(
            asset,
            "dependencies",
            dependency_values,
            "depends_on",
            "B",
        )

    missing_nodes = sorted(
        {
            endpoint
            for edge in edges
            for endpoint in (edge["source"], edge["target"])
            if endpoint not in asset_index.by_canonical_id
        }
    )
    stats = {
        "assets": len(assets),
        "raw_edge_count": raw_edge_count,
        "edge_count": len(edges),
        "duplicate_count": raw_edge_count - len(edges),
        "by_edge_type": dict(
            sorted(Counter(edge["edge_type"] for edge in edges).items())
        ),
        "recovered_assets": recovered_assets,
        "unresolved_reference_count": unresolved_references,
        "missing_node_count": len(missing_nodes),
        "missing_nodes": missing_nodes,
    }
    return edges, stats


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="从资产 JSON 提取血缘边")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """执行边提取并输出统计信息。"""

    args = parse_args(argv)
    assets = load_assets(args.input)
    edges, stats = extract_edges(assets)
    write_json(args.output, edges)

    print(f"读取资产：{args.input}（{stats['assets']} 个）")
    print(f"提取血缘边：{stats['edge_count']} 条")
    for edge_type in sorted(EDGE_TYPES):
        print(f"  {edge_type}: {stats['by_edge_type'].get(edge_type, 0)}")
    print(f"三元组去重：{stats['duplicate_count']} 条")
    print(f"从原始 BOM 补回关系的资产：{stats['recovered_assets']} 个")
    print(f"指向不存在的节点：{stats['missing_node_count']} 个")
    if stats["missing_nodes"]:
        preview = ", ".join(stats["missing_nodes"][:10])
        suffix = " ..." if len(stats["missing_nodes"]) > 10 else ""
        print(f"  示例：{preview}{suffix}")
    print(f"边输出：{args.output}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
