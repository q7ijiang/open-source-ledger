# 模块 9：Delta 变更检测（delta_engine.py）

| 项目 | 内容 |
|---|---|
| 负责人 | B（算法核心） |
| 状态 | 已完成，随 `main` 交付 |
| 对应任务 | 深度部分 · 模块 9 |
| 输入数据 | 两个时间点的标准化快照（t0 / t1），典型来源是模块 1/3 从 BOM 与 ModelScope API 产出的资产与血缘边 |
| 关联测试 | `tests/test_delta_engine.py`（13 项） |

## 一句话摘要

对比 t0 / t1 两份快照，用 **`canonical_id` + `entity_key` 双索引**区分"同一实体换版本"与"实体增删"，产出**八类变更事件**；每个事件带 `before`/`after`、自身证据等级与初步判定，并把血缘边事件的种子统一指向**上游变化资产**（`edge.target`）。

## 输入

| 输入 | 说明 |
|---|---|
| `before_assets[]` / `after_assets[]` | 两个快照的资产列表 |
| `before_edges[]` / `after_edges[]` | 两个快照的血缘边 |
| 资产字段要求 | `canonical_id`（版本化）、`entity_key`（无版本）、`license`、`evidence_chain`、`merge_status` |

## 输出

`detect_delta()` 返回事件数组，每条结构：

```json
{
  "event_id": "evt-t1-001",
  "change_type": "license_changed",
  "seed": "model:Qwen/Qwen-Image-2.1@master",
  "before": {...}, "after": {...},
  "evidence_level": "A",
  "decision": "RISK_CONFIRMED",
  "direction": {"direction": "严格→宽松", "risk_increased": false, "ai_involved": true},
  "path": []
}
```

`path` 在此阶段为空，由模块 10 沿血缘图填充。

## 八类事件

| 事件类型 | 触发条件 | 种子（seed） | 证据来源 |
|---|---|---|---|
| `license_changed` | 同一资产许可证文本变化 | 该资产 | 资产自身证据链 |
| `ancestor_added` | t1 新增血缘边且目标非数据集 | **`edge.target`（上游）** | 边证据；目标缺失则降为 C |
| `ancestor_removed` | t1 消失血缘边且目标非数据集 | `edge.target` | 边证据 |
| `dataset_added` | 新增边且目标 `asset_type == dataset` | `edge.target` | 边证据 |
| `dataset_removed` | 移除边且目标为数据集 | `edge.target` | 边证据 |
| `evidence_downgrade` | 同一资产证据等级变弱 | 该资产 | 新旧较弱者 |
| `version_changed` | `entity_key` 相同、`canonical_id` 版本不同 | 新版本资产 | 资产证据 |
| `version_upgraded` | 同上，且由"无版本"变为"有版本" | 新版本资产 | 资产证据 |

## 为什么要做

1. 只看"当前许可证"无法回答"上游变了有没有传导下来"，必须做**时间维度的差异**。
2. 朴素按 `name` 比对会把"同一实体换版本"误判成"实体消失 + 新增"，产生噪声事件。
3. 边事件的种子方向如果取错（取 `edge.source` 而非 `target`），风险源会指向下游，传播阶段路径证书恒为 0——这是本模块曾经的 **P0 缺陷**，现已修复。

## 具体怎么做

### 步骤 1：双索引

```
asset_index  : canonical_id → asset          # 精确定位"同一版本的同一实体"
entity_index : entity_key   → [canonical_id] # 辅助判断"仅版本变化"
```

### 步骤 2：资产级比对

`canonical_id` 命中 → 比较 `license`（`license_changed`）与证据等级（`evidence_downgrade`）；
未命中但 `entity_key` 命中 → 产出 `version_changed` / `version_upgraded`（由是否有旧版本决定）。

### 步骤 3：边级比对

边的签名按 `(source, target, edge_type)` 对齐。新增边 → `ancestor_added` / `dataset_added`；消失边 → `ancestor_removed` / `dataset_removed`。**种子一律取 `edge.target`**。

### 步骤 4：合并不确定性

同一 `entity_key` 在同一快照有多个 `canonical_id` 时**不自行折叠**：只有模块 2 已判定全部 `MERGED` 才取代表，否则保留 `merge_status` / `reason_code` / `rule_version` 供审计。`REVIEW` / `UNDETERMINED` 资产不视为同一实体。

## 验证

| 验证项 | 数据 | 结论 |
|---|---|---|
| 六类事件覆盖 | `scenario_t0/t1_*` | 恰好 6 类：`license_changed`、`ancestor_added/removed`、`dataset_added/removed`、`evidence_downgrade` ✓ |
| 版本事件 | 内联夹具（`package:pypi/ms@1.0.0 → @2.0.0`） | `version_changed` / `version_upgraded` 正确 ✓ |
| 种子方向 | `ancestor_added` | 种子为 `edge.target`（缺失祖先 `Qwen/Qwen2.5-7B`）✓ |
| 方向判定 | `license_changed` | 带 `compare_direction` 结果 ✓ |
| 无变化 | t0 自比 | 0 事件 ✓ |
| 真实数据 | 项目级 BOM 45 组件 t0/t1 | 2 事件、证书 19 ✓ |

## 已知边界

- **不做跨实体的语义合并**：`foo-model` 改名成 `bar-model` 会被识别为"一删一增"两个事件。
- **证据等级变化即事件**：即使许可证没变，证据从 A 降到 C 也会产出 `evidence_downgrade`（这是有意的——同一结论的可信度下降了）。
- **聚合计数节点的变化会被计为事件**：ModelScope 的 `Total` 计数存在日间波动（实测 2091→2246），这类波动可能产生噪声事件，目前未过滤。
