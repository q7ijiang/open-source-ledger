# -*- coding: utf-8 -*-
"""Shared deterministic layout helpers for the interactive risk renderers."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from render_lineage_layout import layout_lineage_dag

DECISION_RANK = {
    "RISK_CONFIRMED": 3,
    "RISK_POTENTIAL": 2,
    "SAFE": 1,
    "UNDETERMINED": 0,
}
RISK_DECISIONS = {"RISK_CONFIRMED", "RISK_POTENTIAL"}
TOTAL_RE = re.compile(r"\(Total:\s*(\d+)\)", re.IGNORECASE)
CHILD_LABEL_RE = re.compile(r"\(([^()]*)\)\s*$")


def is_aggregate_node(node: dict[str, Any]) -> bool:
    """Return whether a node is an aggregate risk domain.

    Explicit metadata wins. The legacy name fallback deliberately requires a
    Total marker because ordinary model names can contain `` · ``.
    """

    if bool(node.get("aggregate")):
        return True
    if str(node.get("coverage_status") or "").upper() == "AGGREGATE_ONLY":
        return True

    canonical_id = str(node.get("canonical_id") or node.get("entity_key") or "")
    if ":son:" in canonical_id or ":parent:" in canonical_id:
        return True

    name = str(node.get("name") or "")
    return "(Total:" in name and not node.get("purls")


def aggregate_count(node: dict[str, Any]) -> int:
    """Read the aggregate population count, with a legacy-name fallback."""

    raw = node.get("count")
    if isinstance(raw, int) and raw >= 0:
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    match = TOTAL_RE.search(str(node.get("name") or ""))
    return int(match.group(1)) if match else 0


def aggregate_domain_label(node: dict[str, Any]) -> str:
    """Return a compact label for a risk-domain card."""

    label = node.get("lineage_type_ch") or node.get("lineage_type")
    if not label:
        name = str(node.get("name") or node.get("canonical_id") or "聚合域")
        label = name.split(" · ", 1)[1] if " · " in name else name
    label = TOTAL_RE.sub("", str(label)).strip(" ·")
    return label or "聚合域"


def expanded_child_label(node: dict[str, Any]) -> str:
    """Extract the concrete child label without repeating its parent domain."""

    name = str(node.get("name") or node.get("canonical_id") or node.get("id") or "")
    match = CHILD_LABEL_RE.search(name)
    if match:
        return match.group(1).strip() or name
    if " · " in name:
        return name.rsplit(" · ", 1)[-1].strip()
    return name


def _known_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {"red": 0, "yellow": 0, "gray": 0}

    def pick(*keys: str) -> int:
        for key in keys:
            raw = value.get(key)
            if isinstance(raw, int) and raw > 0:
                return raw
            if isinstance(raw, str) and raw.isdigit():
                return int(raw)
        return 0

    return {
        "red": pick("red", "RISK_CONFIRMED", "risk_confirmed"),
        "yellow": pick("yellow", "RISK_POTENTIAL", "risk_potential"),
        "gray": pick("gray", "UNDETERMINED", "undetermined"),
    }


def aggregate_risk_counts(
    node: dict[str, Any],
    child_decisions: list[str] | None = None,
) -> dict[str, int]:
    """Return known red/yellow/gray counts without treating the owner as a child."""

    counts = _known_counts(node.get("known_risk_counts"))
    child_counts = {"red": 0, "yellow": 0, "gray": 0}
    for decision in child_decisions or []:
        if decision == "RISK_CONFIRMED":
            child_counts["red"] += 1
        elif decision == "RISK_POTENTIAL":
            child_counts["yellow"] += 1
        elif decision == "UNDETERMINED":
            child_counts["gray"] += 1

    # known_risk_counts may already include the expanded children. Use the
    # larger side instead of summing, otherwise the badge double-counts them.
    return {
        key: max(counts[key], child_counts[key])
        for key in ("red", "yellow", "gray")
    }


def aggregate_tone(counts: dict[str, int]) -> str:
    """Choose the border tone while keeping the aggregate fill neutral."""

    if counts.get("red", 0) > 0:
        return "RISK_CONFIRMED"
    if counts.get("yellow", 0) > 0:
        return "RISK_POTENTIAL"
    if counts.get("gray", 0) > 0:
        return "UNDETERMINED"
    return "NEUTRAL"


def _node_label(node: dict[str, Any]) -> str:
    return str(node.get("name") or node.get("canonical_id") or node.get("id") or "")


def _ordered_model_nodes(
    nodes: list[dict[str, Any]],
    excluded_ids: set[str],
    *,
    order_by_decision: bool = True,
) -> list[dict[str, Any]]:
    indexed = {str(n.get("id")): i for i, n in enumerate(nodes)}
    models = [
        n
        for n in nodes
        if n.get("asset_type") == "model"
        and not is_aggregate_node(n)
        and str(n.get("id")) not in excluded_ids
    ]

    def key(node: dict[str, Any]) -> tuple[int, int]:
        decision_rank = (
            DECISION_RANK.get(str(node.get("decision") or ""), -1)
            if order_by_decision
            else 0
        )
        return (-decision_rank, indexed.get(str(node.get("id")), 0))

    return sorted(models, key=key)


def _aggregate_columns(count: int, max_columns: int) -> int:
    if count <= 0:
        return 1
    if count <= max_columns:
        return count
    if count <= max_columns + 2:
        return min(max_columns, 3)
    return max_columns


def layout_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    canvas_width: int = 1280,
    stable_order: bool = False,
) -> dict[str, Any]:
    """Assign deterministic positions and return adaptive cluster metadata.

    Aggregate domains are rendered as neutral cards. Concrete children attached
    through ``expanded_from`` stay inside their owner domain as small risk
    cards; they never become separate model clusters.
    """

    if not nodes:
        return {"clusters": [], "width": canvas_width, "height": 520}

    by_id = {str(n.get("id")): n for n in nodes if n.get("id") is not None}
    aggregates = [n for n in nodes if is_aggregate_node(n)]
    aggregate_ids = {str(n.get("id")) for n in aggregates}

    if not aggregates:
        return layout_lineage_dag(nodes, edges, canvas_width=canvas_width)


    adjacent: dict[str, list[str]] = defaultdict(list)
    expanded_children: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        edge_type = str(edge.get("edge_type") or "")
        if edge_type == "expanded_from":
            if source in aggregate_ids:
                expanded_children[source].append(target)
            elif target in aggregate_ids:
                expanded_children[target].append(source)
            continue
        if source in aggregate_ids and target not in aggregate_ids:
            adjacent[source].append(target)
        elif target in aggregate_ids and source not in aggregate_ids:
            adjacent[target].append(source)

    expanded_child_ids = {
        child_id
        for children in expanded_children.values()
        for child_id in children
        if child_id in by_id
    }

    aggregates_by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    orphan_aggregates: list[dict[str, Any]] = []
    for aggregate in aggregates:
        aggregate_id = str(aggregate.get("id"))
        candidates = [
            candidate
            for candidate in adjacent.get(aggregate_id, [])
            if candidate in by_id
            and candidate not in expanded_child_ids
            and by_id[candidate].get("asset_type") == "model"
            and not is_aggregate_node(by_id[candidate])
        ]
        if not candidates:
            candidates = [
                candidate
                for candidate in adjacent.get(aggregate_id, [])
                if candidate in by_id and candidate not in expanded_child_ids
            ]
        if candidates:
            aggregates_by_owner[candidates[0]].append(aggregate)
        else:
            orphan_aggregates.append(aggregate)

    model_nodes = _ordered_model_nodes(
        nodes,
        expanded_child_ids,
        order_by_decision=not stable_order,
    )
    model_ids = {str(n.get("id")) for n in model_nodes}
    for owner_id in aggregates_by_owner:
        if owner_id not in model_ids and owner_id in by_id:
            model_nodes.append(by_id[owner_id])
            model_ids.add(owner_id)

    clusters: list[dict[str, Any]] = []
    placed_ids: set[str] = set(expanded_child_ids)
    margin = 32
    vertical_cluster_gap = 72
    cluster_gap = 28
    compact = canvas_width < 900
    card_w = 136 if compact else 158
    card_h = 68
    card_gap = 8 if compact else 12
    child_cols = 2
    child_w = 64 if compact else 72
    child_h = 38
    child_gap_x = 6
    child_gap_y = 6
    max_agg_cols = 4
    owner_header_h = 104
    orphan_header_h = 64
    cluster_padding = 36
    cursor_x = margin
    cursor_y = 24
    row_height = 0
    usable_width = max(560, canvas_width - margin * 2)

    def make_cluster(
        owner: dict[str, Any] | None,
        aggregate_nodes: list[dict[str, Any]],
        title: str | None = None,
    ) -> None:
        nonlocal cursor_x, cursor_y, row_height

        count = len(aggregate_nodes)
        cols = _aggregate_columns(count, max_agg_cols) if count else 1
        content_width = (
            cols * card_w + max(0, cols - 1) * card_gap if count else 220
        )
        cluster_w = max(232 if compact else 248, content_width + cluster_padding)

        row_cells: list[list[dict[str, Any]]] = []
        for start in range(0, count, cols):
            row_cells.append(aggregate_nodes[start : start + cols])

        cell_heights: list[int] = []
        for row_nodes in row_cells:
            max_cell_h = card_h
            for aggregate in row_nodes:
                aggregate_id = str(aggregate.get("id"))
                child_count = len(expanded_children.get(aggregate_id, []))
                child_rows = (
                    math.ceil(child_count / child_cols) if child_count else 0
                )
                child_height = (
                    child_rows * child_h
                    + max(0, child_rows - 1) * child_gap_y
                    + 10
                    if child_rows
                    else 0
                )
                max_cell_h = max(max_cell_h, card_h + child_height)
            cell_heights.append(max_cell_h)

        header_h = owner_header_h if owner is not None else orphan_header_h
        aggregate_grid_h = (
            sum(cell_heights) + max(0, len(cell_heights) - 1) * card_gap
            if cell_heights
            else 76
        )
        cluster_h = header_h + aggregate_grid_h + 22

        if cursor_x > margin and cursor_x + cluster_w > margin + usable_width:
            cursor_x = margin
            # Keep the next owner's title and labels clear of the previous
            # cluster's aggregate cards.
            cursor_y += row_height + vertical_cluster_gap
            row_height = 0

        cluster_x = cursor_x
        cluster_y = cursor_y
        anchor_id = str(owner.get("id")) if owner else None
        cluster_title = title or (_node_label(owner) if owner else "未关联聚合域")
        expanded_count = sum(
            len(expanded_children.get(str(aggregate.get("id")), []))
            for aggregate in aggregate_nodes
        )

        if owner is not None:
            owner["x"] = cluster_x + cluster_w / 2
            owner["y"] = cluster_y + 50
            owner["lp"] = "bottom"
            placed_ids.add(anchor_id)

        aggregate_top = cluster_y + header_h
        for row_index, row_nodes in enumerate(row_cells):
            if row_index:
                aggregate_top += cell_heights[row_index - 1] + card_gap
            for col, aggregate in enumerate(row_nodes):
                aggregate["x"] = (
                    cluster_x
                    + cluster_padding / 2
                    + card_w / 2
                    + col * (card_w + card_gap)
                )
                aggregate["y"] = aggregate_top + card_h / 2
                aggregate["lp"] = "inside"
                aggregate_id = str(aggregate.get("id"))
                child_ids = [
                    child
                    for child in expanded_children.get(aggregate_id, [])
                    if child in by_id
                ]
                child_decisions = [
                    str(by_id[child].get("decision") or "UNDETERMINED")
                    for child in child_ids
                ]
                counts = aggregate_risk_counts(aggregate, child_decisions)
                aggregate["render_card"] = {
                    "width": card_w,
                    "height": card_h,
                    "label": aggregate_domain_label(aggregate),
                    "total": aggregate_count(aggregate),
                }
                aggregate["render_risk_counts"] = counts
                aggregate["render_tone"] = aggregate_tone(counts)
                placed_ids.add(aggregate_id)

                child_top = aggregate_top + card_h + 10
                for child_index, child_id in enumerate(child_ids):
                    child = by_id[child_id]
                    child_col = child_index % child_cols
                    child_row = child_index // child_cols
                    centered_offset = (
                        card_w - (child_cols * child_w + child_gap_x)
                    ) / 2
                    child["x"] = (
                        aggregate["x"]
                        - card_w / 2
                        + centered_offset
                        + child_w / 2
                        + child_col * (child_w + child_gap_x)
                    )
                    child["y"] = (
                        child_top + child_h / 2 + child_row * (child_h + child_gap_y)
                    )
                    child["lp"] = "inside"
                    child["render_role"] = "expanded_child"
                    child["render_parent_id"] = aggregate_id
                    child["render_card"] = {
                        "width": child_w,
                        "height": child_h,
                        "label": expanded_child_label(child),
                        "parent_id": aggregate_id,
                    }
                    placed_ids.add(child_id)

        clusters.append(
            {
                "id": anchor_id or f"orphan-{len(clusters)}",
                "x": cluster_x,
                "y": cluster_y,
                "width": cluster_w,
                "height": cluster_h,
                "title": cluster_title,
                "decision": str(owner.get("decision") or "UNDETERMINED")
                if owner
                else "UNDETERMINED",
                "aggregate_count": count,
                "expanded_count": expanded_count,
            }
        )
        cursor_x += cluster_w + cluster_gap
        row_height = max(row_height, cluster_h)

    for owner in model_nodes:
        make_cluster(owner, aggregates_by_owner.get(str(owner.get("id")), []))

    if orphan_aggregates:
        make_cluster(None, orphan_aggregates)

    if clusters:
        cursor_y += row_height + 36

    other_nodes = [
        n
        for n in nodes
        if str(n.get("id")) not in placed_ids and not is_aggregate_node(n)
    ]
    if other_nodes:
        other_cols = min(5, max(1, math.floor(usable_width / 210)))
        for index, node in enumerate(other_nodes):
            col = index % other_cols
            row = index // other_cols
            node["x"] = margin + 105 + col * 214
            node["y"] = cursor_y + 32 + row * 72
            node["lp"] = "bottom"
            placed_ids.add(str(node.get("id")))
        cursor_y += math.ceil(len(other_nodes) / other_cols) * 72 + 60

    for index, node in enumerate(nodes):
        if str(node.get("id")) in placed_ids:
            continue
        col = index % 4
        row = index // 4
        node["x"] = margin + 90 + col * 220
        node["y"] = cursor_y + 48 + row * 74
        node["lp"] = "bottom"

    return {
        "clusters": clusters,
        "width": int(canvas_width),
        "height": max(540, int(cursor_y + 110)),
    }
