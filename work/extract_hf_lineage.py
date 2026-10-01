# -*- coding: utf-8 -*-
"""B 交付补充：从真实 HF 模型 BOM 提取血缘边并验证模块 8（血缘图构建）。

背景：
A 的 data/hf_models_bom/ 下 9 份真实 Hugging Face 模型 BOM（CycloneDX 1.7）中，
7 份带 pedigree.ancestors、4 份带 modelCard.modelParameters.datasets，
但仓库内尚无将其转换为接口约定血缘边格式的工具。本脚本补齐该输入链路，
证明模块 8 可消费 A 的真实数据建图。

v0.3（2026-10-01）与主链路版本化对齐：
- 调用 bom_adapter.build_asset_identifiers() 生成 entity_key / 版本化 canonical_id，
  不再手拼 asset_type:name；
- 资产节点补齐 merge_status / reason_code / rule_version / hashes / evidence_chain；
- 边证据等级由 A 改为 B：源数据虽是 HF 官方模型卡字段，但载体是 cdxgen 产出的
  CycloneDX BOM，按 docs/接口约定.md v0.2「工具产物或结构化依赖证据」归为 B 级；
- 保留全部 HF 特化能力：递归展开 pedigree.ancestors、数据集 purl 归一化、
  query 剥离、缺失祖先自动补建、18 节点 / 12 边演示。

用法：
    python work/extract_hf_lineage.py \
        --bom-dir data/hf_models_bom --output-dir out/hf_lineage

输出（均符合 docs/接口约定.md v0.2）：
    out/hf_lineage/assets.json   资产节点（model / dataset，版本化 canonical_id）
    out/hf_lineage/edges.json    血缘边（derived_from / trained_on，证据 B 级）
    out/hf_lineage/graph.json    模块 8 构建的血缘图（含 SCC 与统计）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bom_adapter as ba
import build_graph as bg

RULE_VERSION = "merge-policy-v2"
EDGE_EVIDENCE_LEVEL = "B"  # 见 docstring：CycloneDX 工具产物按接口约定为 B 级


def component_license(component: dict) -> str | None:
    """从 CycloneDX licenses 提取许可证名（多个以 ';' 连接）。

    HF BOM 的 license 对象可能用 id（SPDX，如 Apache-2.0）或 name
    （原始名，如 LLAMA2）标识，两者都取。
    """
    parts = []
    for entry in component.get("licenses", []) or []:
        license_info = entry.get("license", {}) if isinstance(entry, dict) else {}
        name = (
            license_info.get("name")
            or license_info.get("id")
            or (entry.get("name") if isinstance(entry, dict) else None)
        )
        if name:
            parts.append(str(name))
    if not parts:
        return None
    return "; ".join(parts)


def component_hashes(component: dict) -> list[dict]:
    """提取 CycloneDX 组件哈希（复用 bom_adapter 的兼容逻辑）。"""
    return ba.extract_component_hashes(component)


def node(
    asset_type: str,
    name: str,
    version: str | None,
    purls: list[str],
    license_value: str | None,
    snapshot_id: str,
    evidence_chain: list[dict],
    source_file: str,
    backfill_map: dict[str, str] | None = None,
) -> dict:
    """构造符合接口约定 v0.2 的资产节点（entity_key + 版本化 canonical_id）。

    未经过模块 2 合并的资产按独立实体处理：merge_status=KEPT_SEPARATE，
    reason_code=NO_MERGE_CANDIDATE。
    backfill_map：entity_key -> 带版本 canonical_id；命中时把无版本引用
    对齐到该版本化 ID（祖先版本补齐，见 extract() docstring）。
    """
    entity_key, canonical_id, identities = ba.build_asset_identifiers(
        asset_type=asset_type,
        name=name,
        version=version,
        purls=purls,
    )
    # 有 purl 坐标时，展示名优先用解析出的 namespace/name（与 entity_key 口径一致）
    if identities:
        primary = identities[0]
        parsed_name = "/".join(
            part for part in (primary.namespace, primary.name) if part
        )
        if parsed_name:
            name = parsed_name
    filled = (backfill_map or {}).get(entity_key)
    if filled and filled != canonical_id:
        canonical_id = filled
        if "@" in filled:
            version = filled.split("@", 1)[1]
    return {
        "entity_key": entity_key,
        "canonical_id": canonical_id,
        "asset_type": asset_type,
        "name": name,
        "version": version,
        "purls": purls,
        "license": license_value,
        "evidence_chain": evidence_chain,
        "snapshot_id": snapshot_id,
        "merge_status": "KEPT_SEPARATE",
        "reason_code": "NO_MERGE_CANDIDATE",
        "rule_version": RULE_VERSION,
        "hashes": [],
        "source_file": source_file,
    }


def extract(
    bom_path: Path,
    backfill_map: dict[str, str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """从单个 BOM 提取资产节点与血缘边。

    backfill_map：entity_key -> 带版本 canonical_id 的映射。祖先引用
    （pedigree.ancestors）的 purl 常不带版本（如 GGUF 引用基座模型）；
    若全局存在同一 entity_key 的带版本主模型，则把无版本引用对齐到
    该版本化 canonical_id，保证同实体跨 BOM 引用归一（演示 18 节点/12 边）。
    """
    backfill_map = backfill_map or {}
    data = json.loads(bom_path.read_text(encoding="utf-8"))
    snapshot_id = (
        data.get("serialNumber", "").removeprefix("urn:uuid:")
        or f"snapshot-{bom_path.stem}"
    )
    source_file = str(bom_path.resolve())
    assets: list[dict] = []
    edges: list[dict] = []

    components = data.get("components", []) or []
    if not components:
        return assets, edges

    def evidence(field: str, raw_value: object) -> dict:
        return {
            "evidence_level": EDGE_EVIDENCE_LEVEL,
            "source_api": "cyclonedx",
            "source_url": None,
            "source_field": field,
            "retrieved_at": None,
            "status": "ok",
            "raw_value": raw_value,
        }

    # 主模型 = 第一个组件（cdxgen 生成的 HF BOM 惯例）
    model = components[0]
    model_name = f"{model.get('group', '')}/{model.get('name', '')}".strip("/")
    model_purl = model.get("purl")
    model_purls = [model_purl] if model_purl else []
    model_chain: list[dict] = []

    # derived_from：pedigree.ancestors（递归展开，保留全部祖先）
    def ancestors_of(component: dict) -> list[dict]:
        out = []
        for anc in component.get("pedigree", {}).get("ancestors", []) or []:
            if not isinstance(anc, dict):
                continue
            out.append(anc)
            out.extend(ancestors_of(anc))
        return out

    ancestors = ancestors_of(model)
    if ancestors:
        model_chain.append(
            evidence(
                "pedigree.ancestors",
                [anc.get("purl") or anc.get("bom-ref") for anc in ancestors],
            )
        )

    # trained_on：modelCard.modelParameters.datasets
    datasets = (
        model.get("modelCard", {})
        .get("modelParameters", {})
        .get("datasets", []) or []
    )
    if datasets:
        model_chain.append(
            evidence("modelCard.modelParameters.datasets", datasets)
        )

    assets.append(
        node(
            asset_type="model",
            name=model_name,
            version=model.get("version"),
            purls=model_purls,
            license_value=component_license(model),
            snapshot_id=snapshot_id,
            evidence_chain=model_chain,
            source_file=source_file,
            backfill_map=backfill_map,
        )
    )
    model_canonical = assets[-1]["canonical_id"]

    for anc in ancestors:
        anc_purl = anc.get("purl") or anc.get("bom-ref")
        anc_purls = [anc_purl] if anc_purl else []
        anc_name = (
            f"{anc.get('group', '')}/{anc.get('name', '')}".strip("/")
            or (anc.get("name") or "")
        )
        assets.append(
            node(
                asset_type="model",
                name=anc_name or "(未命名祖先)",
                version=anc.get("version"),
                purls=anc_purls,
                license_value=component_license(anc) or None,
                snapshot_id=snapshot_id,
                evidence_chain=[evidence("pedigree.ancestors", anc_purl)],
                source_file=source_file,
                backfill_map=backfill_map,
            )
        )
        edges.append({
            "source": model_canonical,
            "target": assets[-1]["canonical_id"],
            "edge_type": "derived_from",
            "evidence_level": EDGE_EVIDENCE_LEVEL,
            "source_field": "pedigree.ancestors",
            "snapshot_id": snapshot_id,
        })

    for entry in datasets:
        if not isinstance(entry, dict):
            entry = {"ref": None, "name": str(entry)}
        ref = str(entry.get("ref") or "").strip()
        ds_purls = [ref] if ref.startswith("pkg:") else []
        if ds_purls:
            # 名称由 node() 从 purl 坐标解析
            ds_name = None
        else:
            ds_name = entry.get("name") or (ref.split("/")[-1] if ref else None)
        assets.append(
            node(
                asset_type="dataset",
                name=ds_name or "(未命名数据集)",
                version=None,
                purls=ds_purls,
                license_value=None,
                snapshot_id=snapshot_id,
                evidence_chain=[evidence("modelCard.modelParameters.datasets", ref)],
                source_file=source_file,
                backfill_map=backfill_map,
            )
        )
        edges.append({
            "source": model_canonical,
            "target": assets[-1]["canonical_id"],
            "edge_type": "trained_on",
            "evidence_level": EDGE_EVIDENCE_LEVEL,
            "source_field": "modelCard.modelParameters.datasets",
            "snapshot_id": snapshot_id,
        })

    return assets, edges


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="从真实 HF BOM 提取血缘边并建图")
    parser.add_argument("--bom-dir", default="data/hf_models_bom", help="BOM 目录")
    parser.add_argument("--output-dir", default="out/hf_lineage", help="输出目录")
    args = parser.parse_args(argv)

    bom_dir = Path(args.bom_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    bom_paths = sorted(bom_dir.glob("*.json"))

    # 第一遍：收集所有主模型的 entity_key -> 带版本 canonical_id，
    # 供祖先引用做版本补齐（GGUF 等派生模型的 pedigree 引用常不带版本）。
    backfill_map: dict[str, str] = {}
    for bom_path in bom_paths:
        data = json.loads(bom_path.read_text(encoding="utf-8"))
        comps = data.get("components", []) or []
        if not comps:
            continue
        model = comps[0]
        model_purl = model.get("purl")
        if not model_purl:
            continue
        model_name = f"{model.get('group', '')}/{model.get('name', '')}".strip("/")
        entity_key, canonical_id, _ = ba.build_asset_identifiers(
            asset_type="model",
            name=model_name,
            version=model.get("version"),
            purls=[model_purl],
        )
        backfill_map.setdefault(entity_key, canonical_id)

    all_assets: dict[str, dict] = {}
    all_edges: list[dict] = []
    for bom_path in bom_paths:
        assets, edges = extract(bom_path, backfill_map)
        for asset in assets:
            all_assets.setdefault(asset["canonical_id"], asset)
        all_edges.extend(edges)

    assets = list(all_assets.values())
    assets_path = output_dir / "assets.json"
    edges_path = output_dir / "edges.json"
    assets_path.write_text(
        json.dumps(assets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    edges_path.write_text(
        json.dumps(all_edges, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    graph = bg.build_graph(assets, all_edges)
    canonical_to_scc, compressed = bg.compress_scc(graph)
    graph_dict = bg.graph_to_dict(graph, canonical_to_scc, compressed)
    graph_path = output_dir / "graph.json"
    graph_path.write_text(
        json.dumps(graph_dict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    stats = graph_dict
    print(f"真实 BOM 数：{len(list(bom_dir.glob('*.json')))}")
    print(f"资产节点：{stats['node_count']}（含缺失祖先自动补建）")
    print(f"血缘边：{stats['edge_count']}（derived_from + trained_on）")
    print(f"SCC 分量：{stats['scc_count']}")
    by_type: dict[str, int] = {}
    for edge in all_edges:
        by_type[edge["edge_type"]] = by_type.get(edge["edge_type"], 0) + 1
    print(f"边类型分布：{by_type}")
    print(f"证据等级：{EDGE_EVIDENCE_LEVEL}（CycloneDX BOM 工具产物）")
    print(f"已写入 {assets_path} / {edges_path} / {graph_path}")


if __name__ == "__main__":
    main()
