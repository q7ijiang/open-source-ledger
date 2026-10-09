# 项目 ModelScope 模型血缘扫描报告

- 项目路径：`E:\开源账本\open-source-ledger\test_project`
- 生成时间：2026-10-09T15:43:44Z
- 识别模型数：**3**
- 合并血缘图节点数：**14**，边数：**11**
- SCC 强连通分量：**14**
- 合并血缘图 PNG：**已生成**（`E:\开源账本\open-source-ledger\outputs\modelscope_validation\project_lineage_graph.png`）
- 本报告生成：**成功**（流水线耗时 4.0s）

## 一、项目识别出的 ModelScope 模型（来源文件）

| 模型 | 命名空间 | 名称 | 来源文件 |
| --- | --- | --- | --- |
| Qwen/Qwen2.5-7B-Instruct | Qwen | Qwen2.5-7B-Instruct | bom.json |
| Qwen/Qwen3-8B | Qwen | Qwen3-8B | bom.json |
| Qwen/Qwen-Image-2.1 | Qwen | Qwen-Image-2.1 | bom.json |

## 二、合并血缘图节点

| canonical_id | 类型 | 名称 | 版本 | 许可证 |
| --- | --- | --- | --- | --- |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | model | Qwen/Qwen2.5-7B-Instruct | master | Apache-2.0 |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Adapters@master | model | Qwen/Qwen2.5-7B-Instruct · 适配 (Total: 27) | master | - |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Finetunes@master | model | Qwen/Qwen2.5-7B-Instruct · 微调 (Total: 1744) | master | - |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Merges@master | model | Qwen/Qwen2.5-7B-Instruct · 合并 (Total: 16) | master | - |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Quantizations@master | model | Qwen/Qwen2.5-7B-Instruct · 量化 (Total: 50) | master | - |
| model:modelscope/Qwen/Qwen3-8B@master | model | Qwen/Qwen3-8B | master | Apache-2.0 |
| model:modelscope/Qwen/Qwen3-8B:son:Adapters@master | model | Qwen/Qwen3-8B · 适配 (Total: 20) | master | - |
| model:modelscope/Qwen/Qwen3-8B:son:Finetunes@master | model | Qwen/Qwen3-8B · 微调 (Total: 550) | master | - |
| model:modelscope/Qwen/Qwen3-8B:son:Merges@master | model | Qwen/Qwen3-8B · 合并 (Total: 14) | master | - |
| model:modelscope/Qwen/Qwen3-8B:son:Quantizations@master | model | Qwen/Qwen3-8B · 量化 (Total: 127) | master | - |
| model:modelscope/Qwen/Qwen-Image-2.1@master | model | Qwen/Qwen-Image-2.1 | master | qwen-research |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Adapters@master | model | Qwen/Qwen-Image-2.1 · 适配 (Total: 2041) | master | - |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Finetunes@master | model | Qwen/Qwen-Image-2.1 · 微调 (Total: 22) | master | - |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Quantizations@master | model | Qwen/Qwen-Image-2.1 · 量化 (Total: 26) | master | - |

## 三、合并血缘边

| 来源 | 边类型 | 目标 | 证据等级 |
| --- | --- | --- | --- |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Adapters@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | B |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Finetunes@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | B |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Merges@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | B |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct:son:Quantizations@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | B |
| model:modelscope/Qwen/Qwen3-8B:son:Adapters@master | derived_from | model:modelscope/Qwen/Qwen3-8B@master | B |
| model:modelscope/Qwen/Qwen3-8B:son:Finetunes@master | derived_from | model:modelscope/Qwen/Qwen3-8B@master | B |
| model:modelscope/Qwen/Qwen3-8B:son:Merges@master | derived_from | model:modelscope/Qwen/Qwen3-8B@master | B |
| model:modelscope/Qwen/Qwen3-8B:son:Quantizations@master | derived_from | model:modelscope/Qwen/Qwen3-8B@master | B |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Adapters@master | derived_from | model:modelscope/Qwen/Qwen-Image-2.1@master | B |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Finetunes@master | derived_from | model:modelscope/Qwen/Qwen-Image-2.1@master | B |
| model:modelscope/Qwen/Qwen-Image-2.1:son:Quantizations@master | derived_from | model:modelscope/Qwen/Qwen-Image-2.1@master | B |

## 四、统计

- 节点类型分布：`{'model': 14}`
- 边类型分布：`{'derived_from': 11}`

## 免责声明

本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。
