#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开源账本统一入口。

只编排仓库中实际存在的模块函数：

基础模式：
    bom_adapter.convert_bom
    -> entity_resolver.deduplicate_assets
    -> evidence_enricher.enrich_assets
    -> work.extract_modelscope_lineage.extract（ModelScope 模型 BOM）

深度模式：
    对 t0/t1 分别执行基础数据转换，然后：
    build_graph.build_graph
    -> delta_engine.detect_delta
    -> propagation_engine.propagate

基础模式 Markdown 报告由 report_basic.py 生成；深度/diff 模式由 report_enhanced.py 生成。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import report_basic
import export_bom



DECISION_ZH = {
    "RISK_CONFIRMED": "已确认风险",
    "RISK_POTENTIAL": "潜在风险",
    "UNDETERMINED": "待确认",
}

CHANGE_TYPE_ZH = {
    "license_changed": "许可证变更",
    "ancestor_added": "新增祖先",
    "ancestor_removed": "移除祖先",
    "dataset_added": "新增训练数据集",
    "dataset_removed": "移除训练数据集",
    "evidence_downgrade": "证据等级下降",
}

HF_MODEL_TYPES = {"machine-learning-model", "model"}
HF_LINEAGE_EDGE_TYPES = {"derived_from", "trained_on"}
HF_PURL_PREFIX = "pkg:huggingface/"
MODELSCOPE_PURL_PREFIX = "pkg:modelscope/"

# 判定中文标签（与 risk_evaluator 保持一致，含绿灯 SAFE）
_DECISION_ZH = {
    "RISK_CONFIRMED": "高风险（红）",
    "RISK_POTENTIAL": "潜在风险（黄）",
    "SAFE": "安全（绿）",
    "UNDETERMINED": "待确认（灰）",
}

# ---- ModelScope 项目扫描（BOM-Driven）配置 ----
_BOM_FILENAMES = {"bom.json", "cyclonedx.json", "sbom.json"}
_CONFIG_FILENAMES = {"configuration.json", "config.json"}
_CONFIG_KEYS = {"model_id", "modelId", "base_model", "baseModel"}
_TEXT_SUFFIXES = {".py", ".yaml", ".yml"}
_TEXT_FILENAME = "readme.md"
_SKIP_DIRS = {"venv", "node_modules", "__pycache__", "site-packages", "dist", "build"}

# 合法的 namespace/name 形态（用于 BOM/config 提取结果的过滤）。
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

# 文本扫描：namespace/name，但排除 URL（前一个字符不能是 URL/路径分隔符、点、@ 等）。
_TEXT_MODEL_RE = re.compile(
    r"(?<![A-Za-z0-9._:/@-])"
    r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+"
    r"(?![A-Za-z0-9._-])"
)


def _model_output_dir(root: Path, model: str) -> Path:
    """返回模型模式独立产物目录，避免不同模型互相覆盖。"""
    safe_name = model.strip().strip("/").replace("/", "__")
    return root / "outputs" / safe_name


