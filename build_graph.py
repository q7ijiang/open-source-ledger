# -*- coding: utf-8 -*-
"""模块 8：血缘图构建（build_graph.py）。

负责人：B（算法核心）
对应任务：深度部分 · 模块 8（截止 2026-10-07）

功能：
1. 用 networkx 构建有向血缘图：节点为资产（canonical_id），
   边类型支持 derived_from / trained_on / depends_on；
2. 对图中强连通分量（SCC）做压缩，输出凝聚图，供 Delta 检测与风险传播使用；
3. 边证据等级按 weakest link 规则聚合（A > B > C，取最弱）；
4. 输出完整图结构 JSON（节点、边、SCC、压缩后的节点与边）。

用法：
    python build_graph.py --assets data/deep_t0_assets.json \
                          --edges data/deep_t0_edges.json \
                          --output out/graph_t0.json

输入输出字段严格遵循 docs/接口约定.md（资产节点 / 血缘边）。
本模块不涉及网络请求。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import networkx as nx

# 边方向语义（见接口约定）：
#   derived_from：source 派生自 target（target 是祖先）
#   trained_on：  source 训练使用了 target（target 是训练数据/基座）
#   depends_on：  source 依赖 target（target 是依赖）
EDGE_TYPES = {"derived_from", "trained_on", "depends_on"}

# 证据等级强度：A 最强，C 最弱；weakest link 取最低。
EVIDENCE_ORDER = {"A": 0, "B": 1, "C": 2}


def weakest(levels: list[str]) -> str | None:
    """按 weakest link 规则取一组证据等级中最弱的一个（A > B > C）。"""
    if not levels:
        return None
    return max(levels, key=lambda level: EVIDENCE_ORDER.get(level, 9))


def load_assets(path) -> list[dict]:
    """读取资产列表 JSON（接口约定的资产节点数组）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        # 兼容 {"assets": [...]} 包装
        data = data.get("assets", data.get("nodes", []))
    return list(data)


