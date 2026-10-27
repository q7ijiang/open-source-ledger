# -*- coding: utf-8 -*-
"""--diff 时间轴风险传播图渲染器：左 t0、右 t1，中间标变化事件。

用法：
  python render_diff.py --before <t0-bom.json> \
      --after <t1-bom.json> --output <diff.html>

链路与 main.py --diff 一致（只读 BOM 固化的血缘边，零在线请求）：
  _build_snapshot -> build_graph -> delta_engine.detect_delta -> propagation_engine.propagate
"""
from __future__ import annotations

import argparse
import json
import shutil
import copy
from collections import Counter
from pathlib import Path

import build_graph
import delta_engine
import propagation_engine
from render_diff_operational import operational_snapshot
from render_layout import is_aggregate_node, layout_graph
from ai_layer.schemas import semantic_diff

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
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{TITLE}} - 时间轴风险传播图</title>
<script src="{{ECHARTS_SRC}}"></script>
<style>
  :root { --ink:#172033; --muted:#64748b; --line:#e2e8f0; --paper:#f7f9fc; }
  * { box-sizing:border-box; }
  body { font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif; margin:0; background:var(--paper); color:var(--ink); }
  .header { display:flex; justify-content:space-between; align-items:center; gap:18px; padding:12px 20px; background:#fff; border-bottom:1px solid var(--line); }
  .header h1 { font-size:18px; margin:0 0 3px; }
  .header .sub { font-size:11px; color:var(--muted); }
  .stats { font-size:12px; color:#475569; white-space:nowrap; }
  .legend-row { padding:7px 20px; background:#fff; border-bottom:1px solid #eef2f7; font-size:12px; color:#526176; display:flex; flex-wrap:wrap; gap:13px; align-items:center; }
  .legend-row i { display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:4px; vertical-align:-2px; }
  .legend-row .line { width:20px; height:3px; }
  .snapshot-tabs { display:flex; gap:8px; align-items:center; padding:8px 20px; background:#fff; border-bottom:1px solid var(--line); }
  .snapshot-tab { appearance:none; border:1px solid #d8e0eb; border-radius:6px; background:#f8fafc; color:#526176; padding:7px 14px; font:700 12px/1.2 "Microsoft YaHei","Segoe UI",Arial,sans-serif; cursor:pointer; }
  .snapshot-tab:hover { border-color:#8fb5df; color:#275f96; }
  .snapshot-tab.is-active { border-color:#409eff; background:#eef6ff; color:#1e64aa; box-shadow:0 0 0 1px rgba(64,158,255,.08); }
  .snapshot-tab .hint { font-weight:400; opacity:.72; margin-left:5px; }
  .main { display:grid; grid-template-columns:minmax(0,1fr) 270px; min-height:0; background:#fff; }
  .stage { min-width:0; overflow:hidden; background:#fff; }
  .stage-title { position:sticky; top:0; z-index:2; font-size:13px; font-weight:700; padding:8px 14px; color:#475569; background:#fff; border-bottom:1px solid #eef2f7; }
  .stage-title span { margin-left:8px; color:#7b8799; font-size:11px; font-weight:400; }
  .chart-shell { overflow:auto; }
  .ai-status-strip { padding:8px 20px; background:#f8fafc; border-bottom:1px solid var(--line); font-size:12px; color:#475569; }
  .ai-status-strip b { color:#075985; }
  .report-section { display:flex; gap:12px; align-items:flex-start; flex-wrap:wrap; padding:12px 20px; background:#fff; border-top:1px solid var(--line); font-size:12px; }
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
  .chart-page[hidden] { display:none; }
  .chart { width:100%; min-width:1080px; height:{{CHART_HEIGHT}}px; }
  .mid { background:#fff; border-left:1px solid var(--line); padding:10px; font-size:12px; overflow-y:auto; max-height:{{CHART_HEIGHT}}px; }
  .mid h3 { margin:0 0 8px; font-size:13px; }
  .evt { border:1px solid var(--line); border-radius:6px; padding:7px 8px; margin-bottom:8px; cursor:pointer; background:#fafcfe; }
  .evt:hover { border-color:#409eff; }
  .evt .tag { display:inline-block; padding:1px 6px; border-radius:3px; color:#fff; font-size:10px; }
  .evt .arrow { color:#c0392b; font-weight:700; }
  .ai-diff-block { margin-bottom:12px; padding-bottom:10px; border-bottom:1px solid var(--line); }
  .ai-diff { border:1px solid #bae6fd; background:#f0f9ff; border-radius:6px; padding:7px 8px; margin-bottom:7px; line-height:1.5; }
  .ai-diff .route { color:#075985; font-weight:700; }
  .ai-diff .meta { color:#0369a1; font-size:11px; margin-top:3px; }
  .ai-box { margin-top:10px; border:1px solid #bae6fd; background:#f0f9ff; border-radius:8px; padding:10px; line-height:1.55; }
  .ai-box h4 { margin:0 0 7px; color:#075985; font-size:13px; }
  .ai-claim { border-top:1px solid #dbeafe; padding:7px 0; }
  .ai-meta { color:#0369a1; font-size:11px; }
  .ai-quote { margin-top:4px; padding:6px 8px; background:#fff; border-left:3px solid #38bdf8; white-space:pre-wrap; word-break:break-word; }
  .ai-gap { color:#92400e; margin-top:5px; }
  #panel { padding:12px 20px; background:#fff; border-top:1px solid var(--line); font-size:12px; }
  #panel h3 { margin:0 0 8px; font-size:14px; }
  .cert { border:1px solid var(--line); border-radius:6px; padding:8px; margin-bottom:8px; background:#fafcfe; }
  .cert .path { color:#c0392b; word-break:break-all; }
  .kv { margin:3px 0; word-break:break-all; line-height:1.55; }
  .kv b { color:#356fa8; }
  .ev { border-top:1px dashed var(--line); padding:7px 0; line-height:1.5; }
  .risk-section { background:#fff; border-top:1px solid var(--line); padding:14px 20px 20px; }
  .lineage-section { background:#fff; border-top:1px solid var(--line); padding:14px 20px 18px; }
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
  .lineage-empty { color:var(--muted); font-size:12px; }
  .risk-head { display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin-bottom:10px; }
  .risk-head h2 { margin:0 0 3px; font-size:15px; }
  .risk-head p { margin:0; color:var(--muted); font-size:12px; }
  .risk-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(270px,1fr)); gap:10px; }
  .risk-card { background:#fff; border:1px solid var(--line); border-left-width:4px; border-radius:8px; padding:9px 11px; cursor:pointer; text-align:left; font:inherit; }
  .risk-card:hover { box-shadow:0 4px 12px rgba(15,23,42,.08); }
  .risk-card .name { font-weight:700; font-size:12px; color:#253044; word-break:break-all; }
  .risk-card .meta { margin-top:4px; color:var(--muted); font-size:11px; line-height:1.5; }
  .fixture-note { margin-top:6px; color:#a15c00; font-size:11px; }
  .empty { border:1px dashed #cbd5e1; border-radius:8px; padding:10px 12px; color:var(--muted); font-size:12px; }
  @media (min-width:1320px) and (max-width:1549px) {
  }
  @media (max-width:1100px) {
    .main { grid-template-columns:1fr; }
    .mid { border-left:0; border-top:1px solid var(--line); max-height:260px; }
    .stats { display:none; }
  }
  @media (max-width:700px) {
    .snapshot-tabs { padding:8px 12px; }
    .snapshot-tab { flex:1; padding:8px 6px; }
    .snapshot-tab .hint { display:none; }
    .chart-shell { overflow-x:auto; overflow-y:hidden; }
    .chart { min-width:680px; }
  }
</style>
</head>
<body>
<div class="header">
  <div><h1>{{TITLE}}</h1><div class="sub">t0/t1 固定坐标 · 上游在上 · 箭头指向来源模型 · 点击节点查看证据</div></div>
  <div class="stats">t0：{{N0}} 节点 / {{E0}} 边 · t1：{{N1}} 节点 / {{E1}} 边 · 变更事件 {{NE}} · 路径证书 {{NC}}</div>
</div>
<div class="legend-row">
  <span><i style="background:#f56c6c"></i>高风险</span>
  <span><i style="background:#e6a23c"></i>潜在风险</span>
  <span><i style="background:#67c23a"></i>安全</span>
  <span><i style="background:#d3d7de"></i>待确认</span>
  <span><i class="line" style="background:#8794a6"></i>实线箭头 = 下游派生自上游</span>
  <span><i class="line" style="background:#c0392b"></i>红色箭头 = 风险传播路径</span>
  <span id="legend-aggregate" hidden><i style="background:#eef0f4;border:2px solid #f56c6c"></i>聚合域仅表示范围，不是血缘</span>
</div>
<div id="ai-status-strip" class="ai-status-strip">正在读取 AI 语义证据状态…</div>
<div class="snapshot-tabs" role="tablist" aria-label="快照选择">
  <button type="button" class="snapshot-tab is-active" data-snapshot="t1" role="tab" aria-selected="true">t1 当前<span class="hint">{{N1}} 节点 / {{E1}} 边</span></button>
  <button type="button" class="snapshot-tab" data-snapshot="t0" role="tab" aria-selected="false">t0 基线<span class="hint">{{N0}} 节点 / {{E0}} 边</span></button>
</div>
<div class="main">
  <section class="stage">
    <div class="stage-title">上游血缘与风险传播图 <span id="stage-hint">越靠上越上游；同一模型在 t0/t1 保持相同坐标</span></div>
    <div class="chart-shell">
      <div id="chart0" class="chart chart-page" role="tabpanel" hidden></div>
      <div id="chart1" class="chart chart-page" role="tabpanel"></div>
    </div>
  </section>
  <aside class="mid">
    <div class="ai-diff-block">
      <h3>AI 语义差异（C 级）</h3>
      <div id="ai-diff-list"></div>
    </div>
    <h3>变更事件（点击查看传播证书）</h3>
    <div id="evt-list"></div>
  </aside>
</div>
<div id="panel"><h3>证据、传播路径与能力边界</h3><div id="panel-body" style="color:#7b8799">点击图中节点或变更事件查看详情。</div></div>
<section class="lineage-section">
  <h2>项目模型与上游来源路径</h2>
  <p>箭头方向是“下游模型 → 上游来源”。这里把 t1 的路径展开成文字，避免只靠连线猜基座关系；风险变化不会改变路径。</p>
  <div id="lineage-forest" class="lineage-forest"></div>
</section>
<section class="risk-section">
  <div class="risk-head">
    <div><h2>已识别的具体风险模型</h2><p>只列具有具体模型身份的节点；聚合域只作为范围显示，不把聚合计数伪装成模型名称。</p></div>
    <div id="risk-count" style="font-size:12px;color:#64748b"></div>
  </div>
  <div id="risk-grid" class="risk-grid"></div>
  <div id="risk-empty" class="empty" hidden></div>
</section>
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
const DECISION_RANK = {{DECISION_RANK_JSON}};
const CHANGE_LABEL = {{CHANGE_LABEL_JSON}};
const REPORT_MARKDOWN = {{REPORT_MARKDOWN_JSON}};

function escapeHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}
function modelscopeModelPageUrl(raw) {
  if (!raw || raw.asset_type !== "model") return null;
  if (raw.aggregate === true || raw.coverage_status === "AGGREGATE_ONLY") return null;
  const canonical = String(raw.canonical_id || "");
  if (canonical.includes(":son:") || canonical.includes(":parent:")) return null;
  const canonicalPrefix = "model:modelscope/";
  let modelId = canonical.startsWith(canonicalPrefix)
    ? canonical.slice(canonicalPrefix.length).split("@")[0]
    : "";
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
  const labels = {base:"基础",license_file:"LICENSE 文件",readme:"README 文件",structured_file:"结构化文件",exact_quote:"原文精确命中",restriction_wording:"限制措辞",source_sha256:"SHA256",quote_context:"引文长度",uncertain_state:"不确定性",cross_document_support:"跨文档支持"};
  return Object.entries(claim.confidence_factors || {}).map(([key, value]) => {
    const number = Number(value);
    return `${labels[key] || key} ${number >= 0 ? "+" : ""}${number.toFixed(2)}`;
  }).join(" · ");
}
function aiTooltip(n) {
  const ai = aiAnalysis(n);
  if (!ai) return "";
  const first = (ai.claims || [])[0];
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
        `<div class="ai-meta">置信度构成：${escapeHtml(confidenceFactorText(claim) || "—")}</div>` +
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
  return {code, color:DECISION_COLOR[code] || "#d3d7de", label:DECISION_LABEL[code] || code};
}
function isAgg(n) {
  if (n.aggregate === true || n.coverage_status === "AGGREGATE_ONLY") return true;
  if ((n.canonical_id || n.entity_key || "").includes(":son:") ||
      (n.canonical_id || n.entity_key || "").includes(":parent:")) return true;
  return (n.name || "").includes("(Total:") && !(n.purls || []).length;
}
function isFixtureNode(n) {
  // 只认显式声明：名称长得像夹具的真实模型不该被标成构造夹具。
  return !!n && (n.is_fixture === true || n.display_only === true);
}
function aggTotal(n) {
  if (Number.isInteger(n.count)) return n.count;
  const match = String(n.name || "").match(/\\(Total:\\s*(\\d+)\\)/i);
  return match ? Number(match[1]) : 0;
}
function aggLabel(n) {
  if (n.render_card && n.render_card.label) return n.render_card.label;
  const name = n.name || n.canonical_id || "聚合域";
  return (name.includes(" · ") ? name.split(" · ").pop() : name).replace(/\\(Total:\\s*\\d+\\)/i, "").trim();
}
function aggTone(n) {
  const tone = n.render_tone || "NEUTRAL";
  return tone === "NEUTRAL" ? "#aeb8c7" : (DECISION_COLOR[tone] || "#aeb8c7");
}
function isExpandedChild(n) {
  return n.render_role === "expanded_child";
}
function decisionShort(code) {
  return {RISK_CONFIRMED:"高风险",RISK_POTENTIAL:"潜在风险",SAFE:"安全",UNDETERMINED:"待确认"}[code || "UNDETERMINED"] || "待确认";
}
function childFill(code) {
  return {RISK_CONFIRMED:"#fff2f0",RISK_POTENTIAL:"#fff8e8",SAFE:"#f0f9eb",UNDETERMINED:"#f6f7f9"}[code || "UNDETERMINED"] || "#f6f7f9";
}
// 展开状态按快照隔离：在 t0 展开聚合域不应把 t1 的同一聚合域一起展开。
const expandedBySnapshot = {t0:new Set(), t1:new Set()};
function expandedSet(snapshot) {
  const key = snapshot === "t0" ? "t0" : "t1";
  if (!expandedBySnapshot[key]) expandedBySnapshot[key] = new Set();
  return expandedBySnapshot[key];
}

function buildChart(elId, nodes, edges, layout, snapshot) {
  const expandedDomains = expandedSet(snapshot);
  const nodeById = {};
  nodes.forEach(n => nodeById[n.id] = n);
  const childrenByAggregate = {};
  edges.forEach(e => {
    if (e.edge_type !== "expanded_from") return;
    const aggregateId = isAgg(nodeById[e.source] || {}) ? e.source : e.target;
    if (!childrenByAggregate[aggregateId]) childrenByAggregate[aggregateId] = [];
    childrenByAggregate[aggregateId].push(e);
  });
  function makeData() {
    return nodes.map(n => {
    const agg = isAgg(n);
    const j = decisionOf(n.decision);
    const sourceNote = n.decision_source === "diff_propagation" ? "（diff 传播）" : "";
    if (isExpandedChild(n)) {
      const label = n.render_card?.label || n.name || n.id;
      const visible = expandedDomains.has(n.render_parent_id);
      return {
        id:n.id,
        name:label,
        x:n.x,
        y:n.y,
        symbol:"rect",
        symbolSize:visible ? [n.render_card?.width || 64, n.render_card?.height || 38] : [0, 0],
        itemStyle:{color:childFill(n.decision),borderColor:j.color,borderWidth:2,borderRadius:6,opacity:visible ? 1 : 0},
        label:{
          show:visible,
          position:"inside",
          formatter:() => `{name|${label}}\n{state|${decisionShort(n.decision)}}`,
          rich:{name:{fontSize:9,fontWeight:"bold",color:"#253044",lineHeight:14},state:{fontSize:8,color:j.color,lineHeight:13}}
        },
        tooltip:{show:visible,formatter:() => `<b>${escapeHtml(n.name || label)}</b><br/>展开的风险子节点<br/>许可证：${escapeHtml(n.license || "未声明")}<br/>判定：${j.label}${sourceNote}${isFixtureNode(n) ? "<br/>构造测试夹具，不代表真实下游模型" : ""}${aiTooltip(n)}`},
        _raw:n,
        _childParent:n.render_parent_id,
        silent:!visible,
        z:visible ? 5 : 0
      };
    }
    if (agg) {
      const counts = n.render_risk_counts || n.known_risk_counts || {red:0,yellow:0,gray:0};
      const label = aggLabel(n);
      const childCount = (childrenByAggregate[n.id] || []).length;
      const expanded = childCount > 0 && expandedDomains.has(n.id);
      const action = childCount ? `点击${expanded ? "收起" : "展开"} ${childCount} 个模型` : "聚合范围";
      return {
        id:n.id,
        name:label,
        x:n.x,
        y:n.y,
        symbol:"rect",
        symbolSize:[n.render_card?.width || 154, n.render_card?.height || 64],
        itemStyle:{color:"#eef0f4",borderColor:aggTone(n),borderWidth:2,borderRadius:9},
        label:{
          show:true,
          position:"inside",
          formatter:() => `{title|${label}}\n{meta|下游 ${aggTotal(n)} · 红${counts.red} 黄${counts.yellow} 灰${counts.gray}}\n{action|${action}}`,
          rich:{title:{fontSize:12,fontWeight:"bold",color:"#253044",lineHeight:17},meta:{fontSize:9,color:"#64748b",lineHeight:14},action:{fontSize:8,color:childCount ? "#2d6da3" : "#94a3b8",lineHeight:12}}
        },
        tooltip:{formatter:() => `<b>${escapeHtml(label)}</b><br/>聚合风险域<br/>下游总量：${aggTotal(n)}<br/>已知：红 ${counts.red} / 黄 ${counts.yellow} / 灰 ${counts.gray}${childCount ? `<br/>点击${expanded ? "收起" : "展开"} ${childCount} 个具体模型` : ""}${sourceNote}`},
        _raw:n,
        _childCount:childCount,
        cursor:childCount ? "pointer" : "default",
        z:2
      };
    }
    const card = n.render_card || {};
    const role = n.render_role_short || n.render_role_label || (n.lineage_role === "root" ? "项目直接使用" : "上游模型");
    const aiTag = aiAnalysis(n) ? " · AI" : "";
    if (card.width) {
      return {
        id:n.id,
        name:n.name || n.id,
        x:n.x,
        y:n.y,
        symbol:"rect",
        symbolSize:[card.width,card.height],
        itemStyle:{
          color:childFill(n.decision),borderColor:j.color,
          borderWidth:["RISK_CONFIRMED","RISK_POTENTIAL"].includes(n.decision) ? 2.5 : 1.8,
          borderRadius:8,
          shadowBlur:["RISK_CONFIRMED","RISK_POTENTIAL"].includes(n.decision) ? 6 : 0,
          shadowColor:"rgba(15,23,42,.12)"
        },
        label:{
          show:true,position:"inside",
          formatter:() => `{name|${card.label || n.name || n.id}}\n{role|${role}${aiTag}}`,
          rich:{
            name:{fontSize:card.width < 145 ? 8 : 9,fontWeight:"bold",color:"#253044",lineHeight:14,width:card.width - 16,overflow:"truncate"},
            role:{fontSize:7,color:aiAnalysis(n) ? "#0369a1" : j.color,lineHeight:12}
          }
        },
        tooltip:{formatter:() => `<b>${escapeHtml(n.name || n.id)}</b><br/>角色：${escapeHtml(role)}<br/>许可证：${escapeHtml(n.license || "未声明")}<br/>判定：${j.label}${sourceNote}${aiTooltip(n)}`},
        _raw:n,
        z:4
      };
    }
    return {
      id:n.id,
      name:n.name || n.id,
      x:n.x,
      y:n.y,
      symbol:n.asset_type === "dataset" ? "diamond" : "circle",
      symbolSize:n.asset_type === "dataset" ? 28 : 32,
      itemStyle:{color:j.color,borderColor:j.color === "#d3d7de" ? "#abb4c2" : j.color,borderWidth:1.5},
      label:{show:true,formatter:() => n.name || n.id,fontSize:9,color:"#334155",position:n.lp || "bottom"},
      tooltip:{formatter:() => `<b>${escapeHtml(n.name || n.id)}</b><br/>角色：${escapeHtml(role)}<br/>版本：${escapeHtml(n.version || "—")}<br/>许可证：${escapeHtml(n.license || "未声明")}<br/>判定：${j.label}${sourceNote}${aiTooltip(n)}`},
      _raw:n,
      z:4
    };
  });
  }

  function makeLinks() {
    return edges.map(e => {
      const source = nodeById[e.source] || {};
      const target = nodeById[e.target] || {};
      // Grouping is shown by card containment, never as a lineage edge.
      if (e.edge_type === "expanded_from" || isAgg(source) || isAgg(target)) return null;
      const risky = ["RISK_CONFIRMED","RISK_POTENTIAL"].includes(source.decision) ||
        ["RISK_CONFIRMED","RISK_POTENTIAL"].includes(target.decision);
      return {
        source:e.source,
        target:e.target,
        label:{show:false},
        emphasis:{label:{show:true,formatter:e.render_label || e.edge_type || "派生自",fontSize:9,color:risky ? "#c0392b" : "#475569"}},
        lineStyle:{width:risky ? 3 : 1.4,color:risky ? "#c0392b" : "#8794a6",type:"solid",curveness:0.03,opacity:risky ? 0.92 : 0.72},
        _edge:e
      };
  }).filter(Boolean);
  }
  const graphics = (layout?.clusters || []).map(c => {
    const lineageLayer = c.kind === "lineage_layer";
    const subtitle = c.subtitle || `聚合域 ${c.aggregate_count} 个${c.expanded_count ? " · 点击展开" : ""}`;
    return {
      type:"group",left:c.x,top:c.y,z:-1,silent:true,
      children:[
        {type:"rect",shape:{x:0,y:0,width:c.width,height:c.height,r:12},style:{fill:lineageLayer ? "#f8fafc" : "#fbfcfe",stroke:lineageLayer ? "#e5eaf1" : "#dfe7f1",lineWidth:1}},
        {type:"text",style:{x:14,y:20,text:c.title,fill:"#253044",font:"bold 12px Microsoft YaHei"}},
        {type:"text",style:{x:14,y:38,text:subtitle,fill:"#7b8799",font:"10px Microsoft YaHei"}}
      ]
    };
  });
  const chart = echarts.init(document.getElementById(elId));
  chart._refreshExpansion = () => chart.setOption({
    tooltip:{trigger:"item",backgroundColor:"#fff",borderColor:"#d0d7de",textStyle:{color:"#334155",fontSize:12}},
    legend:{show:false},
    graphic:graphics,
    series:[{
      type:"graph",
      layout:"none",
      roam:true,
      draggable:false,
      zoom:0.95,
      scaleLimit:{min:0.55,max:2.5},
      edgeSymbol:["none","arrow"],
      edgeSymbolSize:[0,11],
      data:makeData(),
      links:makeLinks(),
      emphasis:{focus:"adjacency",lineStyle:{width:5}},
      labelLayout:{hideOverlap:false}
    }]
  }, true);
  chart._refreshExpansion();
  return chart;
}

function shortName(id) {
  const all = {};
  DATA.nodes_t0.concat(DATA.nodes_t1).forEach(n => all[n.id] = n);
  const n = all[id];
  if (!n) return id;
  return isAgg(n) ? aggLabel(n) : (n.name || id);
}

function renderCerts(eventId, seed) {
  const certs = DATA.certificates.filter(c => c.event_id === eventId || c.seed === seed);
  if (!certs.length) {
    document.getElementById("panel-body").innerHTML = "<div style='color:#7b8799'>该事件无传播证书（无受影响下游）。</div>";
    return;
  }
  document.getElementById("panel-body").innerHTML = certs.map(c => {
    const steps = (c.path || []).map(s => escapeHtml(shortName(s.source)) + " → " + escapeHtml(shortName(s.target))).join(" → ");
    const chain = `${escapeHtml(shortName(c.affected))} ⇠ ${steps ? steps + " ⇠ " : ""}${escapeHtml(shortName(c.seed))}`;
    return `<div class="cert"><div class="kv"><b>证书</b> ${escapeHtml(c.certificate_id)} · ${escapeHtml(c.change_type)}</div>` +
      `<div class="kv"><b>受影响资产</b> ${escapeHtml(shortName(c.affected))}</div>` +
      `<div class="kv"><b>传播链（受影响 ⇠ … ⇠ 上游变化资产）</b><div class="path">${chain}</div></div>` +
      `<div class="kv"><b>跳数</b> ${escapeHtml(c.hop_count)} · <b>最弱证据</b> ${escapeHtml(c.weakest_evidence)} · <b>判定</b> ${decisionOf(c.decision).label}</div>` +
      `<div class="kv"><b>终止原因</b> ${escapeHtml(c.termination || "—")}</div></div>`;
  }).join("");
}

function renderNodeDetail(raw, snapshot) {
  const pageUrl = modelscopeModelPageUrl(raw);
  const pageLink = pageUrl
    ? `<div class="kv"><b>ModelScope 模型主页</b> <a href="${escapeHtml(pageUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(pageUrl)}</a></div>`
    : "";
  const agg = isAgg(raw);
  const j = decisionOf(raw.decision);
  const counts = raw.render_risk_counts || raw.known_risk_counts || {red:0,yellow:0,gray:0};
  const fixture = isFixtureNode(raw);
  let html = `<div class="kv"><b>快照</b> ${escapeHtml(snapshot || raw.snapshot_id || "—")}</div>` +
    `<div class="kv"><b>名称</b> ${escapeHtml(raw.name || raw.canonical_id || raw.id)}</div>` +
    `<div class="kv"><b>节点类型</b> ${agg ? "聚合风险域（非具体模型）" : escapeHtml(raw.asset_type || "—")}</div>` +
    `<div class="kv"><b>许可证</b> ${escapeHtml(raw.license || "未声明")}</div>` +
    `<div class="kv"><b>判定</b> ${j.label}${raw.decision_source === "diff_propagation" ? "（diff 传播）" : ""}</div>`;
  if (agg) {
    html += `<div class="kv"><b>下游总量</b> ${aggTotal(raw)}</div>` +
      `<div class="kv"><b>已知风险</b> 红 ${counts.red} / 黄 ${counts.yellow} / 灰 ${counts.gray}</div>` +
      `<div class="kv"><b>能力边界</b> ModelScope 血缘接口只返回类型与总数；除非数据源返回具体身份，否则不能把计数写成模型名。</div>`;
  } else {
    html += `<div class="kv"><b>判定来源</b> ${escapeHtml(raw.decision_source || "自身许可证评估")}</div>`;
    if (fixture) {
      html += `<div class="fixture-note">构造测试夹具：该名称用于验证展开与着色逻辑，不代表 ModelScope API 已返回这个真实下游模型。</div>`;
    }
  }
  let evidence = (raw.evidence_chain || []).map(e => {
    const sourceUrl = String(e.source_url || "").trim();
    const sourceLink = sourceUrl
      ? `<br/><a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">原始 API 证据：${escapeHtml(sourceUrl)}</a>`
      : `<br/><span class="evidence-missing">原始 API 证据：未提供</span>`;
    return `<div class="ev"><b>证据 ${escapeHtml(e.evidence_level || "—")}</b> · ${escapeHtml(e.source_api || "")}<br/>字段：${escapeHtml(e.source_field || "—")}${sourceLink}</div>`;
  }).join("") || `<div class="ev">无证据链</div>`;
  evidence = (pageLink || "") + evidence;
  document.getElementById("panel-body").innerHTML = html + renderAiDetails(raw) + evidence;
}

function renderEdgeDetail(edge) {
  document.getElementById("panel-body").innerHTML =
    `<div class="kv"><b>关系类型</b> ${escapeHtml(edge.edge_type || "—")}</div>` +
    `<div class="kv"><b>下游/派生方</b> ${escapeHtml(shortName(edge.source))}</div>` +
    `<div class="kv"><b>上游/来源方</b> ${escapeHtml(shortName(edge.target))}</div>` +
    `<div class="kv"><b>方向</b> ${edge.edge_type === "expanded_from" ? "聚合成员归属，不是血缘" : "箭头指向更上游的来源模型"}</div>` +
    `<div class="kv"><b>语义</b> ${edge.edge_type === "expanded_from" ? "聚合域展开归属，不参与风险传播" : "下游模型派生自上游模型"}</div>`;
}

const aiDiffList = document.getElementById("ai-diff-list");
const aiStatusStrip = document.getElementById("ai-status-strip");
const aiChanges = (DATA.ai_diff && DATA.ai_diff.changes) || [];
if (DATA.ai_diff && DATA.ai_diff.ai_available === false) {
  aiStatusStrip.innerHTML = "<b>AI 状态：未固化条款画像</b> · 本次仅运行规则与传播链；不是图谱渲染失败";
  aiDiffList.innerHTML = `<div class="empty">本次快照生成时未传入 AI 服务，因此没有模型卡或 LICENSE 的 C 级语义画像。AI 不会用当前时间重新猜测许可证含义。</div>`;
} else if (!aiChanges.length) {
  aiStatusStrip.innerHTML = "<b>AI 状态：已读取冻结画像</b> · 未发现可验证的语义变化，仍需人工复核 C 级证据";
  aiDiffList.innerHTML = `<div class="empty">AI 画像已读取，未发现可验证的语义变化；规则 Delta 不受影响。</div>`;
} else {
  aiStatusStrip.innerHTML = `<b>AI 状态：发现 ${aiChanges.length} 项语义差异</b> · 证据等级 C，只提示人工复核，不改变风险灯色`;
  if (DATA.ai_diff && DATA.ai_diff.simulation) {
    aiStatusStrip.innerHTML += " · 验收模拟差异，不代表真实世界许可证已变更";
  }
  aiChanges.forEach(change => {
    const item = document.createElement("div");
    item.className = "ai-diff";
    const confidence = `${change.before_confidence ?? "—"} → ${change.after_confidence ?? "—"}`;
    const sourcePath = change.after_source_path || "—";
    item.innerHTML = `<div class="route">${escapeHtml(change.model_id)} · ${escapeHtml(change.dimension_zh || change.dimension)}</div>` +
      `<div>${escapeHtml(change.before_state_zh || change.before_state)} → ${escapeHtml(change.after_state_zh || change.after_state)}</div>` +
      `<div class="meta">复核优先级 ${escapeHtml(change.review_priority)} · AI 置信度 ${escapeHtml(confidence)} · C 级 · 待人工确认</div>` +
      `<div class="meta">t1 证据来源 ${escapeHtml(sourcePath)} · 原文 SHA256 ${escapeHtml(change.after_quote_sha256 || "—")}</div>` +
      `<div class="ai-quote">旧：${escapeHtml(change.before_quote || "—")}<br/>新：${escapeHtml(change.after_quote || "—")}</div>`;
    aiDiffList.appendChild(item);
  });
}

const evtDiv = document.getElementById("evt-list");
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
    link.download = "diff_report.md";
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

const aggregateLegend = document.getElementById("legend-aggregate");
if (aggregateLegend) aggregateLegend.hidden = !DATA.nodes_t0.concat(DATA.nodes_t1).some(isAgg);

function renderLineageForest() {
  const host = document.getElementById("lineage-forest");
  if (!host) return;
  const byId = {};
  DATA.nodes_t1.forEach(n => byId[n.id] = n);
  const upstream = {};
  DATA.edges_t1.forEach(e => {
    if (e.edge_type === "expanded_from") return;
    if (!upstream[e.source]) upstream[e.source] = [];
    if (byId[e.target]) upstream[e.source].push(e.target);
  });
  let roots = DATA.nodes_t1.filter(n => !isAgg(n) && (n.lineage_role === "root" || n.lineage_depth === 0));
  if (!roots.length) roots = DATA.nodes_t1.filter(n => !isAgg(n));
  if (!roots.length) {
    host.innerHTML = `<div class="lineage-empty">当前快照没有具体模型节点。</div>`;
    return;
  }
  function branch(nodeId, seen, depth) {
    if (depth > 12 || seen.has(nodeId)) return `<li><span class="arrow">↺</span>${escapeHtml(shortName(nodeId))} <span class="role">循环引用，已停止</span></li>`;
    const nextSeen = new Set(seen);
    nextSeen.add(nodeId);
    return (upstream[nodeId] || []).map(target => {
      const targetNode = byId[target] || {};
      const role = targetNode.render_role_label || targetNode.lineage_type_ch || targetNode.lineage_type || "上游来源";
      const license = targetNode.license || "未声明";
      const children = branch(target, nextSeen, depth + 1);
      return `<li><span class="arrow">↑</span><b>${escapeHtml(shortName(target))}</b> <span class="role">${escapeHtml(role)} · ${escapeHtml(license)}</span>${children ? `<ul>${children}</ul>` : ""}</li>`;
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

DATA.events.forEach(ev => {
  const j = decisionOf(ev.decision);
  const d = document.createElement("div");
  d.className = "evt";
  const fromName = shortName(ev.display_source || ev.source || ev.seed);
  const toName = shortName(ev.display_target || ev.target || ev.seed);
  const route = (fromName === toName)
    ? escapeHtml(fromName)
    : `${escapeHtml(fromName)} <span class="arrow">→</span> ${escapeHtml(toName)}`;
  d.innerHTML = `<span class="tag" style="background:${j.color}">${escapeHtml(CHANGE_LABEL[ev.change_type] || ev.change_type)}</span>` +
    `<div style="margin-top:4px">${route}</div>` +
    `<div style="color:#7b8799;margin-top:2px">判定：${j.label} · 证据 ${escapeHtml(ev.evidence_level || "—")}</div>`;
  d.onclick = () => renderCerts(ev.event_id, ev.seed);
  evtDiv.appendChild(d);
});

const charts = {t0:null, t1:null};
let activeSnapshot = "t1";

function createSnapshotChart(snapshot) {
  if (charts[snapshot]) return charts[snapshot];
  const suffix = snapshot === "t1" ? "t1" : "t0";
  const chart = buildChart(`chart${suffix.slice(1)}`, DATA[`nodes_${suffix}`], DATA[`edges_${suffix}`], DATA[`layout_${suffix}`], suffix);
  chart.on("click", p => {
    if (p.dataType === "node") {
      const raw = p.data._raw;
      renderNodeDetail(raw, snapshot);
      if (isAgg(raw) && Number(p.data._childCount || 0) > 0) {
        const expanded = expandedSet(snapshot);
        if (expanded.has(raw.id)) expanded.delete(raw.id);
        else expanded.add(raw.id);
        chart._refreshExpansion();
      }
      setTimeout(() => chart.dispatchAction({type:"downplay", seriesIndex:0}), 0);
    } else if (p.dataType === "edge") {
      renderEdgeDetail(p.data._edge);
    }
  });
  charts[snapshot] = chart;
  return chart;
}

function activateSnapshot(snapshot) {
  activeSnapshot = snapshot;
  document.querySelectorAll(".snapshot-tab").forEach(button => {
    const active = button.dataset.snapshot === snapshot;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.getElementById("chart0").hidden = snapshot !== "t0";
  document.getElementById("chart1").hidden = snapshot !== "t1";
  const chart = createSnapshotChart(snapshot);
  requestAnimationFrame(() => chart.resize());
}

document.querySelectorAll(".snapshot-tab").forEach(button => {
  button.addEventListener("click", () => activateSnapshot(button.dataset.snapshot));
});
activateSnapshot("t1");

const riskGrid = document.getElementById("risk-grid");
const riskEmpty = document.getElementById("risk-empty");
const riskCount = document.getElementById("risk-count");
const riskMap = new Map();
[["t0", DATA.nodes_t0], ["t1", DATA.nodes_t1]].forEach(([snapshot, nodes]) => {
  nodes.filter(n => !isAgg(n) && ["RISK_CONFIRMED","RISK_POTENTIAL"].includes(n.decision || "")).forEach(n => {
    const key = n.canonical_id || n.entity_key || n.id;
    const current = riskMap.get(key);
    if (!current || (DECISION_RANK[n.decision] || 0) > (DECISION_RANK[current.node.decision] || 0)) {
      riskMap.set(key, {node:n, snapshots:[snapshot]});
    } else if (!current.snapshots.includes(snapshot)) {
      current.snapshots.push(snapshot);
    }
  });
});
if (!riskMap.size) {
  riskEmpty.hidden = false;
  riskEmpty.textContent = "当前两张快照中没有具备具体模型身份的红/黄风险节点；这不代表聚合域内不存在风险，请结合聚合统计查看。";
  riskCount.textContent = "0 个具名风险模型";
} else {
  riskCount.textContent = `${riskMap.size} 个具名风险模型`;
  [...riskMap.values()].forEach(item => {
    const n = item.node;
    const j = decisionOf(n.decision);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "risk-card";
    button.style.borderLeftColor = j.color;
    button.innerHTML = `<div class="name">${escapeHtml(n.name || n.canonical_id)}</div>` +
      `<div class="meta">${j.label} · 许可证 ${escapeHtml(n.license || "未声明")} · 快照 ${item.snapshots.join("/")}${aiAnalysis(n) ? ` · AI ${(aiAnalysis(n).claims || []).length} 条待确认` : ""}</div>` +
      `${isFixtureNode(n) ? `<div class="fixture-note">构造测试夹具，不代表真实下游模型</div>` : ""}`;
    button.onclick = () => {
      renderNodeDetail(n, item.snapshots.join("/"));
      const preferred = item.snapshots.includes("t1") ? "t1" : "t0";
      activateSnapshot(preferred);
      const chart = createSnapshotChart(preferred);
      const sourceNodes = preferred === "t1" ? DATA.nodes_t1 : DATA.nodes_t0;
      const index = sourceNodes.findIndex(node => node.id === n.id);
      if (isExpandedChild(n) && n.render_parent_id) {
        expandedSet(preferred).add(n.render_parent_id);
        chart._refreshExpansion();
      }
      chart.dispatchAction({type:"downplay", seriesIndex:0});
      if (index >= 0) chart.dispatchAction({type:"highlight", seriesIndex:0, dataIndex:index});
    };
    riskGrid.appendChild(button);
  });
}

window.addEventListener("resize", () => {
  Object.values(charts).forEach(chart => chart && chart.resize());
});
</script>
</body>
</html>
"""


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
    """Apply propagated decisions to t1 only.

    ``nodes_t0`` is kept in the signature for API compatibility, but a t0
    baseline must retain the decision persisted in its own BOM. A t0 to t1
    delta describes the after state and must not rewrite the baseline.
    """

    event_decisions = _collect_event_decisions(events, certificates)
    for node in nodes_t1:
        if is_aggregate_node(node):
            continue
        node_id = node.get("id") or node.get("canonical_id") or node.get("entity_key")
        event_decision = event_decisions.get(node_id)
        if not event_decision:
            continue
        if _decision_rank(event_decision) > _decision_rank(node.get("decision")):
            node["decision"] = event_decision
            node["decision_source"] = "diff_propagation"


def annotate_event_endpoints(
    events: list[dict], certificates: list[dict]
) -> list[dict]:
    """为事件列表补上真正要显示的起止资产。

    传播生成的事件只带 ``seed`` 与 ``path``，没有 ``source`` / ``target``，
    直接回退到 ``seed`` 会让中栏五条记录全部显示成"种子 → 种子"。受影响下游
    资产在对应路径证书的 ``affected`` 上；没有证书时取 ``path[0].source``
    （路径方向是 受影响资产 → … → 上游变化资产）。
    """

    affected_by_event: dict[str, str] = {}
    for certificate in certificates:
        event_id = certificate.get("event_id")
        affected = certificate.get("affected")
        if event_id and affected and event_id not in affected_by_event:
            affected_by_event[event_id] = affected

    for event in events:
        target = affected_by_event.get(event.get("event_id") or "")
        if not target:
            path = event.get("path") or []
            if path:
                target = path[0].get("source")
        event["display_source"] = event.get("source") or event.get("seed")
        event["display_target"] = (
            target
            or event.get("target")
            or event.get("source")
            or event.get("seed")
        )
    return events


def _stable_node_key(node: dict) -> str:
    """Return the identity shared by t0/t1 snapshots."""
    return str(
        node.get("canonical_id")
        or node.get("entity_key")
        or node.get("id")
        or node.get("name")
        or ""
    )


def synchronize_diff_layouts(
    nodes_t0: list[dict],
    edges_t0: list[dict],
    nodes_t1: list[dict],
    edges_t1: list[dict],
    *,
    canvas_width: int = 1280,
) -> dict:
    """Lay out both snapshots in one coordinate space.

    A risk decision changes colour, never position. Nodes that exist in only
    one snapshot reserve their slot in the union layout, so t0 and t1 remain
    directly comparable and added/removed nodes do not shift every other card.
    """
    by_key: dict[str, dict] = {}
    id_to_key: dict[str, str] = {}
    for node in [*nodes_t0, *nodes_t1]:
        key = _stable_node_key(node)
        if not key:
            continue
        id_to_key[str(node.get("id") or key)] = key
        if key not in by_key:
            layout_node = copy.deepcopy(node)
            layout_node["id"] = key
            by_key[key] = layout_node
        else:
            for field, value in node.items():
                by_key[key].setdefault(field, value)

    union_nodes = list(by_key.values())
    seen_edges: set[tuple[str, str, str]] = set()
    union_edges: list[dict] = []
    for edge in [*edges_t0, *edges_t1]:
        source = id_to_key.get(str(edge.get("source")), str(edge.get("source") or ""))
        target = id_to_key.get(str(edge.get("target")), str(edge.get("target") or ""))
        edge_type = str(edge.get("edge_type") or "")
        signature = (source, target, edge_type)
        if source not in by_key or target not in by_key or source == target or signature in seen_edges:
            continue
        seen_edges.add(signature)
        union_edge = copy.deepcopy(edge)
        union_edge["source"] = source
        union_edge["target"] = target
        union_edges.append(union_edge)

    layout = layout_graph(
        union_nodes,
        union_edges,
        canvas_width=canvas_width,
        stable_order=True,
    )
    coordinate_fields = (
        "x", "y", "lp", "render_layer", "render_role_label", "render_role_short", "render_card",
        "render_risk_counts", "render_tone", "render_role", "render_parent_id",
    )
    for node in [*nodes_t0, *nodes_t1]:
        source = by_key.get(_stable_node_key(node))
        if not source:
            continue
        for field in coordinate_fields:
            if field in source:
                node[field] = copy.deepcopy(source[field])
    return layout


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
    parser = argparse.ArgumentParser(description="开源账本 --diff 时间轴风险传播图渲染器")
    parser.add_argument("--before", required=True, type=Path, help="t0 BOM（CycloneDX，含 pedigree.ancestors）")
    parser.add_argument("--after", required=True, type=Path, help="t1 BOM")
    parser.add_argument("--output", required=True, type=Path, help="输出 HTML 路径")
    parser.add_argument("--report", type=Path, default=None, help="可选：Markdown 审计报告路径，嵌入页面供预览和下载")
    parser.add_argument("--title", default=None, help="页面标题（默认自动）")
    parser.add_argument(
        "--include-fixtures",
        action="store_true",
        help="演示模式：保留 is_fixture / display_only 标记的演示夹具。"
        "默认按生产模式处理，把夹具从 Delta 与风险传播中排除。",
    )
    args = parser.parse_args()

    from main import _build_snapshot
    from main import _ai_model_analyses_from_assets

    include_fixtures = bool(getattr(args, "include_fixtures", False))
    before = _build_snapshot(args.before, "t0", include_fixtures=include_fixtures)
    after = _build_snapshot(args.after, "t1", include_fixtures=include_fixtures)
    ai_diff = semantic_diff(
        _ai_model_analyses_from_assets(before["assets"]),
        _ai_model_analyses_from_assets(after["assets"]),
    )

    operational_before_nodes, operational_before_edges = operational_snapshot(
        before["assets"], before["edges"], include_fixtures=include_fixtures
    )
    operational_after_nodes, operational_after_edges = operational_snapshot(
        after["assets"], after["edges"], include_fixtures=include_fixtures
    )

    graph_before = build_graph.build_graph(
        operational_before_nodes, operational_before_edges
    )
    graph_after = build_graph.build_graph(
        operational_after_nodes, operational_after_edges
    )

    events = delta_engine.detect_delta(
        operational_before_nodes,
        operational_after_nodes,
        operational_before_edges,
        operational_after_edges,
    )
    propagated = propagation_engine.propagate(events, graph_before, graph_after)
    certs = propagated["path_certificates"]

    nodes_t0, edges_t0 = list(before["assets"]), list(before["edges"])
    nodes_t1, edges_t1 = list(after["assets"]), list(after["edges"])
    for node in nodes_t0 + nodes_t1:
        node["id"] = (
            node.get("id")
            or node.get("canonical_id")
            or node.get("entity_key")
            or node.get("name")
        )
    apply_event_decisions(nodes_t0, nodes_t1, propagated["events"], certs)
    annotate_event_endpoints(propagated["events"], certs)
    shared_layout = synchronize_diff_layouts(
        nodes_t0, edges_t0, nodes_t1, edges_t1, canvas_width=1280
    )
    # The two snapshots intentionally share one coordinate space. A colour or
    # decision change must never make the reader think the graph itself moved.
    layout_t0 = shared_layout
    layout_t1 = shared_layout

    data = {
        "nodes_t0": nodes_t0,
        "edges_t0": edges_t0,
        "layout_t0": layout_t0,
        "nodes_t1": nodes_t1,
        "edges_t1": edges_t1,
        "layout_t1": layout_t1,
        "events": propagated["events"],
        "certificates": certs,
        "ai_diff": ai_diff,
    }
    title = args.title or (
        "%s → %s 血缘风险传播" % (args.before.stem, args.after.stem)
    )
    chart_height = max(620, layout_t0["height"], layout_t1["height"])
    report_markdown = ""
    if args.report is not None:
        if not args.report.exists():
            raise FileNotFoundError(f"report not found: {args.report}")
        report_markdown = args.report.read_text(encoding="utf-8")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    echarts_src = _copy_echarts(args.output.parent)

    html = TPL
    replacements = {
        "{{TITLE}}": title,
        "{{N0}}": str(len(nodes_t0)),
        "{{E0}}": str(len(edges_t0)),
        "{{N1}}": str(len(nodes_t1)),
        "{{E1}}": str(len(edges_t1)),
        "{{NE}}": str(len(events)),
        "{{NC}}": str(len(certs)),
        "{{DATA_JSON}}": json.dumps(data, ensure_ascii=False),
        "{{DECISION_COLOR_JSON}}": json.dumps(DECISION_COLOR, ensure_ascii=False),
        "{{DECISION_LABEL_JSON}}": json.dumps(DECISION_LABEL, ensure_ascii=False),
        "{{DECISION_RANK_JSON}}": json.dumps(DECISION_RANK, ensure_ascii=False),
        "{{CHANGE_LABEL_JSON}}": json.dumps(CHANGE_LABEL, ensure_ascii=False),
        "{{REPORT_MARKDOWN_JSON}}": json.dumps(report_markdown, ensure_ascii=False),
        "{{ECHARTS_SRC}}": echarts_src,
        "{{CHART_HEIGHT}}": str(chart_height),
    }
    for marker, value in replacements.items():
        html = html.replace(marker, value)
    args.output.write_text(html, encoding="utf-8")

    dist = Counter(event["decision"] for event in propagated["events"])
    print("已生成：%s" % args.output)
    print(
        "t0 %d 节点/%d 边 · t1 %d 节点/%d 边 · 变更事件 %d · 传播后事件 %d · 路径证书 %d"
        % (
            len(nodes_t0),
            len(edges_t0),
            len(nodes_t1),
            len(edges_t1),
            len(events),
            len(propagated["events"]),
            len(certs),
        )
    )
    print("判定分布：%s" % dict(dist))

if __name__ == "__main__":
    main()
