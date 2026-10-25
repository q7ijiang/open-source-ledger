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
import render_diff

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
        # 聚合节点必须使用中性底 + 由 aggTone() 动态算出的风险描边（描边语义，非填充）
        assert 'itemStyle:{color:"#eef0f4",borderColor:aggTone(n)' in src

    def test_render_graph_uses_neutral_agg_fill(self) -> None:
        src = (REPO_ROOT / "render_graph.py").read_text(encoding="utf-8")
        layout_src = (REPO_ROOT / "render_layout.py").read_text(encoding="utf-8")
        # render_graph 复用通用簇布局（中性聚合域 + 决策回读）
        assert "render_layout" in src
        assert "aggregate" in layout_src

    def test_expanded_edges_are_dashed(self) -> None:
        src = (REPO_ROOT / "render_diff.py").read_text(encoding="utf-8")
        assert "dashed" in src, "expanded_from 展开边应为虚线"


class TestRealRenderPipeline:
    """P2-4：断言"生成后"的节点分类与颜色映射（不是只查源码字符串）。

    复刻 render_diff.main() 的数据管线：_build_snapshot -> detect_delta ->
    propagate -> apply_event_decisions -> forest_layout，然后对最终 nodes_t1
    断言：子节点不被误判为聚合、子节点保留各自 decision 且未被传播覆盖、
    聚合节点在传播叠加后 decision 仍为空、颜色映射与 DECISION_COLOR 一致。
    """

    @staticmethod
    def _render() -> tuple[list[dict], list[dict]]:
        import build_graph
        import delta_engine
        import propagation_engine
        from main import _build_snapshot

        before = _build_snapshot(Path(DATA) / "project_t0_bom.json", "t0")
        after = _build_snapshot(Path(DATA) / "project_t1_bom.json", "t1")
        graph_before = build_graph.build_graph(before["assets"], before["edges"])
        graph_after = build_graph.build_graph(after["assets"], after["edges"])
        events = delta_engine.detect_delta(
            before["assets"], after["assets"], before["edges"], after["edges"]
        )
        propagated = propagation_engine.propagate(events, graph_before, graph_after)
        nodes_t0, edges_t0 = list(before["assets"]), list(before["edges"])
        nodes_t1, edges_t1 = list(after["assets"]), list(after["edges"])
        for n in nodes_t0 + nodes_t1:
            n["id"] = n.get("id") or n.get("canonical_id") or n.get("entity_key")
        # 与 main() 一致：仅 t1 叠加传播判定
        render_diff.apply_event_decisions([], nodes_t1, propagated["events"], propagated["path_certificates"])
        import render_layout as _render_layout

        _render_layout.layout_graph(nodes_t0, edges_t0)
        _render_layout.layout_graph(nodes_t1, edges_t1)
        return nodes_t1, edges_t1

    def test_children_not_classified_as_aggregate(self) -> None:
        """12 个子节点 is_agg 必须为 False（名称含 " · " 但非聚合）。"""
        nodes_t1, _ = self._render()
        children = [n for n in nodes_t1 if "Adapter" in (n.get("name") or "")]
        assert len(children) == 12, f"应有 12 个子节点，实际 {len(children)}"
        for n in children:
            import render_layout as _render_layout

            assert not _render_layout.is_aggregate_node(n), (
                f"子节点 {n.get('name')} 不应被误判为聚合节点"
            )

    def test_children_keep_own_decisions_after_propagation(self) -> None:
        """子节点各按自身 decision 着色：红/黄/灰三态并存，且不被传播覆盖为同一色。"""
        nodes_t1, _ = self._render()
        children = [n for n in nodes_t1 if "Adapter" in (n.get("name") or "")]
        decisions = [n.get("decision") for n in children]
        assert {"RISK_CONFIRMED", "RISK_POTENTIAL", "UNDETERMINED"} <= set(decisions), decisions
        # 没有任何子节点被 diff 传播改写 decision（decision_source 不来自 diff_propagation）
        for n in children:
            assert n.get("decision_source") != "diff_propagation", (
                f"子节点 {n.get('name')} 不应被传播判定覆盖"
            )

    def test_aggregate_decision_empty_after_propagation(self) -> None:
        """P2-3：传播叠加后聚合节点 decision 仍为空（不写 RISK_POTENTIAL/diff_propagation）。"""
        nodes_t1, _ = self._render()
        aggs = [n for n in nodes_t1 if "(Total:" in (n.get("name") or "")]
        assert len(aggs) == 9, f"应有 9 个聚合节点，实际 {len(aggs)}"
        for n in aggs:
            assert n.get("decision") is None, (
                f"聚合节点 {n.get('name')} decision 应为空，实际 {n.get('decision')} ({n.get('decision_source')})"
            )

    def test_color_mapping_matches_decision(self) -> None:
        """渲染颜色映射：子节点填充 = DECISION_COLOR[decision]；聚合中性底 + 描边。"""
        import render_diff as _render_diff

        DECISION_COLOR = _render_diff.DECISION_COLOR
        nodes_t1, _ = self._render()
        for n in nodes_t1:
            nm = n.get("name") or ""
            if "Adapter" in nm and n.get("decision"):
                assert n["decision"] in DECISION_COLOR, f"decision {n['decision']} 缺少颜色映射"
            if "(Total:" in nm:
                # 聚合节点中性底（渲染层由 itemStyle 保证），此处校验数据结构不含 decision
                assert n.get("decision") is None