def load_edges(path) -> list[dict]:
    """读取血缘边列表 JSON（接口约定的血缘边数组）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("edges", [])
    return list(data)


def build_graph(assets: list[dict], edges: list[dict]) -> nx.MultiDiGraph:
    """由资产与血缘边构建有向图。

    - 使用 MultiDiGraph：同一对节点允许多条不同类型边（如同时 derived_from
      与 depends_on），并行边全部保留，由 key 区分；
    - 节点属性：asset_type / name / version / license / snapshot_id；
    - 每条边保留完整信息（edge_type / evidence_level / source_field / snapshot_id）。
    """
    graph = nx.MultiDiGraph()

    for asset in assets:
        canonical_id = asset.get("canonical_id")
        if not canonical_id:
            continue
        if graph.has_node(canonical_id):
            graph.nodes[canonical_id].update(asset)
        else:
            # 节点属性 = 资产全部字段（含 entity_key / purls / evidence_chain /
            # merge_status / reason_code / rule_version / hashes），
            # 保证下游传播可拿到完整证据链与合并状态。
            attrs = {key: value for key, value in asset.items() if key != "canonical_id"}
            graph.add_node(canonical_id, **attrs)

    for index, edge in enumerate(edges):
        source = edge.get("source")
        target = edge.get("target")
        edge_type = edge.get("edge_type")
        if not source or not target:
            continue
        if edge_type not in EDGE_TYPES:
            # 未知边类型仍保留，但标记为 unknown，便于审计
            edge_type = edge_type or "unknown"
        graph.add_edge(
            source,
            target,
            key=index,
            edge_type=edge_type,
            evidence_level=edge.get("evidence_level"),
            source_field=edge.get("source_field"),
            snapshot_id=edge.get("snapshot_id"),
        )

    return graph


def compress_scc(graph: nx.MultiDiGraph) -> tuple[dict, nx.DiGraph]:
    """压缩强连通分量（SCC）。

    返回 (canonical_to_scc, compressed)：
    - canonical_to_scc：canonical_id -> scc_id（如 "scc-0"）；
    - compressed：SCC 之间的有向图，节点属性含 members，
      边属性为聚合结果（edge_types、evidence_level=weakest、count）。
    """
    components = list(nx.strongly_connected_components(graph))
    # 按节点数从大到小排序，便于人工阅读
    components.sort(key=len, reverse=True)

    canonical_to_scc: dict[str, str] = {}
    for index, component in enumerate(components):
        scc_id = f"scc-{index}"
        for canonical_id in component:
            canonical_to_scc[canonical_id] = scc_id

    compressed = nx.DiGraph()
    for component in components:
        scc_id = canonical_to_scc[next(iter(component))]
        compressed.add_node(
            scc_id,
            members=sorted(component),
            size=len(component),
        )

    # 聚合 SCC 之间的边：并行边合并，证据等级取 weakest link
    for source, target, data in graph.edges(data=True):
        source_scc = canonical_to_scc[source]
        target_scc = canonical_to_scc[target]
        if source_scc == target_scc:
            continue
        if not compressed.has_edge(source_scc, target_scc):
            compressed.add_edge(
                source_scc,
                target_scc,
                edge_types=[],
                evidence_levels=[],
                count=0,
            )
        edge_data = compressed.edges[source_scc, target_scc]
        edge_data["edge_types"].append(data["edge_type"])
        edge_data["evidence_levels"].append(data["evidence_level"])
        edge_data["count"] += 1

    for _, _, edge_data in compressed.edges(data=True):
        edge_data["evidence_level"] = weakest(edge_data["evidence_levels"])
        edge_data["edge_types"] = sorted(set(edge_data.pop("edge_types")))
        edge_data.pop("evidence_levels")

    return canonical_to_scc, compressed


def graph_to_dict(
    graph: nx.MultiDiGraph,
    canonical_to_scc: dict[str, str],
    compressed: nx.DiGraph,
) -> dict:
    """把 networkx 图序列化为符合接口约定的 JSON 结构。"""
    nodes = []
    for canonical_id, attrs in graph.nodes(data=True):
        nodes.append({
            "canonical_id": canonical_id,
            "entity_key": attrs.get("entity_key"),
            "asset_type": attrs.get("asset_type"),
            "name": attrs.get("name"),
            "version": attrs.get("version"),
            "purls": list(attrs.get("purls", [])) if attrs.get("purls") else [],
            "license": attrs.get("license"),
            "evidence_chain": attrs.get("evidence_chain") or [],
            "snapshot_id": attrs.get("snapshot_id"),
            "merge_status": attrs.get("merge_status"),
            "reason_code": attrs.get("reason_code"),
            "rule_version": attrs.get("rule_version"),
            "hashes": attrs.get("hashes") or [],
            "scc_id": canonical_to_scc.get(canonical_id),
        })

    edges = []
    for source, target, attrs in graph.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            "edge_type": attrs.get("edge_type"),
            "evidence_level": attrs.get("evidence_level"),
            "source_field": attrs.get("source_field"),
            "snapshot_id": attrs.get("snapshot_id"),
        })

    scc_members = {}
    for scc_id in canonical_to_scc.values():
        scc_members[scc_id] = sorted(
            node for node, sid in canonical_to_scc.items() if sid == scc_id
        )

    compressed_nodes = []
    for scc_id, attrs in compressed.nodes(data=True):
        compressed_nodes.append({
            "scc_id": scc_id,
            "size": attrs["size"],
            "members": attrs["members"],
            "is_cycle": attrs["size"] > 1,
        })

    compressed_edges = []
    for source_scc, target_scc, attrs in compressed.edges(data=True):
        compressed_edges.append({
            "source_scc": source_scc,
            "target_scc": target_scc,
            "edge_types": attrs["edge_types"],
            "evidence_level": attrs["evidence_level"],
            "count": attrs["count"],
        })

    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "scc_count": compressed.number_of_nodes(),
        "nodes": nodes,
        "edges": edges,
        "canonical_to_scc": canonical_to_scc,
        "scc": scc_members,
        "compressed": {
            "nodes": compressed_nodes,
            "edges": compressed_edges,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="血缘图构建（模块 8）")
    parser.add_argument("--assets", required=True, help="资产列表 JSON（接口约定格式）")
    parser.add_argument("--edges", required=True, help="血缘边 JSON（接口约定格式）")
    parser.add_argument("--output", required=True, help="输出图结构 JSON 路径")
    args = parser.parse_args(argv)

    assets = load_assets(args.assets)
    edges = load_edges(args.edges)
    graph = build_graph(assets, edges)
    canonical_to_scc, compressed = compress_scc(graph)
    result = graph_to_dict(graph, canonical_to_scc, compressed)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"资产节点：{result['node_count']}")
    print(f"血缘边：{result['edge_count']}")
    print(f"SCC 分量：{result['scc_count']}（含 {sum(1 for n in result['compressed']['nodes'] if n['is_cycle'])} 个环）")
    print(f"已写入 {output_path}")


if __name__ == "__main__":
    main()
