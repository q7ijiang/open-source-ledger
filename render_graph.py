# -*- coding: utf-8 -*-
"""通用血缘图渲染器：读取 graph.json，生成可双击打开的交互 HTML。"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from render_layout import layout_graph

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

TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{TITLE}} — 开源账本风险血缘图</title>
<script src="{{ECHARTS_SRC}}"></script>
<style>
  :root { --ink:#172033; --muted:#64748b; --line:#e2e8f0; --paper:#f7f9fc; }
  * { box-sizing: border-box; }
  body { font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif; margin:0; background:var(--paper); color:var(--ink); }
  .header { display:flex; justify-content:space-between; align-items:center; gap:20px; padding:14px 22px; background:#fff; border-bottom:1px solid var(--line); }
  .header h1 { font-size:19px; margin:0 0 3px; }
  .header .sub { font-size:12px; color:var(--muted); }
  .stats { font-size:12px; color:#475569; white-space:nowrap; }
  .legend-row { padding:8px 22px; background:#fff; border-bottom:1px solid #eef2f7; font-size:12px; color:#526176; display:flex; flex-wrap:wrap; gap:14px; align-items:center; }
  .legend-row i { display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:5px; vertical-align:-2px; }
  .legend-row .line { width:22px; height:3px; }
  .main { display:grid; grid-template-columns:minmax(0,1fr) 320px; min-height:0; }
  #chart { width:100%; height:{{CHART_HEIGHT}}px; }
  #panel { background:#fff; border-left:1px solid var(--line); padding:14px; font-size:12px; overflow-y:auto; max-height:{{CHART_HEIGHT}}px; }
  #panel h3 { margin:0 0 10px; font-size:14px; }
  .kv { margin:5px 0; word-break:break-all; line-height:1.55; }
  .kv b { color:#356fa8; }
  .ev { border-top:1px dashed var(--line); padding:8px 0; line-height:1.5; }
  .section { padding:16px 22px 4px; }
  .section h2 { font-size:16px; margin:0 0 4px; }
  .section p { margin:0; color:var(--muted); font-size:12px; }
  .risk-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:10px; padding:10px 22px 18px; }
  .risk-card { background:#fff; border:1px solid var(--line); border-left-width:4px; border-radius:8px; padding:10px 12px; cursor:pointer; }
  .risk-card:hover { box-shadow:0 5px 15px rgba(15,23,42,.08); transform:translateY(-1px); }
  .risk-card .name { font-weight:700; font-size:13px; word-break:break-all; }
  .risk-card .meta { margin-top:4px; color:var(--muted); font-size:11px; }
  .empty { margin:0 22px 18px; padding:12px 14px; background:#fff; border:1px dashed #cbd5e1; border-radius:8px; color:var(--muted); font-size:12px; }
  table { width:100%; border-collapse:collapse; background:#fff; }
  th,td { border:1px solid var(--line); padding:7px 9px; font-size:12px; text-align:left; vertical-align:top; }
  th { background:#f5f7fa; position:sticky; top:0; }
  .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }
  .table-wrap { padding:8px 22px 28px; overflow:auto; max-height:400px; }
  @media (max-width:1000px) {
    .main { grid-template-columns:1fr; }
    #panel { border-left:0; border-top:1px solid var(--line); max-height:360px; }
    .stats { display:none; }
  }
  @media (max-width:700px) {
    .main { overflow-x:auto; }
    #chart { min-width:680px; }
  }
</style>
</head>
<body>
<div class="header">
  <div><h1>{{TITLE}}</h1><div class="sub">模型簇优先布局 · 聚合域自适应换行 · 点击节点查看证据与能力边界</div></div>
  <div class="stats">节点 {{NODE_COUNT}} · 边 {{EDGE_COUNT}} · 整体判定：<b>{{OVERALL}}</b></div>
</div>
<div class="legend-row">
  <span><i style="background:#f56c6c"></i>高风险</span>
  <span><i style="background:#e6a23c"></i>潜在风险</span>
  <span><i style="background:#67c23a"></i>安全</span>
  <span><i style="background:#d3d7de"></i>待确认</span>
  <span><i class="line" style="background:#c0392b"></i>真实血缘传播</span>
  <span><i class="line" style="background:#aeb8c7"></i>虚线 = 聚合归属，不属于风险传播</span>
  <span><i style="background:#eef0f4;border:2px solid #f56c6c"></i>中性聚合域 + 风险描边</span>
</div>
<div class="main">
  <div id="chart"></div>
  <aside id="panel"><h3>证据与能力边界</h3><div id="panel-body" style="color:#7b8799">点击模型、聚合域或连线查看详情。</div></aside>
</div>

<section class="section">
  <h2>已识别的具体风险模型</h2>
  <p>聚合域只表示范围；这里只列具有真实模型身份的节点，不把聚合计数伪装成模型名称。</p>
</section>
<div id="risk-grid" class="risk-grid"></div>
<div id="risk-empty" class="empty" hidden></div>

<section class="section">
  <h2>资产判定表</h2>
  <p>绿灯与聚合节点同样保留，便于核对覆盖边界。</p>
</section>
<div class="table-wrap">
  <table id="compliance">
    <thead><tr><th>模型名/组件名</th><th>类型</th><th>版本</th><th>许可证</th><th>判定结果</th></tr></thead>
    <tbody></tbody>
  </table>
</div>
<script>
const DATA = {{DATA_JSON}};
const DECISION_COLOR = {{DECISION_COLOR_JSON}};
const DECISION_LABEL = {{DECISION_LABEL_JSON}};

function escapeHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}
function decisionOf(value) {
  const code = value || "UNDETERMINED";
  return {code, color: DECISION_COLOR[code] || "#d3d7de", label: DECISION_LABEL[code] || code};
}
function isAggregate(n) {
  if (n.aggregate === true || n.coverage_status === "AGGREGATE_ONLY") return true;
  if ((n.canonical_id || n.entity_key || "").includes(":son:") ||
      (n.canonical_id || n.entity_key || "").includes(":parent:")) return true;
  return (n.name || "").includes("(Total:") && !(n.purls || []).length;
}
function isFixtureNode(n) {
  // 只认显式声明：名称长得像夹具的真实模型不该被标成构造夹具。
  return !!n && (n.is_fixture === true || n.display_only === true);
}
function aggregateCount(n) {
  if (Number.isInteger(n.count)) return n.count;
  const match = String(n.name || "").match(/\\(Total:\\s*(\\d+)\\)/i);
  return match ? Number(match[1]) : 0;
}
function aggregateLabel(n) {
  if (n.render_card && n.render_card.label) return n.render_card.label;
  const name = n.name || n.canonical_id || "聚合域";
  return (name.includes(" · ") ? name.split(" · ").pop() : name).replace(/\\(Total:\\s*\\d+\\)/i, "").trim();
}
function aggregateCounts(n) {
  return n.render_risk_counts || n.known_risk_counts || {red:0, yellow:0, gray:0};
}
function aggregateColor(n) {
  const tone = n.render_tone || "NEUTRAL";
  return tone === "NEUTRAL" ? "#aeb8c7" : (DECISION_COLOR[tone] || "#aeb8c7");
}
function decisionShort(code) {
  return {RISK_CONFIRMED:"高风险",RISK_POTENTIAL:"潜在风险",SAFE:"安全",UNDETERMINED:"待确认"}[code || "UNDETERMINED"] || "待确认";
}
function childFill(code) {
  return {RISK_CONFIRMED:"#fff2f0",RISK_POTENTIAL:"#fff8e8",SAFE:"#f0f9eb",UNDETERMINED:"#f6f7f9"}[code || "UNDETERMINED"] || "#f6f7f9";
}
const NL = String.fromCharCode(10);

const nodeById = {};
DATA.nodes.forEach(n => nodeById[n.id] = n);

// 聚合域默认折叠，点击卡片展开/收起（与 Diff 页行为一致）
const expandedDomains = new Set();
const childrenByAggregate = {};
DATA.edges.forEach(e => {
  if (e.edge_type !== "expanded_from") return;
  const aggregateId = isAggregate(nodeById[e.source] || {}) ? e.source : e.target;
  if (!childrenByAggregate[aggregateId]) childrenByAggregate[aggregateId] = [];
  childrenByAggregate[aggregateId].push(e);
});

function buildNodes() {
  return DATA.nodes.map(n => {
  const agg = isAggregate(n);
  const j = decisionOf(n.decision);
  if (n.render_role === "expanded_child") {
    const label = n.render_card?.label || n.name || n.id;
    const visible = expandedDomains.has(n.render_parent_id);
    return {
      id:n.id,
      name:label,
      x:n.x,
      y:n.y,
      symbol:"rect",
      symbolSize:visible ? [n.render_card?.width || 72, n.render_card?.height || 38] : [0, 0],
      itemStyle:{color:childFill(n.decision),borderColor:j.color,borderWidth:2,borderRadius:6,opacity:visible ? 1 : 0},
      label:{show:visible,position:"inside",formatter:() => `{name|${label}}\n{state|${decisionShort(n.decision)}}`,rich:{name:{fontSize:10,fontWeight:"bold",color:"#253044",lineHeight:15},state:{fontSize:8,color:j.color,lineHeight:13}}},
      tooltip:{show:visible,formatter:() => `<b>${escapeHtml(n.name || label)}</b><br/>类型：展开的风险子节点<br/>许可证：${escapeHtml(n.license || "未声明")}<br/>判定：${j.label}${isFixtureNode(n) ? "<br/>构造测试夹具，不代表真实下游模型" : ""}`},
      _raw:n,
      _childParent:n.render_parent_id,
      silent:!visible,
      z:visible ? 5 : 0
    };
  }
  if (agg) {
    const total = aggregateCount(n);
    const counts = aggregateCounts(n);
    const childCount = (childrenByAggregate[n.id] || []).length;
    const expanded = childCount > 0 && expandedDomains.has(n.id);
    const action = childCount ? `点击${expanded ? "收起" : "展开"} ${childCount} 个模型` : "聚合范围";
    return {
      id: n.id,
      name: aggregateLabel(n),
      x: n.x,
      y: n.y,
      symbol: "rect",
      symbolSize: [n.render_card?.width || 174, n.render_card?.height || 68],
      itemStyle: {color:"#eef0f4", borderColor:aggregateColor(n), borderWidth:2, borderRadius:9},
      label: {
        show:true,
        position:"inside",
        formatter: () => `{title|${aggregateLabel(n)}}\\n{meta|下游 ${total} · 红${counts.red} 黄${counts.yellow} 灰${counts.gray}}${NL}{action|${action}}`,
        rich: {
          title:{fontSize:13,fontWeight:"bold",color:"#253044",lineHeight:20},
          meta:{fontSize:10,color:"#64748b",lineHeight:16},
          action:{fontSize:9,color:childCount ? "#2d6da3" : "#94a3b8",lineHeight:14}
        }
      },
      tooltip: {formatter: () => `<b>${escapeHtml(aggregateLabel(n))}</b><br/>类型：聚合风险域<br/>下游总量：${total}<br/>已知：红 ${counts.red} / 黄 ${counts.yellow} / 灰 ${counts.gray}<br/>具体模型身份以数据源返回为准`},
      _raw:n,
      _childCount:childCount,
      cursor:childCount ? "pointer" : "default",
      z:2
    };
  }
  return {
    id: n.id,
    name: n.name || n.id,
    x: n.x,
    y: n.y,
    symbol: n.asset_type === "dataset" ? "diamond" : "circle",
    symbolSize: n.asset_type === "dataset" ? 30 : 38,
    itemStyle: {color:j.color, borderColor:j.color === "#d3d7de" ? "#abb4c2" : j.color, borderWidth:1.5},
    label: {show:true, formatter:() => n.name || n.id, fontSize:11, color:"#334155", position:n.lp || "bottom"},
    tooltip: {formatter: () => `<b>${escapeHtml(n.name || n.id)}</b><br/>类型：${escapeHtml(n.asset_type || "—")}<br/>版本：${escapeHtml(n.version || "—")}<br/>许可证：${escapeHtml(n.license || "未声明")}<br/>判定：${j.label}${n.decision_source === "diff_propagation" ? "（传播）" : ""}`},
    _raw:n,
    z:4
  };
  });
}

function buildLinks() {
  return DATA.edges.map(e => {
  const source = nodeById[e.source] || {};
  const target = nodeById[e.target] || {};
  const expansion = e.edge_type === "expanded_from";
  const aggregateId = expansion ? (isAggregate(source) ? e.source : e.target) : null;
  if (aggregateId && !expandedDomains.has(aggregateId)) return null;
  const membership = isAggregate(source) || isAggregate(target);
  const risky = !membership && (
    ["RISK_CONFIRMED","RISK_POTENTIAL"].includes(source.decision) ||
    ["RISK_CONFIRMED","RISK_POTENTIAL"].includes(target.decision)
  );
  return {
    source:e.source,
    target:e.target,
    edgeSymbol: membership ? ["none","none"] : ["none","arrow"],
    edgeSymbolSize: [0,10],
    label: {show:!membership, formatter:e.edge_type || "", fontSize:10, color:risky ? "#c0392b" : "#7b8799", position:"middle"},
    lineStyle: {
      width:risky ? 4 : (membership ? 1.3 : 2),
      color:risky ? "#c0392b" : (membership ? "#aeb8c7" : "#95a5a6"),
      type:membership ? "dashed" : "solid",
      curveness:0.04
    },
    _edge:e
  };
  }).filter(Boolean);
}

const clusterGraphics = DATA.layout.clusters.map(c => ({
  type:"group",
  left:c.x,
  top:c.y,
  z:-1,
  silent:true,
  children:[
    {type:"rect", shape:{x:0,y:0,width:c.width,height:c.height,r:14}, style:{fill:"#fbfcfe",stroke:"#dfe7f1",lineWidth:1}},
    {type:"text", style:{x:16,y:22,text:c.title,fill:"#253044",font:"bold 13px Microsoft YaHei"}},
    {type:"text", style:{x:16,y:41,text:`风险域 ${c.aggregate_count} 个${c.expanded_count ? ` · 展开 ${c.expanded_count}` : " · 聚合范围"}`,fill:"#7b8799",font:"11px Microsoft YaHei"}}
  ]
}));

const chart = echarts.init(document.getElementById("chart"));
window.__chart = chart;
function refresh() {
  chart.setOption({
    tooltip:{trigger:"item",backgroundColor:"#fff",borderColor:"#d0d7de",textStyle:{color:"#334155",fontSize:12}},
    legend:{show:false},
    graphic:clusterGraphics,
    series:[{
      type:"graph",
      layout:"none",
      roam:false,
      draggable:false,
      data:buildNodes(),
      links:buildLinks(),
      emphasis:{focus:"adjacency",lineStyle:{width:5}},
      labelLayout:{hideOverlap:true}
    }]
  }, true);
}
refresh();
window.addEventListener("resize", () => chart.resize());

function renderNodeDetail(raw) {
  const j = decisionOf(raw.decision);
  const agg = isAggregate(raw);
  const evs = (raw.evidence_chain || []).map(e =>
    `<div class="ev"><b>证据 ${escapeHtml(e.evidence_level || "—")}</b> · ${escapeHtml(e.source_api || "")}<br/>字段：${escapeHtml(e.source_field || "—")}<br/><a href="${escapeHtml(e.source_url || "#")}" target="_blank">${escapeHtml(e.source_url || "—")}</a></div>`
  ).join("") || "<div class='ev'>无证据链</div>";
  let html = `<div class="kv"><b>名称</b> ${escapeHtml(raw.name || raw.canonical_id)}</div>` +
    `<div class="kv"><b>节点类型</b> ${agg ? "聚合风险域（非具体模型）" : escapeHtml(raw.asset_type || "—")}</div>` +
    `<div class="kv"><b>版本</b> ${escapeHtml(raw.version || "—")}</div>` +
    `<div class="kv"><b>许可证</b> ${escapeHtml(raw.license || "未声明")}</div>` +
    `<div class="kv"><b>判定</b> ${j.label}</div>`;
  if (agg) {
    const counts = aggregateCounts(raw);
    html += `<div class="kv"><b>下游总量</b> ${aggregateCount(raw)}</div>` +
      `<div class="kv"><b>已知风险</b> 红 ${counts.red} / 黄 ${counts.yellow} / 灰 ${counts.gray}</div>` +
      `<div class="kv"><b>能力边界</b> 聚合域只表达范围；只有数据源返回具体身份时才展示模拟名称。</div>`;
  } else {
    html += `<div class="kv"><b>判定来源</b> ${escapeHtml(raw.decision_source || "自身许可证评估")}</div>` +
      `<div class="kv"><b>merge_status</b> ${escapeHtml(raw.merge_status || "—")}</div>` +
      `<div class="kv"><b>reason_code</b> ${escapeHtml(raw.reason_code || "—")}</div>`;
  }
  document.getElementById("panel-body").innerHTML = html + `<h3 style="margin-top:12px">证据链</h3>` + evs;
}

function renderEdgeDetail(edge) {
  const source = nodeById[edge.source] || {};
  const target = nodeById[edge.target] || {};
  const membership = isAggregate(source) || isAggregate(target);
  document.getElementById("panel-body").innerHTML =
    `<div class="kv"><b>关系类型</b> ${escapeHtml(edge.edge_type || "—")}</div>` +
    `<div class="kv"><b>来源</b> ${escapeHtml(source.name || edge.source)}</div>` +
    `<div class="kv"><b>目标</b> ${escapeHtml(target.name || edge.target)}</div>` +
    `<div class="kv"><b>证据等级</b> ${escapeHtml(edge.evidence_level || "—")}</div>` +
    `<div class="kv"><b>source_field</b> ${escapeHtml(edge.source_field || "—")}</div>` +
    `<div class="kv"><b>语义</b> ${membership ? "聚合归属，不触发风险传播" : "真实血缘关系"}</div>` +
    `<div class="kv"><b>传播路径证书</b> ${edge.certificates && edge.certificates.length ? edge.certificates.map(escapeHtml).join("<br/>") : "—"}</div>`;
}

chart.on("click", p => {
  if (p.dataType === "node") {
    const raw = p.data._raw;
    renderNodeDetail(raw);
    if (isAggregate(raw) && Number(p.data._childCount || 0) > 0) {
      if (expandedDomains.has(raw.id)) expandedDomains.delete(raw.id);
      else expandedDomains.add(raw.id);
      refresh();
    }
    setTimeout(() => chart.dispatchAction({type:"downplay", seriesIndex:0}), 0);
  } else if (p.dataType === "edge") {
    renderEdgeDetail(p.data._edge);
  }
});

const riskGrid = document.getElementById("risk-grid");
const riskEmpty = document.getElementById("risk-empty");
const concreteRiskNodes = DATA.nodes.filter(n => !isAggregate(n) && ["RISK_CONFIRMED","RISK_POTENTIAL"].includes(n.decision || "UNDETERMINED"));
if (!concreteRiskNodes.length) {
  riskEmpty.hidden = false;
  riskEmpty.textContent = "当前图中没有具名的红/黄风险模型；这不代表聚合域内不存在风险，请结合聚合域的已知风险统计查看。";
} else {
  concreteRiskNodes.forEach(n => {
    const j = decisionOf(n.decision);
    const card = document.createElement("button");
    card.type = "button";
    card.className = "risk-card";
    card.style.borderLeftColor = j.color;
    card.style.textAlign = "left";
    card.style.font = "inherit";
    card.innerHTML = `<div class="name">${escapeHtml(n.name || n.canonical_id)}</div><div class="meta">${j.label} · 许可证 ${escapeHtml(n.license || "未声明")} · 证据链 ${(n.evidence_chain || []).length} 条</div>`;
    card.onclick = () => renderNodeDetail(n);
    riskGrid.appendChild(card);
  });
}

const tbody = document.querySelector("#compliance tbody");
DATA.nodes.forEach(n => {
  const agg = isAggregate(n);
  const j = decisionOf(n.decision);
  const shownDecision = agg ? "聚合域（中性）" : j.label;
  const tr = document.createElement("tr");
  tr.innerHTML = `<td>${escapeHtml(n.name || n.canonical_id)}</td><td>${agg ? "风险域聚合" : escapeHtml(n.asset_type || "—")}</td><td>${escapeHtml(n.version || "—")}</td><td>${escapeHtml(n.license || "未声明")}</td><td><span class="dot" style="background:${agg ? aggregateColor(n) : j.color}"></span>${shownDecision}</td>`;
  tbody.appendChild(tr);
});
</script>
</body>
</html>
"""


