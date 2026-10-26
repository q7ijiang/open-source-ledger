from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from modelscope_lineage import extract

CATALOG = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "modelscope"
    / "recursive_lineage"
    / "model_catalog.json"
)


def _catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def _fetchers():
    data = _catalog()["models"]

    def detail(ns: str, name: str):
        entry = data.get(f"{ns}/{name}")
        return deepcopy(entry["detail"]) if entry else None

    def lineage(ns: str, name: str):
        entry = data.get(f"{ns}/{name}")
        return deepcopy(entry["lineage"]) if entry else None

    return detail, lineage


def test_recursive_upstream_closure_uses_both_parent_sources() -> None:
    detail, lineage = _fetchers()
    assets, edges = extract(
        "org",
        "AppModel",
        "snapshot",
        "fixture://modelscope",
        include_downstream=False,
        detail_fetcher=detail,
        lineage_fetcher=lineage,
    )

    names = {asset["name"] for asset in assets}
    assert names == {
        "org/AppModel",
        "org/Layer3",
        "org/Layer2",
        "org/Layer1",
        "org/BaseModel",
    }
    source_fields = {edge["source_field"] for edge in edges}
    assert "Data.BaseModel" in source_fields
    assert "lineage.ParentsModels" in source_fields
    assert all(not asset.get("aggregate") for asset in assets)

    root = next(asset for asset in assets if asset["name"] == "org/AppModel")
    assert root["lineage_complete"] is True
    assert root["lineage_status"] == "complete"
    assert root["resolved_upstream_count"] == 4
    assert root["max_depth_seen"] == 4


def test_model_survey_keeps_downstream_aggregate_but_project_mode_does_not() -> None:
    detail, lineage = _fetchers()
    project_assets, _ = extract(
        "org",
        "AppModel",
        "project",
        "fixture://modelscope",
        include_downstream=False,
        detail_fetcher=detail,
        lineage_fetcher=lineage,
    )
    survey_assets, _ = extract(
        "org",
        "AppModel",
        "survey",
        "fixture://modelscope",
        include_downstream=True,
        detail_fetcher=detail,
        lineage_fetcher=lineage,
    )

    assert not [asset for asset in project_assets if asset.get("aggregate")]
    aggregates = [asset for asset in survey_assets if asset.get("aggregate")]
    assert len(aggregates) == 1
    assert aggregates[0]["count"] == 99


def test_cycle_is_detected_without_infinite_recursion() -> None:
    detail, lineage = _fetchers()
    assets, edges = extract(
        "org",
        "CycleA",
        "cycle",
        "fixture://modelscope",
        detail_fetcher=detail,
        lineage_fetcher=lineage,
    )

    root = next(asset for asset in assets if asset["name"] == "org/CycleA")
    assert root["lineage_status"] == "cycle_detected"
    assert root["lineage_complete"] is False
    assert root["lineage_cycles"]
    assert len(edges) >= 2


def test_node_budget_preserves_auditable_placeholder() -> None:
    detail, lineage = _fetchers()
    assets, _ = extract(
        "org",
        "AppModel",
        "budget",
        "fixture://modelscope",
        max_upstream_nodes=2,
        detail_fetcher=detail,
        lineage_fetcher=lineage,
    )

    root = next(asset for asset in assets if asset["name"] == "org/AppModel")
    assert root["lineage_status"] == "truncated"
    assert root["lineage_truncation_reason"] == "node_budget"
    assert root["unresolved_upstream_models"]
    placeholder = next(asset for asset in assets if asset.get("unresolved"))
    assert placeholder["lineage_status"] == "budget_exhausted"
    assert placeholder["purls"]
