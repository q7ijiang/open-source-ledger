# -*- coding: utf-8 -*-
"""visualize_lineage.py — 用 networkx + matplotlib 把血缘图渲染成分层 PNG。

布局规则：
- 模型节点按血缘深度分层（基座=0，一层微调=1，…），祖宗在上、后代在下；
- derived_from 边箭头从上游（祖宗）指向下游（后代）；
- 数据集节点放在右侧单独一列，trained_on 边从模型连到数据集；
- 模型深蓝、数据集橙、derived_from 红色实线、trained_on 蓝色虚线，右上角图例。

用法：
    python visualize_lineage.py --graph out/hf_lineage/graph.json \
                                --output outputs/lineage_graph.png

    # diff 模式：叠加风险传播高亮（变更=红、受影响=橙、无关=灰）
    python visualize_lineage.py --graph out/graph_t1.json --output outputs/diff.png \
                                --events out/events.json --certificates out/certificates.json
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, Patch  # noqa: E402
from matplotlib.transforms import ScaledTranslation  # noqa: E402

# 中文字体（用于 diff 模式的图例/标题/标签前缀），避免默认 DejaVu Sans 缺字显示为方框
plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans SC",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

# 颜色
MODEL_COLOR = "#4A7EBB"
DATASET_COLOR = "#E8A33D"
DERIVED_COLOR = "#d62728"
TRAINED_COLOR = "#1f77b4"
DEFAULT_NODE_COLOR = "#55a868"
DEFAULT_EDGE_COLOR = "#7f7f7f"

# 风险传播（diff 模式）颜色与线宽
CHANGE_COLOR = "#d62728"
AFFECTED_COLOR = "#ff7f0e"
UNRELATED_COLOR = "#cccccc"
PROPAGATION_EDGE_COLOR = "#d62728"
PROPAGATION_EDGE_WIDTH = 2.5
UNRELATED_EDGE_WIDTH = 0.8

# 证据等级（A/B/C）对应的传播路径边颜色：A=深红、B=橙红、C=浅红
EVIDENCE_EDGE_COLORS = {
    "A": "#7a0000",
    "B": "#c0392b",
    "C": "#e67e73",
}

# 三级判定颜色：RISK_CONFIRMED 深橙、RISK_POTENTIAL 浅橙、UNDETERMINED 黄
DECISION_COLORS = {
    "RISK_CONFIRMED": "#d95f02",
    "RISK_POTENTIAL": "#ff9d4d",
    "UNDETERMINED": "#f4d03f",
}

# 尺寸与布局参数
MODEL_RADIUS = 0.35
DATASET_RADIUS = MODEL_RADIUS * 0.6   # 数据集半径 = 模型的 60%
DEPTH_SPACING = 1.4                    # 相邻血缘深度的垂直间距
DATASET_SPACING = 0.8                  # 右侧数据集列的节点间距
DATASET_X_GAP = 1.8                    # 数据集列与模型列的横向间距
LABEL_MAX_LEN = 20
LABEL_LONG_MAX_LEN = 30   # 标签冲突时使用的更长显示长度
LABEL_V_GAP = 0.08

# 大图自动切换参数
LARGE_GRAPH_THRESHOLD = 50
LARGE_MAX_NODES = 100               # 模式 3：过滤孤立节点后仍超此上限，只保留度数最高 100 个
LARGE_NODE_RADIUS_SCALE = 0.3
LARGE_TOP_LABEL_NODES = 20
LARGE_EDGE_ALPHA = 0.25
LARGE_FIG_WIDTH_IN = 16.0
LARGE_FIG_HEIGHT_IN = 1600.0 / 150.0


def load_graph(path: Path) -> nx.MultiDiGraph:
    """从 graph.json 还原 networkx 有向多图。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    graph = nx.MultiDiGraph()
    for node in data.get("nodes", []):
        canonical_id = node.get("canonical_id")
        if not canonical_id:
            continue
        graph.add_node(
            canonical_id,
            **{key: value for key, value in node.items() if key != "canonical_id"},
        )
    for edge in data.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        graph.add_edge(
            source,
            target,
            **{key: value for key, value in edge.items() if key not in ("source", "target")},
        )
    return graph


