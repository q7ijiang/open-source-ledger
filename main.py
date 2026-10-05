#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开源账本统一入口。

只编排仓库中实际存在的模块函数：

基础模式：
    bom_adapter.convert_bom
    -> entity_resolver.deduplicate_assets
    -> evidence_enricher.enrich_assets
    -> work.extract_hf_lineage.extract（仅 HF 模型 BOM）

深度模式：
    对 t0/t1 分别执行基础数据转换，然后：
    build_graph.build_graph
    -> delta_engine.detect_delta
    -> propagation_engine.propagate

report_basic.py 和 report_enhanced.py 当前不存在，因此 Markdown 报告在本入口中生成。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any



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

EVIDENCE_ORDER = {"A": 0, "B": 1, "C": 2}
HF_MODEL_TYPES = {"machine-learning-model", "model"}
HF_LINEAGE_EDGE_TYPES = {"derived_from", "trained_on"}


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
            "--output report.md"
        ),
    )
    parser.add_argument("--mode", choices=("basic", "deep"), required=False,
                        help="基础/深度模式（与 --model / --diff 二选一）")
    parser.add_argument("--model", type=str, default=None,
                        help="HF 模型名，触发模型血缘扫描模式（与 --mode / --diff 二选一）")
    parser.add_argument("--diff", action="store_true",
                        help="BOM 对比模式，输出风险报告（与 --model / --mode 互斥）")
    parser.add_argument("--input", type=Path, help="基础模式的 CycloneDX BOM")
    parser.add_argument("--before", type=Path, help="深度/diff 模式的 t0 CycloneDX BOM")
    parser.add_argument("--after", type=Path, help="深度/diff 模式的 t1 CycloneDX BOM")
    parser.add_argument("--output", type=Path, required=True, help="输出 Markdown 报告")
    args = parser.parse_args(argv)

    if args.diff and (args.model is not None or args.mode is not None):
        parser.error("--diff 与 --model / --mode 互斥，请二选一")
    if args.model is not None and args.mode is not None:
        parser.error("--model 与 --mode 互斥，请二选一")
    if not args.diff and args.model is None and args.mode is None:
        parser.error("必须提供 --diff 或 --mode（basic/deep）或 --model")
    if args.diff and (args.before is None or args.after is None):
        parser.error("--diff 必须同时提供 --before 和 --after")
    if args.mode == "basic" and args.input is None:
        parser.error("--mode basic 必须提供 --input")
    if args.mode == "deep" and (args.before is None or args.after is None):
        parser.error("--mode deep 必须同时提供 --before 和 --after")
    return args


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _basic_snapshot_id() -> str:
    return f"basic-{datetime.now().strftime('%Y%m%d')}"


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


def _best_evidence_level(asset: dict[str, Any]) -> str | None:
    levels = [
        entry.get("evidence_level")
        for entry in asset.get("evidence_chain", [])
        if isinstance(entry, dict) and entry.get("evidence_level") in EVIDENCE_ORDER
    ]
    if not levels:
        return None
    return min(levels, key=lambda level: EVIDENCE_ORDER[level])


def _license_assessment(license_text: Any) -> dict[str, Any]:
    import license_db

    if license_text is None or str(license_text).strip() == "":
        return {
            "risk_level": None,
            "category_zh": "未知 / 待人工确认",
            "is_ai_license": False,
            "unknown_items": [],
        }

    expression = license_db.evaluate_expression(str(license_text))
    category = expression.get("worst_category") or "unknown"
    return {
        "risk_level": expression.get("max_risk_level"),
        "category_zh": license_db.CATEGORY_ZH.get(category, "未知 / 待人工确认"),
        "is_ai_license": license_db.is_ai_license(str(license_text)),
        "unknown_items": expression.get("unknown_items", []),
    }


def _evidence_links(asset: dict[str, Any]) -> list[str]:
    links: list[str] = []
    for entry in asset.get("evidence_chain", []):
        if not isinstance(entry, dict):
            continue
        url = entry.get("source_url")
        if url and str(url) not in links:
            links.append(str(url))
    return links


def _format_links(urls: list[str]) -> str:
    if not urls:
        return "-"
    return "<br>".join(f"[{index}]({url})" for index, url in enumerate(urls, start=1))


