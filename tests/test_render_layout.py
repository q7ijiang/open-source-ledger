from __future__ import annotations

from render_layout import (
    aggregate_risk_counts,
    aggregate_tone,
    is_aggregate_node,
    layout_graph,
)


def _node(node_id: str, name: str, **extra) -> dict:
    return {
        "id": node_id,
        "canonical_id": node_id,
        "name": name,
        "asset_type": "model",
        "purls": [],
        **extra,
    }


def _overlap(left: dict, right: dict) -> bool:
    return not (
        left["x"] + left["width"] <= right["x"]
        or right["x"] + right["width"] <= left["x"]
        or left["y"] + left["height"] <= right["y"]
        or right["y"] + right["height"] <= left["y"]
    )


def _node_box(node: dict) -> dict:
    card = node.get("render_card") or {}
    return {
        **node,
        "width": card.get("width", 0),
        "height": card.get("height", 0),
    }


def test_real_model_name_with_middle_dot_is_not_aggregate() -> None:
    node = _node(
        "model:real",
        "acme/model · production",
        purls=["pkg:modelscope/acme/model@master"],
    )

    assert is_aggregate_node(node) is False


def test_only_explicit_aggregate_metadata_or_count_signature_matches() -> None:
    explicit = _node(
        "aggregate:explicit",
        "acme/model · Finetunes",
        aggregate=True,
        coverage_status="AGGREGATE_ONLY",
        count=12,
    )
    legacy = _node("aggregate:legacy", "acme/model · Adapters (Total: 7)")
    model = _node("model:plain", "acme/model · eval")

    assert is_aggregate_node(explicit) is True
    assert is_aggregate_node(legacy) is True
    assert is_aggregate_node(model) is False


def test_aggregate_counts_do_not_double_count_expanded_children() -> None:
    aggregate = {
        "known_risk_counts": {"red": 1, "yellow": 1, "gray": 1},
    }

    counts = aggregate_risk_counts(
        aggregate,
        ["RISK_CONFIRMED", "RISK_POTENTIAL", "UNDETERMINED"],
    )

    assert counts == {"red": 1, "yellow": 1, "gray": 1}
    assert aggregate_tone(counts) == "RISK_CONFIRMED"


def test_layout_keeps_model_clusters_and_domain_cards_separate() -> None:
    nodes = []
    edges = []
    for owner_index in range(2):
        owner_id = f"model:{owner_index}"
        nodes.append(_node(owner_id, f"org/model-{owner_index}"))
        for domain_index in range(5):
            aggregate_id = f"aggregate:{owner_index}:{domain_index}"
            nodes.append(
                _node(
                    aggregate_id,
                    f"org/model-{owner_index} · 类型 {domain_index} (Total: {domain_index + 1})",
                    aggregate=True,
                    coverage_status="AGGREGATE_ONLY",
                    count=domain_index + 1,
                )
            )
            edges.append({"source": aggregate_id, "target": owner_id, "edge_type": "derived_from"})

    layout = layout_graph(nodes, edges, canvas_width=680)
    clusters = layout["clusters"]

    assert len(clusters) == 2
    assert not _overlap(clusters[0], clusters[1])
    assert clusters[1]["y"] - (clusters[0]["y"] + clusters[0]["height"]) >= 56
    assert all(node.get("render_card") for node in nodes if is_aggregate_node(node))
    assert all(node.get("render_tone") in {"NEUTRAL", "RISK_CONFIRMED", "RISK_POTENTIAL", "UNDETERMINED"} for node in nodes if is_aggregate_node(node))


def test_expanded_risk_child_keeps_its_own_decision() -> None:
    owner = _node("model:qwen", "Qwen/Qwen3-8B", decision="RISK_POTENTIAL")
    aggregate = _node(
        "aggregate:adapter",
        "Qwen/Qwen3-8B · 适配 (Total: 20)",
        aggregate=True,
        count=20,
        decision="UNDETERMINED",
    )
    child = _node(
        "model:adapter-a",
        "Qwen/Qwen3-8B · 适配 (Adapter-A)",
        decision="RISK_CONFIRMED",
        license="GPL-3.0",
        purls=["pkg:modelscope/Qwen/Qwen3-8B:adapter-a@1.0.0"],
    )
    edges = [
        {"source": aggregate["id"], "target": owner["id"], "edge_type": "derived_from"},
        {"source": aggregate["id"], "target": child["id"], "edge_type": "expanded_from"},
    ]

    layout = layout_graph([owner, aggregate, child], edges, canvas_width=680)

    assert child["decision"] == "RISK_CONFIRMED"
    assert child["license"] == "GPL-3.0"
    assert aggregate.get("render_tone") == "RISK_CONFIRMED"
    assert aggregate["decision"] == "UNDETERMINED"
    assert layout["clusters"][0]["expanded_count"] == 1
    assert child["render_role"] == "expanded_child"
    assert child["render_parent_id"] == aggregate["id"]
    assert child["render_card"]["label"] == "Adapter-A"
    assert child["y"] > aggregate["y"]
    cluster = layout["clusters"][0]
    assert cluster["y"] + cluster["height"] >= child["y"] + child["render_card"]["height"] / 2


def test_expanded_children_are_small_cards_inside_one_aggregate_cluster() -> None:
    owner = _node("model:owner", "org/base-model")
    aggregate = _node(
        "aggregate:adapters",
        "org/base-model · 适配 (Total: 20)",
        aggregate=True,
        coverage_status="AGGREGATE_ONLY",
        count=20,
    )
    children = [
        _node(
            f"model:adapter-{index}",
            f"org/base-model · 适配 (Adapter-{index})",
            decision=decision,
        )
        for index, decision in enumerate(
            ["RISK_CONFIRMED", "RISK_POTENTIAL", "UNDETERMINED"], start=1
        )
    ]
    edges = [{"source": aggregate["id"], "target": owner["id"], "edge_type": "derived_from"}]
    edges.extend(
        {
            "source": aggregate["id"],
            "target": child["id"],
            "edge_type": "expanded_from",
        }
        for child in children
    )

    layout = layout_graph([owner, aggregate, *children], edges, canvas_width=680)

    assert len(layout["clusters"]) == 1
    assert layout["clusters"][0]["expanded_count"] == 3
    assert all(child["render_role"] == "expanded_child" for child in children)
    assert all(
        child["render_card"]["width"] < aggregate["render_card"]["width"]
        for child in children
    )
    assert all(child["y"] > aggregate["y"] for child in children)
    assert not any(
        _overlap(_node_box(left), _node_box(right))
        for left in children
        for right in children
        if left is not right
    )
    assert aggregate["render_risk_counts"] == {"red": 1, "yellow": 1, "gray": 1}
    assert all(
        child["y"] + child["render_card"]["height"] / 2
        <= layout["clusters"][0]["y"] + layout["clusters"][0]["height"]
        for child in children
    )