def _project_output_dir(root: Path, project_path: Path) -> Path:
    """返回项目模式独立产物目录，避免不同项目互相覆盖。"""
    safe_name = project_path.name.strip().strip("/").replace("/", "__")
    return root / "outputs" / safe_name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析统一入口参数。"""
    parser = argparse.ArgumentParser(
        description="开源账本统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python main.py --mode basic --input bom.json --output report.md\n"
            "  python main.py --mode deep --before t0_bom.json --after t1_bom.json "
            "--output report.md\n"
            "  python main.py --model TheBloke/Llama-2-7B-Chat-GGUF "
            "--output report.md\n"
            "  python main.py --project test-project/ --output report.md"
        ),
    )
    parser.add_argument("--mode", choices=("basic", "deep"), required=False,
                        help="基础/深度模式（与 --model / --diff 二选一）")
    parser.add_argument("--model", type=str, default=None,
                        help="HF 模型名，触发模型血缘扫描模式（与 --mode / --diff / --project 二选一）")
    parser.add_argument("--project", type=Path, default=None,
                        help="项目路径，触发项目扫描模式：识别项目内 ModelScope 模型并生成合并血缘图")
    parser.add_argument("--diff", action="store_true",
                        help="BOM 对比模式，输出风险报告（与 --model / --mode / --project 互斥）")
    parser.add_argument("--input", type=Path, help="基础模式的 CycloneDX BOM")
    parser.add_argument("--before", type=Path, help="深度/diff 模式的 t0 CycloneDX BOM")
    parser.add_argument("--after", type=Path, help="深度/diff 模式的 t1 CycloneDX BOM")
    parser.add_argument("--output", type=Path, required=False, default=None, help="输出 Markdown 报告（模型/项目模式省略时自动生成）")
    args = parser.parse_args(argv)

    if args.diff and (args.model is not None or args.mode is not None or args.project is not None):
        parser.error("--diff 与 --model / --mode / --project 互斥，请二选一")
    if args.model is not None and (args.mode is not None or args.project is not None):
        parser.error("--model 与 --mode / --project 互斥，请二选一")
    if args.project is not None and args.mode is not None:
        parser.error("--project 与 --mode 互斥，请二选一")
    if not args.diff and args.model is None and args.mode is None and args.project is None:
        parser.error("必须提供 --diff 或 --mode（basic/deep）或 --model 或 --project")
    if args.diff and (args.before is None or args.after is None):
        parser.error("--diff 必须同时提供 --before 和 --after")
    if args.mode == "basic" and args.input is None:
        parser.error("--mode basic 必须提供 --input")
    if args.mode == "deep" and (args.before is None or args.after is None):
        parser.error("--mode deep 必须同时提供 --before 和 --after")
    if args.output is None:
        root = Path(__file__).resolve().parent
        if args.model is not None:
            args.output = _model_output_dir(root, args.model) / "report.md"
        elif args.project is not None:
            args.output = _project_output_dir(root, args.project) / "report.md"
        else:
            parser.error("--diff / --mode 模式必须提供 --output")
    return args


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _cell(value: Any) -> str:
    """把任意值转换为可安全放入 Markdown 表格单元格的文本。"""
    if value is None or value == "":
        return "-"
    text = str(value).replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")
    return text


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return ["_无数据_"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return lines


def _component_purls(component: dict[str, Any]) -> list[str]:
    """取组件的全部 purl（单 purl 字段 + bom-ref 里内嵌的 purl）。"""
    purls: list[str] = []
    single = component.get("purl")
    if isinstance(single, str) and single.strip():
        purls.append(single.strip())
    bom_ref = str(component.get("bom-ref") or "")
    if "pkg:" in bom_ref:
        embedded = bom_ref[bom_ref.index("pkg:"):]
        if embedded not in purls:
            purls.append(embedded)
    return purls


def _primary_asset_id(
    component: dict[str, Any],
    purl_to_canonical: dict[str, str],
) -> str | None:
    """在快照资产中查回该组件的 canonical_id（先 purl 精确，再名称兜底）。"""
    for purl in _component_purls(component):
        canonical_id = purl_to_canonical.get(purl)
        if canonical_id:
            return canonical_id
    full_name = f"{component.get('group', '')}/{component.get('name', '')}".strip("/")
    if "/" in full_name:
        canonical_id = purl_to_canonical.get(f"pkg:modelscope/{full_name}")
        if canonical_id:
            return canonical_id
    return None


def _lineage_placeholder_asset(
    purl: str,
    evidence_level: str,
    snapshot_id: str,
    source_file: str,
) -> dict[str, Any] | None:
    """为"只在 pedigree.ancestors 里出现、BOM 未单列"的祖先建占位节点。

    时间化对比要求 t0/t1 图包含同一批祖先节点，否则祖先本身消失后
    变更事件与传播路径都会断链；占位节点显式标注 MISSING_ANCESTOR。
    """
    import bom_adapter

    identity = bom_adapter.parse_purl_identity(purl)
    if identity is None:
        return None
    asset_type = "model"
    if "dataset" in purl:
        asset_type = "dataset"
    lower_name = identity.name.lower()
    if any(token in lower_name for token in ("-data", "_data", "dataset", "-set")):
        asset_type = "dataset"
    name = "/".join(part for part in (identity.namespace, identity.name) if part)
    entity_key, canonical_id, _ = bom_adapter.build_asset_identifiers(
        asset_type, identity.name, identity.version, [purl]
    )
    return {
        "entity_key": entity_key,
        "canonical_id": canonical_id,
        "asset_type": asset_type,
        "name": name or identity.name,
        "version": identity.version or "",
        "purls": [purl],
        "license": None,
        "evidence_chain": [
            {
                "evidence_level": evidence_level,
                "source_api": "bom",
                "source_url": None,
                "source_field": "pedigree.ancestors",
                "status": "missing_ancestor",
                "raw_value": purl,
            }
        ],
        "snapshot_id": snapshot_id,
        "merge_status": "KEPT_SEPARATE",
        "reason_code": "MISSING_ANCESTOR",
        "rule_version": "merge-policy-v2",
        "hashes": [],
        "source_file": source_file,
    }


def _extract_bom_lineage_edges(
    path: Path,
    bom: dict[str, Any],
    assets: list[dict[str, Any]],
    snapshot_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """只读 BOM 里固化的血缘：逐组件读取 pedigree.ancestors，产出 derived_from 边。

    --diff 的时间对比语义要求：t0/t1 必须用各自 BOM 内已固化的血缘，
    不允许回退到在线 API，否则"上周快照"会被今天的最新血缘替换。
    """
    components = bom.get("components")
    if not isinstance(components, list) or not components:
        return assets, []

    import bom_adapter

    source_file = str(path.resolve())
    purl_to_canonical: dict[str, str] = {}
    for asset in assets:
        canonical_id = asset.get("canonical_id")
        if not canonical_id:
            continue
        for purl in (asset.get("purls") or []):
            purl_to_canonical.setdefault(str(purl), str(canonical_id))

    merged = list(assets)
    known_ids = {a.get("canonical_id") for a in merged if a.get("canonical_id")}
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for component in components:
        if not isinstance(component, dict):
            continue
        source_id = _primary_asset_id(component, purl_to_canonical)
        if not source_id:
            continue
        ancestors = (component.get("pedigree") or {}).get("ancestors") or []
        if not isinstance(ancestors, list):
            continue
        for ancestor in ancestors:
            if not isinstance(ancestor, dict):
                continue
            ancestor_purl = str(ancestor.get("purl") or "").strip()
            if not ancestor_purl:
                continue
            evidence_level = str(ancestor.get("evidence_level") or "B")
            target_id = purl_to_canonical.get(ancestor_purl)
            if not target_id:
                placeholder = _lineage_placeholder_asset(
                    ancestor_purl, evidence_level, snapshot_id, source_file
                )
                if placeholder is None:
                    continue
                target_id = str(placeholder["canonical_id"])
                if target_id not in known_ids:
                    merged.append(placeholder)
                    known_ids.add(target_id)
                purl_to_canonical.setdefault(ancestor_purl, target_id)
            if not target_id or target_id == source_id:
                continue
            signature = (source_id, target_id, "derived_from")
            if signature in seen:
                continue
            seen.add(signature)
            edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "edge_type": "derived_from",
                    "evidence_level": evidence_level,
                    "source_field": "pedigree.ancestors",
                    "snapshot_id": snapshot_id,
                }
            )
    return merged, edges


def _bom_snapshot_timestamp(bom: dict[str, Any]) -> str | None:
    """读取 BOM 的 metadata.timestamp（兼容字符串与 CycloneDX 对象两种形态）。"""
    metadata = bom.get("metadata")
    if not isinstance(metadata, dict):
        return None
    value: Any = metadata.get("timestamp")
    if isinstance(value, dict):
        value = value.get("timestamp")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _format_snapshot_date(raw_timestamp: str | None) -> str:
    """把 BOM 时间戳格式化为 YYYY-MM-DD；缺失或无法解析返回"未知"。"""
    if not raw_timestamp:
        return "未知"
    text = str(raw_timestamp).strip()
    if not text:
        return "未知"
    # 先按 ISO 8601 解析（含 Z / ±HH:MM 偏移），失败再取前 10 位日期形态。
    candidate = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        return datetime.fromisoformat(candidate).date().isoformat()
    except ValueError:
        pass
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else "未知"


def _snapshot_interval_days(t0_date: str, t1_date: str) -> int | None:
    """计算两个已格式化日期的间隔天数；任一为"未知"时返回 None。"""
    if t0_date == "未知" or t1_date == "未知":
        return None
    try:
        start = datetime.fromisoformat(t0_date).date()
        end = datetime.fromisoformat(t1_date).date()
    except ValueError:
        return None
    return (end - start).days


def _diff_interval_lines(before_bom: dict[str, Any], after_bom: dict[str, Any]) -> list[str]:
    """生成"对比区间"说明行；任一侧缺 metadata.timestamp 时给出"未知"与提示，不报错。"""
    t0_raw = _bom_snapshot_timestamp(before_bom)
    t1_raw = _bom_snapshot_timestamp(after_bom)
    t0_date = _format_snapshot_date(t0_raw)
    t1_date = _format_snapshot_date(t1_raw)

    lines = [f"> 对比区间：{t0_date} → {t1_date}"]
    days = _snapshot_interval_days(t0_date, t1_date)
    if days is not None:
        lines.append(f"> 间隔天数：{days} 天")
    missing = [
        label
        for label, value in (("t0", t0_raw), ("t1", t1_raw))
        if not value
    ]
    if missing:
        lines.append(
            f"> 提示：{'/'.join(missing)} 的 BOM 缺少 metadata.timestamp，"
            "对比区间显示为「未知」；补齐该字段后即可显示真实区间。"
        )
    elif days is None:
        lines.append("> 提示：BOM 的 metadata.timestamp 无法解析为日期，对比区间显示为「未知」。")
    return lines


def _build_snapshot(path: Path, snapshot_id: str) -> dict[str, Any]:
    """按现有模块真实签名生成一个快照的资产、边和统计。

    血缘边一律来自 BOM 内固化的 pedigree.ancestors，保证 --diff 的时间对比语义：
    同一份 BOM 任何时候跑出的快照都完全一致，不受上游 API 当下状态影响。
    """
    import bom_adapter
    import entity_resolver
    import evidence_enricher

    bom = bom_adapter.load_json(path)
    if not isinstance(bom, dict):
        raise ValueError(f"BOM 根节点必须是对象：{path}")

    raw_assets = bom_adapter.convert_bom(
        bom=bom,
        source_file=str(path.resolve()),
        snapshot_id=snapshot_id,
    )
    deduplicated, merge_log = entity_resolver.deduplicate_assets(raw_assets)
    enriched, evidence_summary = evidence_enricher.enrich_assets(
        deduplicated,
        evidence_enricher.REQUEST_TIMEOUT_SECONDS,
    )
    assets, edges = _extract_bom_lineage_edges(path, bom, enriched, snapshot_id)
    return {
        "path": path,
        "snapshot_id": snapshot_id,
        "raw_assets": raw_assets,
        "assets": assets,
        "merge_log": merge_log,
        "evidence_summary": evidence_summary,
        "edges": edges,
        "snapshot_timestamp": _bom_snapshot_timestamp(bom),
    }


def _format_path(path: list[dict[str, Any]]) -> str:
    if not path:
        return "种子自身"
    parts = [str(path[0].get("source") or "")]
    for step in path:
        parts.append(str(step.get("target") or ""))
    return " -> ".join(parts)


def _render_deep_report(
    before: dict[str, Any],
    after: dict[str, Any],
    graph_before: dict[str, Any],
    graph_after: dict[str, Any],
    events: list[dict[str, Any]],
    propagated: dict[str, Any],
) -> str:
    import license_db

    propagated_events = propagated["events"]
    certificates = propagated["path_certificates"]
    change_distribution = Counter(event["change_type"] for event in events)
    decision_distribution = Counter(event["decision"] for event in propagated_events)

    lines = [
        "# 深度血缘风险传播报告",
        "",
        f"- 生成时间：{_utc_now()}",
        f"- t0 BOM：`{before['path']}`",
        f"- t1 BOM：`{after['path']}`",
        "- 图、Delta 和传播结果均由 `main.py` 调用仓库现有模块函数生成。",
        "",
        "## 图谱摘要",
        "",
    ]
    graph_rows = []
    for label, snapshot, graph in (
        ("t0", before, graph_before),
        ("t1", after, graph_after),
    ):
        graph_rows.append(
            [
                label,
                snapshot["snapshot_id"],
                len(snapshot["assets"]),
                len(snapshot["edges"]),
                graph["node_count"],
                graph["edge_count"],
                graph["scc_count"],
                sum(1 for node in graph["compressed"]["nodes"] if node["is_cycle"]),
            ]
        )
    lines.extend(
        _table(
            ["快照", "snapshot_id", "对齐后资产", "边", "图节点", "图边", "SCC", "循环 SCC"],
            graph_rows,
        )
    )

    lines.extend(["", "## 变更摘要", ""])
    lines.extend(
        _table(
            ["变更类型", "数量"],
            [
                [CHANGE_TYPE_ZH.get(change_type, change_type), count]
                for change_type, count in sorted(change_distribution.items())
            ],
        )
    )

    lines.extend(["", "## 许可证变更方向", ""])
    license_rows = []
    for event in events:
        if event.get("change_type") != "license_changed":
            continue
        before_state = event.get("before") or {}
        after_state = event.get("after") or {}
        direction = license_db.compare_direction(
            before_state.get("license"),
            after_state.get("license"),
        )
        license_rows.append(
            [
                event["event_id"],
                event["seed"],
                before_state.get("license"),
                after_state.get("license"),
                direction["direction"],
                "是" if direction["risk_increased"] else "否",
                "是" if direction["ai_involved"] else "否",
                event["decision"],
            ]
        )
    lines.extend(
        _table(
            ["事件 ID", "资产", "变更前", "变更后", "方向", "风险升高", "涉及 AI 许可证", "判定"],
            license_rows,
        )
    )

    lines.extend(["", "## 风险判定分布", ""])
    lines.extend(
        _table(
            ["判定", "事件数"],
            [
                [f"{decision}（{DECISION_ZH.get(decision, decision)}）", count]
                for decision, count in sorted(decision_distribution.items())
            ],
        )
    )

    lines.extend(["", "## 传播事件", ""])
    event_rows = []
    for event in propagated_events:
        event_rows.append(
            [
                event["event_id"],
                CHANGE_TYPE_ZH.get(event["change_type"], event["change_type"]),
                event["seed"],
                _format_path(event.get("path", [])),
                len(event.get("path", [])),
                event["evidence_level"],
                f"{event['decision']}（{DECISION_ZH.get(event['decision'], event['decision'])}）",
            ]
        )
    lines.extend(
        _table(
            ["事件 ID", "变更类型", "种子资产", "影响路径", "跳数", "证据", "判定"],
            event_rows,
        )
    )

    lines.extend(["", "## 路径证书", ""])
    certificate_rows = [
        [
            certificate["certificate_id"],
            certificate["affected"],
            certificate["change_type"],
            certificate["hop_count"],
            certificate["weakest_evidence"],
            certificate["decision"],
            certificate["termination"],
            "是" if certificate["missing_ancestor"] else "否",
            certificate["path_fingerprint"],
        ]
        for certificate in certificates
    ]
    lines.extend(
        _table(
            [
                "证书 ID",
                "受影响资产",
                "变更类型",
                "跳数",
                "最弱证据",
                "判定",
                "终止原因",
                "缺失祖先",
                "路径指纹",
            ],
            certificate_rows,
        )
    )

    lines.extend(
        [
            "",
            "## 免责声明",
            "",
            "本报告是基于结构化证据和血缘图的辅助分析结果，不构成法律意见。",
            "",
        ]
    )
    return "\n".join(lines)


def run_basic(args: argparse.Namespace) -> None:
    assets, bom = report_basic.generate(str(args.input))
    report = report_basic.render_markdown(assets, bom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"基础模式报告已写入：{args.output}")


def run_deep(args: argparse.Namespace) -> None:
    try:
        import build_graph
        import delta_engine
        import propagation_engine
    except ModuleNotFoundError as exc:
        if exc.name == "networkx":
            raise RuntimeError("深度模式需要安装 networkx，当前 Python 环境未找到该依赖。") from exc
        raise

    before = _build_snapshot(args.before, "t0")
    after = _build_snapshot(args.after, "t1")

    graph_before_obj = build_graph.build_graph(before["assets"], before["edges"])
    canonical_to_scc_before, compressed_before = build_graph.compress_scc(graph_before_obj)
    graph_before = build_graph.graph_to_dict(
        graph_before_obj,
        canonical_to_scc_before,
        compressed_before,
    )

    graph_after_obj = build_graph.build_graph(after["assets"], after["edges"])
    canonical_to_scc_after, compressed_after = build_graph.compress_scc(graph_after_obj)
    graph_after = build_graph.graph_to_dict(
        graph_after_obj,
        canonical_to_scc_after,
        compressed_after,
    )

    events = delta_engine.detect_delta(
        before["assets"],
        after["assets"],
        before["edges"],
        after["edges"],
    )
    propagated = propagation_engine.propagate(events, graph_before_obj, graph_after_obj)

    report = _render_deep_report(
        before,
        after,
        graph_before,
        graph_after,
        events,
        propagated,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"深度模式报告已写入：{args.output}")
    print(f"变更事件：{len(events)}，传播后事件：{len(propagated['events'])}")


def run_diff(before_bom: Path, after_bom: Path, output_path: Path) -> None:
    """BOM 对比模式：实体对齐 → Delta 检测 → 风险传播 → 增强报告。

    依次调用仓库现有模块：
    - entity_resolver.py：对 before 和 after 各跑一次（经 _build_snapshot）
    - delta_engine.py：检测两个快照之间的变更事件
    - propagation_engine.py：沿血缘图传播风险并生成路径证书
    - report_enhanced.py：渲染中文风险传播报告
    """
    try:
        import bom_adapter
        import build_graph
        import delta_engine
        import propagation_engine
        import report_enhanced
    except ModuleNotFoundError as exc:
        if exc.name == "networkx":
            raise RuntimeError("diff 模式需要安装 networkx，当前 Python 环境未找到该依赖。") from exc
        raise

    before = _build_snapshot(before_bom, "t0")
    after = _build_snapshot(after_bom, "t1")

    graph_before = build_graph.build_graph(before["assets"], before["edges"])
    graph_after = build_graph.build_graph(after["assets"], after["edges"])

    events = delta_engine.detect_delta(
        before["assets"],
        after["assets"],
        before["edges"],
        after["edges"],
    )
    propagated = propagation_engine.propagate(events, graph_before, graph_after)

    report = report_enhanced.render_report(
        propagated["events"],
        propagated["path_certificates"],
        str(before_bom),
        str(after_bom),
        interval_lines=_diff_interval_lines(
            bom_adapter.load_json(before_bom),
            bom_adapter.load_json(after_bom),
        ),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    decision_distribution = Counter(
        event["decision"] for event in propagated["events"]
    )
    print(f"diff 模式报告已写入：{output_path}")
    print(
        f"变更事件：{len(events)}，传播后事件：{len(propagated['events'])}，"
        f"路径证书：{len(propagated['path_certificates'])}"
    )
    print(f"三级判定分布：{dict(decision_distribution)}")


def _run_py_script(script: Path, script_args: list[str], label: str) -> None:
    """以子进程方式调用仓库脚本，转发输出，失败时抛异常。"""
    cmd = [sys.executable, str(script), *script_args]
    print(f"[{label}] 运行：{' '.join(cmd)}")
    env = os.environ.copy()
    # 强制子进程以 UTF-8 读写，避免 Windows 下中文输出被按本地代码页解码导致乱码。
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        cmd,
        cwd=str(script.parent),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    if proc.returncode != 0:
        raise RuntimeError(f"{label} 执行失败（退出码 {proc.returncode}）")


def _probe_modelscope(model: str) -> bool | None:
    """探测模型是否在 ModelScope：命中详情 API 返回 True，404 返回 False，网络异常返回 None。"""
    import modelscope_adapter

    model = model.strip().strip("/")
    if "/" not in model:
        return False
    ns, name = model.split("/", 1)
    try:
        detail = modelscope_adapter.fetch_model_detail(ns, name)
    except Exception:
        return None
    return detail is not None


def _run_hf_model(args: argparse.Namespace, model: str, root: Path) -> None:
    """HF 回退逻辑已隔离：本工具不再支持 Hugging Face 旧链路。

    必须抛错而不是静默 return：静默返回会让调用方（含 GitHub Action）
    以 0 退出码"成功"，但实际没有产出任何报告，形成假绿。
    """
    raise RuntimeError(
        f"模型 {model} 无法在 ModelScope 检索；本工具已移除 HF 回退逻辑。"
        "请改用 ModelScope 上的模型名，例如 Qwen/Qwen2.5-0.5B-Instruct。"
    )


def _risk_zh(value: Any) -> str:
    """把 1-5 许可证风险等级渲染为中文标签。"""
    if value is None:
        return "未识别"
    try:
        level = int(value)
    except (TypeError, ValueError):
        return str(value)
    return {
        1: "1（宽松）",
        2: "2（弱 copyleft）",
        3: "3（待确认）",
        4: "4（强 copyleft）",
        5: "5（受限）",
    }.get(level, str(level))


def _decision_zh(value: Any) -> str:
    """判定码 -> 中文标签（含绿灯）；未知码原样返回。"""
    if not value:
        return "-"
    return _DECISION_ZH.get(str(value), str(value))


def _enrich_risk_fields(
    assets_path: Path,
    edges_path: Path,
    graph_path: Path,
) -> dict[str, Any] | None:
    """给提取器产出的节点补上 risk_evaluator 的判定字段。

    A 的验收要求：输出节点要带 risk_level。这里在提取之后统一补字段，
    不改提取器、不改引擎，只调用 risk_evaluator.evaluate_model_risk：
      - 每个节点补 `risk_level`（1-5，未识别为 null）、`decision`、`decision_zh`
      - 图 JSON 的顶层补 `overall_decision` / `overall_decision_zh`
    """
    import risk_evaluator

    if not (assets_path.exists() and edges_path.exists()):
        return None
    assets = json.loads(assets_path.read_text(encoding="utf-8"))
    edges = json.loads(edges_path.read_text(encoding="utf-8"))
    if not isinstance(assets, list) or not isinstance(edges, list):
        return None

    result = risk_evaluator.evaluate_model_risk(assets, edges)
    node_results = {n.get("canonical_id"): n for n in result.get("nodes", [])}

    for asset in assets:
        node = node_results.get(asset.get("canonical_id"))
        if not node:
            continue
        asset["risk_level"] = node.get("risk_level")
        asset["decision"] = node.get("decision")
        asset["decision_zh"] = node.get("decision_zh")
        asset["license_recognized"] = node.get("license_recognized")
        # 兼容"risk_level 表示 1-5 等级"的既有口径：把判定原因一并写清。
        asset["risk_note"] = node.get("note")

    assets_path.write_text(
        json.dumps(assets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if graph_path.exists():
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        if isinstance(graph, dict):
            graph["overall_decision"] = result.get("overall_decision")
            graph["overall_decision_zh"] = result.get("overall_decision_zh")
            for node in graph.get("nodes", []):
                detail = node_results.get(node.get("canonical_id"))
                if not detail:
                    continue
                node["risk_level"] = detail.get("risk_level")
                node["decision"] = detail.get("decision")
                node["decision_zh"] = detail.get("decision_zh")
            graph_path.write_text(
                json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    return result


def _run_modelscope_model(args: argparse.Namespace, model: str, root: Path) -> None:
    """ModelScope 模型模式：提取血缘 → 风险判定 → 中文报告。"""
    model = model.strip().strip("/")
    extract_dir = _model_output_dir(root, model)

    started = datetime.now(timezone.utc)

    # 1. 提取血缘（详情 + lineage → assets/edges/graph.json）
    _run_py_script(
        root / "work" / "extract_modelscope_lineage.py",
        ["--model", model, "--output-dir", str(extract_dir)],
        "extract_modelscope_lineage",
    )

    # 2. 补风险判定字段（risk_level / decision），失败不阻断报告生成。
    try:
        _enrich_risk_fields(
            extract_dir / "assets.json",
            extract_dir / "edges.json",
            extract_dir / "graph.json",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"提示：风险判定字段补全失败（{type(exc).__name__}: {exc}）", file=sys.stderr)

    # 3. 导出标准 CycloneDX BOM，供 --diff 离线对比使用。
    bom_path = extract_dir / "bom.json"
    export_bom.export_bom(
        extract_dir / "assets.json",
        extract_dir / "edges.json",
        bom_path,
    )
    print(f"CycloneDX BOM 已写入：{bom_path}")

    duration_s = (datetime.now(timezone.utc) - started).total_seconds()
    report = _render_modelscope_report(model, extract_dir, duration_s)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"模型模式报告已写入：{args.output}")


def run_model(args: argparse.Namespace) -> None:
    """模型模式：自动探测 ModelScope 来源并运行对应流水线。"""
    model = args.model
    root = Path(__file__).resolve().parent

    is_modelscope = _probe_modelscope(model)
    if is_modelscope is True:
        _run_modelscope_model(args, model, root)
    elif is_modelscope is False:
        _run_hf_model(args, model, root)
    else:
        print("提示：ModelScope 探测因网络异常失败。", file=sys.stderr)
        _run_hf_model(args, model, root)


def _render_modelscope_report(
    model: str,
    extract_dir: Path,
    duration_s: float,
) -> str:
    """渲染 ModelScope 模型血缘扫描的中文 Markdown 报告。"""
    graph = json.loads((extract_dir / "graph.json").read_text(encoding="utf-8"))
    assets = json.loads((extract_dir / "assets.json").read_text(encoding="utf-8"))
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    aggregate_nodes = [a for a in assets if a.get("aggregate")]
    current = next((a for a in assets if not a.get("aggregate")), {})
    overall = graph.get("overall_decision") or current.get("decision")

    node_rows = [
        [
            n.get("canonical_id"),
            n.get("asset_type"),
            n.get("name") or n.get("canonical_id"),
            n.get("version"),
            n.get("license"),
            _risk_zh(n.get("risk_level")),
            _decision_zh(n.get("decision")),
        ]
        for n in nodes
    ]
    edge_rows = [
        [e.get("source"), e.get("edge_type"), e.get("target"), e.get("evidence_level")]
        for e in edges
    ]
    aggregate_rows = [
        [
            a.get("name"),
            a.get("count"),
            (a.get("evidence_chain") or [{}])[0].get("source_field") if a.get("evidence_chain") else None,
        ]
        for a in aggregate_nodes
    ]

    lines: list[str] = [
        "# AI 模型血缘扫描报告（ModelScope）",
        "",
        f"- 扫描模型：`{model}`",
        f"- 生成时间：{_utc_now()}",
        f"- 许可证：**{current.get('license') or '（未识别）'}**",
        f"- 整体判定：**{_decision_zh(overall) if overall else '（未判定）'}**",
        f"- 血缘图节点数：**{len(nodes)}**，边数：**{len(edges)}**",
        f"- 聚合节点：**{len(aggregate_nodes)}** 个（聚合 {sum(a.get('count', 0) for a in aggregate_nodes)} 个派生/祖先模型）",
        f"- SCC 强连通分量：**{graph.get('scc_count', 0)}**",
        f"- 本报告生成：**成功**（流水线耗时 {duration_s:.1f}s）",
        "",
        "## 一、血缘图节点",
        "",
    ]
    lines.extend(
        _table(
            ["canonical_id", "类型", "名称", "版本", "许可证", "风险等级", "判定"],
            node_rows,
        )
    )
    lines.extend(["", "## 二、聚合节点（计数降维）", ""])
    if aggregate_rows:
        lines.extend(_table(["名称", "count", "来源字段"], aggregate_rows))
    else:
        lines.append("_无聚合节点_")
    lines.extend(["", "## 三、血缘边", ""])
    lines.extend(_table(["来源", "边类型", "目标", "证据等级"], edge_rows))
    lines.extend(
        [
            "",
            "## 免责声明",
            "",
            "本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。",
            "",
        ]
    )
    return "\n".join(lines)


def _relpath(path: Path, project_path: Path) -> str:
    """返回相对项目根目录的 POSIX 风格路径（失败时回退绝对路径）。"""
    try:
        return path.relative_to(project_path).as_posix()
    except ValueError:
        return str(path)


def _iter_project_files(project_path: Path) -> Iterator[Path]:
    """遍历项目文件，跳过 vendor / 缓存 / 构建目录。"""
    for dirpath, dirnames, filenames in os.walk(project_path):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in _SKIP_DIRS and not name.startswith(".")
        ]
        for filename in filenames:
            yield Path(dirpath) / filename


def _iter_json_key_values(obj: Any, keys: set[str]) -> Iterator[str]:
    """递归遍历 JSON，产出键名命中 keys 的字符串值。"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys and isinstance(value, str):
                yield value
            yield from _iter_json_key_values(value, keys)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_json_key_values(item, keys)