def _is_hf_model_bom(bom: dict[str, Any]) -> bool:
    """判断 BOM 是否为 work/extract_hf_lineage.py 支持的 HF 模型 BOM。"""
    components = bom.get("components")
    if not isinstance(components, list) or not components:
        return False
    first = components[0]
    if not isinstance(first, dict):
        return False
    purl = str(first.get("purl") or "")
    return first.get("type") in HF_MODEL_TYPES and purl.startswith("pkg:huggingface/")


def _merge_lineage_assets(
    assets: list[dict[str, Any]],
    lineage_assets: list[dict[str, Any]],
    snapshot_id: str,
) -> list[dict[str, Any]]:
    """补入 HF 提取器自动创建的缺失祖先或数据集节点。"""
    merged = list(assets)
    known_ids = {
        asset.get("canonical_id")
        for asset in merged
        if asset.get("canonical_id")
    }
    for asset in lineage_assets:
        canonical_id = asset.get("canonical_id")
        if not canonical_id or canonical_id in known_ids:
            continue
        merged_asset = dict(asset)
        merged_asset["snapshot_id"] = snapshot_id
        merged.append(merged_asset)
        known_ids.add(canonical_id)
    return merged


def _extract_hf_edges(
    path: Path,
    bom: dict[str, Any],
    assets: list[dict[str, Any]],
    snapshot_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """调用 HF 专用提取器，并统一边字段与当前快照 ID。"""
    if not _is_hf_model_bom(bom):
        return assets, []

    from work.extract_hf_lineage import extract as extract_hf_lineage

    lineage_assets, lineage_edges = extract_hf_lineage(path)
    merged_assets = _merge_lineage_assets(assets, lineage_assets, snapshot_id)
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in lineage_edges:
        edge_type = str(edge.get("edge_type") or "")
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if edge_type not in HF_LINEAGE_EDGE_TYPES or not source or not target:
            continue
        signature = (source, target, edge_type)
        if signature in seen:
            continue
        seen.add(signature)
        edges.append(
            {
                "source": source,
                "target": target,
                "edge_type": edge_type,
                "evidence_level": str(edge.get("evidence_level") or "B"),
                "source_field": str(edge.get("source_field") or ""),
                "snapshot_id": snapshot_id,
            }
        )
    return merged_assets, edges


def _build_snapshot(path: Path, snapshot_id: str) -> dict[str, Any]:
    """按现有模块真实签名生成一个快照的资产、边和统计。"""
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
    assets, edges = _extract_hf_edges(path, bom, enriched, snapshot_id)
    return {
        "path": path,
        "snapshot_id": snapshot_id,
        "raw_assets": raw_assets,
        "assets": assets,
        "merge_log": merge_log,
        "evidence_summary": evidence_summary,
        "edges": edges,
    }


def _render_basic_report(snapshot: dict[str, Any]) -> str:
    assets: list[dict[str, Any]] = snapshot["assets"]
    edges: list[dict[str, Any]] = snapshot["edges"]
    merge_log: list[dict[str, Any]] = snapshot["merge_log"]
    evidence_summary: dict[str, Any] = snapshot["evidence_summary"]

    assessments = {
        asset.get("canonical_id"): _license_assessment(asset.get("license"))
        for asset in assets
    }
    risk_distribution = Counter(
        assessment["risk_level"]
        for assessment in assessments.values()
        if assessment["risk_level"] is not None
    )
    category_distribution = Counter(
        assessment["category_zh"] for assessment in assessments.values()
    )
    unknown_assets = [
        asset
        for asset in assets
        if assessments[asset.get("canonical_id")]["unknown_items"]
    ]
    attention_assets = [
        asset
        for asset in assets
        if (assessments[asset.get("canonical_id")]["risk_level"] or 0) >= 4
        or assessments[asset.get("canonical_id")]["is_ai_license"]
    ]

    lines = [
        "# 开源及第三方资源使用清单",
        "",
        f"- 生成时间：{_utc_now()}",
        f"- 输入 BOM：`{snapshot['path']}`",
        f"- 快照 ID：`{snapshot['snapshot_id']}`",
        "- 本报告由 `main.py` 调用 BOM 解析、实体对齐、证据补全和 HF 血缘提取模块生成；通用 depends_on 边已移除。",
        "",
        "## 摘要",
        "",
        f"- BOM 解析资产数：{len(snapshot['raw_assets'])}",
        f"- 实体对齐后资产数：{len(assets)}",
        f"- 候选配对日志数：{len(merge_log)}",
        f"- HF 血缘边数：{len(edges)}",
        f"- 支持远程证据的 purl 数：{evidence_summary['supported_purls']}",
        f"- 成功补全远程证据数：{evidence_summary['remote_ok']}",
        f"- 网络失败降级数：{evidence_summary['network_error']}",
        f"- 处理前无证据资产：{evidence_summary['assets_without_evidence_before']}",
        f"- 处理后无证据资产：{evidence_summary['assets_without_evidence_after']}",
        "",
        "## 许可证风险分布",
        "",
    ]
    lines.extend(
        _table(
            ["风险等级", "资产数"],
            [[level, risk_distribution[level]] for level in sorted(risk_distribution)],
        )
    )
    lines.extend(["", "### 类别分布", ""])
    lines.extend(
        _table(
            ["许可证类别", "资产数"],
            [[category, count] for category, count in sorted(category_distribution.items())],
        )
    )

    lines.extend(["", "## 重点资产", ""])
    attention_rows = []
    for asset in sorted(attention_assets, key=lambda item: str(item.get("canonical_id"))):
        assessment = assessments[asset.get("canonical_id")]
        attention_rows.append(
            [
                asset.get("canonical_id"),
                asset.get("asset_type"),
                asset.get("license"),
                assessment["risk_level"],
                assessment["category_zh"],
                "是" if assessment["is_ai_license"] else "否",
            ]
        )
    lines.extend(
        _table(
            ["canonical_id", "类型", "许可证", "风险等级", "类别", "AI 专用"],
            attention_rows,
        )
    )

    lines.extend(["", "## 资产清单", ""])
    asset_rows = []
    for asset in sorted(
        assets,
        key=lambda item: (
            -(assessments[item.get("canonical_id")]["risk_level"] or 0),
            str(item.get("asset_type") or ""),
            str(item.get("canonical_id") or ""),
        ),
    ):
        assessment = assessments[asset.get("canonical_id")]
        asset_rows.append(
            [
                asset.get("canonical_id"),
                asset.get("asset_type"),
                asset.get("name"),
                asset.get("version"),
                asset.get("license"),
                assessment["risk_level"] if assessment["risk_level"] is not None else "待人工确认",
                assessment["category_zh"],
                _best_evidence_level(asset) or "-",
                _format_links(_evidence_links(asset)),
            ]
        )
    lines.extend(
        _table(
            [
                "canonical_id",
                "类型",
                "名称",
                "版本",
                "许可证",
                "风险",
                "类别",
                "最佳证据",
                "来源",
            ],
            asset_rows,
        )
    )

    lines.extend(["", "## 待人工确认", ""])
    if unknown_assets:
        unknown_rows = []
        for asset in sorted(unknown_assets, key=lambda item: str(item.get("canonical_id"))):
            assessment = assessments[asset.get("canonical_id")]
            unknown_rows.append(
                [
                    asset.get("canonical_id"),
                    asset.get("license"),
                    ", ".join(assessment["unknown_items"]),
                ]
            )
        lines.extend(_table(["canonical_id", "原始许可证字段", "未识别项"], unknown_rows))
    else:
        lines.append("未发现无法识别的许可证片段。")

    lines.extend(["", "## 血缘边统计", ""])
    edge_distribution = Counter(edge.get("edge_type") for edge in edges)
    edge_type_rows = [
        [edge_type, count]
        for edge_type, count in sorted(edge_distribution.items())
        if edge_type
    ]
    lines.extend(_table(["边类型", "数量"], edge_type_rows))
    lines.extend(
        [
            "",
            "- 通用依赖关系边（depends_on）：已移除。",
            "",
            "## 免责声明",
            "",
            "本报告是基于结构化证据的辅助审计结果，不构成法律意见。",
            "",
        ]
    )
    return "\n".join(lines)


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
    snapshot = _build_snapshot(args.input, _basic_snapshot_id())
    report = _render_basic_report(snapshot)
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

    # 附带产物：用 t1 的 BOM 生成血缘图 PNG
    _render_diff_lineage_png(
        after_bom,
        Path(__file__).resolve().parent / "outputs" / "diff_lineage_graph.png",
    )


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


def _render_diff_lineage_png(t1_bom: Path, png_path: Path) -> None:
    """diff 模式附带产物：用 t1 的 BOM 生成血缘图 PNG。

    依次调用仓库现有脚本：
    - work/extract_hf_lineage.py：从 t1 BOM 提取血缘（assets/edges/graph.json）
    - build_graph.py：显式构建血缘图
    - visualize_lineage.py：渲染 PNG
    """
    import shutil
    import tempfile

    root = Path(__file__).resolve().parent
    png_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="diff_lineage_") as tmp:
        tmp_dir = Path(tmp)
        bom_dir = tmp_dir / "bom"
        extract_dir = tmp_dir / "extract"
        bom_dir.mkdir()
        extract_dir.mkdir()
        # extract_hf_lineage.py 以目录为单位扫描 BOM，把 t1 单文件拷入临时目录。
        shutil.copyfile(t1_bom, bom_dir / t1_bom.name)

        _run_py_script(
            root / "work" / "extract_hf_lineage.py",
            ["--bom-dir", str(bom_dir), "--output-dir", str(extract_dir)],
            "extract_hf_lineage",
        )

        graph_path = extract_dir / "graph.json"
        _run_py_script(
            root / "build_graph.py",
            [
                "--assets", str(extract_dir / "assets.json"),
                "--edges", str(extract_dir / "edges.json"),
                "--output", str(graph_path),
            ],
            "build_graph",
        )

        _run_py_script(
            root / "visualize_lineage.py",
            ["--graph", str(graph_path), "--output", str(png_path)],
            "visualize_lineage",
        )

    print(f"diff 模式血缘图 PNG 已生成：{png_path}")


