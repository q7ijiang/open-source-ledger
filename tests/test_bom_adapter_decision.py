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
