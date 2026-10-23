# -*- coding: utf-8 -*-
"""通用血缘图渲染器：直接读取 A 层 graph.json，生成可双击打开的交互 HTML。

用法：
  python render_graph.py --input outputs/Qwen__Qwen-Image-2.1/graph.json --output qwen.html
  python render_graph.py --input outputs/mock_project/graph.json --output project.html --title "项目血缘图"

特性（对齐接口约定 v0.3）：
- 节点按 decision 着色：RISK_CONFIRMED 红灯 / RISK_POTENTIAL 黄灯 / SAFE 绿灯 / UNDETERMINED 灰
- 森林分层布局（基座模型在上、聚合节点在下），边带箭头表示 derived_from 方向
- 一端为风险节点（红灯/黄灯）的边标红加粗 = 风险传播路径
- 点击节点弹出证据链（evidence_chain / license / decision / merge_status / reason_code）
- 不写死输出路径，--input/--output 显式指定；ECharts 优先用本地文件，缺失时回退 CDN
"""
import argparse
import json
import shutil
from pathlib import Path

# 判定 → 颜色 / 中文标签（接口约定 v0.3 四级）
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
ECOSYSTEM_LABEL = {"modelscope": "ModelScope"}

TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>{{TITLE}} — 开源账本风险血缘图</title>
<script src="{{ECHARTS_SRC}}"></script>
<style>
  body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 0; background: #f7f9fc; color: #333; }
  .header { display: flex; justify-content: space-between; align-items: center; padding: 10px 20px; background: #fff; border-bottom: 1px solid #e2e8f0; }
  .header h1 { font-size: 18px; margin: 0; }
  .stats { font-size: 12px; color: #606266; }
  .legend-row { padding: 6px 20px; background: #fff; border-bottom: 1px solid #eef2f7; font-size: 12px; color: #606266; display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }
  .legend-row i { display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
  .legend-row .line { width: 20px; height: 4px; border-radius: 2px; }
  .main { display: flex; }
  #chart { flex: 1; height: 520px; }
  #panel { width: 300px; background: #fff; border-left: 1px solid #e2e8f0; padding: 12px; font-size: 12px; overflow-y: auto; max-height: 520px; }
  #panel h3 { margin: 0 0 8px; font-size: 14px; }
  #panel .kv { margin: 3px 0; word-break: break-all; }
  #panel .kv b { color: #409eff; }
  #panel .ev { border-top: 1px dashed #e2e8f0; padding: 6px 0; }
  table { width: 100%; border-collapse: collapse; background: #fff; margin-top: 8px; }
  th, td { border: 1px solid #e2e8f0; padding: 5px 8px; font-size: 12px; text-align: left; }
  th { background: #f5f7fa; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }
</style>
</head>
<body>
<div class="header">
  <h1>{{TITLE}}</h1>
  <div class="stats">节点 {{NODE_COUNT}} · 边 {{EDGE_COUNT}} · 整体判定：<b>{{OVERALL}}</b></div>
</div>
<div class="legend-row">
  <span><i style="background:#f56c6c"></i>高风险（红灯）</span>
  <span><i style="background:#e6a23c"></i>潜在风险（黄灯）</span>
  <span><i style="background:#67c23a"></i>安全（绿灯）</span>
  <span><i style="background:#d3d7de"></i>待确认（灰）</span>
  <span><i class="line" style="background:#c0392b"></i>红线箭头 = 风险传播（风险源 → 衍生体）</span>
  <span><i class="line" style="background:#95a5a6;border-top:2px dashed #95a5a6"></i>虚线 = expanded_from 展开关系</span>
  <span>节点形状：○ 真实模型 · □ 聚合节点 · ◆ 数据集</span>
  <span><i style="background:#eef0f4;border:2px solid #f56c6c"></i>聚合风险域（内部含已确认风险）</span>
</div>
<div class="main">
  <div id="chart"></div>
  <div id="panel"><h3>证据链与传播详情</h3><div id="panel-body" style="color:#909399">点击节点查看证据链（A/B/C 等级）；点击连线查看传播路径。</div></div>
</div>
<h3 style="padding:0 20px;font-size:14px;margin:8px 0">合规判定表（绿灯出表 · 红灯出图）</h3>
<table id="compliance">
  <thead><tr><th>模型名/组件名</th><th>版本</th><th>许可</th><th>判定结果</th></tr></thead>
  <tbody></tbody>
</table>
<script>
const DATA = {{DATA_JSON}};
const DECISION_COLOR = {{DECISION_COLOR_JSON}};
const DECISION_LABEL = {{DECISION_LABEL_JSON}};

function decisionOf(n) {
  const d = n.decision || "UNDETERMINED";
  return { code: d, color: DECISION_COLOR[d] || "#d3d7de", label: DECISION_LABEL[d] || d };
}
function isAgg(n) { return (n.name || "").indexOf("(Total:") >= 0 || (n.name || "").indexOf(" · ") >= 0; }

// 聚合域统计属性：coverage_status=AGGREGATE_ONLY + count/expanded_count/remaining_count/known_risk_counts
function aggStats(n) {
  const s = n._stats || {};
  const krc = s.known_risk_counts || {};
  return {
    coverage: s.coverage_status || (isAgg(n) ? "AGGREGATE_ONLY" : null),
    count: s.count != null ? s.count : (isAgg(n) ? (n.name || "").match(/Total:\\s*([0-9]+)/) : null),
    expanded: s.expanded_count != null ? s.expanded_count : null,
    remaining: s.remaining_count != null ? s.remaining_count : null,
    red: krc.red || 0, yellow: krc.yellow || 0, gray: krc.gray || 0,
  };
}

// 聚合节点保持中性：不因内部风险整体染红/黄；仅通过描边/徽标提示域内风险。
// 子节点（expanded_from 指向聚合）按各自真实 decision 着色。
function nodeVisual(n) {
  const agg = isAgg(n);
  if (!agg) return decisionOf(n);
  const st = aggStats(n);
  const hasRed = st.red > 0, hasYellow = st.yellow > 0;
  const border = hasRed ? "#f56c6c" : (hasYellow ? "#e6a23c" : (st.gray > 0 ? "#d3d7de" : "#c0c4cc"));
  const width = hasRed ? 3 : (hasYellow ? 2.5 : 1.5);
  return { code: "AGGREGATE", color: "#eef0f4", label: "聚合域（未完全展开）", border, width };
}

const nodeById = {};
DATA.nodes.forEach(n => nodeById[n.id] = n);

const nodes = DATA.nodes.map(n => {
  const agg = isAgg(n);
  const j = nodeVisual(n);
  const st = aggStats(n);
  // 聚合节点 label：名称 + 统计徽标（已知红黄灰 / 剩余未展开）
  let labelText = n.name || n.id;
  if (agg) {
    const short = (n.name || "").split(" · ").pop() || n.name;
    const parts = [short];
    if (st.expanded != null) {
      const known = [];
      if (st.red) known.push(`<span style="color:#f56c6c">${st.red}红</span>`);
      if (st.yellow) known.push(`<span style="color:#e6a23c">${st.yellow}黄</span>`);
      if (st.gray) known.push(`<span style="color:#909399">${st.gray}灰</span>`);
      parts.push(known.length ? `已知 ${known.join("·")} · 剩余 ${st.remaining != null ? st.remaining : "—"}` : `剩余 ${st.remaining != null ? st.remaining : "—"}`);
    }
    labelText = parts.join("\\n");
  }
  return {
    id: n.id, name: n.name || n.id, value: n.version || "",
    x: n.x, y: n.y,
    symbol: agg ? "rect" : (n.asset_type === "dataset" ? "diamond" : "circle"),
    symbolSize: agg ? 30 : (n.asset_type === "dataset" ? 28 : 38),
    itemStyle: { color: j.color, borderColor: agg ? j.border : (j.color === "#d3d7de" ? "#bbb" : j.color), borderWidth: agg ? j.width : 1.5, borderRadius: agg ? 6 : 0, shadowBlur: agg && st.red ? 8 : 0, shadowColor: "rgba(245,108,108,0.5)" },
    category: agg ? "AGGREGATE" : j.code,
    label: { show: true, formatter: labelText, fontSize: agg ? 11 : 11, color: "#333", position: n.lp || "bottom", lineHeight: 15 },
    tooltip: { formatter: () => agg
      ? `<b>${n.name}</b><br/>类型：聚合节点（AGGREGATE_ONLY）<br/>覆盖总数：${st.count != null ? st.count : "—"}<br/>已展开：${st.expanded != null ? st.expanded : "—"} · 剩余未展开：${st.remaining != null ? st.remaining : "—"}<br/>已知风险：<span style="color:#f56c6c">${st.red} 红</span> / <span style="color:#e6a23c">${st.yellow} 黄</span> / <span style="color:#909399">${st.gray} 灰</span><br/><i>聚合节点自身保持中性，不因内部风险整体染色；具体风险落在展开子节点。</i>`
      : `<b>${n.name}</b><br/>类型：${n.asset_type}${agg ? "（聚合节点）" : ""}<br/>版本：${n.version || "—"}<br/>许可证：${n.license || "未声明"}<br/>判定：${j.label}` },
    _raw: n
  };
});

const nodeRiskById = {};
DATA.nodes.forEach(n => nodeRiskById[n.id] = decisionOf(n).code);

const edges = DATA.edges.map(e => {
  const aggFrom = isAgg(nodeById[e.source] || {});
  const aggTo = isAgg(nodeById[e.target] || {});
  const isExpand = (e.edge_type || "") === "expanded_from" || (e.source_field || "") === "expanded_from";
  // 风险边判定：排除聚合节点自身（聚合节点不因内部风险整体变红，边不因聚合节点染红）
  const srcRisky = !aggFrom && ["RISK_CONFIRMED", "RISK_POTENTIAL"].includes(nodeRiskById[e.source]);
  const tgtRisky = !aggTo && ["RISK_CONFIRMED", "RISK_POTENTIAL"].includes(nodeRiskById[e.target]);
  const risky = srcRisky || tgtRisky;
  return {
    source: e.source, target: e.target,
    edgeSymbol: ["none", "arrow"],
    edgeSymbolSize: [0, isExpand ? 0 : 11],
    label: { show: !isExpand, formatter: isExpand ? "expanded_from" : (e.edge_type || ""), fontSize: 10, color: risky ? "#c0392b" : (isExpand ? "#909399" : "#7f8c8d"), position: "middle" },
    lineStyle: { width: risky ? 4 : (isExpand ? 2 : 2), color: risky ? "#c0392b" : (isExpand ? "#909399" : "#95a5a6"), type: isExpand ? "dashed" : "solid", curveness: 0 },
    _edge: e
  };
});

const chart = echarts.init(document.getElementById("chart"));
window.__chart = chart;
chart.setOption({
  tooltip: { trigger: "item", backgroundColor: "#fff", borderColor: "#d0d7de", textStyle: { color: "#333" } },
  legend: { show: false },
  series: [{
    type: "graph", layout: "none", roam: true, draggable: true,
    data: nodes, links: edges,
    categories: [{ name: "RISK_CONFIRMED" }, { name: "RISK_POTENTIAL" }, { name: "SAFE" }, { name: "UNDETERMINED" }, { name: "AGGREGATE" }],
    emphasis: { focus: "adjacency", label: { show: true, fontSize: 14, fontWeight: "bold", color: "#111" } },
    labelLayout: { hideOverlap: true }
  }]
});

function renderNodeDetail(raw) {
  const j = decisionOf(raw);
  const agg = isAgg(raw);
  const st = aggStats(raw);
  const evs = (raw.evidence_chain || []).map(e =>
    `<div class="ev"><b>证据 ${e.evidence_level || "—"}</b> · ${e.source_api || ""}<br/>字段：${e.source_field || "—"}<br/><a href="${e.source_url || "#"}" target="_blank">${e.source_url || "—"}</a></div>`).join("") || "<div>无证据链</div>";
  document.getElementById("panel-body").innerHTML =
    `<div class="kv"><b>名称</b> ${raw.name || raw.canonical_id}</div>` +
    `<div class="kv"><b>canonical_id</b> ${raw.canonical_id || "—"}</div>` +
    `<div class="kv"><b>类型</b> ${agg ? "聚合节点（AGGREGATE_ONLY）" : (raw.asset_type || "—")}</div>` +
    (agg ? `<div class="kv"><b>覆盖总数</b> ${st.count != null ? st.count : "—"}</div>` +
      `<div class="kv"><b>已展开</b> ${st.expanded != null ? st.expanded : "—"} · <b>剩余未展开</b> ${st.remaining != null ? st.remaining : "—"}</div>` +
      `<div class="kv"><b>已知风险</b> <span style="color:#f56c6c">${st.red} 红</span> / <span style="color:#e6a23c">${st.yellow} 黄</span> / <span style="color:#909399">${st.gray} 灰</span></div>` +
      `<div class="kv"><b>聚合判定</b> 中性（不整体染色）</div>`
      : `<div class="kv"><b>版本</b> ${raw.version || "—"}</div>` +
        `<div class="kv"><b>许可证</b> ${raw.license || "未声明"}</div>` +
        `<div class="kv"><b>判定</b> ${j.label}</div>` +
        `<div class="kv"><b>merge_status</b> ${raw.merge_status || "—"}</div>` +
        `<div class="kv"><b>reason_code</b> ${raw.reason_code || "—"}</div>` +
        `<h3 style="margin-top:10px">证据链</h3>` + evs);
}
function renderEdgeDetail(e) {
  document.getElementById("panel-body").innerHTML =
    `<div class="kv"><b>关系</b> ${e.edge_type || "—"}</div>` +
    `<div class="kv"><b>来源</b> ${nodeById[e.source] ? (nodeById[e.source].name || e.source) : e.source}</div>` +
    `<div class="kv"><b>目标</b> ${nodeById[e.target] ? (nodeById[e.target].name || e.target) : e.target}</div>` +
    `<div class="kv"><b>证据等级</b> ${e.evidence_level || "—"}</div>` +
    `<div class="kv"><b>source_field</b> ${e.source_field || "—"}</div>` +
    `<div class="kv"><b>传播路径证书</b> ${e.certificates && e.certificates.length ? e.certificates.join("<br/>") : "—"}</div>`;
}
chart.on("click", p => {
  if (p.dataType === "node") renderNodeDetail(p.data._raw);
  else if (p.dataType === "edge") renderEdgeDetail(p.data._edge);
});

const tbody = document.querySelector("#compliance tbody");
DATA.nodes.forEach(n => {
  const agg = isAgg(n);
  const j = decisionOf(n);
  const st = aggStats(n);
  const cell = agg
    ? `<span class="dot" style="background:#eef0f4;border:2px solid ${st.red ? "#f56c6c" : (st.yellow ? "#e6a23c" : "#c0c4cc")}"></span>聚合域 · 已知 ${st.red}红/${st.yellow}黄/${st.gray}灰 · 剩余 ${st.remaining != null ? st.remaining : "—"}`
    : `<span class="dot" style="background:${j.color}"></span>${j.label}`;
  const tr = document.createElement("tr");
  tr.innerHTML = `<td>${n.name || n.canonical_id}</td><td>${n.version || "—"}</td><td>${n.license || "未声明"}</td><td>${cell}</td>`;
  tbody.appendChild(tr);
});
</script>
</body>
</html>
"""


def forest_layout(nodes, edges):
    """森林分层布局：基座模型在上（一行），聚合/衍生节点在下（两行两列展开）。"""
    nodeById = {n["id"]: n for n in nodes}
    base_nodes = [n for n in nodes if not is_agg(n)]
    base_ids = [n["id"] for n in base_nodes]
    children_of = {bid: [] for bid in base_ids}
    for e in edges:
        if e["target"] in children_of and e["source"] not in children_of:
            children_of[e["target"]].append(e["source"])
    for idx, b in enumerate(base_nodes):
        b["x"] = 160 + idx * 380
        b["y"] = 110
        b["lp"] = "top"
        for kid_i, kid in enumerate(children_of.get(b["id"], [])):
            col = kid_i % 2
            row = kid_i // 2
            xoff = -120 if col == 0 else 120
            yoff = 170 + row * 150
            if kid in nodeById:
                nodeById[kid]["x"] = b["x"] + xoff
                nodeById[kid]["y"] = b["y"] + yoff
                nodeById[kid]["lp"] = "bottom"


def is_agg(n):
    return "(Total:" in (n.get("name") or "") or " · " in (n.get("name") or "")


def main() -> None:
    parser = argparse.ArgumentParser(description="开源账本通用血缘图渲染器（读 A 层 graph.json）")
    parser.add_argument("--input", required=True, type=Path, help="graph.json 路径，例如 outputs/Qwen__Qwen-Image-2.1/graph.json")
    parser.add_argument("--output", required=True, type=Path, help="输出 HTML 路径")
    parser.add_argument("--title", default=None, help="页面标题（默认取输入目录名）")
    args = parser.parse_args()

    graph = json.loads(args.input.read_text(encoding="utf-8"))
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # 补全节点 id（canonical_id 缺失时兜底）
    for n in nodes:
        n.setdefault("id", n.get("canonical_id") or n.get("entity_key") or n.get("name"))

    forest_layout(nodes, edges)

    # 聚合域属性透传：graph.json 节点可能带 coverage_status/count/expanded_count/
    # remaining_count/known_risk_counts（BOM 聚合域结构经 bom_adapter 透出）。
    # 统一挂到 n["_stats"]，供前端聚合节点中性渲染 + 统计徽标使用。
    for n in nodes:
        stats = {
            "coverage_status": n.get("coverage_status"),
            "count": n.get("count"),
            "expanded_count": n.get("expanded_count"),
            "remaining_count": n.get("remaining_count"),
            "known_risk_counts": n.get("known_risk_counts"),
        }
        if any(v is not None for v in stats.values()):
            n["_stats"] = stats

    data = {
        "nodes": nodes,
        "edges": edges,
    }
    title = args.title or f"{args.input.parent.name} · 血缘风险图"
    overall = graph.get("overall_decision_zh") or graph.get("overall_decision") or "—"
    html = TPL
    html = html.replace("{{TITLE}}", title)
    html = html.replace("{{NODE_COUNT}}", str(len(nodes)))
    html = html.replace("{{EDGE_COUNT}}", str(len(edges)))
    html = html.replace("{{OVERALL}}", overall)
    html = html.replace("{{DATA_JSON}}", json.dumps(data, ensure_ascii=False))
    html = html.replace("{{DECISION_COLOR_JSON}}", json.dumps(DECISION_COLOR, ensure_ascii=False))
    html = html.replace("{{DECISION_LABEL_JSON}}", json.dumps(DECISION_LABEL, ensure_ascii=False))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # ECharts：优先本地文件（复制到输出同目录，保证离线可开），缺失回退 CDN。
    # vendor 优先：根目录副本可能被工具链转成 UTF-16 BOM 导致浏览器解析失败，
    # 须做健康检查（跳过 BOM 损坏文件）。
    local_echarts = args.output.parent / "echarts.min.js"
    src_candidates = [
        Path(__file__).resolve().parent / "vendor" / "echarts.min.js",
        Path(__file__).resolve().parent / "echarts.min.js",
        Path(__file__).resolve().parent / "outputs" / "modelscope_validation" / "echarts.min.js",
    ]
    echarts_src = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"
    for cand in src_candidates:
        if not cand.exists():
            continue
        head = cand.read_bytes()[:2]
        if head == b"\xff\xfe" or head == b"\xfe\xff":
            # UTF-16 BOM：编码损坏，浏览器无法执行（Uncaught SyntaxError）
            continue
        # --output 落在仓库根时，cand 与 local_echarts 是同一个文件，
        # 直接 copy 会抛 shutil.SameFileError，这里先判同文件再复制。
        if cand.resolve() != local_echarts.resolve():
            shutil.copy(cand, local_echarts)
        echarts_src = "./echarts.min.js"
        break
    html = html.replace("{{ECHARTS_SRC}}", echarts_src)

    args.output.write_text(html, encoding="utf-8")
    print("已生成：%s（节点 %d / 边 %d，整体判定 %s）" % (args.output, len(nodes), len(edges), overall))


if __name__ == "__main__":
    main()