def load_change_nodes(path: Path) -> set[str]:
    """从 events.json 提取变更节点集合（events[].seed）。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("events", data.get("nodes", []))
    return {str(item.get("seed")) for item in data if item.get("seed")}


def _evidence_rank(level: str) -> int:
    """证据等级排序：A 最强(0)、C 最弱(2)；未知按最弱处理。"""
    return {"A": 0, "B": 1, "C": 2}.get(str(level).upper(), 2)


def load_diff_info(path: Path) -> dict:
    """从 certificates.json 提取受影响节点、传播路径边、边上证据等级与节点判定。

    返回 dict，字段：
        affected: set[str]                         受影响节点集合
        edges: set[tuple[str, str]]                传播路径边 (source, target)
        edge_evidence: dict[tuple[str, str], str]  每条边的证据等级 (A/B/C)
        node_decision: dict[str, str]              受影响节点 -> 三级判定
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("path_certificates", data.get("certificates", []))
    affected: set[str] = set()
    edges: set[tuple[str, str]] = set()
    edge_evidence: dict[tuple[str, str], str] = {}
    node_decision: dict[str, str] = {}
    for cert in data:
        affected_id = cert.get("affected")
        decision = cert.get("decision")
        if affected_id:
            affected_id = str(affected_id)
            affected.add(affected_id)
            if decision and affected_id not in node_decision:
                node_decision[affected_id] = str(decision)
        for step in cert.get("path", []) or []:
            source = step.get("source")
            target = step.get("target")
            if source and target:
                key = (str(source), str(target))
                edges.add(key)
                level = str(step.get("evidence_level") or "").upper()
                if level and (
                    key not in edge_evidence
                    or _evidence_rank(level) > _evidence_rank(edge_evidence[key])
                ):
                    edge_evidence[key] = level
    return {
        "affected": affected,
        "edges": edges,
        "edge_evidence": edge_evidence,
        "node_decision": node_decision,
    }


def _truncate(text: str, max_len: int) -> str:
    """超长时中间省略、保留结尾，确保不截断关键后缀。"""
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    keep = max_len - 3
    tail = keep // 2
    head = keep - tail
    return text[:head] + "..." + text[-tail:]


def short_label(name: str) -> str:
    """取名称最后一段（去掉 org/ 前缀），超 20 字符时中间省略以保留结尾。"""
    name = (name or "").strip()
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    return _truncate(name, LABEL_MAX_LEN)


def _canonical_tail(canonical_id: str, max_len: int = 30) -> str:
    """取 canonical_id 的后 max_len 个字符；超长时前置省略号。"""
    canonical_id = (canonical_id or "").strip()
    if len(canonical_id) <= max_len:
        return canonical_id
    return "…" + canonical_id[-(max_len - 1):]


def compute_node_labels(graph: nx.MultiDiGraph) -> dict[str, str]:
    """为每个节点分配展示标签，保证不同 canonical_id 的标签互不相同。

    规则：
    1. 先按短标签（去 org/ 前缀）分配；
    2. 若多个节点的短标签相同（如裸名 bert-base-uncased 与
       google-bert/bert-base-uncased 截断后相同），冲突组改用更长显示：
       优先保留 org/ 前缀的全名，其次 canonical_id 后 30 字符；
    3. 兜底：若仍撞车，追加短后缀，确保全局唯一。
    """
    base: dict[str, str] = {}
    for nid, attrs in graph.nodes(data=True):
        base[nid] = short_label(attrs.get("name") or nid)

    groups: dict[str, list[str]] = defaultdict(list)
    for nid, lbl in base.items():
        groups[lbl].append(nid)

    labels: dict[str, str] = {}
    used: set[str] = set()
    for nid in sorted(graph.nodes()):
        attrs = graph.nodes[nid]
        name = (attrs.get("name") or nid).strip()
        candidates: list[str] = []
        if len(groups[base[nid]]) == 1:
            candidates.append(base[nid])
        else:
            # 冲突组：优先保留 org/ 前缀，其次 canonical_id 后 30 字符
            candidates.append(_truncate(name, LABEL_LONG_MAX_LEN))
            candidates.append(_canonical_tail(nid))
            candidates.append(_truncate(nid, LABEL_LONG_MAX_LEN))
        assigned = False
        for cand in candidates:
            if cand not in used:
                labels[nid] = cand
                used.add(cand)
                assigned = True
                break
        if not assigned:
            suffix = f" ({nid[-6:]})"
            cand = f"{base[nid]}{suffix}"
            counter = 2
            while cand in used:
                cand = f"{base[nid]}{suffix}#{counter}"
                counter += 1
            labels[nid] = cand
            used.add(cand)
    return labels


