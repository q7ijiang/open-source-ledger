# -*- coding: utf-8 -*-
"""模块 10：风险传播（propagation_engine.py）。

负责人：B（算法核心）
对应任务：深度部分 · 模块 10（截止 2026-10-10）

功能：
1. 以 Delta 检测（模块 9）输出的事件为种子，在血缘图上做反向 BFS，
   找出所有受影响的资产（依赖 / 派生自 / 训练自种子资产的节点）；
2. 沿路径按 weakest link 规则传播证据等级（A > B > C，取最弱）；
3. 输出三级判定：RISK_CONFIRMED / RISK_POTENTIAL / UNDETERMINED；
4. 为每个受影响资产生成路径证书（path certificate）；
5. 通过 visited 集合、SCC 识别与最大深度限制保证循环图正常终止。

用法：
    python propagation_engine.py --events out/events.json \
                                 --graph-before out/graph_t0.json \
                                 --graph-after  out/graph_t1.json \
                                 --output out/propagated.json

说明：
- license_changed / evidence_downgrade / ancestor_added / dataset_added
  在 after 图（t1）上传播；ancestor_removed / dataset_removed 在 before 图（t0）上传播；
- 缺失祖先（边指向的资产没有元数据）强制 UNDETERMINED；
- 最大传播深度 10 层（见项目风险降级方案）。

输入输出字段严格遵循 docs/接口约定.md（事件对象 / 血缘边）。
本模块不涉及网络请求。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from pathlib import Path

import networkx as nx

from build_graph import EDGE_TYPES, EVIDENCE_ORDER, build_graph, load_assets, load_edges

MAX_DEPTH = 10

DECISION_BY_EVIDENCE = {
    "A": "RISK_CONFIRMED",
    "B": "RISK_POTENTIAL",
    "C": "UNDETERMINED",
}

# 传播所使用的图：按事件类型选择 before / after 快照
AFTER_GRAPH_EVENTS = {"license_changed", "evidence_downgrade", "ancestor_added", "dataset_added"}
BEFORE_GRAPH_EVENTS = {"ancestor_removed", "dataset_removed"}

# 并行边选边优先级：血缘关系越直接越优先（同证据等级时）
EDGE_TYPE_PRIORITY = {"derived_from": 0, "trained_on": 1, "depends_on": 2, "unknown": 3}


def load_graph(path: str | Path) -> nx.MultiDiGraph:
    """从模块 8 输出的图 JSON 重建 networkx 图。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assets = data.get("nodes", [])
    edges = data.get("edges", [])
    graph = build_graph(assets, edges)
    # 附带回 SCC 信息
    graph.graph["canonical_to_scc"] = data.get("canonical_to_scc", {})
    graph.graph["scc"] = data.get("scc", {})
    return graph


def decision_for(evidence_level: str | None) -> str:
    return DECISION_BY_EVIDENCE.get(evidence_level or "C", "UNDETERMINED")


def representative_step(graph: nx.MultiDiGraph, source: str, target: str) -> dict | None:
    """在 (source, target) 的并行边中选一条代表性边作为路径步骤。

    选边规则：先取证据最弱（最保守）的边；同证据等级时优先
    derived_from > trained_on > depends_on。
    """
    edge_data = graph.get_edge_data(source, target, default={})
    parallel = [
        (source, target, data)
        for data in edge_data.values()
    ]
    if not parallel:
        return None

    def rank(item):
        _, _, data = item
        level = data.get("evidence_level")
        level_rank = EVIDENCE_ORDER.get(level, 9)
        type_rank = EDGE_TYPE_PRIORITY.get(data.get("edge_type"), 3)
        return (level_rank, type_rank, data.get("edge_type") or "")

    parallel.sort(key=rank)
    _, _, data = parallel[0]
    return {
        "source": source,
        "target": target,
        "edge_type": data.get("edge_type"),
        "evidence_level": data.get("evidence_level") or "C",
        "source_field": data.get("source_field"),
    }


def reverse_bfs(
    graph: nx.MultiDiGraph,
    seed: str,
    max_depth: int = MAX_DEPTH,
) -> dict[str, list[dict]]:
    """从 seed 出发沿反向边 BFS，返回 {受影响资产: [路径步骤, ...]}。

    路径步骤顺序为：受影响资产 -> ... -> seed（与接口约定示例一致）。
    visited 集合保证循环图（含 SCC）不会死循环。
    """
    reached: dict[str, list[dict]] = {}
    queue = deque()
    queue.append((seed, []))
    reached[seed] = []
    while queue:
        node, path = queue.popleft()
        if len(path) >= max_depth:
            continue
        predecessors = sorted(graph.predecessors(node))
        for pred in predecessors:
            if pred in reached:
                continue
            step = representative_step(graph, pred, node)
            if step is None:
                continue
            new_path = [step] + path
            reached[pred] = new_path
            queue.append((pred, new_path))
    reached.pop(seed, None)
    return reached


def path_evidence(path: list[dict], event_evidence: str | None) -> str:
    """weakest link：路径证据 = min(事件自身证据, 各步骤证据)。"""
    levels = [step["evidence_level"] for step in path if step.get("evidence_level")]
    if event_evidence:
        levels.append(event_evidence)
    return max(levels, key=lambda level: EVIDENCE_ORDER.get(level, 9)) if levels else "C"


