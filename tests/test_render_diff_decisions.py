from __future__ import annotations

import render_diff


def _node(node_id: str, decision: str | None = None) -> dict:
    node = {"id": node_id, "name": node_id}
    if decision is not None:
        node["decision"] = decision
    return node


def test_apply_event_decisions_uses_strongest_propagated_decision() -> None:
    nodes_t0 = [_node("seed"), _node("affected"), _node("safe", "SAFE")]
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

    for nodes in (nodes_t0, nodes_t1):
        by_id = {node["id"]: node for node in nodes}
        assert by_id["seed"]["decision"] == "RISK_CONFIRMED"
        assert by_id["affected"]["decision"] == "RISK_CONFIRMED"
        assert by_id["seed"]["decision_source"] == "diff_propagation"
        assert by_id["affected"]["decision_source"] == "diff_propagation"
        assert by_id["safe"]["decision"] == "SAFE"
        assert "decision_source" not in by_id["safe"]