def compute_model_depths(graph: nx.MultiDiGraph) -> dict:
    """基于 derived_from 边计算模型拓扑深度：基座=0，逐层 +1。

    图中 derived_from 边 u->v 表示“u 衍生自 v”（u=下游/后代，v=上游/祖宗）。
    这里构造 v->u 的 DAG（祖宗->后代），再求最长路深度。
    """
    dag = nx.DiGraph()
    for nid, attrs in graph.nodes(data=True):
        if attrs.get("asset_type") == "model":
            dag.add_node(nid)
    for u, v, _key, data in graph.edges(keys=True, data=True):
        if data.get("edge_type") != "derived_from":
            continue
        if dag.has_node(u) and dag.has_node(v):
            dag.add_edge(v, u)  # 祖宗 v -> 后代 u
    depth: dict = {}
    for node in nx.topological_sort(dag):
        preds = list(dag.predecessors(node))
        depth[node] = 0 if not preds else max(depth[p] for p in preds) + 1
    return depth


def _compute_single_layout(graph: nx.MultiDiGraph) -> dict:
    """单个连通分量的层次布局：模型按深度纵向分层，数据集放右侧单列。"""
    depths = compute_model_depths(graph)
    model_nodes = [
        n for n, a in graph.nodes(data=True) if a.get("asset_type") == "model"
    ]
    right_nodes = [
        n for n, a in graph.nodes(data=True) if a.get("asset_type") != "model"
    ]

    depth_groups: dict = defaultdict(list)
    for n in model_nodes:
        depth_groups[depths.get(n, 0)].append(n)

    pos: dict = {}
    # 模型：y = -depth * DEPTH_SPACING（祖宗 depth=0 在上，后代在下）；同层横向居中展开
    for d in sorted(depth_groups):
        nodes = depth_groups[d]
        if len(nodes) == 1:
            xs = [0.0]
        else:
            xs = [i - (len(nodes) - 1) / 2.0 for i in range(len(nodes))]
        for n, x in zip(nodes, xs):
            pos[n] = (x, -float(d) * DEPTH_SPACING)

    # 数据集（及其它非模型节点）：右侧单独一列，纵向均匀排布，保证不重叠
    right_x = (max(x for x, _y in pos.values()) if pos else 0.0) + DATASET_X_GAP
    for i, n in enumerate(right_nodes):
        pos[n] = (right_x, -float(i) * DATASET_SPACING)

    return pos


def compute_layout(graph: nx.MultiDiGraph) -> dict:
    """层次布局：每个连通分量独立布局，再按网格排列，避免分量互相合并。"""
    components = [
        graph.subgraph(c) for c in nx.connected_components(graph.to_undirected())
    ]
    components.sort(key=lambda g: g.number_of_nodes(), reverse=True)
    if len(components) <= 1:
        return _compute_single_layout(graph)

    local_layouts = [_compute_single_layout(comp) for comp in components]
    bounds = []
    for layout in local_layouts:
        if not layout:
            bounds.append((0.0, 0.0, 0.0, 0.0))
            continue
        xs = [p[0] for p in layout.values()]
        ys = [p[1] for p in layout.values()]
        bounds.append((min(xs), max(xs), min(ys), max(ys)))

    max_width = max(b[1] - b[0] for b in bounds) or 1.0
    max_height = max(b[3] - b[2] for b in bounds) or 1.0
    cols = max(1, int(math.ceil(math.sqrt(len(local_layouts)))))
    col_gap = 2.0
    row_gap = 2.0

    pos: dict = {}
    for index, (layout, (min_x, _max_x, _min_y, max_y)) in enumerate(
        zip(local_layouts, bounds)
    ):
        col = index % cols
        row = index // cols
        offset_x = col * (max_width + col_gap)
        offset_y = -row * (max_height + row_gap)
        for nid, (x, y) in layout.items():
            pos[nid] = (x - min_x + offset_x, y - max_y + offset_y)
    return pos


