#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report_basic.py — 基础层中文合规清单生成器（模块5，成员 C）

功能：
    输入一个 CycloneDX BOM（JSON，cdxgen 生成或手工构造），输出一份可直接提交的
    中文《开源及第三方资源使用清单》Markdown 文档，包含：
      - 跨生态去重后的资产列表（同一模型在多个生态出现时合并，保留来源上下文）
      - 许可证识别与高风险标注（GPL/AGPL/SSPL 等）
      - 来源链接与证据位置
      - 表格末尾免责声明

用法：
    python report_basic.py --bom sample_bom.json -o 开源合规清单.md
    python report_basic.py --bom sample_bom.json          # 默认输出到 ./开源合规清单.md
    python report_basic.py --bom sample_bom.json --stdout # 只打印到屏幕，不写文件

模块间接口约定（成员 A/B 交付后如何对接）：
    - 本模块以 --bom 指向的 CycloneDX BOM 为最终输入来源，可独立运行。
    - 模块2（实体对齐）交付后：将 _merge_entities() 替换为对 entity_resolver 的调用；
      若 A 侧输出的是下方 ASSET_SCHEMA 所述的合并资产 JSON，可新增 --assets 参数直接读取。
    - 模块3（证据链补全）交付后：将 _extract_source_url() 替换为对 evidence_enricher 的调用。
    - 模块4（许可证规则库）交付后：将 _classify_license() 替换为对 license_db 的调用。
    - 中间资产字段名以本文件底部 ASSET_SCHEMA 为准，A/B 模块输出 JSON 时对齐即可无缝对接。

免责声明：
    本清单由开源账本自动生成，基于证据的辅助审计，不构成法律意见。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 一、许可证风险分级（内置简化版，待模块4 license_db.py 交付后替换）
# ---------------------------------------------------------------------------

# 高风险：传染性/强保护型许可证
HIGH_RISK_LICENSES = {
    "GPL-1.0-only", "GPL-1.0-or-later", "GPL-1.0+",
    "GPL-2.0-only", "GPL-2.0-or-later", "GPL-2.0+",
    "GPL-3.0-only", "GPL-3.0-or-later", "GPL-3.0+",
    "AGPL-1.0-only", "AGPL-1.0-or-later",
    "AGPL-3.0-only", "AGPL-3.0-or-later", "AGPL-3.0+",
    "SSPL-1.0",
    "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "CC-BY-ND-4.0", "CC-BY-NC-ND-4.0",
}

# 中风险：弱传染型 / 带额外条件
MEDIUM_RISK_LICENSES = {
    "LGPL-2.0-only", "LGPL-2.0-or-later", "LGPL-2.1-only", "LGPL-2.1-or-later",
    "LGPL-3.0-only", "LGPL-3.0-or-later",
    "MPL-1.1", "MPL-2.0", "EPL-1.0", "EPL-2.0", "CDDL-1.0", "CDDL-1.1",
}

# AI 模型常见非 SPDX 许可证（可识别的写法；完整条款需人工核对）
AI_LICENSE_MAP = {
    "llama2": "Llama-2-Community（非 SPDX，需人工核对条款）",
    "llama3": "Llama-3-Community（非 SPDX，需人工核对条款）",
    "openrail-m": "OpenRAIL-M（非 SPDX，需人工核对条款）",
    "openrail": "OpenRAIL（非 SPDX，需人工核对条款）",
    "gemma": "Gemma Terms（非 SPDX，需人工核对条款）",
    "apache-2.0": "Apache-2.0",
    "mit": "MIT",
    "bsd-3-clause": "BSD-3-Clause",
    "cc-by-4.0": "CC-BY-4.0",
}

HIGH_RISK_NOTE = {
    "GPL": "高风险｜传染性许可证（GPL 类）：分发或修改时需遵守开源义务，可能影响整体分发方式",
    "AGPL": "高风险｜传染性许可证（AGPL 类）：网络服务方式使用同样触发开源义务",
    "SSPL": "高风险｜SSPL：商业托管场景义务苛刻，需重点人工核对",
    "CC-BY-NC": "高风险｜非商业用途限制：商业使用需另行授权",
    "CC-BY-ND": "高风险｜禁止演绎：不得修改后分发",
    "default": "高风险｜强约束许可证，建议人工核对义务条款",
}

