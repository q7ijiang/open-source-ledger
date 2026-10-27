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
  .ai-status-strip { padding:8px 22px; background:#f8fafc; border-bottom:1px solid var(--line); font-size:12px; color:#475569; }
  .ai-status-strip b { color:#075985; }
  .lineage-section { background:#fff; border-top:1px solid var(--line); padding:14px 22px 18px; }
  .lineage-section h2 { margin:0 0 4px; font-size:15px; }
  .lineage-section p { margin:0 0 10px; color:var(--muted); font-size:12px; }
  .lineage-forest { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:9px; }
  .lineage-root { border:1px solid var(--line); border-radius:7px; background:#fbfdff; padding:9px 11px; min-width:0; }
  .lineage-root .root-name { font-weight:700; font-size:12px; color:#253044; word-break:break-all; }
  .lineage-root .root-meta { margin-top:3px; font-size:11px; color:var(--muted); }
  .lineage-root ul { margin:7px 0 0 17px; padding:0; }
  .lineage-root li { margin:5px 0; font-size:11px; color:#475569; line-height:1.45; }
  .lineage-root li .arrow { color:#2f6fed; font-weight:700; margin-right:4px; }
  .lineage-root li .role { color:#7b8799; }
  .report-section { display:flex; gap:12px; align-items:flex-start; flex-wrap:wrap; padding:12px 22px; background:#fff; border-top:1px solid var(--line); font-size:12px; }
  .report-actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  .download-button { appearance:none; border:1px solid #2f6fed; border-radius:6px; background:#2f6fed; color:#fff; padding:8px 13px; font:700 12px/1.2 "Microsoft YaHei","Segoe UI",Arial,sans-serif; cursor:pointer; }
  .download-button:disabled { opacity:.5; cursor:not-allowed; }
  .secondary-button { appearance:none; border:1px solid #2f6fed; border-radius:6px; background:#fff; color:#2f6fed; padding:8px 13px; font:700 12px/1.2 "Microsoft YaHei","Segoe UI",Arial,sans-serif; cursor:pointer; }
  .secondary-button:disabled { opacity:.5; cursor:not-allowed; }
  .report-modal[hidden] { display:none; }
  .report-modal { position:fixed; inset:0; z-index:1000; display:flex; align-items:center; justify-content:center; padding:20px; background:rgba(15,23,42,.58); }
  .report-dialog { width:min(1180px,calc(100vw - 32px)); height:min(86vh,900px); display:flex; flex-direction:column; overflow:hidden; background:#fff; border:1px solid #cbd5e1; border-radius:10px; box-shadow:0 24px 70px rgba(15,23,42,.28); }
  .report-modal-head { display:flex; justify-content:space-between; align-items:center; gap:16px; padding:12px 16px; border-bottom:1px solid var(--line); background:#f8fafc; }
  .report-modal-head b { font-size:14px; }
  .report-modal-head span { color:var(--muted); font-size:11px; }
  .report-close { appearance:none; border:1px solid #cbd5e1; border-radius:6px; background:#fff; color:#475569; padding:6px 11px; font:700 12px/1.2 "Microsoft YaHei","Segoe UI",Arial,sans-serif; cursor:pointer; }
  .report-preview { flex:1 1 auto; min-height:0; overflow:auto; overscroll-behavior:contain; margin:0; padding:16px 18px; background:#fbfdff; border:0; white-space:pre-wrap; word-break:break-word; font:12px/1.65 Consolas,"Microsoft YaHei",monospace; outline:none; }
  .report-preview:focus { box-shadow:inset 0 0 0 2px rgba(47,111,237,.22); }
  .main { display:grid; grid-template-columns:minmax(0,1fr) 320px; min-height:0; }
  #chart { width:100%; height:{{CHART_HEIGHT}}px; }
  #panel { background:#fff; border-left:1px solid var(--line); padding:14px; font-size:12px; overflow-y:auto; max-height:{{CHART_HEIGHT}}px; }
  #panel h3 { margin:0 0 10px; font-size:14px; }
  .kv { margin:5px 0; word-break:break-all; line-height:1.55; }
  .kv b { color:#356fa8; }
  .ev { border-top:1px dashed var(--line); padding:8px 0; line-height:1.5; }
  .ev { word-break:break-all; }
  .ai-box { margin-top:10px; border:1px solid #bae6fd; background:#f0f9ff; border-radius:8px; padding:10px; line-height:1.55; }
  .ai-box h4 { margin:0 0 7px; color:#075985; font-size:13px; }
  .ai-claim { border-top:1px solid #dbeafe; padding:7px 0; }
  .ai-meta { color:#0369a1; font-size:11px; word-break:break-all; }
  .ai-factor { color:#475569; font-size:10px; margin-top:3px; word-break:break-all; line-height:1.5; }
  .ai-quote { margin-top:4px; padding:6px 8px; background:#fff; border-left:3px solid #38bdf8; white-space:pre-wrap; word-break:break-word; }
  .ai-gap { color:#92400e; margin-top:5px; }
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
  <div><h1>{{TITLE}}</h1><div class="sub">上游血缘分层 · 越靠上越上游 · 箭头指向来源模型 · 点击节点查看证据</div></div>
  <div class="stats">节点 {{NODE_COUNT}} · 边 {{EDGE_COUNT}} · 整体判定：<b>{{OVERALL}}</b></div>
</div>
<div class="legend-row">
  <span><i style="background:#f56c6c"></i>高风险</span>
  <span><i style="background:#e6a23c"></i>潜在风险</span>
  <span><i style="background:#67c23a"></i>安全</span>
  <span><i style="background:#d3d7de"></i>待确认</span>
  <span><i class="line" style="background:#95a5a6"></i>实线箭头 = 下游模型派生自上游来源</span>
  <span id="legend-aggregate" hidden><i style="background:#eef0f4;border:2px solid #f56c6c"></i>聚合域仅表示范围，不是血缘</span>
</div>
<div id="ai-status-strip" class="ai-status-strip">正在读取 AI 语义证据状态…</div>
<div class="main">
  <div id="chart"></div>
  <aside id="panel"><h3>证据与能力边界</h3><div id="panel-body" style="color:#7b8799">点击模型、聚合域或连线查看详情。</div></aside>
</div>

<section class="lineage-section">
  <h2>项目模型与上游来源路径</h2>
  <p>箭头从下游模型指向更上游的来源。这里把路径展开成文字，便于识别基座模型和中间来源；聚合域不作为血缘节点。</p>
  <div id="lineage-forest" class="lineage-forest"></div>
</section>

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

<section class="report-section">
  <div><b>Markdown 审计报告</b><div style="color:#64748b;margin-top:3px">报告仍由 main.py 生成，HTML 仅附带原文预览与下载，不替代报告文件。</div></div>
  <div class="report-actions">
    <button id="open-report" class="secondary-button" type="button">在大窗口查看报告</button>
    <button id="download-report" class="download-button" type="button">下载 Markdown 报告</button>
  </div>
</section>
<div id="report-modal" class="report-modal" role="dialog" aria-modal="true" aria-labelledby="report-modal-title" hidden>
  <div class="report-dialog">
    <div class="report-modal-head">
      <div><b id="report-modal-title">Markdown 审计报告</b><br/><span>在报告区域滚动查看；按 Esc 关闭</span></div>
      <button id="close-report" class="report-close" type="button">关闭</button>
    </div>
    <pre id="report-preview" class="report-preview" tabindex="0"></pre>
  </div>
</div>
<script>
const DATA = {{DATA_JSON}};
const DECISION_COLOR = {{DECISION_COLOR_JSON}};
const DECISION_LABEL = {{DECISION_LABEL_JSON}};
const REPORT_MARKDOWN = {{REPORT_MARKDOWN_JSON}};

function escapeHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}
function modelscopeModelPageUrl(raw) {
  if (!raw || raw.asset_type !== "model") return null;
  if (raw.aggregate === true || raw.coverage_status === "AGGREGATE_ONLY") return null;
  const canonical = String(raw.canonical_id || "");
  if (canonical.includes(":son:") || canonical.includes(":parent:")) return null;
  const prefix = "model:modelscope/";
  let modelId = canonical.startsWith(prefix) ? canonical.slice(prefix.length).split("@")[0] : "";
  if (!modelId) {
    const purlPrefix = "pkg:modelscope/";
    const purl = (raw.purls || []).find(value => String(value).startsWith(purlPrefix));
    if (purl) modelId = String(purl).slice(purlPrefix.length).split("@")[0];
  }
  const parts = modelId.split("/");
  if (parts.length !== 2 || parts.some(part => !part || /\\s/.test(part))) return null;
  return `https://www.modelscope.cn/models/${parts.map(encodeURIComponent).join("/")}`;
}
function aiAnalysis(n) {
  return n && n.ai_analysis && n.ai_analysis.analysis_type === "model_profile" ? n.ai_analysis : null;
}
function confidenceFactorText(claim) {
  const labels = {base:"基础",license_file:"LICENSE 文件",readme:"README 文件",structured_file:"结构化文件",exact_quote:"原文精确命中",restriction_wording:"限制措辞",source_sha256:"SHA256",quote_context:"引文长度",uncertain_state:"不确定性"};
  return Object.entries(claim.confidence_factors || {}).map(([key, value]) => {
    const number = Number(value);
    return `${labels[key] || key} ${number >= 0 ? "+" : ""}${number.toFixed(2)}`;
  }).join(" · ");
}
function aiTooltip(n) {
  const ai = aiAnalysis(n);
  if (!ai) return "";
  const claims = ai.claims || [];
  const first = claims[0];
  const summary = first ? `${escapeHtml(first.dimension_zh || first.dimension)}：${escapeHtml(first.state_zh || first.state)}（${escapeHtml(first.confidence)}）` : "无通过原文校验的条款";
  return `<br/>AI 语义：C级 · ${summary} · 待人工确认`;
}
function renderAiDetails(raw) {
  const ai = aiAnalysis(raw);
  const project = raw && raw.ai_project_context && raw.ai_project_context.analysis_type === "project_context" ? raw.ai_project_context : null;
  if (!ai && !project) return "";
  let html = `<div class="ai-box"><h4>AI 语义证据（C 级，不改变规则判定）</h4>`;
  if (ai) {
    if (ai.simulation) html += `<div class="ai-gap"><b>验收模拟</b>：${escapeHtml(ai.simulation_note || "该条款画像用于验收，不代表数据源当前事实")}</div>`;
    html += `<div class="kv"><b>模型分析状态</b> ${escapeHtml(ai.status || "unknown")}</div>`;
    if (ai.summary) html += `<div class="kv"><b>摘要</b> ${escapeHtml(ai.summary)}</div>`;
    (ai.claims || []).forEach(claim => {
      const evidence = claim.evidence || {};
      html += `<div class="ai-claim"><div><b>${escapeHtml(claim.dimension_zh || claim.dimension)}</b>：${escapeHtml(claim.state_zh || claim.state)}</div>` +
        `<div class="ai-meta">置信度 ${escapeHtml(claim.confidence)} · 证据等级 ${escapeHtml(claim.evidence_level || "C")} · ${escapeHtml(claim.human_review || "pending")}</div>` +
        `<div class="ai-factor">置信度构成：${escapeHtml(confidenceFactorText(claim))}</div>` +
        `<div class="ai-quote">${escapeHtml(evidence.quote || "—")}</div>` +
        `<div class="ai-meta">原文：${escapeHtml(evidence.source_path || "—")} · SHA256 ${escapeHtml(evidence.quote_sha256 || "—")}</div></div>`;
    });
    const gaps = ai.gaps || [];
    if (gaps.length) html += `<div class="ai-gap"><b>证据缺口</b><br/>${gaps.map(g => `${escapeHtml(g.dimension_zh || g.dimension)}：${escapeHtml(g.reason || "证据不足")}`).join("<br/>")}</div>`;
  }
  if (project) {
    if (project.simulation) html += `<div class="ai-gap"><b>验收模拟</b>：${escapeHtml(project.simulation_note || "该项目上下文用于验收展示")}</div>`;
    html += `<div class="kv"><b>项目使用上下文</b></div>`;
    (project.uses || []).forEach(item => {
      const evidence = item.evidence || {};
      html += `<div class="ai-claim"><div><b>${escapeHtml(item.use_type_zh || item.use_type)}</b>：${escapeHtml(item.statement)}</div>` +
        `<div class="ai-meta">置信度 ${escapeHtml(item.confidence)} · C · ${escapeHtml(item.human_review || "pending")}</div>` +
        `<div class="ai-quote">${escapeHtml(evidence.quote || "—")}</div>` +
        `<div class="ai-meta">项目文件：${escapeHtml(evidence.source_path || "—")}</div></div>`;
    });
  }
  return html + `</div>`;
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
      tooltip:{show:visible,formatter:() => `<b>${escapeHtml(n.name || label)}</b><br/>类型：展开的风险子节点<br/>许可证：${escapeHtml(n.license || "未声明")}<br/>判定：${j.label}${isFixtureNode(n) ? "<br/>构造测试夹具，不代表真实下游模型" : ""}${aiTooltip(n)}`},
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
  const card = n.render_card || {};
  const role = n.render_role_short || n.render_role_label || (n.lineage_role === "root" ? "项目直接使用" : "上游模型");
  const aiTag = aiAnalysis(n) ? " · AI" : "";
  const supplyMeta = n.lineage_depth == null ? "" : `上游深度 ${n.lineage_depth}`;
  if (card.width) {
    return {
      id:n.id,
      name:n.name || n.id,
      x:n.x,
      y:n.y,
      symbol:"rect",
      symbolSize:[card.width, card.height],
      itemStyle:{
        color:childFill(n.decision),
        borderColor:j.color,
        borderWidth:["RISK_CONFIRMED","RISK_POTENTIAL"].includes(n.decision) ? 2.5 : 1.8,
        borderRadius:8,
        shadowBlur:["RISK_CONFIRMED","RISK_POTENTIAL"].includes(n.decision) ? 7 : 0,
        shadowColor:"rgba(15,23,42,.12)"
      },
      label:{
        show:true,
        position:"inside",
        formatter:() => `{name|${card.label || n.name || n.id}}\\n{role|${role}${aiTag}}`,
        rich:{
          name:{fontSize:card.width < 145 ? 9 : 10,fontWeight:"bold",color:"#253044",lineHeight:15,width:card.width - 18,overflow:"truncate"},
          role:{fontSize:8,color:aiAnalysis(n) ? "#0369a1" : j.color,lineHeight:13}
        }
      },
      tooltip:{formatter:() => `<b>${escapeHtml(n.name || n.id)}</b><br/>角色：${escapeHtml(role)}<br/>类型：${escapeHtml(n.asset_type || "—")}<br/>许可证：${escapeHtml(n.license || "未声明")}<br/>${escapeHtml(supplyMeta)}<br/>判定：${j.label}${n.decision_source === "diff_propagation" ? "（传播）" : ""}${aiTooltip(n)}`},
      _raw:n,
      z:4
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
    tooltip: {formatter: () => `<b>${escapeHtml(n.name || n.id)}</b><br/>类型：${escapeHtml(n.asset_type || "—")}<br/>版本：${escapeHtml(n.version || "—")}<br/>许可证：${escapeHtml(n.license || "未声明")}<br/>判定：${j.label}${n.decision_source === "diff_propagation" ? "（传播）" : ""}${aiTooltip(n)}`},
    _raw:n,
    z:4
  };
  });
}

function buildLinks() {
  return DATA.edges.map(e => {
    const source = nodeById[e.source] || {};
    const target = nodeById[e.target] || {};
    // Aggregate membership is expressed by spatial containment. Drawing it as
    // a graph edge makes grouping look like model lineage.
    if (e.edge_type === "expanded_from" || isAggregate(source) || isAggregate(target)) return null;
    const risky = ["RISK_CONFIRMED","RISK_POTENTIAL"].includes(source.decision) ||
      ["RISK_CONFIRMED","RISK_POTENTIAL"].includes(target.decision);
    return {
      source:e.source,
      target:e.target,
      label:{show:false},
      emphasis:{label:{show:true,formatter:e.render_label || e.edge_type || "派生自",fontSize:10,color:risky ? "#c0392b" : "#475569"}},
      lineStyle:{
        width:risky ? 3.2 : 1.6,
        color:risky ? "#c0392b" : "#8794a6",
        type:"solid",
        curveness:0.035,
        opacity:risky ? 0.92 : 0.76
      },
      _edge:e
    };
  }).filter(Boolean);
}

const clusterGraphics = DATA.layout.clusters.map(c => {
  const lineageLayer = c.kind === "lineage_layer";
  const subtitle = c.subtitle || `聚合域 ${c.aggregate_count} 个${c.expanded_count ? ` · 展开 ${c.expanded_count}` : ""}`;
  return {
    type:"group",
    left:c.x,
    top:c.y,
    z:-1,
    silent:true,
    children:[
      {type:"rect",shape:{x:0,y:0,width:c.width,height:c.height,r:12},style:{fill:lineageLayer ? "#f8fafc" : "#fbfcfe",stroke:lineageLayer ? "#e5eaf1" : "#dfe7f1",lineWidth:1}},
      {type:"text",style:{x:16,y:22,text:c.title,fill:"#253044",font:"bold 13px Microsoft YaHei"}},
      {type:"text",style:{x:16,y:41,text:subtitle,fill:"#7b8799",font:"10px Microsoft YaHei"}}
    ]
  };
});
const aggregateLegend = document.getElementById("legend-aggregate");
if (aggregateLegend) aggregateLegend.hidden = !DATA.nodes.some(isAggregate);
if (DATA.layout.cycle_nodes?.length) {
  const subtitle = document.querySelector(".header .sub");
  if (subtitle) subtitle.textContent += ` · 数据源返回 ${DATA.layout.cycle_nodes.length} 个异常循环节点，已保留但未改变关系`;
}

const chart = echarts.init(document.getElementById("chart"));
const aiStatusStrip = document.getElementById("ai-status-strip");
const aiProfiles = DATA.nodes.filter(n => aiAnalysis(n));
const projectContexts = [...new Map(DATA.nodes.filter(n => n.ai_project_context && n.ai_project_context.analysis_type === "project_context").map(n => [n.ai_project_context.subject?.project_path || "project", n])).values()];
if (aiProfiles.length || projectContexts.length) {
  const claimCount = aiProfiles.reduce((sum, n) => sum + ((aiAnalysis(n).claims || []).length), 0);
  const simulated = aiProfiles.some(n => aiAnalysis(n).simulation);
  aiStatusStrip.innerHTML = `<b>AI 证据已启用</b> · ${aiProfiles.length} 个模型条款画像 · ${claimCount} 条逐字条款 · ${projectContexts.length} 个项目上下文 · C 级待人工确认${simulated ? " · 含验收模拟条款" : ""}`;
} else {
  aiStatusStrip.innerHTML = "<b>AI 状态：本图未固化条款画像</b> · 这不影响规则判定与图谱渲染；启用 --ai 后重新扫描可生成 C 级证据";
}
const downloadReport = document.getElementById("download-report");
const reportPreview = document.getElementById("report-preview");
const openReport = document.getElementById("open-report");
const closeReport = document.getElementById("close-report");
const reportModal = document.getElementById("report-modal");
function setReportOpen(open) {
  reportModal.hidden = !open;
  if (open) reportPreview.focus();
}
openReport.addEventListener("click", () => setReportOpen(true));
closeReport.addEventListener("click", () => setReportOpen(false));
reportModal.addEventListener("click", event => {
  if (event.target === reportModal) setReportOpen(false);
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !reportModal.hidden) setReportOpen(false);
});
if (REPORT_MARKDOWN) {
  reportPreview.textContent = REPORT_MARKDOWN;
  downloadReport.addEventListener("click", () => {
    const url = URL.createObjectURL(new Blob([REPORT_MARKDOWN], {type:"text/markdown;charset=utf-8"}));
    const link = document.createElement("a");
    link.href = url;
    link.download = "audit_report.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });
} else {
  downloadReport.disabled = true;
  downloadReport.textContent = "未附带 Markdown 报告";
  openReport.disabled = true;
  reportPreview.textContent = "本次 HTML 渲染未传入 --report；报告生成链路本身仍然保留。";
}

function renderLineageForest() {
  const host = document.getElementById("lineage-forest");
  if (!host) return;
  const upstream = {};
  DATA.edges.forEach(e => {
    if (e.edge_type === "expanded_from") return;
    if (!upstream[e.source]) upstream[e.source] = [];
    if (nodeById[e.target]) upstream[e.source].push(e.target);
  });
  let roots = DATA.nodes.filter(n => !isAggregate(n) && (n.lineage_role === "root" || n.lineage_depth === 0));
  if (!roots.length) roots = DATA.nodes.filter(n => !isAggregate(n));
  if (!roots.length) { host.innerHTML = `<div class="lineage-empty">当前图没有具体模型节点。</div>`; return; }
  function branch(nodeId, seen, depth) {
    if (depth > 12 || seen.has(nodeId)) return `<li><span class="arrow">↺</span>${escapeHtml(nodeId)} <span class="role">循环引用，已停止</span></li>`;
    const nextSeen = new Set(seen);
    nextSeen.add(nodeId);
    return (upstream[nodeId] || []).map(target => {
      const targetNode = nodeById[target] || {};
      const role = targetNode.render_role_label || targetNode.lineage_type_ch || targetNode.lineage_type || "上游来源";
      const children = branch(target, nextSeen, depth + 1);
      return `<li><span class="arrow">↑</span><b>${escapeHtml(targetNode.name || target)}</b> <span class="role">${escapeHtml(role)} · ${escapeHtml(targetNode.license || "未声明")}</span>${children ? `<ul>${children}</ul>` : ""}</li>`;
    }).join("");
  }
  host.innerHTML = roots.map(root => {
    const j = decisionOf(root.decision);
    const tree = branch(root.id, new Set(), 0);
    return `<div class="lineage-root"><div class="root-name">${escapeHtml(root.name || root.canonical_id)}</div>` +
      `<div class="root-meta">项目直接使用 · 许可证 ${escapeHtml(root.license || "未声明")} · ${escapeHtml(j.label)}</div>` +
      `${tree ? `<ul>${tree}</ul>` : `<div class="lineage-empty" style="margin-top:7px">未发现可解析的上游来源。</div>`}</div>`;
  }).join("");
}
renderLineageForest();

window.__chart = chart;
function refresh() {
  chart.setOption({
    tooltip:{trigger:"item",backgroundColor:"#fff",borderColor:"#d0d7de",textStyle:{color:"#334155",fontSize:12}},
    legend:{show:false},
    graphic:clusterGraphics,
    series:[{
      type:"graph",
      layout:"none",
      roam:true,
      draggable:false,
      zoom:0.95,
      scaleLimit:{min:0.55,max:2.5},
      edgeSymbol:["none","arrow"],
      edgeSymbolSize:[0,12],
      data:buildNodes(),
      links:buildLinks(),
      emphasis:{focus:"adjacency",lineStyle:{width:5}},
      labelLayout:{hideOverlap:false}
    }]
  }, true);
}
refresh();
window.addEventListener("resize", () => chart.resize());

function renderNodeDetail(raw) {
  const pageUrl = modelscopeModelPageUrl(raw);
  const pageLink = pageUrl
    ? `<div class="kv"><b>ModelScope 模型主页</b> <a href="${escapeHtml(pageUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(pageUrl)}</a></div>`
    : "";
  const j = decisionOf(raw.decision);
  const agg = isAggregate(raw);
  let evs = (raw.evidence_chain || []).map(e => {
    const sourceUrl = String(e.source_url || "").trim();
    const sourceLink = sourceUrl
      ? `<br/><a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">原始 API 证据：${escapeHtml(sourceUrl)}</a>`
      : `<br/><span class="evidence-missing">原始 API 证据：未提供</span>`;
    return `<div class="ev"><b>证据 ${escapeHtml(e.evidence_level || "—")}</b> · ${escapeHtml(e.source_api || "")}<br/>字段：${escapeHtml(e.source_field || "—")}${sourceLink}</div>`;
  }).join("") || "<div class='ev'>无证据链</div>";
  evs = (pageLink || "") + evs;
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
    const lineageType = raw.lineage_type_ch || raw.lineage_type || "未标注";
    const lineageRole = raw.render_role_label || (raw.lineage_role === "root" ? "项目直接使用" : `上游 · ${lineageType}`);
    html += `<div class="kv"><b>血缘角色</b> ${escapeHtml(lineageRole)}</div>` +
      `<div class="kv"><b>上游深度</b> ${escapeHtml(raw.lineage_depth ?? "—")}</div>` +
      `<div class="kv"><b>血缘状态</b> ${escapeHtml(raw.lineage_status || "—")}</div>` +
      `<div class="kv"><b>判定来源</b> ${escapeHtml(raw.decision_source || "自身许可证评估")}</div>` +
      `<div class="kv"><b>merge_status</b> ${escapeHtml(raw.merge_status || "—")}</div>` +
      `<div class="kv"><b>reason_code</b> ${escapeHtml(raw.reason_code || "—")}</div>`;
  }
  document.getElementById("panel-body").innerHTML = html + renderAiDetails(raw) + `<h3 style="margin-top:12px">证据链</h3>` + evs;
}

function renderEdgeDetail(edge) {
  const source = nodeById[edge.source] || {};
  const target = nodeById[edge.target] || {};
  const membership = isAggregate(source) || isAggregate(target);
  document.getElementById("panel-body").innerHTML =
    `<div class="kv"><b>关系类型</b> ${escapeHtml(edge.edge_type || "—")}</div>` +
    `<div class="kv"><b>下游/派生方</b> ${escapeHtml(source.name || edge.source)}</div>` +
    `<div class="kv"><b>上游/来源方</b> ${escapeHtml(target.name || edge.target)}</div>` +
    `<div class="kv"><b>方向</b> ${membership ? "聚合成员归属，不是血缘" : "箭头指向更上游的来源模型"}</div>` +
    `<div class="kv"><b>证据等级</b> ${escapeHtml(edge.evidence_level || "—")}</div>` +
    `<div class="kv"><b>source_field</b> ${escapeHtml(edge.source_field || "—")}</div>` +
    `<div class="kv"><b>语义</b> ${membership ? "聚合域成员归属，不参与风险传播" : "下游模型派生自上游模型"}</div>` +
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
    card.innerHTML = `<div class="name">${escapeHtml(n.name || n.canonical_id)}</div><div class="meta">${j.label} · 许可证 ${escapeHtml(n.license || "未声明")} · 证据链 ${(n.evidence_chain || []).length} 条${aiAnalysis(n) ? ` · AI ${(aiAnalysis(n).claims || []).length} 条待确认` : ""}</div>`;
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
    parser.add_argument("--report", type=Path, default=None, help="可选：Markdown 审计报告路径，嵌入页面供预览和下载")
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
    report_markdown = ""
    if args.report is not None:
        if not args.report.exists():
            raise FileNotFoundError(f"report not found: {args.report}")
        report_markdown = args.report.read_text(encoding="utf-8")

    html = TPL
    replacements = {
        "{{TITLE}}": title,
        "{{NODE_COUNT}}": str(len(nodes)),
        "{{EDGE_COUNT}}": str(len(edges)),
        "{{OVERALL}}": str(overall),
        "{{DATA_JSON}}": json.dumps(data, ensure_ascii=False),
        "{{DECISION_COLOR_JSON}}": json.dumps(DECISION_COLOR, ensure_ascii=False),
        "{{DECISION_LABEL_JSON}}": json.dumps(DECISION_LABEL, ensure_ascii=False),
        "{{REPORT_MARKDOWN_JSON}}": json.dumps(report_markdown, ensure_ascii=False),
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
