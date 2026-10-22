#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report_basic.py — 基础层中文合规清单生成器（模块5，成员 C）· v3 ModelScope 适配版

v2 变更（对齐组长 main.py 集成要求）：
    1. 去重：不再使用内部 merge_entities()，改为调用
       entity_resolver.deduplicate_assets()（返回 去重资产 + 配对日志）；
    2. 许可证：不再使用内部 classify_license()，改为调用 license_db
       （evaluate_expression / risk_level / category_zh / is_ai_license）；
    3. 字段：对齐 main.py 快照资产格式（bom_adapter.convert_bom 输出）：
       canonical_id / entity_key / asset_type / name / version / purls /
       license / evidence_chain（evidence_level、source_url、source_field、
       raw_value）/ hashes / merge_status / reason_code / rule_version /
       snapshot_id / source_file。

v3 变更（响应组长 10-07 ModelScope 转向要求）：
    1. 数据源标注：自动识别 ModelScope 标注，未标注时输出未知来源；
    2. P/D/P 判定结论：新增判定区块（🟢 安全 / 🟡 潜在风险 / 🔴 风险），
       依据 license_db 评估结果输出「绿灯出表、红灯出图」提示；
    3. 渲染语境：血缘边数等统计不再写死 HF 字样，兼容 ModelScope 聚合节点。

可被 main.py 直接接入：
    import report_basic
    md = report_basic.render_report(
        snapshot["assets"],
        bom_path=str(snapshot["path"]),
        snapshot_id=snapshot["snapshot_id"],
        raw_count=len(snapshot["raw_assets"]),
        merge_log=snapshot["merge_log"],
        evidence_summary=snapshot["evidence_summary"],
        edges=snapshot["edges"],
    )

用法：
    python report_basic.py --bom sample_bom.json -o 开源合规清单.md   # BOM 直出
    python report_basic.py --assets assets_deduplicated.json -o 清单.md # 资产直读
    python report_basic.py --bom sample_bom.json --stdout             # 只打印
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 依赖模块（仓库根目录，须与 main.py 同一目录）
# ---------------------------------------------------------------------------


def _import(module_name: str):
    """导入仓库根目录的模块，缺失时给出中文提示。"""
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"缺少依赖模块 {module_name}.py：请从组长仓库拉取该文件到本项目根目录后重试。"
        ) from exc


# ---------------------------------------------------------------------------
# 一、许可证评估（license_db 封装）
# ---------------------------------------------------------------------------

RISK_LEVEL_ZH = {
    1: "低风险（宽松/公有领域）",
    2: "低风险（宽松+额外义务）",
    3: "中风险（弱 copyleft / AI 受限）",
    4: "高风险（强 copyleft / AI 商用受限）",
    5: "高风险（网络 copyleft）",
}

RISK_BADGE = {1: "🟢 低", 2: "🟢 低", 3: "🟠 中", 4: "🔴 高", 5: "🔴 高"}

ASSET_TYPE_ZH = {
    "model": "模型",
    "package": "软件包",
    "dataset": "数据集",
    "repository": "仓库",
    "framework": "框架",
}

# P/D/P 判定（ModelScope 场景）：灯色、结果码与提示
PDP_LIGHT = {"SAFE": "🟢 安全", "RISK_POTENTIAL": "🟡 潜在风险", "RISK": "🔴 风险"}


def detect_source(assets: list[dict[str, Any]]) -> str:
    """检测数据源生态：ModelScope / 未知。

    依据：资产 purls 与 evidence_chain 中的 source_url / source_api / source_field。
    """
    hits: set[str] = set()
    for asset in assets:
        for purl in asset.get("purls") or []:
            text = str(purl).lower()
            if "modelscope" in text:
                hits.add("ModelScope")
        for entry in asset.get("evidence_chain", []):
            if not isinstance(entry, dict):
                continue
            text = " ".join(
                str(entry.get(key) or "")
                for key in ("source_url", "source_api", "source_field")
            ).lower()
            if "modelscope" in text:
                hits.add("ModelScope")
    if not hits:
        return "未知（本地 BOM / 未标注生态）"
    return " / ".join(sorted(hits))


