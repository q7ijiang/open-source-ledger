#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report_enhanced.py — 深度层中文风险传播报告生成器（模块11，成员 C）

功能：
    消费深度流水线（模块9 delta_engine / 模块10 propagation_engine）的合并输出，
    渲染一份中文 Markdown《AI 模型血缘风险传播报告》，包含：
      - 变更摘要（事件按类型分布 + 逐事件明细，含审计字段与判定）
      - 传播路径（每个事件自带的血缘路径逐跳展示）
      - 路径证书（affected / hop_count / weakest_evidence / decision / termination / missing_ancestor）
      - 受影响资产（按 RISK_CONFIRMED / RISK_POTENTIAL / UNDETERMINED 三级分组）
      - 风险源汇总
      - 证据等级与判定说明（接口约定 v0.3 口径）

用法（推荐，B 的 propagation_engine 合并输出）：
    python report_enhanced.py --input out/propagated.json \
        --bom-t0 test_data/t0_bom.json --bom-t1 test_data/t1_bom.json \
        -o provenance_risk_report.md

兼容旧用法（事件与路径证书分文件）：
    python report_enhanced.py --events events.json --certificates path_certificates.json \
        --bom-t0 t0_bom.json --bom-t1 t1_bom.json -o report.md

输入格式（与组长仓库 docs/接口约定.md v0.3 对齐，见文件底部 SCHEMA）：
    --input        propagated.json：{"events": [...], "path_certificates": [...]}（B 输出形态）
    --events       仅事件数组或 {"events": [...]} envelope
    --certificates 仅路径证书数组或 {"path_certificates": [...]} envelope

免责声明：
    本报告由开源账本自动生成，基于证据的辅助审计，不构成法律意见。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 一、三级判定 / 证据等级 / 事件类型定义（接口约定 v0.3）
# ---------------------------------------------------------------------------

DECISION_LABEL = {
    "RISK_CONFIRMED": ("🔴 确认风险", "confirmed"),
    "RISK_POTENTIAL": ("🟠 潜在风险", "potential"),
    "UNDETERMINED": ("⚪ 无法判定", "undetermined"),
}

EVIDENCE_LEVEL_LABEL = {
    "A": "A（官方或权威元数据直接证明）",
    "B": "B（工具产物或结构化依赖证据）",
    "C": "C（推断、启发式或降级证据）",
}

CHANGE_TYPE_LABEL = {
    "license_changed": "许可证变更",
    "license_field_file_conflict": "许可证字段与文件冲突",
    "metadata_file_conflict": "元数据字段冲突",
    "ancestor_added": "祖先新增",
    "ancestor_removed": "祖先删除",
    "dataset_added": "数据集新增",
    "dataset_removed": "数据集删除",
    "evidence_downgrade": "证据等级下降",
    "evidence_downgraded": "证据等级下降",
    "version_changed": "版本变更",
    "version_upgraded": "版本升级",
    "revision_changed": "版本变更",
    "dependency_edge_changed": "依赖边变更",
    "edge_changed": "血缘边变更",
}


# ---------------------------------------------------------------------------
# 二、输入读取（兼容 propagated 合并输出 / 裸数组 / envelope 三种形态）
# ---------------------------------------------------------------------------