def _component_name(component: dict[str, Any]) -> str:
    """由组件 group/name 拼接出 HF 模型 id 风格的名称。"""
    return f"{component.get('group', '')}/{component.get('name', '')}".strip("/")


def _bom_ancestors(bom_path: Path) -> tuple[str, list[str]]:
    """读取单个 BOM 的主组件名与其直接祖先模型 id 列表。"""
    data = json.loads(bom_path.read_text(encoding="utf-8"))
    comps = data.get("components", []) or []
    if not comps:
        return _component_name({}), []
    model = comps[0]
    ancestors = [
        _component_name(ancestor)
        for ancestor in ((model.get("pedigree") or {}).get("ancestors") or [])
        if isinstance(ancestor, dict) and (ancestor.get("name") or ancestor.get("purl"))
    ]
    return _component_name(model), ancestors


def _ancestor_chain_depth(
    model: str,
    ancestry: dict[str, list[str]],
    seen: set[str],
) -> int:
    """沿 pedigree.ancestors 递归求单个模型的祖先层数（带环保护）。"""
    if model in seen:
        return 0
    seen = seen | {model}
    depth = 0
    for ancestor in ancestry.get(model, []):
        depth = max(depth, 1 + _ancestor_chain_depth(ancestor, ancestry, seen))
    return depth