def pd_judge(assessment: dict[str, Any]) -> tuple[str, str]:
    """P/D/P 判定：依据 license_db 评估结果输出 (灯色码, 判定依据)。

    - SAFE 绿灯：许可证全部识别且风险等级 ≤ 2（宽松/公有领域）
    - RISK_POTENTIAL 黄灯：存在未识别写法（如 qwen-research 等非标协议）、
      风险等级 3、AI 专用许可证、或未声明许可证
    - RISK 红灯：风险等级 ≥ 4（传染性 / 强约束条款）
    """
    risk = assessment.get("risk_level")
    unknown = assessment.get("unknown_items") or []
    if risk is None:
        return "RISK_POTENTIAL", "许可证未声明或规则库未识别（如 qwen-research 等非标协议），需人工核对官方文本"
    if risk >= 4:
        return "RISK", "许可证含传染性或强约束条款（GPL/AGPL/SSPL 等），使用/分发前必须核对义务"
    if risk == 3 or assessment.get("is_ai_license"):
        return "RISK_POTENTIAL", "中风险许可证或 AI 专用许可证，需重点核对许可义务"
    if unknown:
        return "RISK_POTENTIAL", "存在未识别许可证写法，需人工核对"
    return "SAFE", "宽松/公有领域许可证，常规合规"


def assess_license(license_text: Any) -> dict[str, Any]:
    """用 license_db 评估许可证字段，返回对齐 main.py 的评估结果。

    返回：{
        "risk_level": int | None,      # 1-5；None 表示未声明或全未识别
        "category_zh": str,            # 类别中文
        "is_ai_license": bool,
        "known_items": [canonical_id], # 已识别项
        "unknown_items": [raw],        # 未识别项
    }
    """
    license_db = _import("license_db")
    if license_text is None or str(license_text).strip() == "":
        return {
            "risk_level": None,
            "category_zh": "未知 / 待人工确认",
            "is_ai_license": False,
            "known_items": [],
            "unknown_items": [],
        }

    expression = license_db.evaluate_expression(str(license_text))
    worst = expression.get("worst_category") or "unknown"
    return {
        "risk_level": expression.get("max_risk_level"),
        "category_zh": license_db.CATEGORY_ZH.get(worst, "未知 / 待人工确认"),
        "is_ai_license": license_db.is_ai_license(str(license_text)),
        "known_items": [
            item["canonical_id"]
            for item in expression.get("items", [])
            if item.get("known") and item.get("canonical_id")
        ],
        "unknown_items": list(expression.get("unknown_items", [])),
    }


def license_display(license_text: Any, assessment: dict[str, Any]) -> str:
    """许可证展示文本：已识别 canonical_id（AI 专用加注）+ 未识别项原文。"""
    parts = list(assessment["known_items"])
    if assessment["is_ai_license"]:
        parts = [f"{cid}（AI 专用）" for cid in parts]
    parts.extend(f"{raw}（未识别）" for raw in assessment["unknown_items"])
    if parts:
        return "；".join(parts)
    return str(license_text).strip() if license_text and str(license_text).strip() else "未声明"


# ---------------------------------------------------------------------------
# 二、资产工具（字段对齐 main.py 快照资产）
# ---------------------------------------------------------------------------

EVIDENCE_ORDER = {"A": 0, "B": 1, "C": 2}


def best_evidence_level(asset: dict[str, Any]) -> str | None:
    """最佳证据等级：evidence_chain 中 evidence_level 最小（A<B<C）。"""
    levels = [
        entry.get("evidence_level")
        for entry in asset.get("evidence_chain", [])
        if isinstance(entry, dict) and entry.get("evidence_level") in EVIDENCE_ORDER
    ]
    if not levels:
        return None
    return min(levels, key=lambda level: EVIDENCE_ORDER[level])