def _normalize_model_id(value: str) -> str:
    """把候选字符串规范化为 namespace/name；非法形态返回空串。"""
    model = (value or "").strip().strip("/")
    if _MODEL_ID_RE.match(model):
        return model
    return ""


def _scan_bom_files(project_path: Path) -> list[tuple[str, str]]:
    """优先级 1：从 CycloneDX BOM 的 components[].purl 提取 pkg:modelscope/* 模型。"""
    import bom_adapter

    results: list[tuple[str, str]] = []
    for path in _iter_project_files(project_path):
        name = path.name.lower()
        is_bom = name in _BOM_FILENAMES or (
            path.suffix.lower() == ".json"
            and any(token in name for token in ("bom", "cyclonedx", "sbom"))
        )
        if not is_bom:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for component in data.get("components", []) or []:
            if not isinstance(component, dict):
                continue
            purl = str(component.get("purl") or "")
            if not purl.startswith(MODELSCOPE_PURL_PREFIX):
                continue
            identity = bom_adapter.parse_purl_identity(purl)
            if not identity or not identity.namespace or not identity.name:
                continue
            results.append(
                (f"{identity.namespace}/{identity.name}", _relpath(path, project_path))
            )
    return results


def _scan_config_files(project_path: Path) -> list[tuple[str, str]]:
    """优先级 2：从 configuration.json / config.json 递归提取 model_id/modelId/base_model/baseModel。"""
    results: list[tuple[str, str]] = []
    for path in _iter_project_files(project_path):
        if path.name.lower() not in _CONFIG_FILENAMES:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        for value in _iter_json_key_values(data, _CONFIG_KEYS):
            model = _normalize_model_id(value)
            if model:
                results.append((model, _relpath(path, project_path)))
    return results


