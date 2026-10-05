# 模块 12：深度测试数据

| 项目 | 内容 |
|---|---|
| 负责人 | C |
| 状态 | 已完成（t0/t1 已就绪，待 B 验收） |
| 完成日期 | 2026-10-03 |
| 对应任务 | 深度部分 · 模块 12 |

## 一句话摘要

构造深度层双快照测试数据 `t0_bom.json` / `t1_bom.json`：结构完全一致、只注入两处许可证变化，作为 delta_engine / propagation_engine 的联调输入。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| 任务流程.pdf / 现状.docx | 组长发布 | S1–S8 八场景验收要求 |
| 接口约定 v0.3 | B 维护 | 事件/证书字段口径 |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| `t0_bom.json` / `t1_bom.json` | `data/test_scenarios/` | 各 7 组件完整 CycloneDX 1.7，仅许可证不同 |
| `深度测试数据说明.md` | `data/test_scenarios/` | 使用说明、B 验收预期、S1–S8 覆盖计划 |

## 为什么要做

1. B 的 delta_engine 需要"除变化点外完全一致"的双快照，才能证明检测的是真实变化而非噪声。
2. 8 场景（S1–S8）是 10/10–10/11 深度验收的硬指标，测试数据是验收前提。
3. B 明确等待 t0/t1 推到仓库 `data/test_scenarios/` 后跑完整验收。

## 具体怎么做

1. 构造 7 组件 BOM：3 个 AI 模型（基座 Llama-2-7b + finetune-demo + chat-demo）+ 1 个数据集（instruction-dataset）+ 3 个 Python 库。
2. 血缘表达使用 CycloneDX 标准字段：`pedigree.ancestors`（微调）、`modelCard.modelParameters.datasets`（训练数据）、`dependencies`（依赖）。
3. t1 只注入两处变化：Llama-2-7b 许可证 Apache-2.0 → Llama-2-Community（S1）、instruction-dataset CC-BY-4.0 → CC-BY-NC-4.0（S4）。
4. 编写说明文档，登记 S1–S8 覆盖状态与补充计划（S2/S3/S5 数据变体待 10/6–10/7 补充）。

## 验证

- t0/t1 均为合法 CycloneDX 1.7；除注入的两处许可证外，组件结构、purl、revision、血缘关系完全一致（已脚本比对）。
- delta_engine 预期产出 2 个 `license_changed` 事件；`path_certificates > 0`。
- B 输出结构已对齐：`propagated.json = {"events": [...], "path_certificates": [...]}`。
