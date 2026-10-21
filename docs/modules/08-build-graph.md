# 模块 8：血缘图构建与 SCC 压缩（build_graph.py）

| 项目 | 内容 |
|---|---|
| 负责人 | B（算法核心） |
| 状态 | 已完成，随 `main` 交付 |
| 对应任务 | 深度部分 · 模块 8 |
| 数据来源 | 模块 1/3 产出的标准化资产；模块 2 的实体对齐结果；ModelScope 血缘边（证据 B） |
| 关联测试 | `tests/test_build_graph.py`（5 项） |

## 一句话摘要

把「标准化资产列表 + 血缘边列表」构造成 `networkx` 有向多重图，按节点与边的最弱证据聚合颜色语义，再用 **Tarjan/networkx 强连通分量（SCC）压缩**消除循环依赖，输出可序列化的 `graph.json`。

## 输入

| 输入 | 说明 |
|---|---|
| `assets[]` | 每个资产含 `canonical_id`（版本化）、`entity_key`、`asset_type`、`license`、`evidence_chain` |
| `edges[]` | `{source, target, edge_type, evidence_level, source_field}` |

边类型约定：`derived_from`（派生/微调/量化）、`trained_on`（数据集）、`depends_on`（工具依赖）。

**方向语义**：`source` 是下游衍生方，`target` 是上游祖先。这与「谁传染谁」的反向传播方向配套。

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| 图对象 | 内存 `nx.MultiDiGraph` | 供模块 9/10 使用 |
| 图快照 | `graph.json` | 含 `nodes` / `edges` / `scc` / `canonical_to_scc` / `compressed` / 三个计数 |

`graph_to_dict()` 的节点字段：`canonical_id`、`asset_type`、`name`、`version`、`license`、`evidence_chain`、`scc_id`；边字段：`source`、`target`、`edge_type`、`evidence_level`、`source_field`。

## 为什么要做

1. **算法需要图，而不是列表**：模块 10 要做反向 BFS，必须有邻接结构。
2. **真实血缘会成环**：模型互相 merge、工具互相依赖都可能形成环；不压缩会导致传播阶段死循环。
3. **证据要按最弱环节聚合**：一条边只有一个证据等级，但压缩后的"分量到分量"可能有多次观测，需要取最弱并记录次数。

## 具体怎么做

### 步骤 1：建图并补齐端点

遍历边时，若 `source` / `target` 不在资产列表里，就创建**占位节点**（无 `asset_type`）。这类节点即"缺失祖先"场景，模块 9 会据此产出 `UNDETERMINED` 事件。

### 步骤 2：证据等级排序

`EVIDENCE_ORDER = {A: 0, B: 1, C: 2}`，取最小值即最弱。节点证据取 `evidence_chain` 中最弱项；边证据取边自身字段。

### 步骤 3：SCC 压缩

```
FUNCTION compress_scc(graph):
    FOR EACH 强连通分量 c IN networkx.strongly_connected_components(graph):
        scc_id ← "scc-<n>"
        compressed.add_node(scc_id, members=c, size=len(c))
        FOR EACH 原始节点 v IN c: canonical_to_scc[v] = scc_id
    FOR EACH 原始边 (u → v) IN graph.edges:
        IF canonical_to_scc[u] != canonical_to_scc[v]:
            a, b ← canonical_to_scc[u], canonical_to_scc[v]
            compressed[a][b].evidence_level ← weakest(已有, 该边)
            compressed[a][b].count += 1
```

同分量内部的边被吞掉——这正是防环的关键：**环内节点折叠成一个点后，传播不可能在环里无限走**。

### 步骤 4：序列化

`graph_to_dict()` 把原图、SCC 映射与压缩图一并写出，供渲染层（`render_graph.py`）与报告层直接消费。

## 验证

| 验证项 | 数据 | 结论 |
|---|---|---|
| 建图规模 | `scenario_t1_*`（7 资产 / 7 边，含 1 个仅由边创建的基模） | 8 节点 / 7 边 ✓ |
| 边类型覆盖 | 同一夹具 | `derived_from` / `trained_on` / `depends_on` 齐全 ✓ |
| 并行边保留 | 两节点互指（`cycle_a ⇄ cycle_b`） | `MultiDiGraph` 两个方向各 1 条 ✓ |
| SCC 成环检测 | 同上 | 两节点被压成 1 个 `size=2` 的分量 ✓ |
| 最弱证据聚合 | 压缩边 | `evidence_level="B"`、`count>=1` ✓ |
| 真实数据规模 | 项目级语料 177 节点 / 137 边 | 建图成功，SCC 全单点（真实数据无环） |

## 已知边界

- **SCC 压缩后丢失环内拓扑**：报告能告诉你"这 2 个模型互相依赖"，但不能再还原环内方向。
- **占位节点没有元数据**：只有 `canonical_id`，`asset_type` 为空；下游需按"缺失祖先"处理，不能当普通资产判许可。
- **并行边按 evidence + source_field 去重**：同一对节点的重复观测会被合并计数，明细只保留最弱一条。
