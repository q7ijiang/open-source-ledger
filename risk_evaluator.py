# -*- coding: utf-8 -*-
"""单模型/项目级 P/D/P 风险判定（B 侧业务逻辑，模块 4+8+10 对外封装）。

用途：供 main.py --model / --project 调用。输入 A 标准化的资产节点与血缘边
（HF 或 ModelScope 通用），不请求网络、不修改引擎四件套，只做判定汇总。

判定口径（与 propagation_engine 三级判定一致）：
- 许可证规则库可识别 + 证据 A -> RISK_CONFIRMED
- 许可证规则库可识别 + 证据 B -> RISK_POTENTIAL
- 非标/未知协议（如 qwen-research）按证据等级：A/B -> RISK_POTENTIAL，C -> UNDETERMINED
- 无许可证节点 -> UNDETERMINED

用法（库）:
    from risk_evaluator import evaluate_model_risk
    result = evaluate_model_risk(assets, edges)

用法（CLI 自测）:
    python risk_evaluator.py --assets out/hf_lineage/assets.json --edges out/hf_lineage/edges.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import license_db
from build_graph import build_graph, EVIDENCE_ORDER

# 判定严重度（overall 取最严；SAFE 最低，不参与"最严"竞争）
_SEVERITY = {
    "RISK_CONFIRMED": 3,
    "RISK_POTENTIAL": 2,
    "UNDETERMINED": 1,
    "SAFE": 0,
}
_DECISION_ZH = {
    "RISK_CONFIRMED": "高风险（红）",
    "RISK_POTENTIAL": "潜在风险（黄）",
    "SAFE": "安全（绿）",
    "UNDETERMINED": "待确认（灰）",
}
# 判定优先级（整体判定按此取最严），SAFE 垫底
_DECISION_PRIORITY = ["RISK_CONFIRMED", "RISK_POTENTIAL", "UNDETERMINED", "SAFE"]

# 非标/未知协议（有协议文本但规则库不认识，如 qwen-research）：按证据等级降级
_UNKNOWN_LICENSE_DECISION = {"A": "RISK_POTENTIAL", "B": "RISK_POTENTIAL", "C": "UNDETERMINED"}

# 已知许可证：判定由"许可证本身的风险等级"决定，而不是由证据强弱决定。
# 宽松许可证（risk_level 1~2，如 MIT/Apache-2.0/BSD-3-Clause）→ 绿灯；
# 强/网络 copyleft（4~5，如 GPL-3.0/AGPL-3.0）→ 红灯；
# 弱 copyleft 与 AI 专用限制（3，如 MPL-2.0/LGPL-3.0/CC-BY-NC）→ 按证据分级：
#   证据 A（官方 API 原值）→ 红灯；证据 B → 黄灯；证据 C → 灰灯。
_PERMISSIVE_MAX_RISK_LEVEL = 2
_KNOWN_LICENSE_DECISION_BY_EVIDENCE = {
    "A": "RISK_CONFIRMED",
    "B": "RISK_POTENTIAL",
    "C": "UNDETERMINED",
}


def decision_for_license(risk_level: int | None, ev_level: str) -> str:
    """已知许可证的三/四态判定：风险等级优先，其次看证据等级。"""
    if risk_level is None:
        return "UNDETERMINED"
    if risk_level <= _PERMISSIVE_MAX_RISK_LEVEL:
        return "SAFE"
    if risk_level >= 4:
        return "RISK_CONFIRMED"
    return _KNOWN_LICENSE_DECISION_BY_EVIDENCE.get(ev_level, "UNDETERMINED")


def _best_evidence_level(evidence_chain: list[dict] | None) -> str:
    """取 evidence_chain 里最强证据等级（A>B>C）。空 -> C。"""
    levels = [
        e.get("evidence_level")
        for e in (evidence_chain or [])
        if isinstance(e, dict) and e.get("evidence_level") in EVIDENCE_ORDER
    ]
    if not levels:
        return "C"
    return min(levels, key=lambda lv: EVIDENCE_ORDER[lv])


def evaluate_node_risk(asset: dict) -> dict:
    """对单个资产节点做许可证 + 证据判定。"""
    license_value = asset.get("license")
    ev_level = _best_evidence_level(asset.get("evidence_chain"))

    rule_eval = license_db.evaluate_expression(license_value)
    known = rule_eval.get("max_risk_level") is not None
    has_license_text = bool(license_value and str(license_value).strip())

    if known:
        # 已知许可证：先看许可证自身风险等级（宽松→绿，强 copyleft→红），风险等级 3 再按证据分级。
        risk_level = rule_eval.get("max_risk_level")
        category = rule_eval.get("worst_category", "unknown")
        decision = decision_for_license(risk_level, ev_level)
        note = "license_recognized"
    elif has_license_text:
        # 非标/未知协议（如 qwen-research）：有协议文本但规则库不认识，按证据降级
        decision = _UNKNOWN_LICENSE_DECISION.get(ev_level, "UNDETERMINED")
        risk_level = None
        category = "unknown"
        note = "nonstandard_license"
    else:
        # 无许可证信息（空/聚合节点）：不臆断，待确认
        decision = "UNDETERMINED"
        risk_level = None
        category = "unknown"
        note = "no_license_info"

    return {
        "canonical_id": asset.get("canonical_id"),
        "entity_key": asset.get("entity_key"),
        "name": asset.get("name"),
        "asset_type": asset.get("asset_type"),
        "license": license_value,
        "license_recognized": known,
        "risk_level": risk_level,
        "category": category,
        "evidence_level": ev_level,
        "decision": decision,
        "decision_zh": _DECISION_ZH.get(decision, decision),
        "note": note,
    }


def evaluate_model_risk(assets: list[dict], edges: list[dict]) -> dict:
    """输入标准化 assets + edges，输出整体 P/D/P 风险判定。

    容错要求：遇非标协议（qwen-research）、聚合节点（count:NNNN）、缺字段
    均不崩溃、不死循环。build_graph 负责校验图结构。
    """
    # 建图（验证引擎可消化 MS 非标数据；节点数多时也不崩）
    graph = build_graph(assets, edges)
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()

    node_results = [evaluate_node_risk(a) for a in assets]

    # overall 取全图最严判定；全绿时整体为绿灯（不能因为 SAFE 垫底就回落成灰）
    overall = "SAFE"
    for nr in node_results:
        if _SEVERITY[nr["decision"]] > _SEVERITY[overall]:
            overall = nr["decision"]

    risks = [
        nr for nr in node_results
        if nr["decision"] in ("RISK_CONFIRMED", "RISK_POTENTIAL")
    ]
    safe = [nr for nr in node_results if nr["decision"] == "SAFE"]
    undetermined = [nr for nr in node_results if nr["decision"] == "UNDETERMINED"]
    nonstandard = [nr for nr in node_results if nr["note"] == "nonstandard_license"]
    distribution = {name: 0 for name in _DECISION_PRIORITY}
    for nr in node_results:
        distribution[nr["decision"]] = distribution.get(nr["decision"], 0) + 1

    return {
        "overall_decision": overall,
        "overall_decision_zh": _DECISION_ZH.get(overall, overall),
        "node_count": node_count,
        "edge_count": edge_count,
        "decision_distribution": distribution,
        "nodes": node_results,
        "risk_nodes": risks,
        "safe_nodes": safe,
        "undetermined_nodes": undetermined,
        "nonstandard_license_nodes": nonstandard,
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="单模型/项目级 P/D/P 风险判定（B）")
    parser.add_argument("--assets", required=True, help="资产列表 JSON")
    parser.add_argument("--edges", required=True, help="血缘边 JSON")
    parser.add_argument("--output", default=None, help="结果 JSON 输出路径")
    args = parser.parse_args(argv)

    assets = json.loads(Path(args.assets).read_text(encoding="utf-8"))
    edges = json.loads(Path(args.edges).read_text(encoding="utf-8"))
    result = evaluate_model_risk(assets, edges)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(f"整体判定：{result['overall_decision']}（{result['overall_decision_zh']}）")
    print(f"节点 {result['node_count']} / 边 {result['edge_count']}")
    print("判定分布：")
    for decision in _DECISION_PRIORITY:
        count = result["decision_distribution"].get(decision, 0)
        if count:
            print(f"  {_DECISION_ZH[decision]:<12} {decision:<16} {count}")
    print(f"非标协议节点：{len(result['nonstandard_license_nodes'])}")
    reported: set[str] = set()
    for nr in result["risk_nodes"] + result["nonstandard_license_nodes"]:
        if nr["decision"] not in ("RISK_CONFIRMED", "RISK_POTENTIAL"):
            continue
        key = str(nr.get("canonical_id") or nr.get("name"))
        if key in reported:
            continue
        reported.add(key)
        print(f"  - [{nr['decision']}] {nr['name']} | license={nr['license']} | 证据={nr['evidence_level']}")


if __name__ == "__main__":
    main()
