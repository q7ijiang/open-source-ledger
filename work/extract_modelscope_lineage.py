# -*- coding: utf-8 -*-
"""ModelScope 血缘提取器：从 ModelScope 官方 API 提取模型血缘并建图。

与 work/extract_hf_lineage.py 对称，但数据源是 ModelScope 官方 API 而非 CycloneDX BOM。
本脚本只做“数据入口适配”，调用：
  - modelscope_adapter（数据入口）
  - bom_adapter（复用标识生成，不改动）
  - build_graph（复用建图，不改动）

聚合降维：
    ModelScope 血缘端点只返回派生/祖先模型的分组计数（如
    SonModels: [{LineAgeType: "Adapters", Total: 1871}]），不为每个派生模型拉取详情，
    而是生成一个带 count 属性的聚合节点，避免一次展开 1871 个子模型。

证据等级：血缘边（官方 API 聚合计数）-> B；许可证（非标文本推断）-> C。

用法：
    python work/extract_modelscope_lineage.py \
        --model Qwen/Qwen-Image-2.1 --output-dir outputs/modelscope_validation
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bom_adapter as ba
import build_graph as bg
import modelscope_adapter as msa


RULE_VERSION = "merge-policy-v2"


def evidence(
    field: str,
    raw_value: object,
    level: str = msa.LINEAGE_EVIDENCE_LEVEL,
    status: str = "ok",
) -> dict:
    """构造一条 ModelScope 血缘证据。"""
    return {
        "evidence_level": level,
        "source_api": "modelscope",
        "source_url": None,
        "source_field": field,
        "retrieved_at": msa.utc_now(),
        "status": status,
        "raw_value": raw_value,
    }


def aggregate_node(
    ns: str,
    name: str,
    revision: str,
    role: str,
    lineage_type: str | None,
    lineage_type_ch: str | None,
    count: int,
    snapshot_id: str,
    source_file: str,
) -> dict:
    """为 SonModels/ParentsModels 的分组生成一个带 count 的聚合节点。"""
    label = lineage_type_ch or lineage_type or "related"
    entity_key = f"model:modelscope/{ns}/{name}:{role}:{lineage_type or 'related'}"
    canonical_id = f"{entity_key}@{revision}" if revision else entity_key
    display_name = f"{ns}/{name} · {label} (Total: {count})"
    return {
        "entity_key": entity_key,
        "canonical_id": canonical_id,
        "asset_type": "model",
        "name": display_name,
        "version": revision or "",
        "purls": [],
        "license": None,
        "evidence_chain": [
            evidence(
                "lineage",
                {
                    "LineAgeType": lineage_type,
                    "LineAgeTypeCh": lineage_type_ch,
                    "Total": count,
                },
            )
        ],
        "snapshot_id": snapshot_id,
        "merge_status": "KEPT_SEPARATE",
        "reason_code": "NO_MERGE_CANDIDATE",
        "rule_version": RULE_VERSION,
        "hashes": [],
        "source_file": source_file,
        "aggregate": True,
        "count": count,
    }


def extract(
    ns: str,
    name: str,
    snapshot_id: str,
    source_file: str,
) -> tuple[list[dict], list[dict]]:
    """拉取详情 + 血缘，产出资产节点与血缘边（含聚合节点）。"""
    assets: list[dict] = []
    edges: list[dict] = []

    try:
        detail = msa.fetch_model_detail(ns, name)
    except Exception:
        # 网络异常：返回空，由调用方给出中文提示。
        return assets, edges
    if not detail:
        return assets, edges

    current = msa.map_to_asset(detail, snapshot_id, source_file)
    assets.append(current)
    current_id = current["canonical_id"]
    revision = ba.clean_text(detail.get("Revision")) or ""

    try:
        lineage = msa.fetch_lineage(ns, name)
    except Exception:
        lineage = None
    if not lineage:
        # Data: null 或请求失败：仅保留当前模型资产，无血缘边。
        return assets, edges

    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, field: str) -> None:
        signature = (source, target, "derived_from")
        if signature in seen_edges:
            return
        seen_edges.add(signature)
        edges.append(
            {
                "source": source,
                "target": target,
                "edge_type": "derived_from",
                "evidence_level": msa.LINEAGE_EVIDENCE_LEVEL,
                "source_field": field,
                "snapshot_id": snapshot_id,
            }
        )

    seen_canonical = {a["canonical_id"] for a in assets}

    def add_aggregate(role: str, field: str) -> None:
        for entry in ba.as_list(lineage.get(field)):
            if not isinstance(entry, dict):
                continue
            total = entry.get("Total")
            if not isinstance(total, int) or total <= 0:
                continue
            node = aggregate_node(
                ns=ns,
                name=name,
                revision=revision,
                role=role,
                lineage_type=entry.get("LineAgeType"),
                lineage_type_ch=entry.get("LineAgeTypeCh"),
                count=total,
                snapshot_id=snapshot_id,
                source_file=source_file,
            )
            if node["canonical_id"] in seen_canonical:
                continue
            seen_canonical.add(node["canonical_id"])
            assets.append(node)

    # SonModels：由当前模型派生的模型（source=派生模型，target=当前模型）
    add_aggregate("son", "SonModels")
    for asset in assets:
        if asset.get("aggregate") and ":son:" in asset["entity_key"]:
            add_edge(asset["canonical_id"], current_id, "lineage.SonModels")

    # ParentsModels：当前模型派生自的模型（source=当前模型，target=祖先模型）
    add_aggregate("parent", "ParentsModels")
    for asset in assets:
        if asset.get("aggregate") and ":parent:" in asset["entity_key"]:
            add_edge(current_id, asset["canonical_id"], "lineage.ParentsModels")

    return assets, edges


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="从 ModelScope 官方 API 提取血缘并建图")
    parser.add_argument("--model", required=True, help="ModelScope 模型名，如 Qwen/Qwen-Image-2.1")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    args = parser.parse_args(argv)

    model = args.model.strip().strip("/")
    if "/" not in model:
        print("错误：--model 必须是 namespace/name 形式，如 Qwen/Qwen-Image-2.1", file=sys.stderr)
        raise SystemExit(2)
    ns, name = model.split("/", 1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    snapshot_id = f"modelscope-{ns}__{name}"
    source_file = f"{msa.API_BASE}/models/{ns}/{name}"
    assets, edges = extract(ns, name, snapshot_id, source_file)

    if not assets:
        print(
            f"错误：无法从 ModelScope 获取模型 {ns}/{name} 的详情，请检查网络或模型名。",
            file=sys.stderr,
        )
        raise SystemExit(2)

    assets_path = output_dir / "assets.json"
    edges_path = output_dir / "edges.json"
    assets_path.write_text(
        json.dumps(assets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    edges_path.write_text(
        json.dumps(edges, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    graph = bg.build_graph(assets, edges)
    canonical_to_scc, compressed = bg.compress_scc(graph)
    graph_dict = bg.graph_to_dict(graph, canonical_to_scc, compressed)
    graph_path = output_dir / "graph.json"
    graph_path.write_text(
        json.dumps(graph_dict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    aggregate_nodes = [a for a in assets if a.get("aggregate")]
    total_aggregated = sum(a.get("count", 0) for a in aggregate_nodes)
    current = assets[0]
    print(f"模型：{model}")
    print(f"许可证：{current.get('license') or '（未识别）'}")
    print(
        f"资产节点：{graph_dict['node_count']}（含 {len(aggregate_nodes)} 个聚合节点，"
        f"聚合 {total_aggregated} 个派生/祖先模型）"
    )
    print(f"血缘边：{graph_dict['edge_count']}（derived_from，证据等级 {msa.LINEAGE_EVIDENCE_LEVEL}）")
    print(f"SCC 分量：{graph_dict['scc_count']}")
    print(f"已写入 {assets_path} / {edges_path} / {graph_path}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
