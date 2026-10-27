# -*- coding: utf-8 -*-
"""ModelScope 模型血缘提取器。

把 ModelScope 官方详情与血缘接口映射为统一资产节点和边。该模块属于正式
运行链，不依赖未纳入版本控制的本地工作目录脚本。

风险关注方向是“项目所用模型及其上游闭包”。下游 ``SonModels`` 默认不抓取；
单模型调研可以通过 ``include_downstream=True`` 保留平台提供的聚合计数。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

import bom_adapter as ba
import build_graph as bg
import modelscope_adapter as msa

RULE_VERSION = "merge-policy-v3"
DEFAULT_MAX_UPSTREAM_NODES = 128
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

DetailFetcher = Callable[[str, str], dict[str, Any] | None]
LineageFetcher = Callable[[str, str], dict[str, Any] | None]


def evidence(
    field: str,
    raw_value: object,
    level: str = msa.LINEAGE_EVIDENCE_LEVEL,
    status: str = "ok",
    source_url: str | None = None,
) -> dict[str, Any]:
    """构造一条 ModelScope 血缘证据。"""
    return {
        "evidence_level": level,
        "source_api": "modelscope",
        "source_url": source_url,
        "source_field": field,
        "retrieved_at": msa.utc_now(),
        "status": status,
        "raw_value": raw_value,
    }


def aggregate_node(
    ns: str,
    name: str,
    revision: str,
    role: str,
    lineage_type: str | None,
    lineage_type_ch: str | None,
    count: int,
    snapshot_id: str,
    source_file: str,
) -> dict[str, Any]:
    """为 SonModels/ParentsModels 的分组生成带 count 的聚合节点。"""
    label = lineage_type_ch or lineage_type or "related"
    entity_key = f"model:modelscope/{ns}/{name}:{role}:{lineage_type or 'related'}"
    canonical_id = f"{entity_key}@{revision}" if revision else entity_key
    display_name = f"{ns}/{name} · {label} (Total: {count})"
    return {
        "entity_key": entity_key,
        "canonical_id": canonical_id,
        "asset_type": "model",
        "name": display_name,
        "version": revision or "",
        "purls": [],
        "license": None,
        "evidence_chain": [
            evidence(
                "lineage",
                {
                    "LineAgeType": lineage_type,
                    "LineAgeTypeCh": lineage_type_ch,
                    "Total": count,
                },
            )
        ],
        "snapshot_id": snapshot_id,
        "merge_status": "KEPT_SEPARATE",
        "reason_code": "NO_MERGE_CANDIDATE",
        "rule_version": RULE_VERSION,
        "hashes": [],
        "source_file": source_file,
        "aggregate": True,
        "count": count,
        "coverage_status": "AGGREGATE_ONLY",
        "lineage_role": role,
        "lineage_type": lineage_type,
        "lineage_type_ch": lineage_type_ch,
    }


def _model_id(value: Any) -> str | None:
    """从 ModelScope 血缘条目中提取 namespace/name，忽略空值和 URL。"""
    raw: Any = value
    if isinstance(value, dict):
        raw = (
            value.get("Name")
            or value.get("ModelId")
            or value.get("ModelID")
            or value.get("Model")
            or value.get("Path")
        )
    text = ba.clean_text(raw)
    if not text:
        return None
    text = text.strip().strip("/")
    if "@" in text and "/" in text:
        text = text.rsplit("@", 1)[0]
    if not text or "://" in text or not _MODEL_ID_RE.match(text):
        return None
    return text


def _split_model_id(model_id: str) -> tuple[str, str]:
    ns, name = model_id.split("/", 1)
    return ns, name


def _source_url(model_id: str) -> str:
    return f"{msa.API_BASE}/models/{model_id}"


def parent_references(
    detail: dict[str, Any] | None,
    lineage: dict[str, Any] | None,
    current_model_id: str,
) -> list[dict[str, Any]]:
    """合并详情与血缘中的父模型名称，保留每个名称的来源字段。

    ModelScope 在不同模型上可能只填 ``BaseModel``，也可能只填
    ``ParentsModels[].Name``。两处任一存在都应形成可审计的 derived_from 边。
    """
    references: dict[str, list[dict[str, Any]]] = {}
    relation = ba.clean_text((detail or {}).get("BaseModelRelation"))
    for entry in ba.as_list((detail or {}).get("BaseModel")):
        model_id = _model_id(entry)
        if not model_id or model_id == current_model_id:
            continue
        references.setdefault(model_id, []).append(
            {
                "source_field": "Data.BaseModel",
                "lineage_type": relation or None,
                "lineage_type_ch": None,
                "raw_value": entry,
            }
        )

    for entry in ba.as_list((lineage or {}).get("ParentsModels")):
        model_id = _model_id(entry)
        if not model_id or model_id == current_model_id:
            continue
        lineage_type = ba.clean_text(entry.get("LineAgeType")) if isinstance(entry, dict) else ""
        lineage_type_ch = (
            ba.clean_text(entry.get("LineAgeTypeCh")) if isinstance(entry, dict) else ""
        )
        references.setdefault(model_id, []).append(
            {
                "source_field": "lineage.ParentsModels",
                "lineage_type": lineage_type or None,
                "lineage_type_ch": lineage_type_ch or None,
                "raw_value": entry,
            }
        )
    return [
        {"model_id": model_id, "references": entries}
        for model_id, entries in references.items()
    ]


def _placeholder_asset(
    model_id: str,
    snapshot_id: str,
    source_file: str,
    status: str,
    reason: str,
    depth: int,
) -> dict[str, Any]:
    """为未能展开的父模型保留图节点，避免风险链在静默处断开。"""
    ns, name = _split_model_id(model_id)
    purl = f"pkg:modelscope/{model_id}"
    entity_key, canonical_id, _ = ba.build_asset_identifiers(
        asset_type="model",
        name=model_id,
        version=None,
        purls=[purl],
    )
    return {
        "entity_key": entity_key,
        "canonical_id": canonical_id,
        "asset_type": "model",
        "name": model_id,
        "version": "",
        "purls": [purl],
        "license": None,
        "evidence_chain": [
            evidence(
                "upstream.reference",
                {"model_id": model_id, "namespace": ns, "name": name},
                status=status,
                source_url=_source_url(model_id),
            )
        ],
        "snapshot_id": snapshot_id,
        "merge_status": "KEPT_SEPARATE",
        "reason_code": status.upper(),
        "rule_version": RULE_VERSION,
        "hashes": [],
        "source_file": source_file,
        "lineage_role": "upstream",
        "lineage_depth": depth,
        "lineage_status": status,
        "unresolved": True,
        "unresolved_reason": reason,
    }


def extract(
    ns: str,
    name: str,
    snapshot_id: str,
    source_file: str,
    *,
    include_downstream: bool = False,
    max_upstream_depth: int | None = None,
    max_upstream_nodes: int = DEFAULT_MAX_UPSTREAM_NODES,
    detail_fetcher: DetailFetcher | None = None,
    lineage_fetcher: LineageFetcher | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """提取完整上游闭包，并可选保留当前模型的 SonModels 聚合视图。

    Args:
        include_downstream: 仅对输入模型保留下游聚合计数；项目风险模式应为 False。
        max_upstream_depth: ``None`` 表示递归完整上游闭包；显式值用于诊断场景。
        max_upstream_nodes: 防止平台数据异常或血缘爆炸的硬预算。
    """
    if max_upstream_depth is not None and max_upstream_depth < 0:
        raise ValueError("max_upstream_depth 不能为负数")
    if max_upstream_nodes < 1:
        raise ValueError("max_upstream_nodes 必须大于等于 1")

    fetch_detail = detail_fetcher or msa.fetch_model_detail
    fetch_lineage = lineage_fetcher or msa.fetch_lineage
    root_model_id = f"{ns}/{name}"

    assets_by_id: dict[str, dict[str, Any]] = {}
    assets: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str, str]] = set()
    model_to_canonical: dict[str, str] = {}
    detail_cache: dict[str, dict[str, Any] | None] = {}
    lineage_cache: dict[str, dict[str, Any] | None] = {}
    active: set[str] = set()
    unresolved: list[dict[str, str]] = []
    cycles: list[dict[str, str]] = []
    truncation_reasons: list[str] = []
    upstream_resolved = 0
    max_depth_seen = 0

    def add_asset(asset: dict[str, Any]) -> None:
        canonical_id = str(asset.get("canonical_id") or "")
        if canonical_id and canonical_id not in assets_by_id:
            assets_by_id[canonical_id] = asset
            assets.append(asset)

    def add_edge(
        source: str,
        target: str,
        source_field: str,
        evidence_level: str,
    ) -> None:
        signature = (source, target, "derived_from", source_field)
        if source == target or signature in seen_edges:
            return
        seen_edges.add(signature)
        edges.append(
            {
                "source": source,
                "target": target,
                "edge_type": "derived_from",
                "evidence_level": evidence_level,
                "source_field": source_field,
                "snapshot_id": snapshot_id,
            }
        )

    def visit(model_id: str, depth: int, is_root: bool = False) -> str | None:
        nonlocal upstream_resolved, max_depth_seen
        max_depth_seen = max(max_depth_seen, depth)
        if model_id in model_to_canonical:
            return model_to_canonical[model_id]

        if not is_root and max_upstream_depth is not None and depth > max_upstream_depth:
            placeholder = _placeholder_asset(
                model_id,
                snapshot_id,
                source_file,
                status="depth_limit",
                reason=f"超过配置的最大上游深度 {max_upstream_depth}",
                depth=depth,
            )
            add_asset(placeholder)
            model_to_canonical[model_id] = placeholder["canonical_id"]
            unresolved.append(
                {"model_id": model_id, "reason": "depth_limit", "depth": str(depth)}
            )
            truncation_reasons.append("depth_limit")
            return placeholder["canonical_id"]

        if not is_root and upstream_resolved >= max_upstream_nodes:
            placeholder = _placeholder_asset(
                model_id,
                snapshot_id,
                source_file,
                status="budget_exhausted",
                reason=f"达到上游节点预算 {max_upstream_nodes}",
                depth=depth,
            )
            add_asset(placeholder)
            model_to_canonical[model_id] = placeholder["canonical_id"]
            unresolved.append(
                {"model_id": model_id, "reason": "budget_exhausted", "depth": str(depth)}
            )
            truncation_reasons.append("node_budget")
            return placeholder["canonical_id"]

        parent_ns, parent_name = _split_model_id(model_id)
        if model_id not in detail_cache:
            try:
                detail_cache[model_id] = fetch_detail(parent_ns, parent_name)
            except Exception as exc:  # noqa: BLE001
                detail_cache[model_id] = None
                unresolved.append(
                    {
                        "model_id": model_id,
                        "reason": "detail_error",
                        "detail": f"{type(exc).__name__}: {exc}",
                        "depth": str(depth),
                    }
                )
        detail = detail_cache[model_id]
        if detail is None:
            placeholder = _placeholder_asset(
                model_id,
                snapshot_id,
                source_file,
                status="unresolved",
                reason="ModelScope 详情 API 未返回该上游模型",
                depth=depth,
            )
            add_asset(placeholder)
            model_to_canonical[model_id] = placeholder["canonical_id"]
            if not any(
                item.get("model_id") == model_id and item.get("reason") == "detail_error"
                for item in unresolved
            ):
                unresolved.append(
                    {"model_id": model_id, "reason": "not_found", "depth": str(depth)}
                )
            return placeholder["canonical_id"]

        asset = msa.map_to_asset(detail, snapshot_id, _source_url(model_id))
        asset["lineage_role"] = "root" if is_root else "upstream"
        asset["lineage_depth"] = depth
        asset["lineage_status"] = "resolved"
        asset["rule_version"] = RULE_VERSION
        add_asset(asset)
        current_id = str(asset["canonical_id"])
        model_to_canonical[model_id] = current_id
        if not is_root:
            upstream_resolved += 1

        active.add(model_id)
        if model_id not in lineage_cache:
            try:
                lineage_cache[model_id] = fetch_lineage(parent_ns, parent_name)
            except Exception as exc:  # noqa: BLE001
                lineage_cache[model_id] = None
                unresolved.append(
                    {
                        "model_id": model_id,
                        "reason": "lineage_error",
                        "detail": f"{type(exc).__name__}: {exc}",
                        "depth": str(depth),
                    }
                )
        lineage = lineage_cache[model_id]

        for parent in parent_references(detail, lineage, model_id):
            parent_model_id = str(parent["model_id"])
            references = parent["references"]
            primary = references[0] if references else {}
            if parent_model_id in active:
                cycles.append(
                    {
                        "source": model_id,
                        "target": parent_model_id,
                        "reason": "active_upstream_cycle",
                    }
                )
                target_id = model_to_canonical.get(parent_model_id)
                if target_id:
                    add_edge(
                        current_id,
                        target_id,
                        str(primary.get("source_field") or "lineage.ParentsModels"),
                        msa.LINEAGE_EVIDENCE_LEVEL,
                    )
                continue

            target_id = visit(parent_model_id, depth + 1, is_root=False)
            if not target_id:
                continue
            for reference in references:
                field_name = str(reference.get("source_field") or "lineage.ParentsModels")
                raw_value = reference.get("raw_value")
                level = "A" if field_name == "Data.BaseModel" else msa.LINEAGE_EVIDENCE_LEVEL
                target_asset = assets_by_id.get(target_id)
                if target_asset is not None:
                    target_asset.setdefault("evidence_chain", []).append(
                        evidence(field_name, raw_value, level=level)
                    )
                    if reference.get("lineage_type"):
                        target_asset["lineage_type"] = reference["lineage_type"]
                    if reference.get("lineage_type_ch"):
                        target_asset["lineage_type_ch"] = reference["lineage_type_ch"]
                add_edge(current_id, target_id, field_name, level)

        active.discard(model_id)

        if include_downstream and is_root:
            for entry in ba.as_list((lineage or {}).get("SonModels")):
                if not isinstance(entry, dict):
                    continue
                total = entry.get("Total")
                if not isinstance(total, int) or total <= 0:
                    continue
                node = aggregate_node(
                    ns=parent_ns,
                    name=parent_name,
                    revision=ba.clean_text(detail.get("Revision")) or "",
                    role="son",
                    lineage_type=entry.get("LineAgeType"),
                    lineage_type_ch=entry.get("LineAgeTypeCh"),
                    count=total,
                    snapshot_id=snapshot_id,
                    source_file=source_file,
                )
                add_asset(node)
                add_edge(
                    node["canonical_id"],
                    current_id,
                    "lineage.SonModels",
                    msa.LINEAGE_EVIDENCE_LEVEL,
                )

        return current_id

    root_id = visit(root_model_id, 0, is_root=True)
    if root_id is None or root_id not in assets_by_id:
        return assets, edges

    root_asset = assets_by_id[root_id]
    unresolved_by_model = {item["model_id"]: item for item in unresolved}
    complete = not unresolved_by_model and not cycles and not truncation_reasons
    lineage_status = "complete"
    if cycles:
        lineage_status = "cycle_detected"
    elif truncation_reasons:
        lineage_status = "truncated"
    elif unresolved_by_model:
        lineage_status = "partial"

    root_asset.update(
        {
            "lineage_complete": complete,
            "lineage_status": lineage_status,
            "lineage_truncation_reason": ",".join(sorted(set(truncation_reasons))) or None,
            "unresolved_upstream_models": list(unresolved_by_model.values()),
            "lineage_cycles": cycles,
            "max_upstream_depth": max_upstream_depth,
            "max_upstream_nodes": max_upstream_nodes,
            "max_depth_seen": max_depth_seen,
            "resolved_upstream_count": upstream_resolved,
            "include_downstream": include_downstream,
        }
    )
    return assets, edges


def write_graph(
    assets: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    output_path: Path,
) -> dict[str, Any]:
    """构建并写入统一 graph.json。"""
    graph = bg.build_graph(assets, edges)
    canonical_to_scc, compressed = bg.compress_scc(graph)
    graph_dict = bg.graph_to_dict(graph, canonical_to_scc, compressed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(graph_dict, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return graph_dict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从 ModelScope 官方 API 提取血缘并建图")
    parser.add_argument("--model", required=True, help="ModelScope 模型名，如 Qwen/Qwen-Image-2.1")
    parser.add_argument("--output-dir", required=True, type=Path, help="输出目录")
    parser.add_argument("--max-upstream-depth", type=int, default=None,
                        help="最大上游递归深度；省略表示完整闭包")
    parser.add_argument("--max-upstream-nodes", type=int, default=DEFAULT_MAX_UPSTREAM_NODES,
                        help=f"上游节点预算（默认 {DEFAULT_MAX_UPSTREAM_NODES}）")
    parser.add_argument("--no-downstream", action="store_true",
                        help="不生成 SonModels 下游聚合节点")
    args = parser.parse_args(argv)

    model = args.model.strip().strip("/")
    if "/" not in model:
        print("错误：--model 必须是 namespace/name 形式", file=sys.stderr)
        return 2
    ns, name = model.split("/", 1)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_id = f"modelscope-{ns}__{name}"
    assets, edges = extract(
        ns,
        name,
        snapshot_id,
        _source_url(model),
        include_downstream=not args.no_downstream,
        max_upstream_depth=args.max_upstream_depth,
        max_upstream_nodes=args.max_upstream_nodes,
    )
    if not assets:
        print(f"错误：无法从 ModelScope 获取模型 {ns}/{name} 的详情，请检查网络或模型名。",
              file=sys.stderr)
        return 2

    assets_path = output_dir / "assets.json"
    edges_path = output_dir / "edges.json"
    graph_path = output_dir / "graph.json"
    assets_path.write_text(json.dumps(assets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    edges_path.write_text(json.dumps(edges, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    graph = write_graph(assets, edges, graph_path)

    aggregate_nodes = [asset for asset in assets if asset.get("aggregate")]
    total_aggregated = sum(asset.get("count", 0) for asset in aggregate_nodes)
    current = next((asset for asset in assets if asset.get("lineage_role") == "root"), assets[0])
    print(f"模型：{model}")
    print(f"许可证：{current.get('license') or '（未识别）'}")
    print(f"上游血缘：{current.get('lineage_status')}（已展开 {current.get('resolved_upstream_count', 0)} 个父模型）")
    print(f"资产节点：{graph['node_count']}（含 {len(aggregate_nodes)} 个下游聚合节点，"
          f"聚合 {total_aggregated} 个下游模型）")
    print(f"血缘边：{graph['edge_count']}（derived_from）")
    print(f"SCC 分量：{graph['scc_count']}")
    print(f"已写入 {assets_path} / {edges_path} / {graph_path}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
