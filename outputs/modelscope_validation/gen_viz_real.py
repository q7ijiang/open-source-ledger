# -*- coding: utf-8 -*-
"""真实 MS 数据（--project 产物）→ 可视化 HTML。
读取 project_extract/assets.json + edges.json（真实 API 血缘，含聚合节点），
注入 ECharts 模板生成 ms_risk_lineage_real.html。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "outputs" / "modelscope_validation" / "project_extract" / "assets.json"
EDGES = ROOT / "outputs" / "modelscope_validation" / "project_extract" / "edges.json"
TPL = Path(__file__).resolve().with_name("ms_risk_lineage_template.html")
OUT = ROOT / "outputs" / "modelscope_validation" / "ms_risk_lineage_real.html"

assets = json.loads(ASSETS.read_text(encoding="utf-8"))
edges = json.loads(EDGES.read_text(encoding="utf-8"))

nodes = []
for a in assets:
    nodes.append({
        "id": a.get("canonical_id"),
        "name": a.get("name"),
        "version": a.get("version"),
        "type": a.get("asset_type"),
        "license": a.get("license"),
        "evidence": a.get("evidence_chain") or [],
        "merge_status": a.get("merge_status"),
        "reason_code": a.get("reason_code"),
        "aggregate": bool(a.get("aggregate")),
        "count": a.get("count"),
    })

edgelist = []
for e in edges:
    edgelist.append({
        "source": e["source"], "target": e["target"],
        "edge_type": e.get("edge_type"), "evidence_level": e.get("evidence_level"),
    })

# ---- 森林分层布局：每棵基座树 = 基座在上 + 聚合节点在下（两行两列展开）----
nodeById = {n["id"]: n for n in nodes}
base_nodes = [n for n in nodes if not n.get("aggregate")]
base_ids = [n["id"] for n in base_nodes]
children_of = {bid: [] for bid in base_ids}
for e in edgelist:
    if e["target"] in children_of and e["source"] not in children_of:
        children_of[e["target"]].append(e["source"])

for idx, b in enumerate(base_nodes):
    b["x"] = 140 + idx * 370
    b["y"] = 120
    b["lp"] = "top"
    for kid_i, kid in enumerate(children_of.get(b["id"], [])):
        col = kid_i % 2
        row = kid_i // 2
        xoff = -110 if col == 0 else 110
        yoff = 180 + row * 150
        if kid in nodeById:
            nodeById[kid]["x"] = b["x"] + xoff
            nodeById[kid]["y"] = b["y"] + yoff
            nodeById[kid]["lp"] = "bottom"

viz = {"nodes": nodes, "edges": edgelist, "events": [], "certificates": []}

tpl = TPL.read_text(encoding="utf-8")
html = tpl.replace("{{DATA_JSON}}", json.dumps(viz, ensure_ascii=False))
# 标题与说明更新为真实数据口径
html = html.replace("<title>ModelScope 血缘风险传播图 — 开源账本</title>",
                    "<title>ModelScope 真实血缘风险图 — 开源账本</title>")
html = html.replace("<h1>ModelScope 血缘风险传播图</h1>",
                    "<h1>ModelScope 真实数据 · 血缘风险图</h1>")
html = html.replace("来源：ModelScope（魔搭社区）· 开源账本 C 模块",
                    "来源：ModelScope 官方 API 真实数据 · 开源账本 C 模块")
OUT.write_text(html, encoding="utf-8")

# 同时落盘数据供校验
(ROOT / "outputs" / "modelscope_validation" / "ms_viz" / "viz_real_data.json").write_text(
    json.dumps(viz, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

agg = sum(1 for n in nodes if n.get("aggregate"))
print("真实数据可视化已生成：%s" % OUT)
print("节点 %d（含聚合节点 %d）/ 边 %d" % (len(nodes), agg, len(edgelist)))
