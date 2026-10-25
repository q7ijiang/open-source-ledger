from __future__ import annotations

# 显式生效的"仅展示"标记：只认资产上写明的字段，绝不根据 expanded_from 推导。
DISPLAY_ONLY_FLAGS = ("display_only", "is_fixture")


def _is_expansion_edge(edge: dict) -> bool:
    """聚合域展开边（聚合节点 -> 子节点），只用于渲染层展示归属。"""

    return (
        edge.get("edge_type") == "expanded_from"
        or edge.get("source_field") == "expanded_from"
    )


def _node_id(node: dict) -> str:
    return str(
        node.get("id")
        or node.get("canonical_id")
        or node.get("entity_key")
        or ""
    )


def _is_display_only(node: dict) -> bool:
    """资产是否被显式标记为演示夹具（display_only / is_fixture）。

    注意：这里只看资产自身的字段。带 expanded_from 的子节点默认是**真实资产**，
    它们的许可证变化必须进入 Delta；把"是否展开"当成"是否夹具"会让子节点的
    变更被静默吞掉。
    """

    return any(node.get(flag) is True for flag in DISPLAY_ONLY_FLAGS)


def operational_snapshot(
    nodes: list[dict],
    edges: list[dict],
    include_fixtures: bool = False,
) -> tuple[list[dict], list[dict]]:
    """Return the subset used for Delta and propagation.

    ``expanded_from`` is a display-only edge, so **only the edge** is filtered.
    Child nodes stay in the subset: they are real assets, and dropping them used
    to silently swallow their licence changes while leaving ordinary lineage
    edges dangling (``build_graph`` then re-creates the endpoint as an
    attribute-less node with no licence and no evidence chain).

    A node is removed only when the asset itself is explicitly flagged
    ``display_only`` / ``is_fixture``, and only while it carries no real lineage
    edge — otherwise removing it would resurrect exactly that empty node.

    ``include_fixtures=True`` is the demo switch: keep the flagged fixtures in
    Delta and propagation, matching what the rendered page shows.
    """

    lineage_edges = [edge for edge in edges if not _is_expansion_edge(edge)]
    lineage_endpoints = {
        str(edge.get(field))
        for edge in lineage_edges
        for field in ("source", "target")
        if edge.get(field)
    }
    if include_fixtures:
        return list(nodes), lineage_edges
    operational_nodes = [
        node
        for node in nodes
        if not _is_display_only(node) or _node_id(node) in lineage_endpoints
    ]
    return operational_nodes, lineage_edges
