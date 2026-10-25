from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import build_graph
import delta_engine
import render_diff

REPO_ROOT = Path(__file__).resolve().parent.parent


def _node(node_id: str, decision: str | None = None) -> dict:
    node = {"id": node_id, "name": node_id}
    if decision is not None:
        node["decision"] = decision
    return node


def _asset(node_id: str, license_: str | None, name: str | None = None, **extra) -> dict:
    asset = {
        "id": node_id,
        "canonical_id": node_id,
        "entity_key": "model:" + node_id,
        "name": name or node_id,
        "license": license_,
        "evidence_chain": [
            {
                "evidence_level": "A",
                "source_field": "license",
                "source_api": "modelscope",
            }
        ],
    }
    asset.update(extra)
    return asset


def _aggregate(owner: str = "owner") -> dict:
    return {
        "id": "aggregate",
        "canonical_id": "aggregate",
        "entity_key": f"model:{owner}:son:Adapters",
        "name": f"{owner} · 适配 (Total: 20)",
        "aggregate": True,
        "license": None,
    }


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


def test_expanded_child_license_change_still_produces_license_changed() -> None:
    """P1 回归：展开子节点的许可证变化不能被 operational_snapshot 静默吞掉。"""

    owner = _asset("owner", "Apache-2.0")
    aggregate = _aggregate()
    child_t0 = _asset("child", "GPL-3.0", "owner · 适配 (Adapter-A)")
    child_t1 = _asset("child", "Apache-2.0", "owner · 适配 (Adapter-A)")
    lineage = {"source": "aggregate", "target": "owner", "edge_type": "derived_from"}
    expansion = {
        "source": "aggregate",
        "target": "child",
        "edge_type": "expanded_from",
    }

    before_nodes, before_edges = render_diff.operational_snapshot(
        [owner, aggregate, child_t0], [lineage, expansion]
    )
    after_nodes, after_edges = render_diff.operational_snapshot(
        [owner, aggregate, child_t1], [lineage, expansion]
    )

    # 子节点仍然参与资产级 Diff，只是 expanded_from 边被过滤掉
    assert [node["id"] for node in after_nodes] == ["owner", "aggregate", "child"]
    assert after_edges == [lineage]

    events = delta_engine.detect_delta(
        before_nodes, after_nodes, before_edges, after_edges
    )
    assert [event["change_type"] for event in events] == ["license_changed"]
    assert events[0]["seed"] == "child"


def test_real_lineage_edge_to_expanded_child_keeps_node_attributes() -> None:
    """子节点带真实血缘边时，节点与边必须一起保留，不能被重建为空属性节点。"""

    owner = _asset("owner", "Apache-2.0")
    aggregate = _aggregate()
    child = _asset("child", "GPL-3.0", "owner · 适配 (Adapter-A)", decision="UNDETERMINED")
    edges = [
        {"source": "aggregate", "target": "owner", "edge_type": "derived_from"},
        {"source": "child", "target": "owner", "edge_type": "derived_from"},
        {"source": "aggregate", "target": "child", "edge_type": "expanded_from"},
    ]

    nodes, operational_edges = render_diff.operational_snapshot(
        [owner, aggregate, child], edges
    )

    assert "child" in {node["id"] for node in nodes}
    assert operational_edges == edges[:2]

    graph = build_graph.build_graph(nodes, operational_edges)
    assert graph.nodes["child"]["license"] == "GPL-3.0"
    assert graph.nodes["child"]["evidence_chain"]
    assert graph.nodes["child"]["decision"] == "UNDETERMINED"


def test_only_explicit_display_only_flag_filters_nodes() -> None:
    """演示夹具必须显式标注，不能靠 expanded_from 推导。"""

    owner = _asset("owner", "Apache-2.0")
    aggregate = _aggregate()
    fixture = _asset("fixture", "MIT", "owner · 适配 (Adapter-A)", is_fixture=True)
    demo = _asset("demo", "MIT", "owner · 适配 (Adapter-B)", display_only=True)
    edges = [
        {"source": "aggregate", "target": "owner", "edge_type": "derived_from"},
        {"source": "aggregate", "target": "fixture", "edge_type": "expanded_from"},
        {"source": "aggregate", "target": "demo", "edge_type": "expanded_from"},
    ]

    nodes, operational_edges = render_diff.operational_snapshot(
        [owner, aggregate, fixture, demo], edges
    )
    assert [node["id"] for node in nodes] == ["owner", "aggregate"]
    assert operational_edges == edges[:1]

    # 被标记为夹具但带真实血缘边时仍需保留，否则边会把空节点复活
    real_edge = {"source": "fixture", "target": "owner", "edge_type": "derived_from"}
    nodes, operational_edges = render_diff.operational_snapshot(
        [owner, fixture], [real_edge]
    )
    assert [node["id"] for node in nodes] == ["owner", "fixture"]
    assert operational_edges == [real_edge]