def _lineage_depth(bom_dir: Path) -> int:
    """扫描 BOM 目录，返回所有模型血缘链的最大祖先层数。"""
    ancestry: dict[str, list[str]] = {}
    for bom_path in sorted(bom_dir.glob("*.json")):
        try:
            model, ancestors = _bom_ancestors(bom_path)
        except (json.JSONDecodeError, OSError):
            continue
        if model:
            ancestry[model] = ancestors
    return max((_ancestor_chain_depth(m, ancestry, set()) for m in ancestry), default=0)


def _render_model_report(
    model: str,
    bom_dir: Path,
    extract_dir: Path,
    png_path: Path,
    duration_s: float,
) -> str:
    """渲染模型血缘扫描的中文 Markdown 报告。"""
    graph = json.loads((extract_dir / "graph.json").read_text(encoding="utf-8"))
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    depth = _lineage_depth(bom_dir)
    bom_files = sorted(bom_dir.glob("*.json"))

    node_type_counter = Counter((n.get("asset_type") or "unknown") for n in nodes)
    edge_type_counter = Counter((e.get("edge_type") or "unknown") for e in edges)

    bom_rows = []
    for bom_file in bom_files:
        try:
            name, _ = _bom_ancestors(bom_file)
        except (json.JSONDecodeError, OSError):
            name = bom_file.stem
        bom_rows.append([name or bom_file.stem, bom_file.name, bom_file.stat().st_size])

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

    lines: list[str] = [
        "# AI 模型血缘扫描报告",
        "",
        f"- 扫描模型：`{model}`",
        f"- 生成时间：{_utc_now()}",
        f"- 血缘层级（祖先层数）：**{depth}**",
        f"- 生成 BOM 数量：**{len(bom_files)}**",
        f"- 血缘图节点数：**{len(nodes)}**，边数：**{len(edges)}**",
        f"- SCC 强连通分量：**{graph.get('scc_count', 0)}**",
        f"- 血缘图 PNG：**{'已生成' if png_path.exists() else '未生成'}**（`{png_path}`）",
        f"- 本报告生成：**成功**（流水线耗时 {duration_s:.1f}s）",
        "",
        "## 一、BOM 清单",
        "",
    ]
    lines.extend(_table(["模型", "文件", "大小（字节）"], bom_rows))
    lines.extend(["", "## 二、血缘图节点", ""])
    lines.extend(_table(["canonical_id", "类型", "名称", "版本", "许可证"], node_rows))
    lines.extend(["", "## 三、血缘边", ""])
    lines.extend(_table(["来源", "边类型", "目标", "证据等级"], edge_rows))
    lines.extend([
        "",
        "## 四、统计",
        "",
        f"- 节点类型分布：`{dict(node_type_counter)}`",
        f"- 边类型分布：`{dict(edge_type_counter)}`",
        "",
        "## 免责声明",
        "",
        "本报告基于结构化证据与血缘图的辅助分析结果，不构成法律意见。",
        "",
    ])
    return "\n".join(lines)