def compute_force_layout(graph: nx.MultiDiGraph) -> dict:
    """力导向布局：spring_layout(k=3/sqrt(n), iterations=200)，异常时回退 kamada_kawai_layout。"""
    simple = nx.Graph()
    simple.add_nodes_from(graph.nodes())
    simple.add_edges_from((u, v) for u, v, _key in graph.edges(keys=True))
    n = simple.number_of_nodes()
    k = 3.0 / math.sqrt(n) if n > 0 else None
    try:
        return nx.spring_layout(simple, seed=42, k=k, iterations=200)
    except Exception:
        return nx.kamada_kawai_layout(simple)


def filter_isolated(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """过滤孤立节点：仅保留度数 ≥ 1 的节点。"""
    keep = [nid for nid in graph.nodes() if graph.degree(nid) >= 1]
    return graph.subgraph(keep).copy()


def compute_top_degree_nodes(graph: nx.MultiDiGraph, top_k: int) -> set[str]:
    """返回度数最高的 top_k 个节点。"""
    if top_k <= 0 or graph.number_of_nodes() == 0:
        return set()
    degree = graph.degree()
    ordered = sorted(graph.nodes(), key=lambda n: degree[n], reverse=True)
    return set(ordered[:top_k])


def _node_radius(attrs: dict) -> float:
    return MODEL_RADIUS if attrs.get("asset_type") == "model" else DATASET_RADIUS


def _node_color(attrs: dict) -> str:
    asset_type = attrs.get("asset_type")
    if asset_type == "model":
        return MODEL_COLOR
    if asset_type == "dataset":
        return DATASET_COLOR
    return DEFAULT_NODE_COLOR


def _draw_arrow(ax, pos, u, v, color, linestyle, r_u, r_v, linewidth=1.4, alpha=1.0) -> None:
    """从 u 指向 v 的箭头，两端缩进到各自节点圆边。"""
    x1, y1 = pos[u]
    x2, y2 = pos[v]
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return
    ux, uy = dx / length, dy / length
    start = (x1 + ux * r_u, y1 + uy * r_u)
    end = (x2 - ux * r_v, y2 - uy * r_v)
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=14,
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            alpha=alpha,
            zorder=2,
            shrinkA=0,
            shrinkB=0,
        )
    )