def prepare_graph(graph: dict) -> dict:
    """Normalize ids and attach deterministic layout metadata."""

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    for node in nodes:
        node.setdefault(
            "id",
            node.get("canonical_id") or node.get("entity_key") or node.get("name"),
        )
    layout = layout_graph(nodes, edges)
    return {"nodes": nodes, "edges": edges, "layout": layout}


def forest_layout(nodes: list[dict], edges: list[dict]) -> dict:
    """Backward-compatible wrapper around the shared cluster layout."""

    return layout_graph(nodes, edges)


def _copy_echarts(output_dir: Path) -> str:
    local_echarts = output_dir / "echarts.min.js"
    candidates = [
        Path(__file__).resolve().parent / "echarts.min.js",
        Path(__file__).resolve().parent / "vendor" / "echarts.min.js",
        Path(__file__).resolve().parent / "outputs" / "modelscope_validation" / "echarts.min.js",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            if candidate.resolve() == local_echarts.resolve():
                return "./echarts.min.js"
        except OSError:
            pass
        try:
            with candidate.open("rb") as stream:
                if stream.read(2) in (b"\xff\xfe", b"\xfe\xff"):
                    continue
        except OSError:
            continue
        shutil.copy2(candidate, local_echarts)
        return "./echarts.min.js"
    return "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"


def main() -> None:
    parser = argparse.ArgumentParser(description="开源账本通用血缘图渲染器（读 graph.json）")
    parser.add_argument("--input", required=True, type=Path, help="graph.json 路径")
    parser.add_argument("--output", required=True, type=Path, help="输出 HTML 路径")
    parser.add_argument("--title", default=None, help="页面标题")
    args = parser.parse_args()

    graph = json.loads(args.input.read_text(encoding="utf-8"))
    data = prepare_graph(graph)
    nodes = data["nodes"]
    edges = data["edges"]
    layout = data["layout"]

    title = args.title or f"{args.input.parent.name} · 血缘风险图"
    overall = graph.get("overall_decision_zh") or graph.get("overall_decision") or "—"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    echarts_src = _copy_echarts(args.output.parent)
    chart_height = max(620, int(layout.get("height", 620)))

    html = TPL
    replacements = {
        "{{TITLE}}": title,
        "{{NODE_COUNT}}": str(len(nodes)),
        "{{EDGE_COUNT}}": str(len(edges)),
        "{{OVERALL}}": str(overall),
        "{{DATA_JSON}}": json.dumps(data, ensure_ascii=False),
        "{{DECISION_COLOR_JSON}}": json.dumps(DECISION_COLOR, ensure_ascii=False),
        "{{DECISION_LABEL_JSON}}": json.dumps(DECISION_LABEL, ensure_ascii=False),
        "{{ECHARTS_SRC}}": echarts_src,
        "{{CHART_HEIGHT}}": str(chart_height),
    }
    for marker, value in replacements.items():
        html = html.replace(marker, value)
    args.output.write_text(html, encoding="utf-8")
    print(
        "已生成：%s（节点 %d / 边 %d，模型簇 %d，整体判定 %s）"
        % (args.output, len(nodes), len(edges), len(layout["clusters"]), overall)
    )


if __name__ == "__main__":
    main()
