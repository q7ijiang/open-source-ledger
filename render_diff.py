# -*- coding: utf-8 -*-
"""--diff 时间轴风险传播图渲染器：左 t0、右 t1，中间红色箭头标传播路径，点击弹出 path_certificates。

用法：
  python render_diff.py --before data/test_scenarios/ms_t0_bom.json --after data/test_scenarios/ms_t1_bom.json \
      --output outputs/ms_diff/diff_lineage.html

链路与 main.py --diff 完全一致（只读 BOM 固化的 pedigree 边，零在线请求）：
  _build_snapshot → build_graph → delta_engine.detect_delta → propagation_engine.propagate
"""
import argparse
import json
import shutil
from pathlib import Path
from collections import Counter

import build_graph
import delta_engine
import propagation_engine

DECISION_COLOR = {
    "RISK_CONFIRMED": "#f56c6c",
    "RISK_POTENTIAL": "#e6a23c",
    "SAFE": "#67c23a",
    "UNDETERMINED": "#d3d7de",
}
DECISION_LABEL = {
    "RISK_CONFIRMED": "高风险（红灯）",
    "RISK_POTENTIAL": "潜在风险（黄灯）",
    "SAFE": "安全（绿灯）",
    "UNDETERMINED": "待确认（灰）",
}
DECISION_RANK = {
    "UNDETERMINED": 0,
    "SAFE": 1,
    "RISK_POTENTIAL": 2,
    "RISK_CONFIRMED": 3,
}
CHANGE_LABEL = {
    "license_changed": "许可证变更",
    "version_changed": "版本变更",
    "version_upgraded": "版本升级",
    "version_downgraded": "版本降级",
    "evidence_downgrade": "证据降级",
    "edge_added": "新增血缘边",
    "edge_removed": "血缘边移除",
    "asset_added": "新增资产",
    "asset_removed": "资产移除",
}

TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>{{TITLE}} — 时间轴风险传播图</title>
<script src="{{ECHARTS_SRC}}"></script>
<style>
  body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 0; background: #f7f9fc; color: #333; }
  .header { display: flex; justify-content: space-between; align-items: center; padding: 10px 20px; background: #fff; border-bottom: 1px solid #e2e8f0; }
  .header h1 { font-size: 18px; margin: 0; }
  .stats { font-size: 12px; color: #606266; }
  .legend-row { padding: 6px 20px; background: #fff; border-bottom: 1px solid #eef2f7; font-size: 12px; color: #606266; display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }
  .legend-row i { display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
  .main { display: flex; min-height: 480px; }
  .side { width: 38%; }
  .mid { width: 24%; background: #fff; border-left: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; padding: 10px; font-size: 12px; overflow-y: auto; }
  .mid h3 { margin: 0 0 8px; font-size: 13px; }
  .evt { border: 1px solid #e2e8f0; border-radius: 4px; padding: 6px 8px; margin-bottom: 8px; cursor: pointer; background: #fafcfe; }
  .evt:hover { border-color: #409eff; }
  .evt .ct { font-weight: bold; font-size: 11px; }
  .evt .arrow { color: #c0392b; font-weight: bold; }
  .evt .tag { display: inline-block; padding: 1px 6px; border-radius: 3px; color: #fff; font-size: 10px; }
  .side .side-title { text-align: center; font-size: 13px; font-weight: bold; padding: 6px; color: #606266; }
  .chart { height: 420px; }
  #panel { padding: 10px 20px; background: #fff; border-top: 1px solid #e2e8f0; font-size: 12px; }
  #panel h3 { margin: 0 0 8px; font-size: 14px; }
  .cert { border: 1px solid #e2e8f0; border-radius: 4px; padding: 8px; margin-bottom: 8px; background: #fafcfe; }
  .cert .path { color: #c0392b; word-break: break-all; }
  .kv { margin: 2px 0; word-break: break-all; }
</style>
</head>
<body>
<div class="header">
  <h1>{{TITLE}}</h1>
  <div class="stats">t0：{{N0}} 节点 / {{E0}} 边 · t1：{{N1}} 节点 / {{E1}} 边 · 变更事件 {{NE}} · 路径证书 {{NC}}</div>
</div>
<div class="legend-row">
  <span><i style="background:#f56c6c"></i>高风险（红灯）</span>
  <span><i style="background:#e6a23c"></i>潜在风险（黄灯）</span>
  <span><i style="background:#67c23a"></i>安全（绿灯）</span>
  <span><i style="background:#d3d7de"></i>待确认（灰）</span>
  <span><i style="background:#c0392b;width:20px;height:4px;border-radius:2px"></i>红色箭头 = 风险传播路径（上游变化资产 → 受影响下游）</span>
</div>
<div class="main">
  <div class="side"><div class="side-title">t0 快照（基线）</div><div id="chart0" class="chart"></div></div>
  <div class="mid">
    <h3>变更事件（点击查看传播证书）</h3>
    <div id="evt-list"></div>
  </div>
  <div class="side"><div class="side-title">t1 快照（当前）</div><div id="chart1" class="chart"></div></div>
</div>
<div id="panel"><h3>传播路径证书（path_certificates）</h3><div id="panel-body" style="color:#909399">点击左侧变更事件查看对应传播路径证书。</div></div>
<script>
const DATA = {{DATA_JSON}};
const DECISION_COLOR = {{DECISION_COLOR_JSON}};
const DECISION_LABEL = {{DECISION_LABEL_JSON}};
const CHANGE_LABEL = {{CHANGE_LABEL_JSON}};

function decisionOf(d) { return { code: d || "UNDETERMINED", color: DECISION_COLOR[d] || "#d3d7de", label: DECISION_LABEL[d] || d }; }
function isAgg(n) { return (n.name || "").indexOf("(Total:") >= 0 || (n.name || "").indexOf(" · ") >= 0; }

function buildChart(elId, nodes, edges, title) {
  const nodeById = {};
  nodes.forEach(n => nodeById[n.id] = n);
  const data = nodes.map(n => {
    const j = decisionOf(n.decision);
    const agg = isAgg(n);
    const sourceNote = n.decision_source === "diff_propagation" ? "（diff 传播）" : "";
    return {
      id: n.id, name: n.name || n.id,
      x: n.x, y: n.y,
      symbol: agg ? "rect" : (n.asset_type === "dataset" ? "diamond" : "circle"),
      symbolSize: agg ? 24 : 34,
      itemStyle: { color: j.color, borderColor: j.color === "#d3d7de" ? "#bbb" : j.color, borderWidth: 1.5, borderRadius: agg ? 5 : 0 },
      label: { show: true, formatter: () => (agg ? ((n.name || "").split(" · ").pop() || n.name) : (n.name || n.id)), fontSize: 10, color: "#333", position: n.lp || "bottom" },
      tooltip: { formatter: () => `<b>${n.name}</b><br/>版本：${n.version || "—"}<br/>许可证：${n.license || "未声明"}<br/>判定：${j.label}${sourceNote}` },
      _raw: n
    };
  });
  const links = edges.map(e => ({
    source: e.source, target: e.target,
    edgeSymbol: ["none", "arrow"], edgeSymbolSize: [0, 10],
    lineStyle: { width: 1.5, color: "#95a5a6" },
    _edge: e
  }));
  const chart = echarts.init(document.getElementById(elId));
  chart.setOption({
    tooltip: { trigger: "item", backgroundColor: "#fff", borderColor: "#d0d7de", textStyle: { color: "#333" } },
    legend: { show: false },
    series: [{ type: "graph", layout: "none", roam: true, data, links, categories: [{name:"RISK_CONFIRMED"},{name:"RISK_POTENTIAL"},{name:"SAFE"},{name:"UNDETERMINED"}], emphasis: { focus: "adjacency" }, labelLayout: { hideOverlap: true } }]
  });
  return chart;
}

function shortName(id) {
  const all = {};
  DATA.nodes_t0.concat(DATA.nodes_t1).forEach(n => all[n.id] = n);
  const n = all[id];
  if (!n) return id;
  const nm = n.name || id;
  return isAgg(n) ? nm.split(" · ").pop() : nm;
}

function renderCerts(eventId, seed) {
  const certs = DATA.certificates.filter(c => c.event_id === eventId || c.seed === seed);
  if (!certs.length) { document.getElementById("panel-body").innerHTML = "<div style='color:#909399'>该事件无传播证书（无受影响下游）。</div>"; return; }
  document.getElementById("panel-body").innerHTML = certs.map(c => {
    const steps = c.path.map(s => shortName(s.source) + " → " + shortName(s.target)).join(" → ");
    const chain = `${shortName(c.affected)} ⇠ ${steps ? steps + " ⇠ " : ""}${shortName(c.seed)}`;
    return `<div class="cert"><div class="kv"><b>证书</b> ${c.certificate_id} · ${c.change_type}</div>` +
      `<div class="kv"><b>受影响资产</b> ${shortName(c.affected)}</div>` +
      `<div class="kv"><b>传播链（受影响 ⇠ … ⇠ 上游变化资产）</b><div class="path">${chain}</div></div>` +
      `<div class="kv"><b>跳数</b> ${c.hop_count} · <b>最弱证据</b> ${c.weakest_evidence} · <b>判定</b> ${decisionOf(c.decision).label}</div>` +
      `<div class="kv"><b>终止原因</b> ${c.termination || "—"}</div></div>`;
  }).join("");
}

// 事件列表
const evtDiv = document.getElementById("evt-list");
DATA.events.forEach(ev => {
  const j = decisionOf(ev.decision);
  const d = document.createElement("div");
  d.className = "evt";
  d.innerHTML = `<span class="tag" style="background:${j.color}">${CHANGE_LABEL[ev.change_type] || ev.change_type}</span> ` +
    `<div style="margin-top:4px">${shortName(ev.source || ev.seed)} <span class="arrow">→</span> ${shortName(ev.target || ev.seed)}</div>` +
    `<div style="color:#909399;margin-top:2px">判定：${j.label} · 证据 ${ev.evidence_level || "—"}</div>`;
  d.onclick = () => renderCerts(ev.event_id, ev.seed);
  evtDiv.appendChild(d);
});

buildChart("chart0", DATA.nodes_t0, DATA.edges_t0);
buildChart("chart1", DATA.nodes_t1, DATA.edges_t1);
</script>
</body>
</html>
"""


def forest_layout(nodes, edges):
    """快照分层布局（双图共用）：模型基座一行、库/数据集一行、聚合节点挂基座下方。"""
    nodeById = {n["id"]: n for n in nodes}

    def is_agg(n):
        return "(Total:" in (n.get("name") or "") or " · " in (n.get("name") or "")

    bases = [n for n in nodes if not is_agg(n)]
    base_ids = [n["id"] for n in bases]
    children_of = {bid: [] for bid in base_ids}
    for e in edges:
        if e["target"] in children_of and e["source"] not in children_of:
            children_of[e["target"]].append(e["source"])

    model_bases = [n for n in bases if n.get("asset_type") == "model"]
    other_bases = [n for n in bases if n.get("asset_type") != "model"]
    for idx, b in enumerate(model_bases):
        b["x"] = 150 + idx * 170
        b["y"] = 70
        b["lp"] = "top"
    for idx, b in enumerate(other_bases):
        b["x"] = 150 + idx * 220
        b["y"] = 250
        b["lp"] = "top"
    agg_row = 350
    for idx, b in enumerate(model_bases):
        for kid_i, kid in enumerate(children_of.get(b["id"], [])):
            col = kid_i % 2
            xoff = -110 if col == 0 else 110
            if kid in nodeById:
                nodeById[kid]["x"] = b["x"] + xoff
                nodeById[kid]["y"] = agg_row + (kid_i // 2) * 110
                nodeById[kid]["lp"] = "bottom"


def _decision_rank(decision: str | None) -> int:
    return DECISION_RANK.get(decision or "", -1)


def _collect_event_decisions(
    events: list[dict], certificates: list[dict]
) -> dict[str, str]:
    """收集每个种子/路径节点最强的 diff 传播判定。"""

    decisions: dict[str, str] = {}

    def add(node_id: str | None, decision: str | None) -> None:
        if not node_id or not decision:
            return
        current = decisions.get(node_id)
        if current is None or _decision_rank(decision) > _decision_rank(current):
            decisions[node_id] = decision

    for event in events:
        decision = event.get("decision")
        add(event.get("seed"), decision)
        add(event.get("source"), decision)
        add(event.get("target"), decision)
        for step in event.get("path") or []:
            add(step.get("source"), decision)
            add(step.get("target"), decision)

    for certificate in certificates:
        decision = certificate.get("decision")
        add(certificate.get("seed"), decision)
        add(certificate.get("affected"), decision)

    return decisions


def apply_event_decisions(
    nodes_t0: list[dict],
    nodes_t1: list[dict],
    events: list[dict],
    certificates: list[dict],
) -> None:
    """把传播判定叠加到节点，且不覆盖更强或更明确的既有判定。"""

    event_decisions = _collect_event_decisions(events, certificates)
    for nodes in (nodes_t0, nodes_t1):
        for node in nodes:
            node_id = node.get("id") or node.get("canonical_id") or node.get("entity_key")
            event_decision = event_decisions.get(node_id)
            if not event_decision:
                continue
            if _decision_rank(event_decision) > _decision_rank(node.get("decision")):
                node["decision"] = event_decision
                node["decision_source"] = "diff_propagation"


def main() -> None:
    parser = argparse.ArgumentParser(description="开源账本 --diff 时间轴风险传播图渲染器")
    parser.add_argument("--before", required=True, type=Path, help="t0 BOM（CycloneDX，含 pedigree.ancestors）")
    parser.add_argument("--after", required=True, type=Path, help="t1 BOM")
    parser.add_argument("--output", required=True, type=Path, help="输出 HTML 路径")
    parser.add_argument("--title", default=None, help="页面标题（默认自动）")
    args = parser.parse_args()

    from main import _build_snapshot

    before = _build_snapshot(args.before, "t0")
    after = _build_snapshot(args.after, "t1")

    graph_before = build_graph.build_graph(before["assets"], before["edges"])
    graph_after = build_graph.build_graph(after["assets"], after["edges"])

    events = delta_engine.detect_delta(before["assets"], after["assets"], before["edges"], after["edges"])
    propagated = propagation_engine.propagate(events, graph_before, graph_after)
    certs = propagated["path_certificates"]

    nodes_t0, edges_t0 = list(before["assets"]), list(before["edges"])
    nodes_t1, edges_t1 = list(after["assets"]), list(after["edges"])
    for n in nodes_t0 + nodes_t1:
        n["id"] = n.get("id") or n.get("canonical_id") or n.get("entity_key")
    apply_event_decisions(
        nodes_t0,
        nodes_t1,
        propagated["events"],
        certs,
    )
    forest_layout(nodes_t0, edges_t0)
    forest_layout(nodes_t1, edges_t1)

    data = {
        "nodes_t0": nodes_t0, "edges_t0": edges_t0,
        "nodes_t1": nodes_t1, "edges_t1": edges_t1,
        "events": propagated["events"],
        "certificates": certs,
    }
    title = args.title or ("%s → %s 血缘风险传播" % (args.before.stem, args.after.stem))

    html = TPL
    html = html.replace("{{TITLE}}", title)
    html = html.replace("{{N0}}", str(len(nodes_t0)))
    html = html.replace("{{E0}}", str(len(edges_t0)))
    html = html.replace("{{N1}}", str(len(nodes_t1)))
    html = html.replace("{{E1}}", str(len(edges_t1)))
    html = html.replace("{{NE}}", str(len(events)))
    html = html.replace("{{NC}}", str(len(certs)))
    html = html.replace("{{DATA_JSON}}", json.dumps(data, ensure_ascii=False))
    html = html.replace("{{DECISION_COLOR_JSON}}", json.dumps(DECISION_COLOR, ensure_ascii=False))
    html = html.replace("{{DECISION_LABEL_JSON}}", json.dumps(DECISION_LABEL, ensure_ascii=False))
    html = html.replace("{{CHANGE_LABEL_JSON}}", json.dumps(CHANGE_LABEL, ensure_ascii=False))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    local_echarts = args.output.parent / "echarts.min.js"
    candidates = [
        Path(__file__).resolve().parent / "echarts.min.js",
        Path(__file__).resolve().parent / "outputs" / "modelscope_validation" / "echarts.min.js",
    ]
    echarts_src = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"
    for cand in candidates:
        if cand.exists():
            # --output 落在仓库根时，cand 与 local_echarts 是同一个文件，
            # 直接 copy 会抛 shutil.SameFileError，这里先判同文件再复制。
            if cand.resolve() != local_echarts.resolve():
                shutil.copy(cand, local_echarts)
            echarts_src = "./echarts.min.js"
            break
    html = html.replace("{{ECHARTS_SRC}}", echarts_src)

    args.output.write_text(html, encoding="utf-8")
    dist = Counter(e["decision"] for e in propagated["events"])
    print("已生成：%s" % args.output)
    print("t0 %d 节点/%d 边 · t1 %d 节点/%d 边 · 变更事件 %d · 传播后事件 %d · 路径证书 %d" % (
        len(nodes_t0), len(edges_t0), len(nodes_t1), len(edges_t1), len(events), len(propagated["events"]), len(certs)))
    print("判定分布：%s" % dict(dist))


if __name__ == "__main__":
    main()
