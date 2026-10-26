from __future__ import annotations

from render_layout import layout_graph


def _node(node_id: str, name: str, **extra) -> dict:
    return {
        "id": node_id,
        "canonical_id": node_id,
        "name": name,
        "asset_type": "model",
        "purls": [f"pkg:modelscope/{name}@master"],
        **extra,
    }


def _edge(source: str, target: str) -> dict:
    return {"source": source, "target": target, "edge_type": "derived_from"}


def test_lineage_layout_places_ancestors_in_lower_layers() -> None:
    direct = _node("model:direct", "org/chat-awq", lineage_role="root", lineage_depth=0)
    finetuned = _node(
        "model:finetuned",
        "org/chat-instruct",
        lineage_role="upstream",
        lineage_type_ch="微调",
        lineage_depth=1,
    )
    base = _node(
        "model:base",
        "org/chat-base",
        lineage_role="upstream",
        lineage_type_ch="基模型",
        lineage_depth=2,
    )
    nodes = [direct, finetuned, base]
    edges = [_edge(direct["id"], finetuned["id"]), _edge(finetuned["id"], base["id"])]

    layout = layout_graph(nodes, edges, canvas_width=1280)

    assert layout["layout_mode"] == "lineage_dag"
    assert len(layout["clusters"]) == 3
    assert direct["render_layer"] == 0
    assert finetuned["render_layer"] == 1
    assert base["render_layer"] == 2
    assert base["y"] < finetuned["y"] < direct["y"]
    assert direct["render_role_label"] == "项目直接使用"
    assert base["render_role_label"] == "上游 · 基座模型"
    assert all(node["render_card"]["width"] > 0 for node in nodes)
    assert all(len(node["render_card"]["label"]) <= 24 for node in nodes)
    assert base["render_role_short"] == "上游·基座模型"
    assert all(cluster["kind"] == "lineage_layer" for cluster in layout["clusters"])


def test_lineage_layout_handles_shared_ancestor_and_isolated_model() -> None:
    chat = _node("model:chat", "org/chat", lineage_role="root", lineage_depth=0)
    coder = _node("model:coder", "org/coder", lineage_role="root", lineage_depth=0)
    shared = _node(
        "model:shared",
        "org/shared-base",
        lineage_role="upstream",
        lineage_type_ch="基模型",
        lineage_depth=1,
    )
    isolated = _node("model:embed", "org/embedding", lineage_role="root", lineage_depth=0)
    nodes = [chat, coder, shared, isolated]
    edges = [_edge(chat["id"], shared["id"]), _edge(coder["id"], shared["id"])]

    layout = layout_graph(nodes, edges, canvas_width=680)

    assert len(layout["clusters"]) == 2
    assert layout["cycle_nodes"] == []
    assert shared["render_layer"] == 1
    assert shared["y"] < min(chat["y"], coder["y"])
    assert isolated["render_layer"] == 0


def test_lineage_layout_survives_inconsistent_cycle_without_dropping_nodes() -> None:
    first = _node("model:a", "org/a")
    second = _node("model:b", "org/b")
    nodes = [first, second]
    edges = [_edge(first["id"], second["id"]), _edge(second["id"], first["id"])]

    layout = layout_graph(nodes, edges, canvas_width=1280)

    assert set(layout["cycle_nodes"]) == {first["id"], second["id"]}
    assert all(node.get("render_card") for node in nodes)
