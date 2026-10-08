# -*- coding: utf-8 -*-
"""模块 9：Delta 检测（delta_engine.py）。

负责人：B（算法核心）
对应任务：深度部分 · 模块 9

功能：
1. 对比两个时间快照的资产列表与血缘边（before=t0 / after=t1）；
2. 输出变更事件 events.json，覆盖接口约定的变更事件：
   license_changed / ancestor_added / ancestor_removed /
   dataset_added / dataset_removed / evidence_downgrade /
   version_changed / version_upgraded；
3. 每个事件带 before / after 状态、事件自身证据等级与初步三级判定；
   path 由模块 10（propagation_engine）沿血缘图传播时填充。

v0.3（2026-10-01，与模块 2 版本化 canonical_id 对齐）：
- asset_index() 按 canonical_id 索引；新增 entity_index() 提供
  entity_key -> [canonical_id...] 辅助索引，区分"同一实体换版本"与
  "旧实体消失、新实体出现"；
- detect_delta() 先按 canonical_id 找完全同一版本；未命中再用 entity_key
  判断是否仅版本变化，产生 version_changed / version_upgraded 事件；
- 同一 entity_key 同一快照存在多个 canonical_id 时不自行折叠，以模块 2
  的 merge_status 为准（仅全部 MERGED 时取代表）；
- REVIEW / UNDETERMINED 资产不自动视为同一实体，事件 before/after 保留
  merge_status / reason_code / rule_version；
- 边变更事件 seed 修复为 edge.target（上游变化资产），before/after 同步
  取 target 资产状态（P0：修复后 path_certificates 应 > 0）；
- 接入 license_db.compare_direction()：license_changed 事件附带方向判定。

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
from license_db import compare_direction, get_triplets

# 证据等级 -> 三级判定
DECISION_BY_EVIDENCE = {
    "A": "RISK_CONFIRMED",
    "B": "RISK_POTENTIAL",
    "C": "UNDETERMINED",
}

# 血缘边类型（见 build_graph.EDGE_TYPES）
LINEAGE_EDGE_TYPES = {"derived_from", "trained_on", "depends_on"}

# 禁止自动视为同一实体的合并状态（模块 2 决策表）
NON_AUTO_MERGE_STATUS = {"REVIEW", "UNDETERMINED"}

# 许可证继承冲突：上游"继承型义务"要求衍生作品沿用/开源相同许可证，
# 与下游"不得附加额外限制"禁止项相互矛盾。
INHERITANCE_DUTIES = {
    "衍生作品保留相同许可证",
    "衍生分发需附带相同使用限制",
    "衍生作品必须以 GPL 开源",
    "衍生作品必须以 AGPL 开源",
    "衍生文档必须以 GFDL 分发",
}

NO_EXTRA_RESTRICTION_PROHIBITIONS = {
    "不得附加额外限制",
    "不得附加限制",
}


def check_license_conflict(upstream_license, downstream_license):
    """检测许可证继承冲突：上游义务（Duty）与下游禁止（Prohibition）是否矛盾。

    上游许可证若带有"继承型义务"（衍生作品须沿用/开源相同许可证），
    而下游许可证禁止"附加额外限制"，二者即构成继承冲突。

    返回：
        {conflict: bool, type: str, detail: str}
        type 为 "duty_prohibition" 或 "none"。
    """
    if upstream_license == downstream_license:
        return {
            "conflict": False,
            "type": "none",
            "detail": "同一许可证，自我兼容",
        }
    upstream = get_triplets(upstream_license)
    downstream = get_triplets(downstream_license)
    if upstream is None or downstream is None:
        return {
            "conflict": False,
            "type": "none",
            "detail": "上游或下游许可证规则未知，无法判定继承冲突",
        }

    up_duties = set(upstream.get("duties", []))
    down_prohibitions = set(downstream.get("prohibitions", []))

    conflict_duty = next((d for d in up_duties if d in INHERITANCE_DUTIES), None)
    conflict_prohibition = next(
        (p for p in down_prohibitions if p in NO_EXTRA_RESTRICTION_PROHIBITIONS),
        None,
    )

    if conflict_duty and conflict_prohibition:
        return {
            "conflict": True,
            "type": "duty_prohibition",
            "detail": (
                f"上游 {upstream['canonical_id']} 义务『{conflict_duty}』"
                f"与下游 {downstream['canonical_id']} 禁止『{conflict_prohibition}』冲突"
            ),
        }
    return {
        "conflict": False,
        "type": "none",
        "detail": "上游义务与下游禁止未检测到冲突",
    }


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


def entity_key_of(asset: dict) -> str:
    """取资产的 entity_key；旧数据缺省时从版本化 canonical_id 推导。"""
    entity_key = asset.get("entity_key")
    if entity_key:
        return str(entity_key)
    canonical_id = asset.get("canonical_id") or ""
    if "@" in canonical_id:
        return canonical_id.split("@", 1)[0]
    return canonical_id


def state_of(asset: dict | None) -> dict | None:
    """按接口约定生成事件的 before/after 状态对象。

    包含审计字段：entity_key、merge_status、reason_code、rule_version
    （旧数据缺失时为 null）。
    """
    if asset is None:
        return None
    return {
        "canonical_id": asset.get("canonical_id"),
        "entity_key": entity_key_of(asset),
        "license": asset.get("license"),
        "purls": list(asset.get("purls", [])),
        "snapshot_id": asset.get("snapshot_id"),
        "merge_status": asset.get("merge_status"),
        "reason_code": asset.get("reason_code"),
        "rule_version": asset.get("rule_version"),
    }


def event_id_generator(after_snapshot: str):
    """生成事件唯一标识：evt-<after_snapshot>-<三位序号>。"""
    counter = 0
    while True:
        counter += 1
        yield f"evt-{after_snapshot}-{counter:03d}"


def asset_index(assets: list[dict]) -> dict[str, dict]:
    """按 canonical_id 建立索引（版本化 ID，完全同一版本匹配）。"""
    return {asset["canonical_id"]: asset for asset in assets if asset.get("canonical_id")}


def entity_index(assets: list[dict]) -> dict[str, dict[str, dict]]:
    """entity_key -> {canonical_id: asset} 辅助索引。

    用于区分"同一实体换版本"（同一 entity_key 多个 canonical_id）和
    "旧实体消失、新实体出现"（entity_key 只出现在单侧）。
    """
    index: dict[str, dict[str, dict]] = {}
    for asset in assets:
        canonical_id = asset.get("canonical_id")
        if not canonical_id:
            continue
        index.setdefault(entity_key_of(asset), {})[canonical_id] = asset
    return index


def edge_signature(edge: dict) -> tuple:
    """边的唯一标识：(source, target, edge_type)。

    注意：source / target 必须使用版本化 canonical_id（接口约定 v0.2），
    不得回退到非版本化的 asset_type:name 或裸名字。
    """
    return (edge.get("source"), edge.get("target"), edge.get("edge_type"))


def edge_set(edges: list[dict]) -> set:
    return {edge_signature(edge) for edge in edges if edge.get("source") and edge.get("target")}


def decision_for(evidence_level: str | None) -> str:
    """证据等级 -> 三级判定；缺证据一律 UNDETERMINED。"""
    return DECISION_BY_EVIDENCE.get(evidence_level or "C", "UNDETERMINED")


def weaker_evidence(*levels: str | None) -> str:
    """取多个证据等级中最弱（保守）的一档；全缺为 C。"""
    present = [lv for lv in levels if lv]
    if not present:
        return "C"
    return max(present, key=lambda lv: EVIDENCE_ORDER[lv])


def _representative(id_map: dict[str, dict]) -> dict | None:
    """同快照同 entity_key 多 canonical_id 时取代表资产。

    模块 2 已合并（全部 MERGED）时取任一代表；否则不自行折叠返回 None。
    """
    if not id_map:
        return None
    if len(id_map) == 1:
        return next(iter(id_map.values()))
    if all(asset.get("merge_status") == "MERGED" for asset in id_map.values()):
        return next(iter(id_map.values()))
    return None


def _auto_mergeable(before_ids: dict[str, dict], after_ids: dict[str, dict]) -> bool:
    """两侧任一侧存在 REVIEW / UNDETERMINED 资产时不自动视为同一实体。"""
    for id_map in (before_ids, after_ids):
        if any(
            asset.get("merge_status") in NON_AUTO_MERGE_STATUS
            for asset in id_map.values()
        ):
            return False
    return True


def version_event_type(before_cid: str, after_cid: str) -> str:
    """判断版本事件类型：从无版本升级为有版本 -> version_upgraded，否则 version_changed。"""
    before_has_version = "@" in before_cid
    after_has_version = "@" in after_cid
    if not before_has_version and after_has_version:
        return "version_upgraded"
    return "version_changed"


def detect_delta(
    before_assets: list[dict],
    after_assets: list[dict],
    before_edges: list[dict],
    after_edges: list[dict],
) -> list[dict]:
    """对比两个快照，返回原始事件列表（path 为空，由模块 10 填充）。"""
    before_canon = asset_index(before_assets)
    after_canon = asset_index(after_assets)
    before_entity = entity_index(before_assets)
    after_entity = entity_index(after_assets)
    before_sig = edge_set(before_edges)
    after_sig = edge_set(after_edges)

    after_snapshot = next(iter(after_canon.values()), {}).get("snapshot_id", "t1") if after_canon else "t1"
    gen = event_id_generator(after_snapshot)

    events: list[dict] = []

    # ---- 1) 资产级事件：完全同一版本（canonical_id 相同）----
    all_ids = set(before_canon) | set(after_canon)
    for canonical_id in sorted(all_ids):
        old_asset = before_canon.get(canonical_id)
        new_asset = after_canon.get(canonical_id)
        if not (old_asset and new_asset):
            continue

        # license_changed（接入 compare_direction 方向判定）
        old_license = old_asset.get("license")
        new_license = new_asset.get("license")
        if old_license != new_license:
            evidence = weaker_evidence(
                best_evidence(old_asset, ("license",)),
                best_evidence(new_asset, ("license",)),
            )
            conflict = check_license_conflict(new_license, old_license)
            event = {
                "event_id": next(gen),
                "seed": canonical_id,
                "change_type": "license_changed",
                "before": state_of(old_asset),
                "after": state_of(new_asset),
                "path": [],
                "evidence_level": evidence,
                "decision": decision_for(evidence),
                "direction": compare_direction(old_license, new_license),
                "conflict_detected": conflict["conflict"],
                "conflict_type": conflict["type"],
                "conflict_detail": conflict["detail"],
            }
            events.append(event)

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

    # ---- 2) 版本变化事件：同一 entity_key、不同 canonical_id ----
    #     同一 entity_key 单侧出现（实体消失/新增）不在此产生事件，
    #     由血缘边事件覆盖；REVIEW / UNDETERMINED 不自动视为同一实体。
    for entity_key in sorted(set(before_entity) | set(after_entity)):
        before_ids = before_entity.get(entity_key, {})
        after_ids = after_entity.get(entity_key, {})
        if not before_ids or not after_ids:
            continue
        before_id_set = set(before_ids)
        after_id_set = set(after_ids)
        if before_id_set == after_id_set:
            continue  # 同一版本，已在上一步处理
        # REVIEW / UNDETERMINED 不自动合并
        if not _auto_mergeable(before_ids, after_ids):
            continue
        old_rep = _representative(before_ids)
        new_rep = _representative(after_ids)
        if old_rep is None or new_rep is None:
            continue  # 同快照多 canonical_id 且非全部 MERGED：不自行折叠
        old_cid = old_rep["canonical_id"]
        new_cid = new_rep["canonical_id"]
        if old_cid == new_cid:
            continue
        evidence = weaker_evidence(
            best_evidence(old_rep, ("license",)),
            best_evidence(new_rep, ("license",)),
        )
        events.append({
            "event_id": next(gen),
            "seed": new_cid,
            "change_type": version_event_type(old_cid, new_cid),
            "before": state_of(old_rep),
            "after": state_of(new_rep),
            "path": [],
            "evidence_level": evidence,
            "decision": decision_for(evidence),
        })

    # ---- 3) 血缘边新增 / 移除（seed 指向 edge.target：上游变化资产）----
    edge_by_signature = {
        edge_signature(edge): edge
        for edge in before_edges + after_edges
        if edge.get("source") and edge.get("target")
    }

    for signature in sorted(after_sig - before_sig):
        edge = edge_by_signature[signature]
        seed = edge["target"]
        after_asset = after_canon.get(seed)
        before_asset = before_canon.get(seed)
        is_dataset = (
            edge.get("edge_type") == "trained_on"
            and after_asset is not None
            and after_asset.get("asset_type") == "dataset"
        )
        change_type = "dataset_added" if is_dataset else "ancestor_added"
        # 缺失祖先：边指向的资产未出现在 BOM 中 -> 证据按 C 级、判定 UNDETERMINED
        evidence = edge.get("evidence_level") or "C"
        if after_asset is None:
            evidence = "C"
        events.append({
            "event_id": next(gen),
            "seed": seed,
            "change_type": change_type,
            "before": state_of(before_asset),
            "after": state_of(after_asset),
            "path": [],
            "evidence_level": evidence,
            "decision": decision_for(evidence),
        })

    for signature in sorted(before_sig - after_sig):
        edge = edge_by_signature[signature]
        seed = edge["target"]
        before_asset = before_canon.get(seed)
        after_asset = after_canon.get(seed)
        is_dataset = (
            edge.get("edge_type") == "trained_on"
            and before_asset is not None
            and before_asset.get("asset_type") == "dataset"
        )
        change_type = "dataset_removed" if is_dataset else "ancestor_removed"
        evidence = edge.get("evidence_level") or "C"
        if before_asset is None:
            evidence = "C"
        events.append({
            "event_id": next(gen),
            "seed": seed,
            "change_type": change_type,
            "before": state_of(before_asset),
            "after": state_of(after_asset),
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
