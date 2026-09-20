# 模块 9：Delta 检测

| 项目 | 内容 |
|---|---|
| 负责人 | B |
| 状态 | 待验收 |
| 完成日期 | 2026-09-20 |
| 对应任务 | 深度部分 · 模块 9 |

## 一句话摘要

对比两个时间快照（t0 / t1）的资产列表与血缘边，识别出六类变更事件，输出符合接口约定的事件对象（path 由模块 10 传播时填充）。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| t0 资产列表 + 血缘边 | 深度测试数据（C 准备） | before 快照 |
| t1 资产列表 + 血缘边 | 深度测试数据（C 准备） | after 快照 |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| 检测代码 | `delta_engine.py` | 事件检测逻辑 |
| 事件 JSON | 如 `out/events.json` | 六类变更事件，字段符合接口约定 |

## 为什么要做

1. 合规风险往往来自"变化"：许可证换了、祖先加了、证据降级了，静态清单看不出来。
2. 风险传播（模块 10）需要明确的"种子"事件作为起点，Delta 检测就是种子的来源。
3. 接口约定的六类变更需要统一识别规则，避免三人各自实现产生口径分歧。

## 具体怎么做

### 步骤 1：按 canonical_id 对齐两个快照

`asset_index()` 建立 before/after 资产索引，`edge_set()` 建立边签名（source, target, edge_type）集合。

### 步骤 2：识别资产级变更

- **license_changed**：同一资产许可证字段发生变化。事件证据取变更前后许可证证据中较弱的一方（weakest link）。
- **evidence_downgrade**：同一资产、同一 `source_field` 的证据等级下降（A→B、A→C、B→C），事件证据取降级后的等级。

### 步骤 3：识别边级变更

- 仅在 after 出现的边 → `ancestor_added`（新祖先）或 `dataset_added`（trained_on 指向 dataset 资产）；
- 仅在 before 出现的边 → `ancestor_removed` 或 `dataset_removed`；
- 边指向的资产未出现在 BOM 中（缺失祖先）→ 证据强制降为 C 级、判定 UNDETERMINED。

### 步骤 4：三级判定映射

`A → RISK_CONFIRMED`，`B → RISK_POTENTIAL`，`C / 缺证据 → UNDETERMINED`。

## 得到了什么

以 t0/t1 测试夹具为例，检测出 7 个事件：
- license_changed × 2（Llama-2-7b、example-parser）
- evidence_downgrade × 1（finetuned-model）
- ancestor_added × 1（serving-model + Qwen，缺失祖先 → UNDETERMINED）
- ancestor_removed × 1（serving-model − old-model）
- dataset_added × 1、dataset_removed × 1

## 暴露了什么问题

| 问题 | 影响 | 交给哪个模块解决 |
|---|---|---|
| 事件本身只携带种子信息，不带传播路径 | 无法直接回答"谁受影响" | 模块 10 沿图反向 BFS 填充 path |
| 缺失祖先的边证据等级可能被标为 A/B | 会误判为已确认 | 模块 9 已在检测时强制降为 C 级 |

## 如何验证

1. 运行 `python delta_engine.py`（参数见文件头），确认六类事件均被识别。
2. 检查事件 JSON：每个事件含 `event_id/seed/change_type/before/after/path/evidence_level/decision` 且 `path == []`。
3. `python -m pytest tests/test_delta_engine.py`：回归测试全部通过。

## 相关文件

| 文件 | 路径 |
|---|---|
| 检测代码 | `delta_engine.py` |
| 测试夹具 | `tests/fixtures/deep_t0/t1_*.json` |
| 回归测试 | `tests/test_delta_engine.py` |

## 给队友的话

- 对 A：`detect_delta()` 可被模块 13 直接调用；事件字段与接口约定 v0.1 完全一致。
- 对 C：深度测试数据只需覆盖"许可证变更、祖先新增/移除、数据集新增/移除、证据降级"各至少一例，本模块测试夹具可作参考样例。
- 对 C：增强层报告的"变更摘要"直接用本模块输出的事件列表即可。
