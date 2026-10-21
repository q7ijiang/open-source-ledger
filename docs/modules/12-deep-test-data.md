# 模块 12：深度测试数据

> 状态更新（2026-10-21）：HF 版 `t0_bom.json` / `t1_bom.json`（Llama-2-7b 构造）已按清仓库要求删除（无代码/测试引用，且与 ModelScope 口径不一致）。深度测试数据现由 **`ms_t0_bom.json` / `ms_t1_bom.json`**（ModelScope Qwen-Image-2.1 场景）承担，见 `tests/test_diff_frozen_lineage.py`。

| 项目 | 内容 |
|---|---|
| 负责人 | C |
| 状态 | 已完成（ms_t0/ms_t1 已就绪，B 回归依赖） |
| 完成日期 | 2026-10-03（HF 版）/ 2026-10-09（MS 版） |
| 对应任务 | 深度部分 · 模块 12 |

## 一句话摘要

构造深度层双快照测试数据 `ms_t0_bom.json` / `ms_t1_bom.json`（ModelScope Qwen-Image-2.1 场景，含聚合降维节点），作为 delta_engine / propagation_engine 的联调输入；离线 diff 回归由 `tests/test_diff_frozen_lineage.py` 直接引用。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| 任务流程.pdf / 现状.docx | 组长发布 | S1–S8 八场景验收要求 |
| 接口约定 v0.3 | B 维护 | 事件/证书字段口径 |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| `ms_t0_bom.json` / `ms_t1_bom.json` | `data/test_scenarios/` | ModelScope Qwen-Image-2.1 双快照，各 7 组件完整 CycloneDX 1.7 |
| ~~`t0_bom.json` / `t1_bom.json`~~ | ~~`data/test_scenarios/`~~ | HF Llama-2-7b 构造版，2026-10-21 已删除（清仓库） |

## 为什么要做

1. B 的 delta_engine 需要"除变化点外完全一致"的双快照，才能证明检测的是真实变化而非噪声。
2. 8 场景（S1–S8）是深度验收的硬指标，测试数据是验收前提。
3. 当前离线 diff 回归直接依赖 `ms_t0_bom.json` / `ms_t1_bom.json`（`tests/test_diff_frozen_lineage.py`）。

## 具体怎么做

1. 构造 7 组件 BOM：3 个 AI 模型（基座 Qwen-Image-2.1 + 聚合降维 Finetune/Quantize）+ 1 个数据集 + 3 个 Python 库。
2. 血缘表达使用 CycloneDX 标准字段：`pedigree.ancestors`（微调/量化）、`modelCard.modelParameters.datasets`（训练数据）、`dependencies`（依赖）。
3. t1 变化点与聚合节点 count 随 ModelScope 快照注入（Qwen-Image-2.1 主模型 qwen-research 非标协议）。
4. 场景覆盖登记见 `tests/fixtures/modelscope/README.md`（S1–S8 覆盖状态随数据迁移归档）。

## 验证

- ms_t0/ms_t1 均为合法 CycloneDX 1.7；结构、purl、revision、血缘关系与快照一致（已脚本比对）。
- delta_engine 预期产出对应 `license_changed` 事件；`path_certificates > 0`。
- B 输出结构已对齐：`propagated.json = {"events": [...], "path_certificates": [...]}`。
