#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把数据管道产出的 assets/edges 导出为标准 CycloneDX BOM。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import license_db


_COMPONENT_TYPE_MAP = {
    "model": "machine-learning-model",
    "dataset": "data",
    "package": "library",
    "repository": "application",
}


def _load_json_list(path: Path, label: str) -> list[dict[str, Any]]:
    """读取 JSON 数组，并把错误转换为清楚的中文提示。"""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"找不到{label}文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}文件不是合法 JSON：{path}，位置：{exc.pos}") from exc

    if not isinstance(raw, list):
        raise ValueError(f"{label}文件根节点必须是数组：{path}")
    return [item for item in raw if isinstance(item, dict)]


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_purl(asset: dict[str, Any]) -> str | None:
    purls = asset.get("purls")
    if isinstance(purls, list):
        for raw_purl in purls:
            purl = _clean_text(raw_purl)
            if purl:
                return purl
    return _clean_text(asset.get("purl"))


def _fallback_purl(canonical_id: str) -> str | None:
    """为没有外部 purl 的内部节点生成可逆 purl。

    ModelScope 聚合血缘节点没有真实 purl，但 --diff 需要 ancestors[].purl
    才能恢复离线边。这里由 canonical_id 反向构造稳定 purl，不改变标识算法。
    """
    asset_type, separator, rest = canonical_id.partition(":")
    if not separator or asset_type not in {"model", "dataset", "package"}:
        return None
    purl_type, path_separator, path = rest.partition("/")
    if not purl_type or not path_separator or not path:
        return None

    version = ""
    if "@" in path:
        path, version = path.rsplit("@", 1)
    purl = f"pkg:{purl_type}/{path}"
    return f"{purl}@{version}" if version else purl

def _license_object(license_text: str) -> dict[str, str]:
    """标准协议使用 SPDX id，未知协议保留原始 name。"""
    parts = license_db.split_license_text(license_text)
    if len(parts) == 1:
        rule = license_db.get_rule(parts[0])
        if rule is not None and rule.spdx_like:
            return {"id": rule.canonical_id}
    return {"name": license_text}


def _license_entry(asset: dict[str, Any]) -> dict[str, Any] | None:
    license_text = _clean_text(asset.get("license"))
    if not license_text:
        return None

    raw_chain = asset.get("evidence_chain")
    evidence_chain = (
        [item for item in raw_chain if isinstance(item, dict)]
        if isinstance(raw_chain, list)
        else []
    )

    evidence_level = None
    for item in evidence_chain:
        candidate = _clean_text(item.get("evidence_level"))
        if candidate:
            evidence_level = candidate
            break

    entry: dict[str, Any] = {"license": _license_object(license_text)}
    if evidence_level:
        entry["evidence_level"] = evidence_level
    if evidence_chain:
        entry["evidence_chain"] = evidence_chain
    return entry


def _component_properties(asset: dict[str, Any]) -> list[dict[str, str]]:
    properties: list[dict[str, str]] = []

    def add(name: str, value: Any) -> None:
        text = _clean_text(value)
        if text is not None:
            properties.append({"name": f"open-source-ledger:{name}", "value": text})

    add("snapshot_id", asset.get("snapshot_id"))
    add("risk_level", asset.get("risk_level"))
    add("decision", asset.get("decision"))
    add("decision_zh", asset.get("decision_zh"))
    add("aggregate", asset.get("aggregate"))
    add("count", asset.get("count"))
    add("source_file", asset.get("source_file"))
    add("simulation", asset.get("simulation"))
    add("simulation_reason", asset.get("simulation_reason"))
    add("simulation_original_license", asset.get("simulation_original_license"))
    add("simulation_target_license", asset.get("simulation_target_license"))
    add("historical_reconstruction", asset.get("historical_reconstruction"))
    add("historical_commit", asset.get("historical_commit"))
    add("historical_source_url", asset.get("historical_source_url"))
    add("lineage_role", asset.get("lineage_role"))
    add("lineage_depth", asset.get("lineage_depth"))
    add("lineage_status", asset.get("lineage_status"))
    add("lineage_complete", asset.get("lineage_complete"))
    add("lineage_truncation_reason", asset.get("lineage_truncation_reason"))
    add("max_upstream_depth", asset.get("max_upstream_depth"))
    add("max_upstream_nodes", asset.get("max_upstream_nodes"))
    add("resolved_upstream_count", asset.get("resolved_upstream_count"))
    add("max_depth_seen", asset.get("max_depth_seen"))
    if isinstance(asset.get("unresolved_upstream_models"), list):
        add(
            "unresolved_upstream_models_json",
            json.dumps(asset["unresolved_upstream_models"], ensure_ascii=False, sort_keys=True),
        )
    if isinstance(asset.get("lineage_cycles"), list):
        add(
            "lineage_cycles_json",
            json.dumps(asset["lineage_cycles"], ensure_ascii=False, sort_keys=True),
        )
    ai_analysis = asset.get("ai_analysis")
    if isinstance(ai_analysis, dict):
        add("ai_status", ai_analysis.get("status"))
        add("ai_evidence_level", "C")
        add("ai_analysis_json", json.dumps(ai_analysis, ensure_ascii=False, sort_keys=True))
    project_context = asset.get("ai_project_context")
    if isinstance(project_context, dict):
        add("ai_project_context_json", json.dumps(project_context, ensure_ascii=False, sort_keys=True))
    return properties


