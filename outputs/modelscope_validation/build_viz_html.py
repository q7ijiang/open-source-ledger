# -*- coding: utf-8 -*-
"""把 viz_data.json 注入 HTML 模板，生成可双击打开的风险血缘图。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIZ = ROOT / "outputs" / "modelscope_validation" / "ms_viz" / "viz_data.json"
TPL = Path(__file__).resolve().with_name("ms_risk_lineage_template.html")
OUT = ROOT / "outputs" / "modelscope_validation" / "ms_risk_lineage.html"

data = json.loads(VIZ.read_text(encoding="utf-8"))
tpl = TPL.read_text(encoding="utf-8")
out = tpl.replace("{{DATA_JSON}}", json.dumps(data, ensure_ascii=False))
OUT.write_text(out, encoding="utf-8")
print("已生成：%s" % OUT)
