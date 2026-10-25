from __future__ import annotations

import bom_adapter


def test_convert_component_restores_open_source_ledger_decisions() -> None:
    component = {
        "type": "machine-learning-model",
        "name": "acme/demo",
        "version": "v1",
        "purl": "pkg:modelscope/acme/demo@v1",
        "properties": [
            {"name": "open-source-ledger:decision", "value": "RISK_POTENTIAL"},
            {"name": "open-source-ledger:decision_zh", "value": "潜在风险"},
            {"name": "open-source-ledger:risk_level", "value": "2"},
            {"name": "unrelated:decision", "value": "SAFE"},
        ],
    }

    asset = bom_adapter.convert_component(
        component,
        retrieved_at="2026-10-22T00:00:00Z",
        source_file="bom.json",
        snapshot_id="t1",
    )

    assert asset["decision"] == "RISK_POTENTIAL"
    assert asset["decision_zh"] == "潜在风险"
    assert asset["risk_level"] == 2


def test_convert_component_restores_aggregate_metadata() -> None:
    component = {
        "type": "machine-learning-model",
        "name": "acme/demo · 适配 (Total: 20)",
        "version": "v1",
        "purl": "pkg:modelscope/acme/demo:son:Adapters@v1",
        "properties": [
            {"name": "open-source-ledger:aggregate", "value": "True"},
            {"name": "open-source-ledger:coverage_status", "value": "AGGREGATE_ONLY"},
            {"name": "open-source-ledger:count", "value": "20"},
            {"name": "open-source-ledger:expanded_count", "value": "3"},
            {"name": "open-source-ledger:remaining_count", "value": "17"},
            {
                "name": "open-source-ledger:known_risk_counts",
                "value": "{\"red\":1,\"yellow\":1,\"gray\":1}",
            },
        ],
    }

    asset = bom_adapter.convert_component(
        component,
        retrieved_at="2026-10-22T00:00:00Z",
        source_file="bom.json",
        snapshot_id="t1",
    )

    assert asset["aggregate"] is True
    assert asset["coverage_status"] == "AGGREGATE_ONLY"
    assert asset["count"] == 20
    assert asset["expanded_count"] == 3
    assert asset["remaining_count"] == 17
    assert asset["known_risk_counts"] == {"red": 1, "yellow": 1, "gray": 1}
