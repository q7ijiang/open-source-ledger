# -*- coding: utf-8 -*-
"""Layered lineage layout for model supply-chain graphs.

The regular cluster layout is optimized for aggregate risk domains. Project
graphs and Diff snapshots, however, are primarily ancestry DAGs. This module
places downstream models above their upstream ancestors so arrow direction is
readable without relying on arbitrary grid positions.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any

LINEAGE_EDGE_TYPES = {"derived_from", "trained_on", "depends_on"}


def _role_label(node: dict[str, Any], layer: int) -> str:
    if node.get("lineage_role") == "root" or layer == 0:
        return "项目直接使用"

    lineage_type = str(node.get("lineage_type_ch") or node.get("lineage_type") or "")
    normalized = lineage_type.lower()
    if "base" in normalized or "基" in lineage_type:
        return "上游 · 基座模型"
    if "finetun" in normalized or "微调" in lineage_type:
        return "上游 · 微调模型"
    if "merge" in normalized or "合并" in lineage_type:
        return "上游 · 合并模型"
    if lineage_type:
        return f"上游 · {lineage_type}"
    if node.get("asset_type") == "dataset":
        return "上游 · 数据集"
    return f"上游 · 第 {layer} 层"


def _card_label(node: dict[str, Any], limit: int = 24) -> str:
    value = str(node.get("name") or node.get("id") or "")
    if len(value) <= limit:
        return value
    if "/" in value:
        namespace, model = value.split("/", 1)
        available = limit - len(namespace) - 2
        if available >= 8:
            return f"{namespace}/{model[:available]}…"
        return f"{model[: limit - 1]}…"
    return f"{value[: limit - 1]}…"


def _short_role_label(value: str) -> str:
    return value.replace("上游 · ", "上游·")


def _layer_map(
    node_ids: list[str],
    adjacency: dict[str, list[str]],
) -> tuple[dict[str, int], list[str]]:
    order = {node_id: index for index, node_id in enumerate(node_ids)}
    indegree = {node_id: 0 for node_id in node_ids}
    for targets in adjacency.values():
        for target in targets:
            indegree[target] += 1

    queue = deque(sorted((node_id for node_id, value in indegree.items() if value == 0), key=order.get))
    layers = {node_id: 0 for node_id in node_ids}
    processed: set[str] = set()

    while queue:
        source = queue.popleft()
        processed.add(source)
        for target in sorted(adjacency.get(source, []), key=order.get):
            layers[target] = max(layers[target], layers[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    cycle_nodes = [node_id for node_id in node_ids if node_id not in processed]
    for node_id in cycle_nodes:
        # The source graph should be a DAG. If an upstream service returns an
        # inconsistent cycle, preserve the explicit depth rather than dropping
        # the node from the visualization.
        layers[node_id] = max(layers.get(node_id, 0), 0)
    return layers, cycle_nodes


def _order_layers(
    layers: dict[str, int],
    node_order: dict[str, int],
    predecessors: dict[str, set[str]],
    successors: dict[str, set[str]],
) -> list[list[str]]:
    depth_count = max(layers.values(), default=0) + 1
    grouped = [[] for _ in range(depth_count)]
    for node_id, depth in layers.items():
        grouped[depth].append(node_id)

    for group in grouped:
        group.sort(key=node_order.get)

    if depth_count <= 1:
        return grouped

    positions = {
        node_id: index
        for group in grouped
        for index, node_id in enumerate(group)
    }

    for _ in range(4):
        for depth in range(1, depth_count):
            def forward_key(node_id: str) -> tuple[float, int]:
                neighbors = [positions[item] for item in predecessors[node_id] if item in positions]
                return (
                    sum(neighbors) / len(neighbors) if neighbors else positions[node_id],
                    node_order[node_id],
                )

            grouped[depth].sort(key=forward_key)
            positions.update({node_id: index for index, node_id in enumerate(grouped[depth])})

        for depth in range(depth_count - 2, -1, -1):
            def backward_key(node_id: str) -> tuple[float, int]:
                neighbors = [positions[item] for item in successors[node_id] if item in positions]
                return (
                    sum(neighbors) / len(neighbors) if neighbors else positions[node_id],
                    node_order[node_id],
                )

            grouped[depth].sort(key=backward_key)
            positions.update({node_id: index for index, node_id in enumerate(grouped[depth])})

    return grouped


def _layer_subtitle(nodes: list[dict[str, Any]], depth: int) -> str:
    if depth == 0:
        return "由项目配置、代码或 BOM 直接识别"
    base_count = sum(
        _role_label(node, depth) == "上游 · 基座模型" for node in nodes
    )
    if base_count:
        return f"继承来源层 · 含 {base_count} 个上游基座模型"
    return f"向上追溯第 {depth} 层 · 箭头继续指向上游"


def layout_lineage_dag(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    canvas_width: int,
) -> dict[str, Any]:
    """Place downstream models above their upstream ancestors."""

    by_id = {str(node.get("id")): node for node in nodes}
    node_ids = list(by_id)
    node_order = {node_id: index for index, node_id in enumerate(node_ids)}

    adjacency: dict[str, list[str]] = defaultdict(list)
    predecessors: dict[str, set[str]] = defaultdict(set)
    successors: dict[str, set[str]] = defaultdict(set)
    lineage_edges = []
    for edge in edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        edge_type = str(edge.get("edge_type") or "")
        if edge_type not in LINEAGE_EDGE_TYPES or source == target:
            continue
        if source not in by_id or target not in by_id:
            continue
        if target in adjacency[source]:
            continue
        adjacency[source].append(target)
        predecessors[target].add(source)
        successors[source].add(target)
        lineage_edges.append(edge)

    layers, cycle_nodes = _layer_map(node_ids, adjacency)
    ordered_layers = _order_layers(layers, node_order, predecessors, successors)

    margin = 20 if canvas_width < 900 else 28
    compact = canvas_width < 900
    card_w = 128 if compact else 158
    card_h = 62 if compact else 66
    card_gap_x = 8 if compact else 12
    card_gap_y = 18 if compact else 20
    band_header_h = 54
    band_padding_x = 16
    band_padding_bottom = 20

    usable_width = canvas_width - margin * 2
    inner_width = usable_width - band_padding_x * 2
    cards_per_row = max(
        1,
        math.floor((inner_width + card_gap_x) / (card_w + card_gap_x)),
    )

    band_heights: dict[int, int] = {}
    for depth, layer_ids in enumerate(ordered_layers):
        row_count = math.ceil(len(layer_ids) / cards_per_row)
        band_heights[depth] = (
            band_header_h
            + row_count * card_h
            + max(0, row_count - 1) * card_gap_y
            + band_padding_bottom
        )

    clusters: list[dict[str, Any]] = []
    cursor_y = 24
    # Deeper ancestors are drawn above the project's direct dependencies so
    # every lineage arrow points upward, matching the "trace upstream" model.
    for depth in range(len(ordered_layers) - 1, -1, -1):
        layer_ids = ordered_layers[depth]
        layer_nodes = [by_id[node_id] for node_id in layer_ids]
        band_height = band_heights[depth]
        band_x = margin
        band_width = usable_width
        cluster = {
            "id": f"lineage-layer-{depth}",
            "x": band_x,
            "y": cursor_y,
            "width": band_width,
            "height": band_height,
            "title": (
                "项目直接使用的模型"
                if depth == 0
                else f"上游第 {depth} 层"
            ),
            "subtitle": _layer_subtitle(layer_nodes, depth),
            "decision": "NEUTRAL",
            "aggregate_count": 0,
            "expanded_count": 0,
            "kind": "lineage_layer",
            "layer_depth": depth,
        }
        clusters.append(cluster)

        for index, node in enumerate(layer_nodes):
            row = index // cards_per_row
            column = index % cards_per_row
            items_in_row = min(cards_per_row, len(layer_nodes) - row * cards_per_row)
            row_width = items_in_row * card_w + max(0, items_in_row - 1) * card_gap_x
            row_left = band_x + (band_width - row_width) / 2
            node["x"] = row_left + card_w / 2 + column * (card_w + card_gap_x)
            node["y"] = (
                cursor_y
                + band_header_h
                + card_h / 2
                + row * (card_h + card_gap_y)
            )
            node["lp"] = "inside"
            node["render_layer"] = depth
            node["render_role_label"] = _role_label(node, depth)
            node["render_role_short"] = _short_role_label(node["render_role_label"])
            node["render_card"] = {
                "width": card_w,
                "height": card_h,
                "label": _card_label(node),
            }

        cursor_y += band_height + 28

    for edge in lineage_edges:
        edge["render_label"] = "派生自"

    return {
        "clusters": clusters,
        "width": int(canvas_width),
        "height": max(540, int(cursor_y + 10)),
        "layout_mode": "lineage_dag",
        "cycle_nodes": cycle_nodes,
    }
