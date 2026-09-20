# 模块 10：风险传播

| 项目 | 内容 |
|---|---|
| 负责人 | B |
| 状态 | 待验收 |
| 完成日期 | 2026-09-20 |
| 对应任务 | 深度部分 · 模块 10 |

## 一句话摘要

以 Delta 检测（模块 9）的事件为种子，在血缘图上做反向 BFS，沿路径按 weakest link 传播证据等级，为每个受影响资产输出三级判定（RISK_CONFIRMED / RISK_POTENTIAL / UNDETERMINED）和路径证书。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| 事件 JSON | 模块 9 输出 `events.json` | 变更种子事件 |
| t0 图 JSON | 模块 8 输出 `graph_t0.json` | 祖先移除类事件在 before 图上传播 |
| t1 图 JSON | 模块 8 输出 `graph_t1.json` | 其余事件在 after 图上传播 |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| 传播代码 | `propagation_engine.py` | 反向 BFS + weakest link + 路径证书 |
| 传播结果 JSON | 如 `out/propagated.json` | `events`（种子 + 受影响资产）+ `path_certificates` |

## 为什么要做

1. 只报"基座模型许可证变了"不够，必须回答"哪些下游资产受影响、影响多严重、证据可靠吗"。
2. 证据可靠性需要沿路径逐跳衰减：路径上有一条 B/C 级证据，结论就不能是"已确认"——这就是 weakest link 规则。
3. 路径证书让每次判定可复现、可审计（每条边、每个证据字段、每个判定都有据可查）。

## 具体怎么做

### 步骤 1：按事件类型选图

- `license_changed / evidence_downgrade / ancestor_added / dataset_added` 在 t1 图上传播（新状态下的血缘关系）；
- `ancestor_removed / dataset_removed` 在 t0 图上传播（被移除的边仍属于旧快照）。

### 步骤 2：反向 BFS

`reverse_bfs(graph, seed)`：从种子出发沿反向边遍历（`predecessors`），找出所有依赖 / 派生自 / 训练自种子的资产。路径步骤方向为"受影响资产 → … → 种子"，与接口约定示例一致。visited 集合保证环（SCC）不产生死循环。

### 步骤 3：选边规则

同一对节点存在并行边时，选一条代表性边作为路径步骤：先取证据最弱（最保守）的边；同等级时优先 `derived_from > trained_on > depends_on`。

### 步骤 4：weakest link 传播与三级判定

`path_evidence()` = 路径各步骤证据与种子事件证据中最弱的一方（A > B > C，取最弱）；映射到三级判定。缺失祖先（边指向无元数据的节点）强制 UNDETERMINED。

### 步骤 5：路径证书

每个受影响资产生成一份证书：seed、affected、path、hop_count、weakest_evidence、decision、termination（exhausted / max_depth / scc_cycle）、missing_ancestor、path_fingerprint（SHA-1）、verified。

## 得到了什么

以 t0/t1 测试夹具为例：
- 7 个种子事件 → 15 个传播后事件、8 份路径证书；
- 三级判定分布：RISK_CONFIRMED × 3、RISK_POTENTIAL × 7、UNDETERMINED × 5；
- 例：Llama-2-7b 许可证变更（A 级证据）→ finetuned-model RISK_CONFIRMED（A 级路径）、serving-model RISK_POTENTIAL（路径含 B 级边）；
- 例：`example-parser ↔ lib-x` 成环，传播正常终止并标记 `scc_cycle`。

## 暴露了什么问题

| 问题 | 影响 | 交给哪个模块解决 |
|---|---|---|
| 反向 BFS 只保证"最短跳数"路径，不保证"证据最优"路径 | 存在多条路径时可能不是最保守的 | 已用 weakest link 取路径最弱证据兜底；如需证据最优路径可扩展为最短路+证据加权 |
| 种子事件本身（path 为空）只有自己的证据，不反映下游 | 需要配合传播事件看全貌 | 模块 11 报告时按种子聚合种子+受影响事件 |

## 如何验证

1. 依次运行模块 8 → 9 → 10（命令见各文件头），确认传播结果 JSON 生成。
2. 抽查关键路径：路径方向、证据等级、三级判定是否符合 weakest link 规则。
3. 循环图（如测试夹具中 parser↔lib-x）能正常终止，证书标记 `scc_cycle`。
4. `python -m pytest tests/test_propagation_engine.py`：回归测试全部通过。

## 相关文件

| 文件 | 路径 |
|---|---|
| 传播代码 | `propagation_engine.py` |
| 测试夹具 | `tests/fixtures/deep_t0/t1_*.json` |
| 回归测试 | `tests/test_propagation_engine.py` |

## 给队友的话

- 对 A：模块 13 集成时调用 `propagate(events, graph_before, graph_after)`；`--max-depth` 默认 10 层（项目风险降级方案）。
- 对 C：增强层报告直接消费 `propagated.json`：`events` 做变更摘要、`path_certificates` 做路径证书展示。
- 对 A/C：传播所用图若直接来自模块 8 输出，SCC 信息已内置；直接用 `build_graph` 构建的图也会自动现场计算环。
