# -*- coding: utf-8 -*-
"""聚合节点"风险域"展示的约束测试。

覆盖组长 10-23 命令第⑤条验收点：
1. 聚合节点不能被标记为 SAFE（无许可证证据时不得预填安全）。
2. 聚合节点不能因内部子节点有风险而被标记为 RISK_CONFIRMED（自身保持中性）。
3. 已知风险模型子节点按各自真实 decision 着色（RISK_CONFIRMED / RISK_POTENTIAL / UNDETERMINED）。
4. expanded_count + remaining_count == count。
5. 聚合节点只显示统计徽标，不整体染红（渲染层由 itemStyle 中性底 + 描边实现，此处校验数据结构与渲染判定）。

数据来源：data/test_scenarios/project_t0_bom.json 与 project_t1_bom.json（真实 ModelScope 场景）。
"""

from __future__ import annotations

import json
from pathlib import Path

import bom_adapter

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data" / "test_scenarios"
PROP_PREFIX = "open-source-ledger:"

AGG_REQUIRED_FIELDS = ("coverage_status", "count", "expanded_count", "remaining_count", "known_risk_counts")


def _load_bom(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _props(component: dict) -> dict:
    out: dict[str, str] = {}
    for p in component.get("properties", []) or []:
        out[p["name"]] = p["value"]
    return out


def _aggregate_components(bom: dict) -> list[dict]:
    comps = []
    for c in bom.get("components", []) or []:
        props = _props(c)
        if props.get(PROP_PREFIX + "aggregate") in ("True", "true", "1"):
            comps.append(c)
    return comps


def _child_components(bom: dict) -> list[dict]:
    comps = []
    for c in bom.get("components", []) or []:
        props = _props(c)
        if props.get(PROP_PREFIX + "expanded_from"):
            comps.append(c)
    return comps


class TestAggregateNeutral:
    """聚合节点自身保持中性：不 SAFE、不整体 RISK_CONFIRMED。"""

    def test_t0_t1_aggregates_never_prefilled_safe(self) -> None:
        for name in ("project_t0_bom.json", "project_t1_bom.json"):
            bom = _load_bom(name)
            for agg in _aggregate_components(bom):
                props = _props(agg)
                assert props.get(PROP_PREFIX + "decision") is None, (
                    f"{name}: 聚合节点不应预填 decision={props.get(PROP_PREFIX + 'decision')}"
                )
                assert props.get(PROP_PREFIX + "decision") != "SAFE"

    def test_aggregates_carry_stats_contract(self) -> None:
        for name in ("project_t0_bom.json", "project_t1_bom.json"):
            bom = _load_bom(name)
            for agg in _aggregate_components(bom):
                props = _props(agg)
                assert props.get(PROP_PREFIX + "coverage_status") == "AGGREGATE_ONLY", name
                for field in ("count", "expanded_count", "remaining_count"):
                    assert PROP_PREFIX + field in props, f"{name}: 聚合节点缺少 {field}"
                    int(props[PROP_PREFIX + field])  # 可转 int
                assert PROP_PREFIX + "known_risk_counts" in props, f"{name}: 聚合节点缺少 known_risk_counts"

    def test_expanded_plus_remaining_equals_count(self) -> None:
        for name in ("project_t0_bom.json", "project_t1_bom.json"):
            bom = _load_bom(name)
            for agg in _aggregate_components(bom):
                props = _props(agg)
                count = int(props[PROP_PREFIX + "count"])
                expanded = int(props[PROP_PREFIX + "expanded_count"])
                remaining = int(props[PROP_PREFIX + "remaining_count"])
                assert expanded + remaining == count, (
                    f"{name}: expanded({expanded}) + remaining({remaining}) != count({count})"
                )

    def test_aggregate_not_overridden_to_confirmed(self) -> None:
        """转换后聚合节点 asset 不得出现 decision=RISK_CONFIRMED（即使内部有红）。"""
        for name in ("project_t0_bom.json", "project_t1_bom.json"):
            bom = _load_bom(name)
            assets = bom_adapter.convert_bom(
                bom=bom,
                source_file=str((DATA / name).resolve()),
                snapshot_id=name.split("_")[1].split(".")[0],
            )
            for a in assets:
                if a.get("aggregate"):
                    assert a.get("decision") is None, (
                        f"{name}: 聚合节点 {a.get('name')} 不应有 decision={a.get('decision')}"
                    )
                    assert a.get("decision") != "RISK_CONFIRMED"


class TestExpandedChildren:
    """已知风险模型作为独立子节点，使用各自真实 decision。"""

    def test_t1_has_expanded_children_with_real_decisions(self) -> None:
        bom = _load_bom("project_t1_bom.json")
        children = _child_components(bom)
        assert len(children) >= 3  # 至少有一个聚合域展开 3 个子节点
        for child in children:
            props = _props(child)
            decision = props.get(PROP_PREFIX + "decision")
            assert decision in ("RISK_CONFIRMED", "RISK_POTENTIAL", "UNDETERMINED"), (
                f"子节点 {child.get('name')} decision={decision} 不合法"
            )
            # 子节点必须通过 expanded_from 指回聚合节点
            assert props.get(PROP_PREFIX + "expanded_from"), (
                f"子节点 {child.get('name')} 缺少 expanded_from"
            )

    def test_t1_children_red_yellow_gray_present(self) -> None:
        """展开样例应覆盖红/黄/灰三种状态（设计稿 Adapter-A/B/C 语义）。"""
        bom = _load_bom("project_t1_bom.json")
        decisions = {_props(c).get(PROP_PREFIX + "decision") for c in _child_components(bom)}
        assert {"RISK_CONFIRMED", "RISK_POTENTIAL", "UNDETERMINED"} <= decisions

    def test_t0_has_no_expanded_children(self) -> None:
        bom = _load_bom("project_t0_bom.json")
        assert _child_components(bom) == []


class TestRenderBadgeNotFullRed:
    """渲染层徽标逻辑：聚合节点中性底、红描边但不整体染红（源码级约束）。"""

    def test_render_diff_uses_neutral_agg_fill(self) -> None:
        src = (REPO_ROOT / "render_diff.py").read_text(encoding="utf-8")
        # 聚合节点填充色是中性浅灰，而非风险红
        assert "#eef0f4" in src, "聚合节点应使用中性底色"
        # 描边按 known_risk_counts 分级：红 > 黄 > 灰 > 无风险
        assert "#f56c6c" in src, "聚合风险域应具备红色描边（徽标而非填充）"
        # 聚合节点必须使用 rect 符号且带 borderColor（描边语义）
        assert 'symbol: agg ? "rect"' in src

    def test_render_graph_uses_neutral_agg_fill(self) -> None:
        src = (REPO_ROOT / "render_graph.py").read_text(encoding="utf-8")
        assert "#eef0f4" in src
        assert "#f56c6c" in src

    def test_expanded_edges_are_dashed(self) -> None:
        src = (REPO_ROOT / "render_diff.py").read_text(encoding="utf-8")
        assert "dashed" in src, "expanded_from 展开边应为虚线"