def render(graph: nx.MultiDiGraph, out_path: Path) -> str:
    """渲染血缘图并返回布局类型：≤50 节点用层次布局，>50 节点用力导向布局。"""
    original_count = graph.number_of_nodes()
    large = original_count > LARGE_GRAPH_THRESHOLD

    # 模式 1：只画有血缘边的节点（过滤孤立节点，度数 ≥ 1）
    filtered = filter_isolated(graph)
    # 模式 3：大图过滤孤立节点后仍超上限，仅保留度数最高的 100 个节点
    if large and filtered.number_of_nodes() > LARGE_MAX_NODES:
        top = compute_top_degree_nodes(filtered, LARGE_MAX_NODES)
        filtered = filtered.subgraph(top).copy()
    graph = filtered

    node_count = graph.number_of_nodes()
    print(f"渲染节点：{node_count}（过滤前 {original_count}），边：{graph.number_of_edges()}")

    if large:
        pos = compute_force_layout(graph)
        figsize = (LARGE_FIG_WIDTH_IN, LARGE_FIG_HEIGHT_IN)
        radius_scale = LARGE_NODE_RADIUS_SCALE
        edge_alpha = LARGE_EDGE_ALPHA
        label_nodes = compute_top_degree_nodes(graph, LARGE_TOP_LABEL_NODES)
        bbox_inches = None
    else:
        pos = compute_layout(graph)
        figsize = (12, 12)
        radius_scale = 1.0
        edge_alpha = 1.0
        label_nodes = None
        bbox_inches = "tight"

    fig, ax = plt.subplots(figsize=figsize)

    # 1. 边：derived_from 反向（祖宗->后代），trained_on 正向（模型->数据集）
    for u, v, _key, data in graph.edges(keys=True, data=True):
        etype = data.get("edge_type")
        r_u = _node_radius(graph.nodes[u]) * radius_scale
        r_v = _node_radius(graph.nodes[v]) * radius_scale
        if etype == "derived_from":
            # 数据中 u(下游/后代) -> v(上游/祖宗)；绘制时反向：祖宗 -> 后代（从上往下）
            _draw_arrow(ax, pos, v, u, DERIVED_COLOR, "solid", r_v, r_u,
                        alpha=edge_alpha)
        elif etype == "trained_on":
            _draw_arrow(ax, pos, u, v, TRAINED_COLOR, "dashed", r_u, r_v,
                        alpha=edge_alpha)
        else:
            _draw_arrow(ax, pos, u, v, DEFAULT_EDGE_COLOR, "solid", r_u, r_v,
                        alpha=edge_alpha)

    # 2. 节点
    for nid, (x, y) in pos.items():
        attrs = graph.nodes[nid]
        ax.add_patch(
            Circle(
                (x, y),
                radius=_node_radius(attrs) * radius_scale,
                facecolor=_node_color(attrs),
                edgecolor="white",
                linewidth=1.0,
                zorder=3,
            )
        )

    # 3. 标签（大图只给度数最高的 20 个节点画标签）
    labels = compute_node_labels(graph)
    for nid, (x, y) in pos.items():
        if large and nid not in label_nodes:
            continue
        attrs = graph.nodes[nid]
        ax.text(
            x,
            y - _node_radius(attrs) * radius_scale - LABEL_V_GAP,
            labels[nid],
            ha="center",
            va="top",
            fontsize=8,
            zorder=4,
        )

    # 4. 图例（右上角）
    legend_handles = [
        Patch(facecolor=MODEL_COLOR, edgecolor="white", label="model"),
        Patch(facecolor=DATASET_COLOR, edgecolor="white", label="dataset"),
        Line2D([0], [0], color=DERIVED_COLOR, linestyle="-", linewidth=1.4,
               marker=">", markersize=7, label="derived_from"),
        Line2D([0], [0], color=TRAINED_COLOR, linestyle="--", linewidth=1.4,
               marker=">", markersize=7, label="trained_on"),
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=9, framealpha=0.9)

    # 5. 坐标范围与标题
    if pos:
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        ax.set_xlim(min(xs) - 1.2, max(xs) + 1.2)
        ax.set_ylim(min(ys) - 1.0, max(ys) + 1.2)
    ax.set_aspect("equal")
    ax.axis("off")
    layout_name = "force-directed" if large else "hierarchical"
    ax.set_title(
        f"Lineage Graph ({graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges, {layout_name} layout)",
        fontsize=12,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches=bbox_inches)
    plt.close()
    return layout_name


def compute_diff_nodes(graph: nx.MultiDiGraph, diff: dict) -> set[str]:
    """模式 2：变更节点 + 受影响节点 + 传播路径上的中间节点。"""
    keep = set(diff.get("change", set()))
    keep |= set(diff.get("affected", set()))
    for source, target in diff.get("edges", set()):
        if graph.has_node(source):
            keep.add(source)
        if graph.has_node(target):
            keep.add(target)
    return {nid for nid in keep if graph.has_node(nid)}