def _scan_text_files(project_path: Path) -> list[tuple[str, str]]:
    """优先级 3：对 .py/.yaml/.yml/README.md 做纯字符串正则提取（不做代码逻辑解析）。"""
    results: list[tuple[str, str]] = []
    for path in _iter_project_files(project_path):
        lower = path.name.lower()
        if lower != _TEXT_FILENAME and path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in _TEXT_MODEL_RE.findall(text):
            model = _normalize_model_id(match)
            if model:
                results.append((model, _relpath(path, project_path)))
    return results


def _scan_project_models(project_path: Path) -> list[dict[str, Any]]:
    """按 BOM → config → 文本 三级扫描，去重并聚合来源文件路径。"""
    candidates: dict[str, dict[str, Any]] = {}

    def add(model: str, source: str) -> None:
        model = _normalize_model_id(model)
        if not model or "/" not in model:
            return
        ns, name = model.split("/", 1)
        if not ns or not name:
            return
        entry = candidates.setdefault(
            model,
            {"model": model, "ns": ns, "name": name, "sources": []},
        )
        if source not in entry["sources"]:
            entry["sources"].append(source)

    for model, source in _scan_bom_files(project_path):
        add(model, source)
    for model, source in _scan_config_files(project_path):
        add(model, source)
    for model, source in _scan_text_files(project_path):
        add(model, source)

    return list(candidates.values())


