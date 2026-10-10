# 项目 ModelScope 模型血缘扫描报告

- 项目路径：`example\multi_model_project`
- 生成时间：2026-10-10T15:41:12Z
- 识别模型数：**3**
- 合并血缘图节点数：**12**，边数：**9**
- SCC 强连通分量：**12**
- 本报告生成：**成功**（流水线耗时 4.0s）

## 一、项目识别出的 ModelScope 模型（来源文件）

| 模型 | 命名空间 | 名称 | 来源文件 |
| --- | --- | --- | --- |
| Qwen/Qwen2.5-7B-Instruct | Qwen | Qwen2.5-7B-Instruct | config.json<br>app.py |
| Qwen/Qwen3-8B | Qwen | Qwen3-8B | app.py |
| XingChen-AGI/TeleOCR | XingChen-AGI | TeleOCR | app.py |

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
| model:modelscope/Qwen/Qwen3-8B:son:Finetunes@master | model | Qwen/Qwen3-8B · 微调 (Total: 551) | master | - |
| model:modelscope/Qwen/Qwen3-8B:son:Merges@master | model | Qwen/Qwen3-8B · 合并 (Total: 14) | master | - |
| model:modelscope/Qwen/Qwen3-8B:son:Quantizations@master | model | Qwen/Qwen3-8B · 量化 (Total: 127) | master | - |
| model:modelscope/XingChen-AGI/TeleOCR@master | model | XingChen-AGI/TeleOCR | master | - |
| model:modelscope/XingChen-AGI/TeleOCR:son:Quantizations@master | model | XingChen-AGI/TeleOCR · 量化 (Total: 7) | master | - |

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
| model:modelscope/XingChen-AGI/TeleOCR:son:Quantizations@master | derived_from | model:modelscope/XingChen-AGI/TeleOCR@master | B |

## 四、统计

- 节点类型分布：`{'model': 12}`
- 边类型分布：`{'derived_from': 9}`

## 免责声明

本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。
