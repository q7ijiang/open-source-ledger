# AI 模型血缘扫描报告（ModelScope）

- 扫描模型：`Qwen/Qwen2.5-7B-Instruct`
- 生成时间：2026-10-13T15:39:06Z
- 许可证：**Apache-2.0**
- 整体判定：**待确认（灰）**
- 血缘图节点数：**5**，边数：**4**
- 聚合节点：**4** 个（聚合 1837 个派生/祖先模型）
- SCC 强连通分量：**5**
- 本报告生成：**成功**（流水线耗时 2.7s）

## 一、血缘图节点

| canonical_id | 类型 | 名称 | 版本 | 许可证 | 风险等级 | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | model | Qwen/Qwen2.5-7B-Instruct | master | Apache-2.0 | 2（弱 copyleft） | 安全（绿） |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Adapters@master | model | Qwen/Qwen2.5-7B-Instruct · 适配 (Total: 27) | master | - | 未识别 | 待确认（灰） |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Finetunes@master | model | Qwen/Qwen2.5-7B-Instruct · 微调 (Total: 1744) | master | - | 未识别 | 待确认（灰） |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Merges@master | model | Qwen/Qwen2.5-7B-Instruct · 合并 (Total: 16) | master | - | 未识别 | 待确认（灰） |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Quantizations@master | model | Qwen/Qwen2.5-7B-Instruct · 量化 (Total: 50) | master | - | 未识别 | 待确认（灰） |

## 二、聚合节点（计数降维）

| 名称 | count | 来源字段 |
| --- | --- | --- |
| Qwen/Qwen2.5-7B-Instruct · 适配 (Total: 27) | 27 | lineage |
| Qwen/Qwen2.5-7B-Instruct · 微调 (Total: 1744) | 1744 | lineage |
| Qwen/Qwen2.5-7B-Instruct · 合并 (Total: 16) | 16 | lineage |
| Qwen/Qwen2.5-7B-Instruct · 量化 (Total: 50) | 50 | lineage |

## 三、血缘边

| 来源 | 边类型 | 目标 | 证据等级 |
| --- | --- | --- | --- |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Adapters@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | B |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Finetunes@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | B |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Merges@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | B |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Quantizations@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | B |

## 免责声明

本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。