def evidence_links(asset: dict[str, Any]) -> list[str]:
    """来源链接：evidence_chain[].source_url 去重保序。"""
    links: list[str] = []
    for entry in asset.get("evidence_chain", []):
        if not isinstance(entry, dict):
            continue
        url = entry.get("source_url")
        if url and str(url) not in links:
            links.append(str(url))
    return links


def evidence_locations(asset: dict[str, Any]) -> list[str]:
    """证据文件位置：evidence_chain 中 source_field 含 location/occurrence 的 raw_value。"""
    locs: list[str] = []
    for entry in asset.get("evidence_chain", []):
        if not isinstance(entry, dict):
            continue
        field = str(entry.get("source_field") or "").lower()
        if not any(token in field for token in ("location", "occurrence", "filepath")):
            continue
        value = entry.get("raw_value")
        if isinstance(value, dict):
            value = value.get("location") or value.get("path")
        if value and str(value) not in locs:
            locs.append(str(value))
    return locs


def format_links(urls: list[str]) -> str:
    """把链接列表渲染为 Markdown 链接，空列表返回占位文本。"""
    if not urls:
        return "未提供 URL（本地证据）"
    return "；".join(f"[链接]({url})" for url in urls)


def _cell(value: Any) -> str:
    """清洗单元格文本，避免破坏 Markdown 表格。"""
    return str(value or "").replace("|", "\\|").replace("\r", " ").replace("\n", "<br>").strip()


# ---------------------------------------------------------------------------
# 三、实体去重（entity_resolver.deduplicate_assets）
# ---------------------------------------------------------------------------