def path_fingerprint(path: list[dict]) -> str:
    """路径证书指纹：路径步骤序列的 SHA-1 摘要。"""
    raw = json.dumps(path, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def cycle_members(graph: nx.MultiDiGraph) -> set:
    """返回图中位于多节点 SCC（环）内的节点集合。

    优先使用模块 8 图 JSON 附带的 SCC 信息；未附带时现场计算，
    保证任何入口（CLI / 测试直接构建图）都能正确识别环。
    """
    scc = graph.graph.get("scc")
    if scc:
        return {
            member
            for members in scc.values()
            if len(members) > 1
            for member in members
        }
    return {
        member
        for component in nx.strongly_connected_components(graph)
        if len(component) > 1
        for member in component
    }


def termination_reason(graph: nx.MultiDiGraph, path: list[dict], seed: str) -> str:
    """判断路径终止原因：exhausted / max_depth / scc_cycle。"""
    if len(path) >= MAX_DEPTH:
        return "max_depth"
    multi_members = cycle_members(graph)
    nodes_in_path = {seed}
    for step in path:
        nodes_in_path.add(step["source"])
        nodes_in_path.add(step["target"])
    if any(node in multi_members for node in nodes_in_path):
        return "scc_cycle"
    return "exhausted"


def propagate_event(
    event: dict,
    graph: nx.MultiDiGraph,
) -> tuple[list[dict], list[dict]]:
    """对单个事件做风险传播。

    返回 (enriched_events, certificates)：
    - enriched_events：种子自身事件（path 为空）+ 每个受影响资产一个事件；
    - certificates：每个受影响资产一个路径证书。
    """
    seed = event["seed"]
    reached = reverse_bfs(graph, seed)

    enriched: list[dict] = []
    certificates: list[dict] = []

    # 种子自身：path 为空，沿用 Delta 事件证据与判定
    seed_event = dict(event)
    seed_event["path"] = []
    enriched.append(seed_event)

    for seq, (affected, path) in enumerate(
        sorted(reached.items(), key=lambda item: item[0]), start=1
    ):
        step_evidence = path_evidence(path, event.get("evidence_level"))
        decision = decision_for(step_evidence)

        # 缺失祖先：路径上任一节点无资产元数据（资产未出现在 BOM 中）-> UNDETERMINED
        nodes_in_path = {affected}
        for step in path:
            nodes_in_path.add(step["source"])
            nodes_in_path.add(step["target"])
        missing_ancestor = any(
            graph.nodes[node].get("asset_type") is None
            for node in nodes_in_path
        )
        if missing_ancestor:
            decision = "UNDETERMINED"
            step_evidence = "C"

        affected_event = dict(event)
        affected_event["event_id"] = f"{event['event_id']}-p{seq:02d}"
        affected_event["path"] = path
        affected_event["evidence_level"] = step_evidence
        affected_event["decision"] = decision
        enriched.append(affected_event)

        certificates.append({
            "certificate_id": f"cert-{event['event_id']}-{seq:02d}",
            "event_id": affected_event["event_id"],
            "seed": seed,
            "affected": affected,
            "change_type": event["change_type"],
            "path": path,
            "hop_count": len(path),
            "weakest_evidence": step_evidence,
            "decision": decision,
            "termination": termination_reason(graph, path, seed),
            "missing_ancestor": missing_ancestor,
            "path_fingerprint": path_fingerprint(path),
            "verified": True,
        })

    return enriched, certificates


def propagate(
    events: list[dict],
    graph_before: nx.MultiDiGraph,
    graph_after: nx.MultiDiGraph,
) -> dict:
    """对全部事件传播，返回 {"events": [...], "path_certificates": [...]}。"""
    enriched_all: list[dict] = []
    certificates_all: list[dict] = []
    for event in events:
        change_type = event["change_type"]
        if change_type in BEFORE_GRAPH_EVENTS:
            graph = graph_before
            graph_for = "before"
        else:
            graph = graph_after
            graph_for = "after"
        enriched, certificates = propagate_event(event, graph)
        enriched_all.extend(enriched)
        certificates_all.extend(certificates)
    return {
        "events": enriched_all,
        "path_certificates": certificates_all,
    }


def main(argv=None):
    global MAX_DEPTH
    parser = argparse.ArgumentParser(description="风险传播（模块 10）")
    parser.add_argument("--events", required=True, help="模块 9 输出的 events.json")
    parser.add_argument("--graph-before", required=True, help="t0 图 JSON（模块 8 输出）")
    parser.add_argument("--graph-after", required=True, help="t1 图 JSON（模块 8 输出）")
    parser.add_argument("--output", required=True, help="输出 propagated.json 路径")
    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH,
                        help=f"最大传播深度（默认 {MAX_DEPTH}）")
    args = parser.parse_args(argv)

    MAX_DEPTH = args.max_depth

    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    graph_before = load_graph(args.graph_before)
    graph_after = load_graph(args.graph_after)

    result = propagate(events, graph_before, graph_after)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    by_decision: dict[str, int] = {}
    for item in result["events"]:
        by_decision[item["decision"]] = by_decision.get(item["decision"], 0) + 1
    print(f"种子事件：{len(events)}，传播后事件：{len(result['events'])}，"
          f"路径证书：{len(result['path_certificates'])}")
    print(f"三级判定分布：{by_decision}")
    print(f"已写入 {output_path}")


if __name__ == "__main__":
    main()
