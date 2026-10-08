# 模块 9：Delta 检测

| 项目 | 内容 |
|---|---|
| 负责人 | B |
| 状态 | 待验收（v0.3 已按模块 2 版本化对齐，2026-10-01） |
| 完成日期 | 2026-09-20（首版）；2026-10-01（版本化迁移 + P0 修复） |
| 对应任务 | 深度部分 · 模块 9 |

## 一句话摘要

对比两个时间快照（t0 / t1）的资产列表与血缘边，识别变更事件（六类 + 版本变化两类），输出符合接口约定 v0.3 的事件对象（path 由模块 10 传播时填充）。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| t0 资产列表 + 血缘边 | 深度测试数据（C 准备） | before 快照 |
| t1 资产列表 + 血缘边 | 深度测试数据（C 准备） | after 快照 |
| 模块 2 版本化 canonical_id / entity_key / merge_status | bom_adapter.py / entity_resolver.py | 跨版本对齐依据 |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| 检测代码 | `delta_engine.py` | 事件检测逻辑 |
| 事件 JSON | 如 `out/events.json` | 事件列表，字段符合接口约定 v0.3 |

## 为什么要做

1. 合规风险往往来自"变化"：许可证换了、祖先加了、证据降级了，静态清单看不出来。
2. 风险传播（模块 10）需要明确的"种子"事件作为起点，Delta 检测就是种子的来源。
3. 模块 2 canonical_id 版本化后，跨版本许可证变更必须靠 entity_key 对齐，否则会漏报。

## 具体怎么做

### 步骤 1：建立双索引

- `asset_index()`：canonical_id -> asset（完全同一版本匹配）。
- `entity_index()`：entity_key -> {canonical_id: asset}（跨版本对齐辅助索引），用于区分"同一实体换版本"与"旧实体消失、新实体出现"。

### 步骤 2：资产级变更（同一 canonical_id）

- **license_changed**：同一资产许可证字段发生变化；事件证据取变更前后许可证证据中较弱的一方（weakest link）；附带 `direction`（license_db.compare_direction 结果）。
- **evidence_downgrade**：同一资产、同一 `source_field` 的证据等级下降（A→B、A→C、B→C）。

### 步骤 3：版本变化事件（同一 entity_key、不同 canonical_id）

- before/after 各取代表资产；仅当两侧无 REVIEW / UNDETERMINED 且同快照多 canonical_id 全部 MERGED 时才自动对齐。
- `version_changed`：换版本；`version_upgraded`：从无版本引用升级为带版本。
- seed 取 after 的 canonical_id；REVIEW / UNDETERMINED 不自动视为同一实体（不产生版本事件，事件 before/after 保留 reason_code）。

### 步骤 4：边级变更（seed 指向 edge.target）

- 仅在 after 出现的边 → `ancestor_added` 或 `dataset_added`；仅在 before 出现的边 → `ancestor_removed` 或 `dataset_removed`。
- **seed = edge.target（上游变化资产）**：P0 修复，修复前取 edge.source 导致真实链路 0 证书。
- before/after 取 target 资产的对应快照状态。
- 边指向的资产未出现在 BOM 中（缺失祖先）→ 证据强制降为 C 级、判定 UNDETERMINED。

### 步骤 5：三级判定映射

`A → RISK_CONFIRMED`，`B → RISK_POTENTIAL`，`C / 缺证据 → UNDETERMINED`。

## 得到了什么

以 t0/t1 测试夹具为例，检测出 7 个事件（边事件 seed 均为 edge.target）：
- license_changed × 2（Llama-2-7b、example-parser，均带 direction）
- evidence_downgrade × 1（finetuned-model）
- ancestor_added × 1（seed=Qwen2.5-7B 缺失祖先 → UNDETERMINED）
- ancestor_removed × 1（seed=old-model）
- dataset_added × 1（seed=new-training-data）、dataset_removed × 1（seed=training-data）

端到端（模块 8 → 9 → 10）：7 种子事件 → 19 传播事件、**12 张路径证书**（P0 修复后 > 0）。

## 暴露了什么问题

| 问题 | 影响 | 解决状态 |
|---|---|---|
| 边变更事件 seed 用 edge.source | 传播从错误方向出发，真实链路 0 证书 | 已修复：seed=edge.target（P0） |
| canonical_id 版本化后跨版本变更漏报 | 同实体换版本被当作无关新增/消失 | 已修复：entity_index + version_changed/upgraded |
| REVIEW / UNDETERMINED 资产被自动对齐 | 误报版本事件 | 已修复：不自动合并，保留 reason_code |
| 事件缺少许可证变更方向 | 报告无法判断风险升高/降低 | 已接入 license_db.compare_direction |

## 如何验证

1. `python -m pytest tests/test_delta_engine.py`：13 个测试（含 3 类新增：版本事件 / 同版本变更 / REVIEW 保留 reason_code）。
2. 运行 `python delta_engine.py`（参数见文件头），检查边事件 seed 是否为 edge.target。
3. 端到端：`python propagation_engine.py ...`，确认 `path_certificates > 0`。

## 相关文件

| 文件 | 路径 |
|---|---|
| 检测代码 | `delta_engine.py` |
| 测试夹具 | `tests/fixtures/deep_t0/t1_*.json` |
| 回归测试 | `tests/test_delta_engine.py` |

## 给队友的话

- 对 A：`detect_delta()` 可被模块 13 直接调用；事件字段与接口约定 v0.3 一致（含 direction、before/after 审计字段）。边变更事件 seed 为 edge.target。
- 对 C：深度测试数据覆盖"版本变化"（同 entity_key 不同 canonical_id）至少一例；增强层报告的"变更摘要"直接用本模块输出。
- 对 A：接口约定 v0.3 已同步事件对象变更（change_type 八类、before/after 审计字段、direction）。
