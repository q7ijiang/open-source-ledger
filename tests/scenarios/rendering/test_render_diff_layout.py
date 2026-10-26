from __future__ import annotations

import copy
from render_diff import synchronize_diff_layouts


def _node(model_id: str, *, role: str = "upstream") -> dict:
    return {
        "id": f"model:modelscope/{model_id}@master",
        "canonical_id": f"model:modelscope/{model_id}@master",
        "name": model_id,
        "asset_type": "model",
        "lineage_role": role,
        "lineage_depth": 0 if role == "root" else 1,
        "decision": "SAFE",
    }


def _edge(source: dict, target: dict) -> dict:
    return {
        "source": source["id"],
        "target": target["id"],
        "edge_type": "derived_from",
    }


def test_diff_layout_reuses_one_coordinate_space_for_common_models() -> None:
    base = _node("org/base")
    direct = _node("org/direct", role="root")
    added = _node("org/added", role="root")

    nodes_t0 = [direct, base]
    nodes_t1 = [copy.deepcopy(direct), copy.deepcopy(base), added]
    edges_t0 = [_edge(direct, base)]
    edges_t1 = [_edge(direct, base), _edge(added, base)]

    layout = synchronize_diff_layouts(
        nodes_t0,
        edges_t0,
        nodes_t1,
        edges_t1,
        canvas_width=1080,
    )

    assert layout["layout_mode"] == "lineage_dag"
    assert (direct["x"], direct["y"]) == (nodes_t1[0]["x"], nodes_t1[0]["y"])
    assert (base["x"], base["y"]) == (nodes_t1[1]["x"], nodes_t1[1]["y"])
    assert direct["render_layer"] == added["render_layer"] == 0
    assert base["render_layer"] == 1


def test_diff_layout_keeps_removed_node_slot_without_moving_common_nodes() -> None:
    base = _node("org/base")
    direct = _node("org/direct", role="root")
    removed = _node("org/old-upstream", role="root")

    nodes_t0 = [direct, removed, base]
    nodes_t1 = [copy.deepcopy(direct), copy.deepcopy(base)]
    edges_t0 = [_edge(direct, base), _edge(removed, base)]
    edges_t1 = [_edge(direct, base)]

    synchronize_diff_layouts(
        nodes_t0,
        edges_t0,
        nodes_t1,
        edges_t1,
        canvas_width=1080,
    )

    assert (direct["x"], direct["y"]) == (nodes_t1[0]["x"], nodes_t1[0]["y"])
    assert (base["x"], base["y"]) == (nodes_t1[1]["x"], nodes_t1[1]["y"])


def test_rendered_pages_expose_report_download_and_ai_status() -> None:
    import render_diff
    import render_graph

    assert 'id="download-report"' in render_graph.TPL
    assert 'id="open-report"' in render_graph.TPL
    assert 'id="report-modal"' in render_graph.TPL
    assert 'aria-modal="true"' in render_graph.TPL
    assert "REPORT_MARKDOWN" in render_graph.TPL
    assert "AI 证据已启用" in render_graph.TPL
    assert "renderLineageForest" in render_graph.TPL

    assert 'id="download-report"' in render_diff.TPL
    assert 'id="open-report"' in render_diff.TPL
    assert 'id="report-modal"' in render_diff.TPL
    assert 'aria-modal="true"' in render_diff.TPL
    assert "REPORT_MARKDOWN" in render_diff.TPL
    assert "AI 状态" in render_diff.TPL
    assert "同一模型在 t0/t1 保持相同坐标" in render_diff.TPL
