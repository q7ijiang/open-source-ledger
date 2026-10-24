from __future__ import annotations


def operational_snapshot(
    nodes: list[dict], edges: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Return the subset used for Delta and propagation.

    ``expanded_from`` children are display-only evidence. They must remain in
    the rendered graph, but cannot become timeline changes or propagation
    seeds merely because a risk domain was expanded for visualization.
    """

    expanded_child_ids = {
        str(edge.get("target"))
        for edge in edges
        if (
            edge.get("edge_type") == "expanded_from"
            or edge.get("source_field") == "expanded_from"
        )
        and edge.get("target")
    }
    operational_nodes = [
        node
        for node in nodes
        if str(
            node.get("id")
            or node.get("canonical_id")
            or node.get("entity_key")
            or ""
        )
        not in expanded_child_ids
    ]
    operational_edges = [
        edge
        for edge in edges
        if edge.get("edge_type") != "expanded_from"
        and edge.get("source_field") != "expanded_from"
    ]
    return operational_nodes, operational_edges
