from __future__ import annotations

import render_diff


def _node(node_id: str, decision: str | None = None) -> dict:
    node = {"id": node_id, "name": node_id}
    if decision is not None:
        node["decision"] = decision
    return node


def test_apply_event_decisions_uses_strongest_propagated_decision() -> None:
    nodes_t0 = [_node("seed", "SAFE"), _node("affected", "SAFE"), _node("safe", "SAFE")]
    nodes_t1 = [_node("seed"), _node("affected"), _node("safe", "SAFE")]
    events = [
        {
            "event_id": "evt-1",
            "seed": "seed",
            "decision": "RISK_POTENTIAL",
            "path": [],
        },
        {
            "event_id": "evt-1-p01",
            "seed": "seed",
            "decision": "RISK_CONFIRMED",
            "path": [{"source": "affected", "target": "seed"}],
        },
        {
            "event_id": "evt-2",
            "seed": "safe",
            "decision": "UNDETERMINED",
            "path": [],
        },
    ]
    certificates = [
        {
            "seed": "seed",
            "affected": "affected",
            "decision": "RISK_CONFIRMED",
        }
    ]

    render_diff.apply_event_decisions(nodes_t0, nodes_t1, events, certificates)

    by_id_t0 = {node["id"]: node for node in nodes_t0}
    assert by_id_t0["seed"]["decision"] == "SAFE"
    assert by_id_t0["affected"]["decision"] == "SAFE"
    assert all("decision_source" not in node for node in nodes_t0)

    by_id_t1 = {node["id"]: node for node in nodes_t1}
    assert by_id_t1["seed"]["decision"] == "RISK_CONFIRMED"
    assert by_id_t1["affected"]["decision"] == "RISK_CONFIRMED"
    assert by_id_t1["seed"]["decision_source"] == "diff_propagation"
    assert by_id_t1["affected"]["decision_source"] == "diff_propagation"
    assert by_id_t1["safe"]["decision"] == "SAFE"
    assert "decision_source" not in by_id_t1["safe"]

    aggregate_t0 = {"id": "aggregate", "name": "Qwen · 适配 (Total: 3)", "aggregate": True, "decision": "UNDETERMINED"}
    aggregate_t1 = dict(aggregate_t0)
    render_diff.apply_event_decisions(
        [aggregate_t0],
        [aggregate_t1],
        [{"seed": "aggregate", "decision": "RISK_CONFIRMED", "path": []}],
        [],
    )
    assert aggregate_t0["decision"] == "UNDETERMINED"
    assert aggregate_t1["decision"] == "UNDETERMINED"
    assert "decision_source" not in aggregate_t0
import delta_engine


def test_expanded_children_are_display_only_for_delta() -> None:
    owner = {
        "id": "owner",
        "canonical_id": "owner",
        "entity_key": "model:owner",
        "name": "owner",
        "license": "Apache-2.0",
    }
    aggregate = {
        "id": "aggregate",
        "canonical_id": "aggregate",
        "entity_key": "model:owner:son:Adapters",
        "name": "owner · 适配 (Total: 20)",
        "aggregate": True,
        "license": None,
    }
    child = {
        "id": "child",
        "canonical_id": "child",
        "entity_key": "model:owner:adapter:child",
        "name": "owner · 适配 (Adapter-A)",
        "license": "GPL-3.0",
    }
    lineage = {"source": "aggregate", "target": "owner", "edge_type": "derived_from"}
    expansion = {
        "source": "aggregate",
        "target": "child",
        "edge_type": "expanded_from",
    }

    before_nodes, before_edges = render_diff.operational_snapshot(
        [owner, aggregate], [lineage]
    )
    after_nodes, after_edges = render_diff.operational_snapshot(
        [owner, aggregate, child], [lineage, expansion]
    )

    assert [node["id"] for node in after_nodes] == ["owner", "aggregate"]
    assert after_edges == [lineage]
    assert delta_engine.detect_delta(
        before_nodes, after_nodes, before_edges, after_edges
    ) == []


def test_diff_template_uses_snapshot_tabs_and_click_expansion() -> None:
    template = render_diff.TPL

    assert 'data-snapshot="t0"' in template
    assert 'data-snapshot="t1"' in template
    assert 'class="side"' not in template
    assert "const expandedDomains = new Set();" in template
    assert "visible = expandedDomains.has(n.render_parent_id)" in template
    assert "if (aggregateId && !expandedDomains.has(aggregateId)) return null;" in template
    assert "button.addEventListener(\"click\", () => activateSnapshot" in template
