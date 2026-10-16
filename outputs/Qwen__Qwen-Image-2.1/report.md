# AI 模型血缘扫描报告（ModelScope）

- 扫描模型：`Qwen/Qwen-Image-2.1`
- 生成时间：2026-10-13T15:38:45Z
- 许可证：**qwen-research**
- 整体判定：**潜在风险（黄）**
- 血缘图节点数：**4**，边数：**3**
- 聚合节点：**3** 个（聚合 2368 个派生/祖先模型）
- SCC 强连通分量：**4**
- 本报告生成：**成功**（流水线耗时 5.0s）

## 一、血缘图节点

| canonical_id | 类型 | 名称 | 版本 | 许可证 | 风险等级 | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| model:modelscope/Qwen/Qwen-Image-2.1@master | model | Qwen/Qwen-Image-2.1 | master | qwen-research | 未识别 | 潜在风险（黄） |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Adapters@master | model | Qwen/Qwen-Image-2.1 · 适配 (Total: 2320) | master | - | 未识别 | 待确认（灰） |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Finetunes@master | model | Qwen/Qwen-Image-2.1 · 微调 (Total: 22) | master | - | 未识别 | 待确认（灰） |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Quantizations@master | model | Qwen/Qwen-Image-2.1 · 量化 (Total: 26) | master | - | 未识别 | 待确认（灰） |

## 二、聚合节点（计数降维）

| 名称 | count | 来源字段 |
| --- | --- | --- |
| Qwen/Qwen-Image-2.1 · 适配 (Total: 2320) | 2320 | lineage |
| Qwen/Qwen-Image-2.1 · 微调 (Total: 22) | 22 | lineage |
| Qwen/Qwen-Image-2.1 · 量化 (Total: 26) | 26 | lineage |

## 三、血缘边

| 来源 | 边类型 | 目标 | 证据等级 |
| --- | --- | --- | --- |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Adapters@master | derived_from | model:modelscope/Qwen/Qwen-Image-2.1@master | B |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Finetunes@master | derived_from | model:modelscope/Qwen/Qwen-Image-2.1@master | B |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Quantizations@master | derived_from | model:modelscope/Qwen/Qwen-Image-2.1@master | B |

## 免责声明

本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。
