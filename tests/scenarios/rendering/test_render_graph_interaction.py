from __future__ import annotations

import render_graph


def test_project_graph_aggregates_collapse_until_clicked() -> None:
    """P2 回归：项目级图与 Diff 页一致——聚合域默认折叠，点击后展开。"""

    tpl = render_graph.TPL

    assert "const expandedDomains = new Set();" in tpl
    assert "const childrenByAggregate = {};" in tpl
    assert "function buildNodes() {" in tpl
    assert "function buildLinks() {" in tpl
    assert "const visible = expandedDomains.has(n.render_parent_id);" in tpl
    assert "symbolSize:visible ? [n.render_card?.width || 72, n.render_card?.height || 38] : [0, 0]," in tpl
    assert "if (e.edge_type === \"expanded_from\" || isAggregate(source) || isAggregate(target)) return null;" in tpl
    assert "aggregate membership" in tpl.lower() or "grouping" in tpl.lower()
    assert "data:buildNodes()," in tpl
    assert "links:buildLinks()," in tpl
    assert "}, true);" in tpl
    assert '点击${expanded ? "收起" : "展开"} ${childCount} 个模型' in tpl
    assert "if (expandedDomains.has(raw.id)) expandedDomains.delete(raw.id);" in tpl
    assert "else expandedDomains.add(raw.id);" in tpl