ECOSYSTEM_LABEL = {
    "pypi": "PyPI",
    "npm": "npm",
    "huggingface": "HuggingFace",
    "github": "GitHub",
    "maven": "Maven",
    "golang": "Go",
}


# ---------------------------------------------------------------------------
# 二、BOM 读取
# ---------------------------------------------------------------------------

def load_bom(path: str) -> dict:
    """读取并校验 CycloneDX BOM JSON。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"BOM 文件不存在: {p}")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("bomFormat") != "CycloneDX":
        raise ValueError(f"{p.name} 不是 CycloneDX BOM（bomFormat 应为 CycloneDX）")
    return data


def _iter_components(bom: dict):
    """产出 BOM 中全部组件（不含 metadata.component 根组件，避免把项目自身当依赖列出）。"""
    root_ref = None
    meta = bom.get("metadata") or {}
    if meta.get("component"):
        root_ref = meta["component"].get("bom-ref")
    for comp in bom.get("components", []):
        if comp.get("bom-ref") == root_ref:
            continue
        yield comp


# ---------------------------------------------------------------------------
# 三、实体对齐（简化版，模块2 交付后替换为 entity_resolver 调用）
# ---------------------------------------------------------------------------

def _model_merge_key(comp: dict) -> tuple:
    """AI 模型的合并键：name + modelFamily + 证据位置。"""
    props = {p.get("name"): p.get("value") for p in comp.get("properties", [])}
    family = props.get("cdx:ai:modelFamily", "")
    ev_locs = tuple(sorted(_evidence_locations(comp)))
    return ("model", comp.get("name", ""), family, ev_locs)


def _library_merge_key(comp: dict) -> tuple:
    """普通库的合并键：purl（同名不同版本/不同 hash 不合并）。"""
    return ("library", comp.get("purl", comp.get("bom-ref", "")))


def _evidence_locations(comp: dict) -> list:
    """提取 evidence.occurrences[].location 列表。"""
    locs = []
    for occ in (comp.get("evidence") or {}).get("occurrences", []):
        loc = occ.get("location")
        if loc:
            locs.append(loc)
    return locs


def merge_entities(components: list) -> list:
    """
    跨生态实体对齐（简化版）：
      - 普通库：按 purl 严格去重（同名不同版本不合并）；
      - AI 模型：name + modelFamily + 证据位置 相同则合并，保留全部 purl 与来源上下文。
    返回合并后的资产列表（ASSET_SCHEMA 见文件底部）。
    """
    groups = {}
    for comp in components:
        ctype = comp.get("type", "")
        if ctype == "machine-learning-model":
            key = _model_merge_key(comp)
        else:
            key = _library_merge_key(comp)
        groups.setdefault(key, []).append(comp)

    assets = []
    for key, comps in groups.items():
        first = comps[0]
        ctype = first.get("type", "")
        if ctype == "machine-learning-model":
            props = {p.get("name"): p.get("value") for p in first.get("properties", [])}
            purls = sorted({c.get("purl") for c in comps if c.get("purl")})
            asset = {
                "asset_id": first.get("name", ""),
                "type": ctype,
                "name": first.get("name", ""),
                "version": first.get("version", ""),
                "purls": purls,
                "ecosystems": sorted({_ecosystem_of(p) for p in purls if _ecosystem_of(p)}),
                "model_family": props.get("cdx:ai:modelFamily", ""),
                "licenses": _collect_licenses(comps),
                "evidence_locations": sorted({loc for c in comps for loc in _evidence_locations(c)}),
                "merged_from": [c.get("bom-ref", "") for c in comps],
            }
        else:
            asset = {
                "asset_id": f"{first.get('name', '')}@{first.get('version', '')}",
                "type": ctype,
                "name": first.get("name", ""),
                "version": first.get("version", ""),
                "purls": [first.get("purl", "")] if first.get("purl") else [],
                "ecosystems": [_ecosystem_of(first.get("purl", ""))] if _ecosystem_of(first.get("purl", "")) else [],
                "model_family": "",
                "licenses": _collect_licenses([first]),
                "evidence_locations": _evidence_locations(first),
                "merged_from": [first.get("bom-ref", "")],
            }
        asset["source_urls"] = _extract_source_urls(first)
        assets.append(asset)
    return assets


def _ecosystem_of(purl: str) -> str:
    """从 purl 提取生态名，例如 pkg:pypi/... -> pypi。"""
    if not purl or not purl.startswith("pkg:"):
        return ""
    parts = purl.split("/")
    return parts[0].split(":")[1] if len(parts) >= 2 else ""


def _collect_licenses(comps: list) -> list:
    """收集组件声明的许可证 id（保持出现顺序、去重）。"""
    out = []
    for comp in comps:
        for lic in comp.get("licenses", []):
            l = lic.get("license") or {}
            lid = l.get("id") or l.get("name") or ""
            if lid and lid not in out:
                out.append(lid)
    return out


# ---------------------------------------------------------------------------
# 四、证据补全（简化版，模块3 交付后替换为 evidence_enricher 调用）
# ---------------------------------------------------------------------------

def _extract_source_urls(comp: dict) -> list:
    """
    从组件中提取可点击的来源链接，优先级：
      1. externalReferences 中 type=distribution/vcs/website 的 url；
      2. evidence.identity[].methods[].value（cdxgen 远程扫描把 API 地址放在这里）；
    没有则返回空列表（降级为 L1：仅本地证据位置，不丢失组件）。
    """
    urls = []
    for ref in comp.get("externalReferences", []):
        rtype = ref.get("type", "")
        url = ref.get("url", "")
        if url and rtype in ("distribution", "vcs", "website", "documentation"):
            urls.append(url)
    if not urls:
        for ident in (comp.get("evidence") or {}).get("identity", []):
            for m in ident.get("methods", []):
                v = m.get("value", "")
                if v.startswith("http://") or v.startswith("https://"):
                    urls.append(v)
    # 去重保序
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


# ---------------------------------------------------------------------------
# 五、许可证分类（简化版，模块4 交付后替换为 license_db 调用）
# ---------------------------------------------------------------------------

def classify_license(licenses: list, comp_type: str) -> tuple:
    """
    返回 (展示名, 风险等级, 风险提示)。
    风险等级：high / medium / low / unknown
    """
    if not licenses:
        if comp_type == "machine-learning-model":
            return "未声明", "unknown", "待人工确认｜模型未声明许可证，不得默认猜测（模型卡缺失≠无许可证）"
        return "未声明", "unknown", "待人工确认｜未声明许可证，需向提供方核实"

    labels, levels = [], []
    for lid in licenses:
        low = lid.lower().strip()
        display = AI_LICENSE_MAP.get(low, lid)
        labels.append(display)

        if low in {k.lower() for k in HIGH_RISK_LICENSES}:
            levels.append("high")
        elif low in {k.lower() for k in MEDIUM_RISK_LICENSES}:
            levels.append("medium")
        elif low.startswith(("gpl", "agpl", "sspl")):
            levels.append("high")
        else:
            levels.append("low")

    worst = "high" if "high" in levels else ("medium" if "medium" in levels else "low")
    label = "、".join(labels)

    if worst == "high":
        for prefix, note in HIGH_RISK_NOTE.items():
            if any(l.lower().startswith(prefix.lower()) for l in licenses):
                return label, worst, note
        return label, worst, HIGH_RISK_NOTE["default"]
    if worst == "medium":
        return label, worst, "中风险｜弱传染性许可证（LGPL/MPL/EPL 类），分发时注意对应义务"
    return label, worst, "低风险｜宽松许可证"


# ---------------------------------------------------------------------------
# 六、Markdown 渲染
# ---------------------------------------------------------------------------

RISK_ICON = {"high": "🔴 高", "medium": "🟠 中", "low": "🟢 低", "unknown": "⚪ 待确认"}


def _cell(text: str) -> str:
    """清洗单元格文本，避免破坏表格。"""
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(assets: list, bom_meta: dict) -> str:
    """渲染中文 Markdown 清单。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("# 开源及第三方资源使用清单")
    lines.append("")
    lines.append(f"> 生成时间：{now}")
    lines.append(f"> 输入 BOM：{bom_meta.get('serialNumber', '—')}")
    lines.append(f"> 生成工具：开源账本（基础层）· report_basic.py")
    lines.append("")

    # 统计摘要
    total = len(assets)
    high = sum(1 for a in assets if classify_license(a["licenses"], a["type"])[1] == "high")
    unknown = sum(1 for a in assets if not a["licenses"])
    merged = sum(1 for a in assets if len(a.get("merged_from", [])) > 1)
    lines.append("## 一、统计摘要")
    lines.append("")
    lines.append(f"- 资产总数（去重后）：**{total}**")
    lines.append(f"- 高风险许可证资产：**{high}**")
    lines.append(f"- 待人工确认（未声明许可证）：**{unknown}**")
    lines.append(f"- 跨生态合并去重资产：**{merged}**")
    lines.append("")

    # 资产明细表
    lines.append("## 二、资产明细")
    lines.append("")
    lines.append("| 资源名称 | 版本 | 许可证 | 风险 | 来源链接 | 证据位置 | 来源生态 |")
    lines.append("|---|---|---|---|---|---|---|")
    for a in sorted(assets, key=lambda x: (x["type"] != "machine-learning-model", x["name"].lower())):
        name = a["name"]
        if a["model_family"]:
            name = f"{name}（{a['model_family']}）"
        version = a["version"] or "—"
        lic_label, risk, risk_note = classify_license(a["licenses"], a["type"])
        lic_cell = f"{lic_label}<br>{risk_note}"
        if a["purls"]:
            purl_txt = _cell("；".join(a["purls"]))
            lic_cell = f"{lic_cell}<br><small>{purl_txt}</small>"
        src = "；".join(f"[链接]({_cell(u)})" for u in a["source_urls"]) if a["source_urls"] else "未提供 URL（本地证据 L1）"
        ev = "；".join(_cell(l) for l in a["evidence_locations"]) if a["evidence_locations"] else "—"
        eco = "、".join(ECOSYSTEM_LABEL.get(e, e) for e in a["ecosystems"]) if a["ecosystems"] else "—"
        lines.append(f"| {_cell(name)} | {_cell(version)} | {lic_cell} | {RISK_ICON[risk]} | {src} | {ev} | {eco} |")
    lines.append("")

    # 风险说明
    lines.append("## 三、风险说明")
    lines.append("")
    lines.append("- 🔴 高：许可证含传染性或强约束条款，使用/分发前必须核对义务（详见各条提示）。")
    lines.append("- ⚪ 待确认：组件未声明许可证，或声明为非 SPDX 的 AI 专用条款，需人工核对官方文本。")
    lines.append("")

    # 免责声明
    lines.append("---")
    lines.append("")
    lines.append("> **免责声明**：本清单由开源账本自动生成，基于证据的辅助审计，不构成法律意见，也不能替代针对具体许可证、司法辖区和业务模式的执业法律审查。")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 七、主流程
