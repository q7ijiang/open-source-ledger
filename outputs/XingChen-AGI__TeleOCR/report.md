# AI 模型血缘扫描报告（ModelScope）

- 扫描模型：`XingChen-AGI/TeleOCR`
- 生成时间：2026-10-13T15:39:10Z
- 许可证：**（未识别）**
- 整体判定：**待确认（灰）**
- 血缘图节点数：**2**，边数：**1**
- 聚合节点：**1** 个（聚合 7 个派生/祖先模型）
- SCC 强连通分量：**2**
- 本报告生成：**成功**（流水线耗时 2.5s）

## 一、血缘图节点

| canonical_id | 类型 | 名称 | 版本 | 许可证 | 风险等级 | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| model:modelscope/XingChen-AGI/TeleOCR@master | model | XingChen-AGI/TeleOCR | master | - | 未识别 | 待确认（灰） |
| model:modelscope/XingChen-AGI/TeleOCR:son:Quantizations@master | model | XingChen-AGI/TeleOCR · 量化 (Total: 7) | master | - | 未识别 | 待确认（灰） |

## 二、聚合节点（计数降维）

| 名称 | count | 来源字段 |
| --- | --- | --- |
| XingChen-AGI/TeleOCR · 量化 (Total: 7) | 7 | lineage |

## 三、血缘边

| 来源 | 边类型 | 目标 | 证据等级 |
| --- | --- | --- | --- |
| model:modelscope/XingChen-AGI/TeleOCR:son:Quantizations@master | derived_from | model:modelscope/XingChen-AGI/TeleOCR@master | B |

## 免责声明

本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。
