# -*- coding: utf-8 -*-
"""--diff 时间轴风险传播图渲染器：左 t0、右 t1，中间标变化事件。

用法：
  python render_diff.py --before data/test_scenarios/project_t0_bom.json \
      --after data/test_scenarios/project_t1_bom.json --output outputs/diff.html

链路与 main.py --diff 一致（只读 BOM 固化的血缘边，零在线请求）：
  _build_snapshot -> build_graph -> delta_engine.detect_delta -> propagation_engine.propagate
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

import build_graph
import delta_engine
import propagation_engine
from render_diff_operational import operational_snapshot
from render_layout import is_aggregate_node, layout_graph

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
  .chart-shell { overflow:hidden; }
  .chart-page[hidden] { display:none; }
  .chart { width:100%; height:{{CHART_HEIGHT}}px; }
  .mid { background:#fff; border-left:1px solid var(--line); padding:10px; font-size:12px; overflow-y:auto; max-height:{{CHART_HEIGHT}}px; }
  .mid h3 { margin:0 0 8px; font-size:13px; }
  .evt { border:1px solid var(--line); border-radius:6px; padding:7px 8px; margin-bottom:8px; cursor:pointer; background:#fafcfe; }
  .evt:hover { border-color:#409eff; }
  .evt .tag { display:inline-block; padding:1px 6px; border-radius:3px; color:#fff; font-size:10px; }
  .evt .arrow { color:#c0392b; font-weight:700; }
  #panel { padding:12px 20px; background:#fff; border-top:1px solid var(--line); font-size:12px; }
  #panel h3 { margin:0 0 8px; font-size:14px; }
  .cert { border:1px solid var(--line); border-radius:6px; padding:8px; margin-bottom:8px; background:#fafcfe; }
  .cert .path { color:#c0392b; word-break:break-all; }
  .kv { margin:3px 0; word-break:break-all; line-height:1.55; }
  .kv b { color:#356fa8; }
  .ev { border-top:1px dashed var(--line); padding:7px 0; line-height:1.5; }
  .risk-section { background:#fff; border-top:1px solid var(--line); padding:14px 20px 20px; }
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
  <div><h1>{{TITLE}}</h1><div class="sub">模型簇自适应布局 · 聚合域保持中性 · 点击节点或变更事件查看详情</div></div>
  <div class="stats">t0：{{N0}} 节点 / {{E0}} 边 · t1：{{N1}} 节点 / {{E1}} 边 · 变更事件 {{NE}} · 路径证书 {{NC}}</div>
</div>
<div class="legend-row">
  <span><i style="background:#f56c6c"></i>高风险</span>
  <span><i style="background:#e6a23c"></i>潜在风险</span>
  <span><i style="background:#67c23a"></i>安全</span>
  <span><i style="background:#d3d7de"></i>待确认</span>
  <span><i style="background:#eef0f4;border:2px solid #f56c6c"></i>中性聚合域 + 风险描边</span>
  <span><i class="line" style="background:#c0392b"></i>真实风险传播</span>
  <span><i class="line" style="background:#aeb8c7"></i>虚线 = 聚合归属，不参与传播</span>
</div>
<div class="snapshot-tabs" role="tablist" aria-label="快照选择">
  <button type="button" class="snapshot-tab is-active" data-snapshot="t1" role="tab" aria-selected="true">t1 当前<span class="hint">{{N1}} 节点 / {{E1}} 边</span></button>
  <button type="button" class="snapshot-tab" data-snapshot="t0" role="tab" aria-selected="false">t0 基线<span class="hint">{{N0}} 节点 / {{E0}} 边</span></button>
</div>
<div class="main">
  <section class="stage">
    <div class="stage-title">风险血缘图 <span id="stage-hint">聚合域默认折叠，点击风险域展开具体模型</span></div>
    <div class="chart-shell">
      <div id="chart0" class="chart chart-page" role="tabpanel" hidden></div>
      <div id="chart1" class="chart chart-page" role="tabpanel"></div>
    </div>
  </section>
  <aside class="mid">
    <h3>变更事件（点击查看传播证书）</h3>
    <div id="evt-list"></div>
  </aside>
</div>
<div id="panel"><h3>证据、传播路径与能力边界</h3><div id="panel-body" style="color:#7b8799">点击图中节点或变更事件查看详情。</div></div>
<section class="risk-section">
  <div class="risk-head">
    <div><h2>已识别的具体风险模型</h2><p>只列具有具体模型身份的节点；聚合域只作为范围显示，不把聚合计数伪装成模型名称。</p></div>
    <div id="risk-count" style="font-size:12px;color:#64748b"></div>
  </div>
  <div id="risk-grid" class="risk-grid"></div>
  <div id="risk-empty" class="empty" hidden></div>
</section>
<script>
const DATA = {{DATA_JSON}};
const DECISION_COLOR = {{DECISION_COLOR_JSON}};
const DECISION_LABEL = {{DECISION_LABEL_JSON}};
const DECISION_RANK = {{DECISION_RANK_JSON}};
const CHANGE_LABEL = {{CHANGE_LABEL_JSON}};

function escapeHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
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
        tooltip:{show:visible,formatter:() => `<b>${escapeHtml(n.name || label)}</b><br/>展开的风险子节点<br/>许可证：${escapeHtml(n.license || "未声明")}<br/>判定：${j.label}${sourceNote}${isFixtureNode(n) ? "<br/>构造测试夹具，不代表真实下游模型" : ""}`},
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
    return {
      id:n.id,
      name:n.name || n.id,
      x:n.x,
      y:n.y,
      symbol:n.asset_type === "dataset" ? "diamond" : "circle",
      symbolSize:n.asset_type === "dataset" ? 28 : 32,
      itemStyle:{color:j.color,borderColor:j.color === "#d3d7de" ? "#abb4c2" : j.color,borderWidth:1.5},
      label:{show:true,formatter:() => n.name || n.id,fontSize:9,color:"#334155",position:n.lp || "bottom"},
      tooltip:{formatter:() => `<b>${escapeHtml(n.name || n.id)}</b><br/>版本：${escapeHtml(n.version || "—")}<br/>许可证：${escapeHtml(n.license || "未声明")}<br/>判定：${j.label}${sourceNote}`},
      _raw:n,
      z:4
    };
  });
  }

  function makeLinks() {
    return edges.map(e => {
    const source = nodeById[e.source] || {};
    const target = nodeById[e.target] || {};
    const expansion = e.edge_type === "expanded_from";
    const aggregateId = expansion ? (isAgg(source) ? e.source : e.target) : null;
    if (aggregateId && !expandedDomains.has(aggregateId)) return null;
    const membership = expansion || isAgg(source) || isAgg(target);
    const risky = !membership && (
      ["RISK_CONFIRMED","RISK_POTENTIAL"].includes(source.decision) ||
      ["RISK_CONFIRMED","RISK_POTENTIAL"].includes(target.decision)
    );
    return {
      source:e.source,
      target:e.target,
      edgeSymbol:membership ? ["none","none"] : ["none","arrow"],
      edgeSymbolSize:[0,9],
      lineStyle:{width:risky ? 4 : (membership ? 1.2 : 1.5),color:risky ? "#c0392b" : (membership ? "#aeb8c7" : "#95a5a6"),type:membership ? "dashed" : "solid"},
      _edge:e
    };
  }).filter(Boolean);
  }
  const graphics = (layout?.clusters || []).map(c => ({
    type:"group",
    left:c.x,
    top:c.y,
    z:-1,
    silent:true,
    children:[
      {type:"rect",shape:{x:0,y:0,width:c.width,height:c.height,r:14},style:{fill:"#fbfcfe",stroke:"#dfe7f1",lineWidth:1}},
      {type:"text",style:{x:14,y:20,text:c.title,fill:"#253044",font:"bold 12px Microsoft YaHei"}},
      {type:"text",style:{x:14,y:38,text:`风险域 ${c.aggregate_count} 个${c.expanded_count ? " · 点击风险域展开" : " · 聚合范围"}`,fill:"#7b8799",font:"10px Microsoft YaHei"}}
    ]
  }));
  const chart = echarts.init(document.getElementById(elId));
  chart._refreshExpansion = () => chart.setOption({
    tooltip:{trigger:"item",backgroundColor:"#fff",borderColor:"#d0d7de",textStyle:{color:"#334155",fontSize:12}},
    legend:{show:false},
    graphic:graphics,
    series:[{
      type:"graph",
      layout:"none",
      roam:false,
      draggable:false,
      data:makeData(),
      links:makeLinks(),
      emphasis:{focus:"none",lineStyle:{width:5}},
      labelLayout:{hideOverlap:true}
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
  const evidence = (raw.evidence_chain || []).map(e =>
    `<div class="ev"><b>证据 ${escapeHtml(e.evidence_level || "—")}</b> · ${escapeHtml(e.source_api || "")}<br/>字段：${escapeHtml(e.source_field || "—")}</div>`
  ).join("") || `<div class="ev">无证据链</div>`;
  document.getElementById("panel-body").innerHTML = html + evidence;
}

function renderEdgeDetail(edge) {
  document.getElementById("panel-body").innerHTML =
    `<div class="kv"><b>关系类型</b> ${escapeHtml(edge.edge_type || "—")}</div>` +
    `<div class="kv"><b>来源</b> ${escapeHtml(shortName(edge.source))}</div>` +
    `<div class="kv"><b>目标</b> ${escapeHtml(shortName(edge.target))}</div>` +
    `<div class="kv"><b>语义</b> ${edge.edge_type === "expanded_from" ? "聚合域展开归属，不参与风险传播" : "真实血缘关系"}</div>`;
}

const evtDiv = document.getElementById("evt-list");
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
      `<div class="meta">${j.label} · 许可证 ${escapeHtml(n.license || "未声明")} · 快照 ${item.snapshots.join("/")}</div>` +
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
    parser.add_argument("--title", default=None, help="页面标题（默认自动）")
    parser.add_argument(
        "--include-fixtures",
        action="store_true",
        help="演示模式：保留 is_fixture / display_only 标记的演示夹具。"
        "默认按生产模式处理，把夹具从 Delta 与风险传播中排除。",
    )
    args = parser.parse_args()

    from main import _build_snapshot

    include_fixtures = bool(getattr(args, "include_fixtures", False))
    before = _build_snapshot(args.before, "t0", include_fixtures=include_fixtures)
    after = _build_snapshot(args.after, "t1", include_fixtures=include_fixtures)

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
    layout_t0 = layout_graph(nodes_t0, edges_t0, canvas_width=680)
    layout_t1 = layout_graph(nodes_t1, edges_t1, canvas_width=680)

    data = {
        "nodes_t0": nodes_t0,
        "edges_t0": edges_t0,
        "layout_t0": layout_t0,
        "nodes_t1": nodes_t1,
        "edges_t1": edges_t1,
        "layout_t1": layout_t1,
        "events": propagated["events"],
        "certificates": certs,
    }
    title = args.title or (
        "%s → %s 血缘风险传播" % (args.before.stem, args.after.stem)
    )
    chart_height = max(620, layout_t0["height"], layout_t1["height"])

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