# ---------------------------------------------------------------------------

def generate(bom_path: str) -> list:
    """完整流水线：BOM -> 对齐 -> 证据 -> 分类 -> 资产列表。"""
    bom = load_bom(bom_path)
    components = list(_iter_components(bom))
    assets = merge_entities(components)
    return assets, bom


def main(argv=None):
    parser = argparse.ArgumentParser(description="开源账本·基础层：中文开源合规清单生成器")
    parser.add_argument("--bom", required=True, help="CycloneDX BOM JSON 路径")
    parser.add_argument("-o", "--output", default="开源合规清单.md", help="输出 Markdown 路径")
    parser.add_argument("--stdout", action="store_true", help="只输出到屏幕，不写文件")
    args = parser.parse_args(argv)

    try:
        assets, bom = generate(args.bom)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    md = render_markdown(assets, bom)
    if args.stdout:
        print(md)
        return 0

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[完成] 共 {len(assets)} 个资产（去重后），清单已写入：{out.resolve()}")
    return 0


# ---------------------------------------------------------------------------
# ASSET_SCHEMA（模块间对接用的中间资产格式，A/B 模块输出 JSON 时对齐此字段）
# ---------------------------------------------------------------------------
ASSET_SCHEMA = {
    "asset_id": "资产唯一标识（模型用名称，库用 name@version）",
    "type": "library | machine-learning-model | dataset",
    "name": "资源名称",
    "version": "版本或空串",
    "purls": ["全部来源 purl（跨生态合并后多个）"],
    "ecosystems": ["pypi", "npm", "huggingface", ...],
    "model_family": "AI 模型族（非模型为空串）",
    "licenses": ["声明的许可证 id"],
    "evidence_locations": ["evidence.occurrences[].location"],
    "source_urls": ["可点击来源链接"],
    "merged_from": ["被合并的原始 bom-ref"],
}

if __name__ == "__main__":
    sys.exit(main())