def _build_components(
    assets: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    components: list[dict[str, Any]] = []
    canonical_to_purl: dict[str, str] = {}

    for asset in assets:
        canonical_id = _clean_text(asset.get("canonical_id"))
        name = _clean_text(asset.get("name")) or canonical_id
        if not canonical_id or not name:
            continue

        component: dict[str, Any] = {
            "bom-ref": canonical_id,
            "type": _COMPONENT_TYPE_MAP.get(
                _clean_text(asset.get("asset_type")) or "",
                "library",
            ),
            "name": name,
        }

        version = _clean_text(asset.get("version"))
        if version:
            component["version"] = version

        purl = _first_purl(asset)
        if not purl:
            purl = _fallback_purl(canonical_id)
        if purl:
            component["purl"] = purl
            canonical_to_purl[canonical_id] = purl

        license_entry = _license_entry(asset)
        if license_entry is not None:
            component["licenses"] = [license_entry]

        properties = _component_properties(asset)
        if properties:
            component["properties"] = properties

        components.append(component)

    return components, canonical_to_purl


def _attach_ancestors(
    components: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    canonical_to_purl: dict[str, str],
) -> None:
    components_by_ref = {
        str(component["bom-ref"]): component
        for component in components
        if component.get("bom-ref")
    }

    for edge in edges:
        if _clean_text(edge.get("edge_type")) != "derived_from":
            continue
        source = _clean_text(edge.get("source"))
        target = _clean_text(edge.get("target"))
        if not source or not target or source not in components_by_ref:
            continue

        ancestor: dict[str, Any] = {"ref": target}
        target_purl = canonical_to_purl.get(target)
        if target_purl:
            ancestor["purl"] = target_purl

        evidence_level = _clean_text(edge.get("evidence_level"))
        if evidence_level:
            ancestor["evidence_level"] = evidence_level
        source_field = _clean_text(edge.get("source_field"))
        if source_field:
            ancestor["source_field"] = source_field

        ancestor_key = (
            ancestor.get("ref"),
            ancestor.get("purl"),
            ancestor.get("evidence_level"),
            ancestor.get("source_field"),
        )
        component = components_by_ref[source]
        pedigree = component.setdefault("pedigree", {})
        ancestors = pedigree.setdefault("ancestors", [])
        existing = {
            (
                item.get("ref"),
                item.get("purl"),
                item.get("evidence_level"),
                item.get("source_field"),
            )
            for item in ancestors
            if isinstance(item, dict)
        }
        if ancestor_key not in existing:
            ancestors.append(ancestor)


def _build_dependencies(
    components: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    refs = [
        str(component["bom-ref"])
        for component in components
        if component.get("bom-ref")
    ]
    known_refs = set(refs)
    depends_on: dict[str, list[str]] = {ref: [] for ref in refs}
    seen: set[tuple[str, str]] = set()

    for edge in edges:
        if _clean_text(edge.get("edge_type")) != "depends_on":
            continue
        source = _clean_text(edge.get("source"))
        target = _clean_text(edge.get("target"))
        if (
            not source
            or not target
            or source not in known_refs
            or target not in known_refs
        ):
            continue
        signature = (source, target)
        if signature in seen:
            continue
        seen.add(signature)
        depends_on[source].append(target)

    return [
        {"ref": ref, "dependsOn": depends_on[ref]}
        for ref in refs
    ]


def export_bom(
    assets_path: Path,
    edges_path: Path,
    output_path: Path,
) -> Path:
    """读取 assets/edges，写出 CycloneDX 1.7 BOM，返回输出路径。"""
    assets = _load_json_list(assets_path, "资产")
    edges = _load_json_list(edges_path, "血缘边")
    components, canonical_to_purl = _build_components(assets)
    _attach_ancestors(components, edges, canonical_to_purl)
    dependencies = _build_dependencies(components, edges)

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now().astimezone().isoformat(),
        },
        "components": components,
        "dependencies": dependencies,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(bom, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出 CycloneDX 1.7 BOM")
    parser.add_argument("--assets", type=Path, required=True, help="assets.json 路径")
    parser.add_argument("--edges", type=Path, required=True, help="edges.json 路径")
    parser.add_argument("--output", type=Path, required=True, help="bom.json 输出路径")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        output = export_bom(args.assets, args.edges, args.output)
    except (FileNotFoundError, ValueError) as exc:
        print(f"BOM 导出失败：{exc}", file=sys.stderr)
        raise SystemExit(2) from None
    print(f"CycloneDX BOM 已写入：{output}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    main()
