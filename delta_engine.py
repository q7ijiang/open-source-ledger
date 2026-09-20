# -*- coding: utf-8 -*-
"""模块 9：Delta 检测（delta_engine.py）。

负责人：B（算法核心）
对应任务：深度部分 · 模块 9（截止 2026-10-09）

功能：
1. 对比两个时间快照的资产列表与血缘边（before=t0 / after=t1）；
2. 输出变更事件 events.json，覆盖接口约定的六类变更：
   license_changed / ancestor_added / ancestor_removed /
   dataset_added / dataset_removed / evidence_downgrade；
3. 每个事件带 before / after 状态、事件自身证据等级与初步三级判定；
   path 由模块 10（propagation_engine）沿血缘图传播时填充。

用法：
    python delta_engine.py --before-assets data/deep_t0_assets.json \
                           --before-edges  data/deep_t0_edges.json \
                           --after-assets  data/deep_t1_assets.json \
                           --after-edges   data/deep_t1_edges.json \
                           --output out/events.json

输入输出字段严格遵循 docs/接口约定.md（资产节点 / 血缘边 / 事件对象）。
本模块不涉及网络请求。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_graph import EVIDENCE_ORDER, load_assets, load_edges

# 证据等级 -> 三级判定
DECISION_BY_EVIDENCE = {
    "A": "RISK_CONFIRMED",
    "B": "RISK_POTENTIAL",
    "C": "UNDETERMINED",
}

# 血缘边类型（见 build_graph.EDGE_TYPES）
LINEAGE_EDGE_TYPES = {"derived_from", "trained_on", "depends_on"}


def best_evidence(asset: dict, field_keywords: tuple[str, ...] | None = None) -> str | None:
    """取某资产证据链中最强的证据等级（A > B > C）。

    field_keywords 用于只看与某字段相关的证据；为 None 时看全部证据。
    没有任何证据时返回 None（调用方按 C 级 / UNDETERMINED 处理）。
    """
    best = None
    for entry in asset.get("evidence_chain", []):
        level = entry.get("evidence_level")
        if level not in EVIDENCE_ORDER:
            continue
        if field_keywords:
            field = str(entry.get("source_field") or "")
            if not any(keyword in field.lower() for keyword in field_keywords):
                continue
        if best is None or EVIDENCE_ORDER[level] < EVIDENCE_ORDER[best]:
            best = level
    return best


def state_of(asset: dict | None) -> dict | None:
    """按接口约定生成事件的 before/after 状态对象。"""
    if asset is None:
        return None
    return {
        "license": asset.get("license"),
        "purls": list(asset.get("purls", [])),
        "snapshot_id": asset.get("snapshot_id"),
    }


def event_id_generator(after_snapshot: str):
    """生成事件唯一标识：evt-<after_snapshot>-<三位序号>。"""
    counter = 0
    while True:
        counter += 1
        yield f"evt-{after_snapshot}-{counter:03d}"


def asset_index(assets: list[dict]) -> dict[str, dict]:
    """按 canonical_id 建立资产索引。"""
    return {asset["canonical_id"]: asset for asset in assets if asset.get("canonical_id")}


def edge_signature(edge: dict) -> tuple:
    """边的唯一标识：(source, target, edge_type)。"""
    return (edge.get("source"), edge.get("target"), edge.get("edge_type"))


def edge_set(edges: list[dict]) -> set:
    return {edge_signature(edge) for edge in edges if edge.get("source") and edge.get("target")}


def decision_for(evidence_level: str | None) -> str:
    """证据等级 -> 三级判定；缺证据一律 UNDETERMINED。"""
    return DECISION_BY_EVIDENCE.get(evidence_level or "C", "UNDETERMINED")


def detect_delta(
    before_assets: list[dict],
    after_assets: list[dict],
    before_edges: list[dict],
    after_edges: list[dict],
) -> list[dict]:
    """对比两个快照，返回原始事件列表（path 为空，由模块 10 填充）。"""
    before_idx = asset_index(before_assets)
    after_idx = asset_index(after_assets)
    before_sig = edge_set(before_edges)
    after_sig = edge_set(after_edges)

    all_ids = set(before_idx) | set(after_idx)
    after_snapshot = next(iter(after_idx.values()), {}).get("snapshot_id", "t1") if after_idx else "t1"
    gen = event_id_generator(after_snapshot)

    events: list[dict] = []

    # ---- 1) 资产许可证变更 + 证据降级 ----
    for canonical_id in sorted(all_ids):
        old_asset = before_idx.get(canonical_id)
        new_asset = after_idx.get(canonical_id)

        if old_asset and new_asset:
            # license_changed
            old_license = old_asset.get("license")
            new_license = new_asset.get("license")
            if old_license != new_license:
                old_evidence = best_evidence(old_asset, ("license",))
                new_evidence = best_evidence(new_asset, ("license",))
                # weakest link：取两者中较弱的证据等级
                evidence = max(
                    [lv for lv in (old_evidence, new_evidence) if lv],
                    key=lambda lv: EVIDENCE_ORDER[lv],
                ) if (old_evidence or new_evidence) else "C"
                events.append({
                    "event_id": next(gen),
                    "seed": canonical_id,
                    "change_type": "license_changed",
                    "before": state_of(old_asset),
                    "after": state_of(new_asset),
                    "path": [],
                    "evidence_level": evidence,
                    "decision": decision_for(evidence),
                })

            # evidence_downgrade：同一字段证据等级下降
            old_chain = {e.get("source_field"): e for e in old_asset.get("evidence_chain", [])}
            new_chain = {e.get("source_field"): e for e in new_asset.get("evidence_chain", [])}
            for field, old_entry in old_chain.items():
                new_entry = new_chain.get(field)
                if not new_entry:
                    continue
                old_level = old_entry.get("evidence_level")
                new_level = new_entry.get("evidence_level")
                if old_level in EVIDENCE_ORDER and new_level in EVIDENCE_ORDER:
                    if EVIDENCE_ORDER[new_level] > EVIDENCE_ORDER[old_level]:
                        events.append({
                            "event_id": next(gen),
                            "seed": canonical_id,
                            "change_type": "evidence_downgrade",
                            "before": state_of(old_asset),
                            "after": state_of(new_asset),
                            "path": [],
                            "evidence_level": new_level,
                            "decision": decision_for(new_level),
                        })
        # 仅 before / 仅 after 的资产不做独立事件：
        # 资产出现/消失由祖先边事件覆盖（ancestor_added/removed）

    # ---- 2) 血缘边新增 / 移除 ----
    edge_by_signature = {
        edge_signature(edge): edge
        for edge in before_edges + after_edges
        if edge.get("source") and edge.get("target")
    }

    for signature in sorted(after_sig - before_sig):
        edge = edge_by_signature[signature]
        target_asset = after_idx.get(edge["target"])
        is_dataset = (
            edge.get("edge_type") == "trained_on"
            and target_asset is not None
            and target_asset.get("asset_type") == "dataset"
        )
        change_type = "dataset_added" if is_dataset else "ancestor_added"
        # 缺失祖先：边指向的资产未出现在 BOM 中 -> 证据按 C 级、判定 UNDETERMINED
        evidence = edge.get("evidence_level") or "C"
        if target_asset is None:
            evidence = "C"
        events.append({
            "event_id": next(gen),
            "seed": edge["source"],
            "change_type": change_type,
            "before": state_of(before_idx.get(edge["source"])),
            "after": state_of(after_idx.get(edge["source"])),
            "path": [],
            "evidence_level": evidence,
            "decision": decision_for(evidence),
        })

    for signature in sorted(before_sig - after_sig):
        edge = edge_by_signature[signature]
        target_asset = before_idx.get(edge["target"])
        is_dataset = (
            edge.get("edge_type") == "trained_on"
            and target_asset is not None
            and target_asset.get("asset_type") == "dataset"
        )
        change_type = "dataset_removed" if is_dataset else "ancestor_removed"
        evidence = edge.get("evidence_level") or "C"
        if target_asset is None:
            evidence = "C"
        events.append({
            "event_id": next(gen),
            "seed": edge["source"],
            "change_type": change_type,
            "before": state_of(before_idx.get(edge["source"])),
            "after": state_of(after_idx.get(edge["source"])),
            "path": [],
            "evidence_level": evidence,
            "decision": decision_for(evidence),
        })

    return events


def main(argv=None):
    parser = argparse.ArgumentParser(description="Delta 检测（模块 9）")
    parser.add_argument("--before-assets", required=True, help="t0 资产列表 JSON")
    parser.add_argument("--before-edges", required=True, help="t0 血缘边 JSON")
    parser.add_argument("--after-assets", required=True, help="t1 资产列表 JSON")
    parser.add_argument("--after-edges", required=True, help="t1 血缘边 JSON")
    parser.add_argument("--output", required=True, help="输出 events.json 路径")
    args = parser.parse_args(argv)

    before_assets = load_assets(args.before_assets)
    after_assets = load_assets(args.after_assets)
    before_edges = load_edges(args.before_edges)
    after_edges = load_edges(args.after_edges)

    events = detect_delta(before_assets, after_assets, before_edges, after_edges)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(events, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary: dict[str, int] = {}
    for event in events:
        summary[event["change_type"]] = summary.get(event["change_type"], 0) + 1
    print(f"共检测到 {len(events)} 个事件：")
    for change_type, count in sorted(summary.items()):
        print(f"  {change_type}: {count}")
    print(f"已写入 {output_path}")


if __name__ == "__main__":
    main()