def load_json(path: str) -> dict | list:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _unwrap(data, *keys):
    """从 envelope 里取数组：data 本身是数组直接返回；否则尝试多个键名。"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in keys:
            v = data.get(k)
            if isinstance(v, list):
                return v
        for v in data.values():
            if isinstance(v, list):
                return v
    return []


def load_input(path: str) -> tuple[list, list]:
    """读取 B 的 propagation_engine 合并输出：{"events": [...], "path_certificates": [...]}。"""
    data = load_json(path)
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return data.get("events", []), data.get("path_certificates", [])
    # 退化为仅事件数组
    return _unwrap(data, "events", "delta_events", "changes"), []


def load_events(path: str) -> list:
    return _unwrap(load_json(path), "events", "delta_events", "changes")


def load_certificates(path: str) -> list:
    return _unwrap(load_json(path), "path_certificates", "certificates", "certs", "paths")


# ---------------------------------------------------------------------------
# 三、资产名映射（用 BOM 快照把 canonical_id / purl 变成可读名称）
# ---------------------------------------------------------------------------

def _load_asset_names(bom_path: str | None) -> dict:
    """purl -> "name@version" 映射，供报告可读化。"""
    if not bom_path:
        return {}
    try:
        bom = load_json(bom_path)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    mapping = {}
    for comp in bom.get("components", []):
        name = comp.get("name", "")
        ver = comp.get("version", "")
        display = f"{name}@{ver}" if ver else name
        for key in (comp.get("purl"), comp.get("bom-ref")):
            if key:
                mapping[key] = display
    return mapping


def _human(ident, names: dict) -> str:
    """把 canonical_id / purl 显示为可读短名；找不到则提取尾段。"""
    if not ident:
        return "—"
    if ident in names:
        return names[ident]
    for prefix in ("pkg:", "model:", "dataset:", "package:", "repository:"):
        if ident.startswith(prefix):
            rest = ident[len(prefix):]
            parts = rest.split("/")
            tail = "/".join(parts[-2:]) if len(parts) >= 2 else rest
            return tail
    return ident


def _ev_field(ev: dict, key: str, default=""):
    v = ev.get(key)
    if v is not None:
        return v
    return ev.get(key.replace("_", "-"), default)


def _state_audit(st) -> str:
    """从 before/after 状态对象提取审计字段（merge_status / reason_code / rule_version）。"""
    if not isinstance(st, dict):
        return ""
    parts = []
    for k in ("merge_status", "reason_code", "rule_version"):
        v = st.get(k)
        if v:
            parts.append(f"{k}={v}")
    return "；".join(parts)


def _audit_txt(ev: dict) -> str:
    """事件审计字段：优先事件顶层，其次 before/after 状态对象。"""
    parts = []
    for k in ("merge_status", "reason_code", "rule_version"):
        v = _ev_field(ev, k)
        if v:
            parts.append(f"{k}={v}")
    st_audit = _state_audit(ev.get("before")) or _state_audit(ev.get("after"))
    if st_audit and st_audit not in parts:
        parts.append(st_audit)
    return "；".join(parts) if parts else "—"


def _state_str(ev: dict, key: str, names: dict) -> str:
    """把 before/after 渲染为可读变更值：license_changed 用 license，版本事件用 canonical_id。"""
    st = ev.get(key)
    if st is None:
        return "（无）"
    if not isinstance(st, dict):
        return str(st) or "（无）"
    ctype = ev.get("change_type", "")
    if ctype in ("version_changed", "version_upgraded", "revision_changed"):
        cid = st.get("canonical_id")
        if cid:
            return _human(cid, names)
    lic = st.get("license")
    if lic is not None:
        return str(lic)
    cid = st.get("canonical_id")
    if cid:
        return _human(cid, names)
    return "（无）"


def _render_change(ev: dict, names: dict) -> str:
    before = _state_str(ev, "before", names)
    after = _state_str(ev, "after", names)
    if before != "（无）" or after != "（无）":
        return f"{before} → {after}"
    return "—"


def _format_path(path: list, names: dict) -> str:
    """把事件自带 path 步骤（source/target/edge_type/evidence_level/source_field）渲染成链。"""
    if not path:
        return "—"
    parts = []
    for i, hop in enumerate(path):
        if isinstance(hop, dict):
            src = _human(hop.get("source") or hop.get("node") or hop.get("purl") or hop.get("id", ""), names)
            tgt = _human(hop.get("target") or "", names)
            etype = hop.get("edge_type") or hop.get("edge") or "lineage"
            ev_lv = hop.get("evidence_level") or hop.get("evidence") or "?"
            if tgt and tgt != "—":
                if i == 0:
                    parts.append(f"{src} —[{etype} / {ev_lv}]→ {tgt}")
                else:
                    parts.append(f"—[{etype} / {ev_lv}]→ {tgt}")
            else:
                parts.append(src)
        else:
            parts.append(_human(str(hop), names))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# 四、报告渲染
# ---------------------------------------------------------------------------

def render_report(events: list, certs: list, bom_t0: str | None, bom_t1: str | None,
                  ev_path: str = "", cert_path: str = "") -> str:
    names_t0 = _load_asset_names(bom_t0)
    names_t1 = _load_asset_names(bom_t1)
    names = {**names_t0, **names_t1}

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    L = []
    L.append("# AI 模型血缘风险传播报告")
    L.append("")
    L.append(f"> 生成时间：{now}")
    if ev_path:
        L.append(f"> 输入事件：`{ev_path}`" + (f" ｜ 路径证书：`{cert_path}`" if cert_path else ""))
    L.append(f"> 快照：t0 `{bom_t0 or '—'}` → t1 `{bom_t1 or '—'}`")
    L.append("> 生成工具：开源账本（深度层）· report_enhanced.py（接口约定 v0.3）")
    L.append("")

    # ---- 一、变更摘要 ----
    L.append("## 一、变更摘要")
    L.append("")
    if not events:
        L.append("未检测到两个 BOM 快照之间的变更事件。")
        L.append("")
    else:
        by_type = Counter(_ev_field(e, "change_type") or "unknown" for e in events)
        L.append(f"共检测到 **{len(events)}** 个变更事件，按类型分布：")
        L.append("")
        for t, n in by_type.most_common():
            label = CHANGE_TYPE_LABEL.get(t, t)
            L.append(f"- **{label}**（`{t}`）：{n} 个")
        L.append("")
        L.append("| 事件 ID | 类型 | 风险源（seed） | 变更（before → after） | 证据 | 判定 | 审计（merge_status / reason_code / rule_version） |")
        L.append("|---|---|---|---|---|---|---|")
        for ev in events:
            eid = _ev_field(ev, "event_id") or "—"
            ctype = _ev_field(ev, "change_type") or "unknown"
            ctype_label = CHANGE_TYPE_LABEL.get(ctype, ctype)
            seed = _human(_ev_field(ev, "seed"), names)
            change = _render_change(ev, names)
            ev_lv = _ev_field(ev, "evidence_level") or "—"
            decision = _ev_field(ev, "decision") or "—"
            audit = _audit_txt(ev).replace("|", "\\|")
            L.append(f"| {eid} | {ctype_label} | {seed} | {change} | {ev_lv} | {decision} | {audit} |")
        L.append("")

    # ---- 二、传播路径 ----
    L.append("## 二、传播路径")
    L.append("")
    events_with_path = [e for e in events if e.get("path")]
    if not events_with_path:
        L.append("事件均未携带血缘路径（path 为空）。")
        L.append("")
    else:
        L.append("每个事件携带从种子到受影响资产的传播路径（weakest link 规则取最弱证据）：")
        L.append("")
        for ev in events_with_path:
            eid = _ev_field(ev, "event_id") or "—"
            ctype = CHANGE_TYPE_LABEL.get(_ev_field(ev, "change_type"), _ev_field(ev, "change_type"))
            path = ev.get("path") or []
            L.append(f"### {eid} · {ctype}")
            L.append("")
            L.append(f"- 种子资产：`{_human(_ev_field(ev, 'seed'), names)}`")
            L.append(f"- 传播路径（共 {len(path)} 跳，最弱证据 {_ev_field(ev, 'evidence_level') or '—'}，判定 {_ev_field(ev, 'decision') or '—'}）：")
            L.append("")
            L.append("```text")
            L.append(_format_path(path, names))
            L.append("```")
            L.append("")
        L.append("")

    # ---- 三、路径证书 ----
    L.append("## 三、路径证书")
    L.append("")
    if not certs:
        L.append("未生成任何路径证书（path_certificates 为空，path_certificates 数为 0）。")
        L.append("")
    else:
        L.append(f"共生成 **{len(certs)}** 张路径证书：")
        L.append("")
        L.append("| 证书 ID | 受影响资产 | 变更类型 | 跳数 | 最弱证据 | 判定 | 终止原因 | 缺失祖先 | 路径指纹 |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for c in certs:
            cid = _ev_field(c, "certificate_id") or _ev_field(c, "cert_id") or "—"
            affected = _human(_ev_field(c, "affected") or _ev_field(c, "target") or _ev_field(c, "asset"), names)
            ctype = CHANGE_TYPE_LABEL.get(_ev_field(c, "change_type"), _ev_field(c, "change_type") or "—")
            hops = _ev_field(c, "hop_count", "—")
            weakest = _ev_field(c, "weakest_evidence", "—")
            decision = _ev_field(c, "decision") or "—"
            termination = _ev_field(c, "termination") or "—"
            missing = "是" if _ev_field(c, "missing_ancestor", False) else "否"
            fp = _ev_field(c, "path_fingerprint") or "—"
            L.append(f"| {cid} | {affected} | {ctype} | {hops} | {weakest} | {decision} | {termination} | {missing} | {fp} |")
        L.append("")

    # ---- 四、受影响资产（按三级判定分组） ----
    L.append("## 四、受影响资产（按判定分组）")
    L.append("")
    groups = defaultdict(list)
    for c in certs:
        decision = _ev_field(c, "decision") or "UNDETERMINED"
        groups[decision].append(c)
    if not groups:
        L.append("无路径证书，无法分组。")
        L.append("")
    else:
        for decision in ("RISK_CONFIRMED", "RISK_POTENTIAL", "UNDETERMINED"):
            items = groups.get(decision, [])
            dlabel, _ = DECISION_LABEL.get(decision, (decision, "unknown"))
            if not items:
                continue
            L.append(f"### {dlabel}（{len(items)} 项）")
            L.append("")
            L.append("| 受影响资产 | 变更类型 | 跳数 | 最弱证据 | 证书 ID |")
            L.append("|---|---|---|---|---|")
            for c in items:
                affected = _human(_ev_field(c, "affected") or _ev_field(c, "target") or _ev_field(c, "asset"), names)
                ctype = CHANGE_TYPE_LABEL.get(_ev_field(c, "change_type"), _ev_field(c, "change_type") or "—")
                hops = _ev_field(c, "hop_count", "—")
                weakest = _ev_field(c, "weakest_evidence", "—")
                cid = _ev_field(c, "certificate_id") or _ev_field(c, "cert_id") or "—"
                L.append(f"| {affected} | {ctype} | {hops} | {weakest} | {cid} |")
            L.append("")

    # ---- 五、风险源汇总 ----
    L.append("## 五、风险源汇总")
    L.append("")
    seeds = Counter(_human(_ev_field(e, "seed"), names) for e in events if _ev_field(e, "seed"))
    if not seeds:
        L.append("—")
        L.append("")
    else:
        L.append("| 风险源 | 关联事件数 |")
        L.append("|---|---|")
        for seed, n in seeds.most_common():
            L.append(f"| {seed} | {n} |")
        L.append("")

    # ---- 六、证据等级与判定说明 ----
    L.append("## 六、证据等级与判定说明")
    L.append("")
    L.append("| 等级 | 定义（接口约定 v0.3） |")
    L.append("|---|---|")
    L.append("| A | 官方或权威元数据直接证明（PyPI / npm / Hugging Face API 许可证字段、仓库 LICENSE 文件） |")
    L.append("| B | 工具产物或结构化依赖证据（CycloneDX BOM、lockfile、模型卡结构化字段） |")
    L.append("| C | 推断、启发式或降级证据（同名对齐、模型卡文本推断、API 失败降级） |")
    L.append("")
    L.append("| 判定 | 含义 |")
    L.append("|---|---|")
    L.append("| RISK_CONFIRMED | 路径上所有边证据等级为 A，规则明确适用 |")
    L.append("| RISK_POTENTIAL | 路径上存在 B 级边，规则可能适用 |")
    L.append("| UNDETERMINED | 路径上存在 C 级边、缺失祖先或冲突字段 |")
    L.append("")
    L.append("> 口径（接口约定 v0.3）：Hugging Face 官方 API 返回的模型卡元数据本可为 A，但 BOM 为 CycloneDX 工具产物，**血缘边证据等级统一按 B 级处理**，避免口径混用。")
    L.append("> 风险传播使用 weakest link 规则：路径证据等级取路径中最低等级；`UNDETERMINED` 不是“无风险”，而是“证据不足以判定”。")
    L.append("")
    L.append("---")
    L.append("")
    L.append("> **免责声明**：本报告由开源账本自动生成，基于证据的辅助审计，不构成法律意见，也不能替代针对具体许可证、司法辖区和业务模式的执业法律审查。")
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# 五、主流程
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="开源账本·深度层：AI 模型血缘风险传播报告生成器")
    parser.add_argument("--input", help="propagation_engine 合并输出 JSON：{\"events\": [...], \"path_certificates\": [...]}（推荐）")
    parser.add_argument("--events", help="delta_engine 输出的事件 JSON（数组或 envelope；--input 未提供时使用）")
    parser.add_argument("--certificates", help="propagation_engine 输出的路径证书 JSON（数组或 envelope；可选）")
    parser.add_argument("--bom-t0", help="t0 快照 BOM（可选，用于资产名可读化）")
    parser.add_argument("--bom-t1", help="t1 快照 BOM（可选）")
    parser.add_argument("-o", "--output", default="provenance_risk_report.md", help="输出 Markdown 路径")
    parser.add_argument("--stdout", action="store_true", help="只输出到屏幕，不写文件")
    args = parser.parse_args(argv)

    try:
        if args.input:
            events, certs = load_input(args.input)
            ev_path = cert_path = args.input
        else:
            if not args.events:
                parser.error("必须提供 --input 或 --events")
            events = load_events(args.events)
            certs = load_certificates(args.certificates) if args.certificates else []
            ev_path, cert_path = args.events, args.certificates or ""
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    md = render_report(events, certs, args.bom_t0, args.bom_t1,
                       ev_path=ev_path, cert_path=cert_path)
    if args.stdout:
        print(md)
        return 0

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[完成] 事件 {len(events)} 个，路径证书 {len(certs)} 张，报告已写入：{out.resolve()}")
    return 0


# ---------------------------------------------------------------------------
# SCHEMA（与组长仓库 docs/接口约定.md v0.3 对齐）
# ---------------------------------------------------------------------------
EVENT_SCHEMA = {
    "event_id": "事件唯一标识",
    "seed": "事件种子资产的 canonical_id；边变更事件（ancestor_*/dataset_*）为 edge.target（上游变化资产）",
    "change_type": "license_changed | ancestor_added | ancestor_removed | dataset_added | dataset_removed | evidence_downgrade | version_changed | version_upgraded",
    "before": "变更前状态对象（canonical_id / entity_key / license / purls / snapshot_id / merge_status / reason_code / rule_version）",
    "after": "变更后状态对象（同上）",
    "path": "从种子到受影响资产的血缘路径（步骤含 source / target / edge_type / evidence_level / source_field）",
    "evidence_level": "本次事件证据等级（weakest link）",
    "decision": "RISK_CONFIRMED | RISK_POTENTIAL | UNDETERMINED",
}

CERTIFICATE_SCHEMA = {
    "certificate_id": "路径证书唯一标识",
    "affected": "受影响资产 canonical_id",
    "change_type": "变更类型",
    "hop_count": "传播跳数",
    "weakest_evidence": "路径最弱证据等级 A/B/C",
    "decision": "RISK_CONFIRMED | RISK_POTENTIAL | UNDETERMINED",
    "termination": "传播终止原因",
    "missing_ancestor": "是否缺失祖先（bool）",
    "path_fingerprint": "路径指纹",
}

if __name__ == "__main__":
    sys.exit(main())
