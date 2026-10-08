# -*- coding: utf-8 -*-
"""validate_fallback.py — 验证 enrich_lineage 三级降级推断（临时验证脚本）。

对 5 个场景模型，分别打印：
  1) 三级各自独立的推断结果（HF API / 关键词 / 文本提取）；
  2) enrich_bom 全流程结果（status + 回填祖先的 source / evidence_level）；
  3) extract_hf_lineage.extract 得到的节点 / 边数量。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import enrich_lineage as el
import work.extract_hf_lineage as ex

SCENARIOS = [
    "TheBloke/Qwen2.5-0.5B-Instruct-GGUF",
    "distilbert-base-uncased",
    "microsoft/Phi-3-mini-4k",
    "TheBloke/Llama-2-7B-Chat-GGUF",
    "nonexistent-org/nonexistent-model",
]


def show_inference(model: str, fn, *args) -> str:
    try:
        r = fn(*args)
    except Exception as exc:  # noqa: BLE001
        return f"EXC: {type(exc).__name__}: {exc}"
    if r is None:
        return "None"
    return f"{r.ancestor} | source={r.source} | evidence={r.evidence_level}"


out: list[str] = []
for model in SCENARIOS:
    out.append(f"=== {model} ===")
    out.append(f"  L1 hf_api     : {show_inference(model, el.infer_from_hf_api, model)}")
    out.append(f"  L2 keyword    : {show_inference(model, el.infer_from_keyword, model)}")
    out.append(f"  L3 text(None) : {show_inference(model, el.infer_from_text, model, None)}")

    with tempfile.TemporaryDirectory() as tmp:
        bom_path = Path(tmp) / (model.replace("/", "__") + ".json")
        data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "version": 1,
            "metadata": {"component": {"name": model.rsplit("/", 1)[-1]}},
            "components": [],
        }
        bom_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        status, msg = el.enrich_bom(bom_path, model)
        out.append(f"  enrich       : status={status} | {msg}")

        enriched = json.loads(bom_path.read_text(encoding="utf-8"))
        comps = enriched.get("components") or []
        if comps:
            anc = (comps[0].get("pedigree", {}) or {}).get("ancestors", [{}])[0]
            out.append(
                f"  ancestor     : {anc.get('group', '')}/{anc.get('name', '')}"
                f" | source={anc.get('source')} | evidence={anc.get('evidence_level')}"
            )
        if "undetermined" in enriched:
            out.append(f"  undetermined : {enriched['undetermined']}")

        try:
            assets, edges = ex.extract(bom_path)
            out.append(f"  extract      : {len(assets)} nodes, {len(edges)} edges")
        except Exception as exc:  # noqa: BLE001
            out.append(f"  extract      : EXC {type(exc).__name__}: {exc}")

text = "\n".join(out)
Path("outputs/validate_fallback.txt").write_text(text, encoding="utf-8")
print(text)