def run_model(args: argparse.Namespace) -> None:
    """模型模式：递归扫祖先 → 补数据 → 提取血缘 → 建图 → 可视化 → 中文报告。"""
    model = args.model
    root = Path(__file__).resolve().parent
    bom_dir = root / "outputs" / "lineage_scan"
    extract_dir = root / "outputs" / "lineage_extract"
    png_path = root / "outputs" / "lineage_graph.png"

    started = datetime.now(timezone.utc)

    # 1. 递归扫描祖先链 → BOM 目录
    _run_py_script(
        root / "generate_bom.py",
        [model, "--recursive", "--outdir", str(bom_dir)],
        "generate_bom",
    )

    # 2. 补数据：对 cdxgen 空 BOM 从模型名推断祖先（证据等级 C）
    _run_py_script(
        root / "enrich_lineage.py",
        ["--bom-dir", str(bom_dir), "--model", model],
        "enrich_lineage",
    )

    # 3. 提取血缘边 → assets/edges/graph.json
    _run_py_script(
        root / "work" / "extract_hf_lineage.py",
        ["--bom-dir", str(bom_dir), "--output-dir", str(extract_dir)],
        "extract_hf_lineage",
    )

    # 4. 显式构建血缘图
    _run_py_script(
        root / "build_graph.py",
        [
            "--assets", str(extract_dir / "assets.json"),
            "--edges", str(extract_dir / "edges.json"),
            "--output", str(extract_dir / "graph.json"),
        ],
        "build_graph",
    )

    # 5. 可视化 → PNG
    _run_py_script(
        root / "visualize_lineage.py",
        ["--graph", str(extract_dir / "graph.json"), "--output", str(png_path)],
        "visualize_lineage",
    )

    duration_s = (datetime.now(timezone.utc) - started).total_seconds()
    report = _render_model_report(model, bom_dir, extract_dir, png_path, duration_s)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"模型模式报告已写入：{args.output}")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.diff:
        run_diff(args.before, args.after, args.output)
    elif args.model is not None:
        run_model(args)
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