def _validate_modelscope_models(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """调用 ModelScope 详情 API 在线验证；仅保留 200 且 Data 非 null 的候选，其余静默过滤。"""
    import modelscope_adapter

    validated: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            detail = modelscope_adapter.fetch_model_detail(
                candidate["ns"], candidate["name"]
            )
        except Exception:
            detail = None
        if detail is not None:
            validated.append(candidate)
    return validated


def _render_modelscope_project_report(
    project_path: Path,
    models: list[dict[str, Any]],
    graph: dict[str, Any] | None,
    duration_s: float,
    no_manifest: bool,
) -> str:
    """渲染项目模式（ModelScope）的中文 Markdown 报告，标注每个模型的来源文件。"""
    header = [
        "# 项目 ModelScope 模型血缘扫描报告",
        "",
        f"- 项目路径：`{project_path}`",
        f"- 生成时间：{_utc_now()}",
    ]

    if not models:
        note = (
            f"未在路径 {project_path} 下找到可识别的 ModelScope 模型清单"
            if no_manifest
            else "识别到候选模型标识，但均未通过 ModelScope 详情 API 在线验证"
        )
        return "\n".join(
            header
            + [
                "- 识别模型数：**0**",
                f"- 本报告生成：**成功**（{note}）",
                "",
                "## 一、项目识别出的模型",
                "",
                "_无数据_",
                "",
                "## 免责声明",
                "",
                "本报告基于结构化证据与血缘图的辅助分析结果，不构成法律意见。",
                "",
            ]
        )

    model_rows = [
        [m["model"], m["ns"], m["name"], "\n".join(m["sources"])]
        for m in models
    ]

    lines = header + [f"- 识别模型数：**{len(models)}**"]

    if graph:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        node_type_counter = Counter((n.get("asset_type") or "unknown") for n in nodes)
        edge_type_counter = Counter((e.get("edge_type") or "unknown") for e in edges)
        node_rows = [
            [
                n.get("canonical_id"),
                n.get("asset_type"),
                n.get("name") or n.get("canonical_id"),
                n.get("version"),
                n.get("license"),
            ]
            for n in nodes
        ]
        edge_rows = [
            [e.get("source"), e.get("edge_type"), e.get("target"), e.get("evidence_level")]
            for e in edges
        ]
        lines.extend([
            f"- 合并血缘图节点数：**{len(nodes)}**，边数：**{len(edges)}**",
            f"- SCC 强连通分量：**{graph.get('scc_count', 0)}**",
            f"- 本报告生成：**成功**（流水线耗时 {duration_s:.1f}s）",
            "",
            "## 一、项目识别出的 ModelScope 模型（来源文件）",
            "",
        ])
        lines.extend(_table(["模型", "命名空间", "名称", "来源文件"], model_rows))
        lines.extend(["", "## 二、合并血缘图节点", ""])
        lines.extend(_table(["canonical_id", "类型", "名称", "版本", "许可证"], node_rows))
        lines.extend(["", "## 三、合并血缘边", ""])
        lines.extend(_table(["来源", "边类型", "目标", "证据等级"], edge_rows))
        lines.extend(
            [
                "",
                "## 四、统计",
                "",
                f"- 节点类型分布：`{dict(node_type_counter)}`",
                f"- 边类型分布：`{dict(edge_type_counter)}`",
                "",
                "## 免责声明",
                "",
                "本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。",
                "",
            ]
        )
    else:
        lines.extend([
            "- 本报告生成：**成功**（血缘图构建失败，仅列出已识别模型）",
            "",
            "## 一、项目识别出的 ModelScope 模型（来源文件）",
            "",
        ])
        lines.extend(_table(["模型", "命名空间", "名称", "来源文件"], model_rows))
        lines.extend(
            [
                "",
                "## 免责声明",
                "",
                "本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。",
                "",
            ]
        )

    return "\n".join(lines)


def _write_project_report(report: str, report_path: Path, args: argparse.Namespace) -> None:
    """把同一份项目报告同时写入固定路径与 --output，保证两份内容一致。"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"项目模式报告已写入：{report_path}")
    print(f"项目模式报告已写入：{args.output}")


def run_project(args: argparse.Namespace) -> None:
    """项目模式：BOM-Driven 扫描 → ModelScope API 在线验证 → 合并血缘图 → 中文报告。"""
    import modelscope_adapter

    from work.extract_modelscope_lineage import extract as extract_modelscope_lineage

    root = Path(__file__).resolve().parent
    project_path = Path(args.project)

    # 0. 目录校验：目录不存在或不是目录时优雅报错。
    if not project_path.exists():
        print(f"错误：项目路径不存在：{project_path}", file=sys.stderr)
        raise SystemExit(2)
    if not project_path.is_dir():
        print(f"错误：项目路径不是目录：{project_path}", file=sys.stderr)
        raise SystemExit(2)

    started = datetime.now(timezone.utc)

    # 1. 三级扫描候选模型标识。
    candidates = _scan_project_models(project_path)
    no_manifest = not candidates

    # 2. 在线验证，静默过滤无效候选。
    models = _validate_modelscope_models(candidates)

    # 3. 输出目录。
    report_dir = _project_output_dir(root, project_path)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.md"

    if not models:
        report = _render_modelscope_project_report(
            project_path, [], None, 0.0, no_manifest
        )
        if no_manifest:
            print(f"未在路径 {project_path} 下找到可识别的 ModelScope 模型清单", file=sys.stderr)
        else:
            print("识别到候选模型标识，但均未通过 ModelScope 详情 API 在线验证", file=sys.stderr)
        _write_project_report(report, report_path, args)
        return

    # 4. 逐模型提取血缘并合并（按 canonical_id 与边签名去重）。
    merged_assets: list[dict[str, Any]] = []
    merged_edges: list[dict[str, Any]] = []
    seen_assets: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    for model in models:
        snapshot_id = f"modelscope-{model['ns']}__{model['name']}"
        source_url = f"{modelscope_adapter.API_BASE}/models/{model['ns']}/{model['name']}"
        assets, edges = extract_modelscope_lineage(
            model["ns"], model["name"], snapshot_id, source_url
        )
        for asset in assets:
            canonical_id = asset.get("canonical_id")
            if canonical_id and canonical_id not in seen_assets:
                seen_assets.add(canonical_id)
                merged_assets.append(asset)
        for edge in edges:
            signature = (
                edge.get("source"),
                edge.get("target"),
                edge.get("edge_type"),
            )
            if signature not in seen_edges:
                seen_edges.add(signature)
                merged_edges.append(edge)

    duration_s = (datetime.now(timezone.utc) - started).total_seconds()

    if not merged_assets:
        report = _render_modelscope_project_report(
            project_path, models, None, duration_s, no_manifest
        )
        _write_project_report(report, report_path, args)
        return

    assets_path = report_dir / "assets.json"
    edges_path = report_dir / "edges.json"
    assets_path.write_text(
        json.dumps(merged_assets, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    edges_path.write_text(
        json.dumps(merged_edges, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 5. 显式构建合并血缘图。
    graph_path = report_dir / "graph.json"
    _run_py_script(
        root / "build_graph.py",
        [
            "--assets", str(assets_path),
            "--edges", str(edges_path),
            "--output", str(graph_path),
        ],
        "build_graph",
    )

    graph = json.loads(graph_path.read_text(encoding="utf-8"))

    # 6. 补风险判定字段（risk_level / decision），失败不阻断报告生成。
    try:
        _enrich_risk_fields(assets_path, edges_path, graph_path)
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"提示：风险判定字段补全失败（{type(exc).__name__}: {exc}）", file=sys.stderr)

    # 7. 导出标准 CycloneDX BOM，供 --diff 离线对比使用。
    bom_path = report_dir / "bom.json"
    export_bom.export_bom(assets_path, edges_path, bom_path)
    print(f"CycloneDX BOM 已写入：{bom_path}")

    report = _render_modelscope_project_report(
        project_path, models, graph, duration_s, no_manifest
    )
    _write_project_report(report, report_path, args)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.diff:
        run_diff(args.before, args.after, args.output)
    elif args.model is not None:
        run_model(args)
    elif args.project is not None:
        run_project(args)
    elif args.mode == "basic":
        run_basic(args)
    else:
        run_deep(args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        main()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(2) from None
