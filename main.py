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
            "--output report.md"
        ),
    )
    parser.add_argument("--mode", choices=("basic", "deep"), required=True)
    parser.add_argument("--input", type=Path, help="基础模式的 CycloneDX BOM")
    parser.add_argument("--before", type=Path, help="深度模式的 t0 CycloneDX BOM")
    parser.add_argument("--after", type=Path, help="深度模式的 t1 CycloneDX BOM")
    parser.add_argument("--output", type=Path, required=True, help="输出 Markdown 报告")
    args = parser.parse_args(argv)

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


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.mode == "basic":
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