def test_event_list_annotates_distinct_affected_targets() -> None:
    """P2：传播事件只有 seed/path，列表目标名必须取证书的 affected。"""

    seed = "Qwen/Qwen3-8B@master"
    events = []
    certificates = []
    for index, domain in enumerate(
        ["Adapters", "FineTunes", "Merges", "Quantizations", "Datasets"]
    ):
        event_id = f"evt-t1-{index:03d}-p01"
        events.append(
            {
                "event_id": event_id,
                "seed": seed,
                "change_type": "license_changed",
                "decision": "RISK_POTENTIAL",
                "path": [{"source": domain, "target": seed}],
            }
        )
        certificates.append(
            {
                "event_id": event_id,
                "seed": seed,
                "affected": domain,
                "decision": "RISK_POTENTIAL",
            }
        )

    render_diff.annotate_event_endpoints(events, certificates)

    targets = [event["display_target"] for event in events]
    assert len(set(targets)) == 5, f"事件列表目标名仍然重复：{targets}"
    assert all(event["display_source"] == seed for event in events)

    fallback = render_diff.annotate_event_endpoints(
        [
            {"event_id": "x", "seed": "a", "path": [{"source": "b", "target": "a"}]},
            {"event_id": "y", "seed": "a", "path": []},
        ],
        [],
    )
    assert fallback[0]["display_target"] == "b"
    assert fallback[1]["display_target"] == "a"


def test_real_review_fixture_renders_distinct_propagation_targets(tmp_path: Path) -> None:
    """真实 t0/t1 夹具：五条传播事件必须显示到四个不同聚合域，而不是种子自指。"""

    out = tmp_path / "diff.html"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "render_diff.py"),
            "--before",
            str(REPO_ROOT / "data/test_scenarios/project_t0_bom.json"),
            "--after",
            str(REPO_ROOT / "data/test_scenarios/project_t1_bom.json"),
            "--output",
            str(out),
        ],
        check=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )
    html = out.read_text(encoding="utf-8")
    match = re.search(r"const DATA = (\{.*?\});\n", html, re.S)
    assert match, "渲染结果缺少 DATA 数据块"
    data = json.loads(match.group(1))

    events = data["events"]
    assert len(events) == 5
    # 1 条种子事件显示种子自身；其余 4 条必须分别指向四个不同聚合域
    self_events = [e for e in events if e["display_target"] == e["display_source"]]
    propagated = [e for e in events if e["display_target"] != e["display_source"]]
    assert len(self_events) == 1
    assert len(propagated) == 4
    targets = {event["display_target"] for event in propagated}
    assert len(targets) == 4, f"传播目标名重复：{sorted(targets)}"
    assert all(event["display_target"].endswith("@master") for event in propagated)
    assert len(data["certificates"]) == 4


def test_diff_template_uses_snapshot_tabs_and_per_snapshot_expansion() -> None:
    template = render_diff.TPL

    assert 'data-snapshot="t0"' in template
    assert 'data-snapshot="t1"' in template
    assert 'class="side"' not in template
    assert "const expandedBySnapshot = {t0:new Set(), t1:new Set()};" in template
    assert "expandedDomains = new Set();" not in template
    assert "const expandedDomains = expandedSet(snapshot);" in template
    assert "visible = expandedDomains.has(n.render_parent_id)" in template
    assert "if (aggregateId && !expandedDomains.has(aggregateId)) return null;" in template
    assert "const expanded = expandedSet(snapshot);" in template
    assert "expandedSet(preferred).add(n.render_parent_id);" in template
    assert "button.addEventListener(\"click\", () => activateSnapshot" in template
    assert "ev.display_source || ev.source || ev.seed" in template
    assert "ev.display_target || ev.target || ev.seed" in template
    assert "const route = (fromName === toName)" in template