def _node_diff_kind(nid: str, diff: dict) -> str:
    """返回节点在 diff 模式下的分类：change / affected / unrelated。"""
    if nid in diff["change"]:
        return "change"
    if nid in diff["affected"]:
        return "affected"
    return "unrelated"


def _node_diff_color(kind: str) -> str:
    return {
        "change": CHANGE_COLOR,
        "affected": AFFECTED_COLOR,
        "unrelated": UNRELATED_COLOR,
    }[kind]


def render_diff(graph: nx.MultiDiGraph, out_path: Path, diff: dict) -> None:
    """渲染风险传播图：只画变更/受影响/传播路径中间节点，其余不画。"""
    original_count = graph.number_of_nodes()
    change_nodes = set(diff["change"])
    affected_nodes = set(diff["affected"])
    keep = compute_diff_nodes(graph, diff)
    graph = graph.subgraph(keep).copy()
    intermediate_nodes = keep - change_nodes - affected_nodes
    print(
        f"渲染节点：{graph.number_of_nodes()}（过滤前 {original_count}；"
        f"变更 {len(change_nodes)}，受影响 {len(affected_nodes)}，"
        f"中间 {len(intermediate_nodes)}），边：{graph.number_of_edges()}"
    )

    pos = compute_layout(graph)
    propagation_edges = diff["edges"]
    edge_evidence = diff.get("edge_evidence", {})
    node_decision = diff.get("node_decision", {})

    fig, ax = plt.subplots(figsize=(12, 12))

    # 1. 边：传播路径按证据等级着色（A 深红 / B 橙红 / C 浅红），其余灰色细线
    for u, v, _key, data in graph.edges(keys=True, data=True):
        r_u = _node_radius(graph.nodes[u])
        r_v = _node_radius(graph.nodes[v])
        on_path = (u, v) in propagation_edges
        level = edge_evidence.get((u, v)) if on_path else None
        if on_path:
            color = EVIDENCE_EDGE_COLORS.get(level or "B", EVIDENCE_EDGE_COLORS["B"])
            linewidth = PROPAGATION_EDGE_WIDTH
        else:
            color = UNRELATED_COLOR
            linewidth = UNRELATED_EDGE_WIDTH
        if data.get("edge_type") == "derived_from":
            _draw_arrow(ax, pos, v, u, color, "solid", r_v, r_u, linewidth=linewidth)
        else:
            _draw_arrow(ax, pos, u, v, color, "solid", r_u, r_v, linewidth=linewidth)
        # 传播路径边：在中点标注证据等级
        if on_path and level:
            x_mid = (pos[u][0] + pos[v][0]) / 2.0
            y_mid = (pos[u][1] + pos[v][1]) / 2.0
            ax.text(
                x_mid,
                y_mid,
                f"({level})",
                ha="center",
                va="center",
                fontsize=7,
                zorder=5,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.6),
            )

    # 2. 节点：变更红、受影响橙、其余灰
    for nid, (x, y) in pos.items():
        attrs = graph.nodes[nid]
        kind = _node_diff_kind(nid, diff)
        ax.add_patch(
            Circle(
                (x, y),
                radius=_node_radius(attrs),
                facecolor=_node_diff_color(kind),
                edgecolor="white",
                linewidth=1.0,
                zorder=3,
            )
        )

    # 3. 标签（加前缀标记风险角色；受影响节点下方标注三级判定）
    labels = compute_node_labels(graph)
    for nid, (x, y) in pos.items():
        attrs = graph.nodes[nid]
        kind = _node_diff_kind(nid, diff)
        label = labels[nid]
        if kind == "change":
            label = f"[变更] {label}"
        elif kind == "affected":
            label = f"[受影响] {label}"
        anchor_y = y - _node_radius(attrs) - LABEL_V_GAP
        ax.text(
            x,
            anchor_y,
            label,
            ha="center",
            va="top",
            fontsize=8,
            zorder=4,
        )
        if kind == "affected":
            decision = node_decision.get(nid)
            if decision:
                ax.text(
                    x,
                    anchor_y,
                    decision,
                    ha="center",
                    va="top",
                    fontsize=7,
                    zorder=4,
                    fontweight="bold",
                    color=DECISION_COLORS.get(decision, "#000000"),
                    transform=ax.transData + ScaledTranslation(0, -12 / 72, fig.dpi_scale_trans),
                )

    # 4. 图例（说明颜色含义）
    legend_handles = [
        Patch(facecolor=CHANGE_COLOR, edgecolor="white", label="变更"),
        Patch(facecolor=AFFECTED_COLOR, edgecolor="white", label="受影响"),
        Patch(facecolor=UNRELATED_COLOR, edgecolor="white", label="无关"),
        Line2D([0], [0], color=EVIDENCE_EDGE_COLORS["A"], linestyle="-",
               linewidth=PROPAGATION_EDGE_WIDTH, marker=">", markersize=7,
               label="证据A"),
        Line2D([0], [0], color=EVIDENCE_EDGE_COLORS["B"], linestyle="-",
               linewidth=PROPAGATION_EDGE_WIDTH, marker=">", markersize=7,
               label="证据B"),
        Line2D([0], [0], color=EVIDENCE_EDGE_COLORS["C"], linestyle="-",
               linewidth=PROPAGATION_EDGE_WIDTH, marker=">", markersize=7,
               label="证据C"),
        Patch(facecolor=DECISION_COLORS["RISK_CONFIRMED"], edgecolor="white",
              label="RISK_CONFIRMED"),
        Patch(facecolor=DECISION_COLORS["RISK_POTENTIAL"], edgecolor="white",
              label="RISK_POTENTIAL"),
        Patch(facecolor=DECISION_COLORS["UNDETERMINED"], edgecolor="white",
              label="UNDETERMINED"),
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=8, framealpha=0.9)

    # 5. 坐标范围与标题
    if pos:
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        ax.set_xlim(min(xs) - 1.2, max(xs) + 1.2)
        ax.set_ylim(min(ys) - 1.0, max(ys) + 1.2)
    ax.set_aspect("equal")
    ax.axis("off")
    decision_counts: dict[str, int] = defaultdict(int)
    for decision in node_decision.values():
        decision_counts[decision] += 1
    ax.set_title(
        f"风险传播图（{len(diff['change'])} 处变更，"
        f"{len(diff['affected'])} 个受影响节点；"
        f"{decision_counts.get('RISK_CONFIRMED', 0)} 确认，"
        f"{decision_counts.get('RISK_POTENTIAL', 0)} 可能，"
        f"{decision_counts.get('UNDETERMINED', 0)} 无法判定）",
        fontsize=12,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="把血缘图渲染成 PNG")
    parser.add_argument("--graph", required=True, help="模块 8 的 graph.json")
    parser.add_argument("--output", required=True, help="输出 PNG 路径")
    parser.add_argument("--events", default=None,
                        help="events.json（可选）：触发 diff 风险高亮，与 --certificates 成对使用")
    parser.add_argument("--certificates", default=None,
                        help="certificates.json（可选）：受影响节点与传播路径")
    args = parser.parse_args(argv)

    graph = load_graph(Path(args.graph))

    if args.events or args.certificates:
        if not args.events or not args.certificates:
            parser.error("--events 与 --certificates 需同时提供")
        change_nodes = load_change_nodes(Path(args.events))
        diff_info = load_diff_info(Path(args.certificates))
        diff = {
            "change": change_nodes,
            "affected": diff_info["affected"],
            "edges": diff_info["edges"],
            "edge_evidence": diff_info["edge_evidence"],
            "node_decision": diff_info["node_decision"],
        }
        render_diff(graph, Path(args.output), diff)
        print(
            f"变更节点：{len(change_nodes)}，受影响节点：{len(diff_info['affected'])}，"
            f"传播路径边：{len(diff_info['edges'])}"
        )
    else:
        layout_name = render(graph, Path(args.output))

    print(f"原始图：节点 {graph.number_of_nodes()}，边 {graph.number_of_edges()}")
    if not (args.events or args.certificates):
        print(f"布局类型：{layout_name}")
    print(f"已写入 {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