def deduplicate_assets(assets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """调用 entity_resolver.deduplicate_assets() 执行跨生态实体对齐。

    返回 (去重后资产列表, 逐对判定日志)。
    """
    entity_resolver = _import("entity_resolver")
    return entity_resolver.deduplicate_assets(assets)


# ---------------------------------------------------------------------------
# 四、Markdown 渲染（字段对齐 main.py 快照）
# ---------------------------------------------------------------------------


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return ["_无数据_"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return lines


def render_report(
    assets: list[dict[str, Any]],
    *,
    bom_path: str | None = None,
    snapshot_id: str | None = None,
    raw_count: int | None = None,
    merge_log: list[dict[str, Any]] | None = None,
    evidence_summary: dict[str, Any] | None = None,
    edges: list[dict[str, Any]] | None = None,
) -> str:
    """渲染中文《开源及第三方资源使用清单》。

    assets 为资产 dict 列表，字段对齐 main.py 快照（bom_adapter / entity_resolver 输出）。
    其余可选参数用于在摘要中展示流水线统计（main.py 可传入）。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    assessments = {
        asset.get("canonical_id") or asset.get("name"): assess_license(asset.get("license"))
        for asset in assets
    }

    # 统计
    high_risk = sum(
        1 for a in assessments.values() if (a["risk_level"] or 0) >= 4
    )
    ai_count = sum(1 for a in assessments.values() if a["is_ai_license"])
    unknown = sum(
        1 for a in assessments.values() if a["unknown_items"] or a["risk_level"] is None
    )
    merged_pairs = sum(
        1 for entry in (merge_log or []) if entry.get("status") == "merged"
    )

    lines: list[str] = []
    lines.append("# 开源及第三方资源使用清单")
    lines.append("")
    lines.append(f"> 生成时间：{now}")
    lines.append(f"> 生成工具：开源账本（基础层）· report_basic.py（v3：ModelScope 渲染适配）")
    lines.append(f"> 数据源：**{detect_source(assets)}**")
    if bom_path:
        lines.append(f"> 输入 BOM：`{bom_path}`")
    if snapshot_id:
        lines.append(f"> 快照 ID：`{snapshot_id}`")
    lines.append("")

    # 一、统计摘要
    lines.append("## 一、统计摘要")
    lines.append("")
    if raw_count is not None:
        lines.append(f"- BOM 解析资产数：**{raw_count}**")
    lines.append(f"- 实体对齐后资产数：**{len(assets)}**")
    if merged_pairs:
        lines.append(f"- 自动合并对数：**{merged_pairs}**")
    if merge_log is not None:
        lines.append(f"- 候选配对日志数：**{len(merge_log)}**")
    if edges is not None:
        lines.append(f"- 血缘边数：**{len(edges)}**")
    lines.append(f"- 高风险许可证资产（风险等级 ≥ 4）：**{high_risk}**")
    lines.append(f"- AI 专用许可证资产：**{ai_count}**")
    lines.append(f"- 待人工确认（未声明或未识别）：**{unknown}**")
    if evidence_summary:
        lines.append("")
        lines.append("### 远程证据补全（evidence_enricher）")
        lines.append("")
        lines.append(
            f"- 支持远程证据的 purl 数：**{evidence_summary.get('supported_purls', 0)}**"
        )
        lines.append(f"- 成功补全远程证据数：**{evidence_summary.get('remote_ok', 0)}**")
        lines.append(f"- 网络失败降级数：**{evidence_summary.get('network_error', 0)}**")
        lines.append(
            f"- 处理前无证据资产：**{evidence_summary.get('assets_without_evidence_before', 0)}**"
        )
        lines.append(
            f"- 处理后无证据资产：**{evidence_summary.get('assets_without_evidence_after', 0)}**"
        )
    lines.append("")

    # 二、P/D/P 判定结论（ModelScope 适配：绿灯出表 / 红灯出图）
    verdicts = {
        asset.get("canonical_id") or asset.get("name"): pd_judge(
            assessments[asset.get("canonical_id") or asset.get("name")]
        )
        for asset in assets
    }
    safe_count = sum(1 for code, _ in verdicts.values() if code == "SAFE")
    potential_count = sum(1 for code, _ in verdicts.values() if code == "RISK_POTENTIAL")
    risk_count = sum(1 for code, _ in verdicts.values() if code == "RISK")
    lines.append("## 二、P/D/P 判定结论")
    lines.append("")
    lines.append(
        f"- 判定结果：🟢 安全 **{safe_count}** 个 / 🟡 潜在风险 **{potential_count}** 个 / 🔴 风险 **{risk_count}** 个"
    )
    if risk_count or potential_count:
        lines.append(
            "- 输出方式：存在 🟡/🔴 资产，需配合 **风险血缘图**（--model / --diff）查看传播路径，本清单附判定依据。"
        )
    else:
        lines.append("- 输出方式：**绿灯出表**——全部资产合规，仅输出本中文表格（10 秒内完成）。")
    lines.append("")
    lines.append("### 模型判定表")
    lines.append("")
    rows = []
    for asset in sorted(
        assets,
        key=lambda item: (
            -(assessments[item.get("canonical_id") or item.get("name")]["risk_level"] or 0),
            str(item.get("name") or ""),
        ),
    ):
        key = asset.get("canonical_id") or asset.get("name")
        assessment = assessments[key]
        code, reason = verdicts[key]
        version = asset.get("version") or "—"
        lic = license_display(asset.get("license"), assessment)
        rows.append(
            [
                asset.get("name") or "—",
                version,
                lic,
                PDP_LIGHT.get(code, code),
                reason,
            ]
        )
    lines.extend(_table(["模型名", "版本", "许可", "判定结果", "判定依据"], rows))
    lines.append("")

    # 三、许可证风险分布
    lines.append("## 三、许可证风险分布")
    lines.append("")
    risk_dist = {}
    for a in assessments.values():
        level = a["risk_level"]
        risk_dist[level] = risk_dist.get(level, 0) + 1
    lines.extend(
        _table(
            ["风险等级", "资产数"],
            [
                [
                    f"{level}（{RISK_LEVEL_ZH.get(level, '待人工确认')}）",
                    count,
                ]
                for level, count in sorted(
                    risk_dist.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)
                )
            ],
        )
    )
    lines.append("")
    lines.append("### 许可证类别分布")
    lines.append("")
    category_dist = {}
    for a in assessments.values():
        category_dist[a["category_zh"]] = category_dist.get(a["category_zh"], 0) + 1
    lines.extend(
        _table(
            ["许可证类别", "资产数"],
            [[category, count] for category, count in sorted(category_dist.items())],
        )
    )
    lines.append("")

    # 三、重点资产
    attention = [
        asset
        for asset in assets
        if (assessments[asset.get("canonical_id") or asset.get("name")]["risk_level"] or 0) >= 4
        or assessments[asset.get("canonical_id") or asset.get("name")]["is_ai_license"]
    ]
    lines.append("## 四、重点资产（高风险 / AI 专用）")
    lines.append("")
    if attention:
        rows = []
        for asset in sorted(
            attention, key=lambda item: str(item.get("canonical_id") or item.get("name"))
        ):
            key = asset.get("canonical_id") or asset.get("name")
            assessment = assessments[key]
            rows.append(
                [
                    asset.get("canonical_id") or "—",
                    ASSET_TYPE_ZH.get(asset.get("asset_type"), asset.get("asset_type") or "—"),
                    license_display(asset.get("license"), assessment),
                    assessment["risk_level"] if assessment["risk_level"] is not None else "待人工确认",
                    assessment["category_zh"],
                    "是" if assessment["is_ai_license"] else "否",
                ]
            )
        lines.extend(_table(["canonical_id", "类型", "许可证", "风险等级", "类别", "AI 专用"], rows))
    else:
        lines.append("未发现风险等级 ≥ 4 或 AI 专用许可证的资产。")
    lines.append("")

    # 五、资产明细
    lines.append("## 五、资产明细")
    lines.append("")
    rows = []
    for asset in sorted(
        assets,
        key=lambda item: (
            -(assessments[item.get("canonical_id") or item.get("name")]["risk_level"] or 0),
            str(item.get("asset_type") or ""),
            str(item.get("canonical_id") or item.get("name") or ""),
        ),
    ):
        key = asset.get("canonical_id") or asset.get("name")
        assessment = assessments[key]
        version = asset.get("version") or "—"
        lic = license_display(asset.get("license"), assessment)
        risk = (
            f"{assessment['risk_level']}（{RISK_BADGE.get(assessment['risk_level'], '')}）"
            if assessment["risk_level"] is not None
            else "待人工确认"
        )
        best = best_evidence_level(asset) or "—"
        links = format_links(evidence_links(asset))
        purls = "；".join(asset.get("purls") or [])
        rows.append(
            [
                asset.get("canonical_id") or "—",
                ASSET_TYPE_ZH.get(asset.get("asset_type"), asset.get("asset_type") or "—"),
                asset.get("name") or "—",
                version,
                lic,
                risk,
                assessment["category_zh"],
                best,
                links,
                purls,
            ]
        )
    lines.extend(
        _table(
            ["canonical_id", "类型", "名称", "版本", "许可证", "风险", "类别", "最佳证据", "来源链接", "purl"],
            rows,
        )
    )
    lines.append("")

    # 六、待人工确认
    lines.append("## 六、待人工确认")
    lines.append("")
    unknown_assets = [
        asset
        for asset in assets
        if assessments[asset.get("canonical_id") or asset.get("name")]["unknown_items"]
    ]
    if unknown_assets:
        rows = []
        for asset in sorted(
            unknown_assets, key=lambda item: str(item.get("canonical_id") or item.get("name"))
        ):
            assessment = assessments[asset.get("canonical_id") or asset.get("name")]
            rows.append(
                [
                    asset.get("canonical_id") or "—",
                    str(asset.get("license") or "未声明"),
                    "；".join(assessment["unknown_items"]),
                ]
            )
        lines.extend(_table(["canonical_id", "原始许可证字段", "未识别项"], rows))
    else:
        lines.append("未发现无法识别的许可证片段。")
    lines.append("")

    # 七、风险说明与免责声明
    lines.append("## 七、风险说明")
    lines.append("")
    lines.append("- 风险等级 1–5 来自 license_db 规则库：1–2 低风险（宽松/公有领域）；3 中风险（弱 copyleft / AI 受限）；4–5 高风险（强 copyleft / 网络 copyleft）。")
    lines.append("- 🔴 高：许可证含传染性或强约束条款（GPL/AGPL/SSPL 等），使用/分发前必须核对义务。")
    lines.append("- ⚪ 待确认：组件未声明许可证，或存在规则库无法识别的许可证写法，需人工核对官方文本。")
    lines.append("- AI 专用许可证（Llama 2 社区许可、OpenRAIL-M、Gemma 条款等）非 SPDX，义务条款需重点人工核对。")
    lines.append("- ModelScope 场景：非标协议（如 qwen-research）不在规则库中，一律判定为潜在风险（黄灯），需人工核对官方许可文本后确认。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> **免责声明**：本清单由开源账本自动生成，基于证据的辅助审计，不构成法律意见，也不能替代针对具体许可证、司法辖区和业务模式的执业法律审查。")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 五、流水线入口
# ---------------------------------------------------------------------------


def generate_from_bom(
    bom_path: str,
    *,
    snapshot_id: str | None = None,
    deduplicate: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    """BOM → bom_adapter.convert_bom → entity_resolver.deduplicate_assets → 中文清单。

    返回 (去重后资产列表, 渲染好的 Markdown 文本)。
    """
    bom_adapter = _import("bom_adapter")
    path = Path(bom_path)
    bom = bom_adapter.load_json(path)
    if not isinstance(bom, dict):
        raise ValueError(f"BOM 根节点必须是对象：{path}")

    sid = snapshot_id or f"basic-{datetime.now().strftime('%Y%m%d')}"
    raw_assets = bom_adapter.convert_bom(
        bom=bom,
        source_file=str(path.resolve()),
        snapshot_id=sid,
    )
    if deduplicate:
        assets, merge_log = deduplicate_assets(raw_assets)
    else:
        assets, merge_log = raw_assets, []
    md = render_report(
        assets,
        bom_path=str(path),
        snapshot_id=sid,
        raw_count=len(raw_assets),
        merge_log=merge_log,
    )
    return assets, md


def generate(bom_path: str) -> tuple[list[dict[str, Any]], str]:
    """兼容旧调用：返回 (资产列表, Markdown 文本)。"""
    return generate_from_bom(bom_path)


# ---------------------------------------------------------------------------
# 六、CLI
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description="开源账本·基础层：中文开源合规清单生成器（v3 ModelScope 适配）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bom", help="CycloneDX BOM JSON 路径（自动：bom_adapter → entity_resolver → 渲染）")
    group.add_argument("--assets", help="资产 JSON 路径（bom_adapter / entity_resolver / main.py 产物，直接渲染）")
    parser.add_argument("-o", "--output", default="开源合规清单.md", help="输出 Markdown 路径")
    parser.add_argument("--stdout", action="store_true", help="只输出到屏幕，不写文件")
    parser.add_argument("--snapshot-id", default=None, help="快照 ID（默认 basic-YYYYMMDD）")
    args = parser.parse_args(argv)

    try:
        if args.bom:
            assets, md = generate_from_bom(args.bom, snapshot_id=args.snapshot_id)
        else:
            with open(args.assets, encoding="utf-8") as f:
                assets = json.load(f)
            if not isinstance(assets, list):
                raise ValueError(f"资产文件顶层必须是数组：{args.assets}")
            md = render_report(assets, bom_path=args.assets, snapshot_id=args.snapshot_id)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    if args.stdout:
        print(md)
        return 0

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[完成] 共 {len(assets)} 个资产（去重后），清单已写入：{out.resolve()}")
    return 0


if __name__ == "__main__":
    # Windows 终端 UTF-8，避免中文乱码。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
