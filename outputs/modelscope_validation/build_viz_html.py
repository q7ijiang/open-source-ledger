# -*- coding: utf-8 -*-
"""把 viz_data.json 注入 HTML 模板，生成可双击打开的风险血缘图（构造数据版）。
节点按血缘链分层布局：基座在上、下游衍生在下。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIZ = ROOT / "tests" / "fixtures" / "modelscope" / "ms_viz" / "viz_data.json"
TPL = Path(__file__).resolve().with_name("ms_risk_lineage_template.html")
OUT = ROOT / "outputs" / "modelscope_validation" / "ms_risk_lineage.html"

data = json.loads(VIZ.read_text(encoding="utf-8"))
nodes = data.get("nodes", [])
edges = data.get("edges", [])

# ---- 链状分层布局：从基座（无入边）开始自上而下排列 ----
nodeById = {n["id"]: n for n in nodes}
in_degree = {nid: 0 for nid in nodeById}
children = {nid: [] for nid in nodeById}
for e in edges:
    if e["target"] in in_degree and e["source"] in nodeById:
        in_degree[e["target"]] += 1
        children[e["target"]].append(e["source"])

roots = [nid for nid, d in in_degree.items() if d == 0 and nid in nodeById]
if not roots:
    roots = list(nodeById)[:1]

def place(nid, x, y):
    n = nodeById[nid]
    n["x"] = x
    n["y"] = y
    n["lp"] = "bottom"
    kids = children.get(nid, [])
    for i, k in enumerate(kids):
        place(k, x + (i - (len(kids) - 1) / 2) * 320, y + 260)

for i, r in enumerate(roots):
    place(r, 500 + i * 0, 80)

tpl = TPL.read_text(encoding="utf-8")
out = tpl.replace("{{DATA_JSON}}", json.dumps(data, ensure_ascii=False))
OUT.write_text(out, encoding="utf-8")
print("已生成：%s" % OUT)
