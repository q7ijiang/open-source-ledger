# -*- coding: utf-8 -*-
"""visualize_lineage.py — 用 networkx + matplotlib 把模块 8 的血缘图渲染成 PNG。

用法：
    python visualize_lineage.py --graph out/hf_lineage/graph.json \
                                --output outputs/lineage_graph.png

输入为模块 8 graph_to_dict 产出的 graph.json（含 nodes / edges），
输出为无头模式（Agg）下的静态 PNG 图。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402

EDGE_COLOR = {
    "derived_from": "#d62728",
    "trained_on": "#1f77b4",
    "depends_on": "#2ca02c",
}
NODE_COLOR = {"model": "#4c72b0", "dataset": "#dd8452"}
DEFAULT_NODE_COLOR = "#55a868"
DEFAULT_EDGE_COLOR = "#7f7f7f"


def load_graph(path: Path) -> nx.MultiDiGraph:
    """从 graph.json 还原 networkx 有向多图。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    graph = nx.MultiDiGraph()
    for node in data.get("nodes", []):
        canonical_id = node.get("canonical_id")
        if not canonical_id:
            continue
        graph.add_node(
            canonical_id,
            **{key: value for key, value in node.items() if key != "canonical_id"},
        )
    for edge in data.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        graph.add_edge(
            source,
            target,
            **{key: value for key, value in edge.items() if key not in ("source", "target")},
        )
    return graph


def render(graph: nx.MultiDiGraph, out_path: Path) -> None:
    """把图渲染为 PNG。节点按资产类型着色，边按边类型着色。"""
    k = 2.0 / max(1.0, len(graph) ** 0.5)
    pos = nx.spring_layout(graph, seed=42, k=k)

    node_colors = []
    labels = {}
    for node_id, attrs in graph.nodes(data=True):
        node_colors.append(NODE_COLOR.get(attrs.get("asset_type"), DEFAULT_NODE_COLOR))
        name = attrs.get("name") or node_id
        labels[node_id] = name if len(name) <= 32 else name[:29] + "..."

    plt.figure(figsize=(14, 10))
    nx.draw_networkx_nodes(graph, pos, node_color=node_colors, node_size=2400, alpha=0.92)
    nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8)

    if graph.number_of_edges():
        edge_colors = [
            EDGE_COLOR.get(graph.edges[u, v, key].get("edge_type"), DEFAULT_EDGE_COLOR)
            for u, v, key in graph.edges(keys=True)
        ]
        nx.draw_networkx_edges(
            graph,
            pos,
            edgelist=list(graph.edges(keys=True)),
            edge_color=edge_colors,
            arrows=True,
            arrowsize=16,
            connectionstyle="arc3,rad=0.12",
        )

    plt.axis("off")
    plt.title(
        f"Lineage Graph ({graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges)"
    )
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="把血缘图渲染成 PNG")
    parser.add_argument("--graph", required=True, help="模块 8 的 graph.json")
    parser.add_argument("--output", required=True, help="输出 PNG 路径")
    args = parser.parse_args(argv)

    graph = load_graph(Path(args.graph))
    render(graph, Path(args.output))
    print(f"节点：{graph.number_of_nodes()}，边：{graph.number_of_edges()}")
    print(f"已写入 {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
