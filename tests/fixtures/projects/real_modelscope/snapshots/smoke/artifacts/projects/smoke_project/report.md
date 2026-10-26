# 项目 ModelScope 模型血缘扫描报告

- 项目路径：`tests\fixtures\projects\real_modelscope\smoke_project`
- 生成时间：2026-10-26T13:03:40Z
- 识别模型数：**1**
- 扫描范围：**仅项目直接使用模型及其上游闭包；默认不枚举下游模型**
- 合并血缘图节点数：**3**，边数：**3**
- SCC 强连通分量：**3**
- 本报告生成：**成功**（流水线耗时 4.0s）

## 一、项目识别出的 ModelScope 模型（来源文件）

| 模型 | 命名空间 | 名称 | 来源文件 |
| --- | --- | --- | --- |
| Qwen/Qwen2.5-7B-Instruct-AWQ | Qwen | Qwen2.5-7B-Instruct-AWQ | app.py<br>README.md |

## 二、合并血缘图节点

| canonical_id | 类型 | 名称 | 版本 | 许可证 | 血缘状态 | 上游深度 |
| --- | --- | --- | --- | --- | --- | --- |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct-AWQ@master | model | Qwen/Qwen2.5-7B-Instruct-AWQ | master | Apache-2.0 | complete | 0 |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | model | Qwen/Qwen2.5-7B-Instruct | master | Apache-2.0 | resolved | 1 |
| model:modelscope/Qwen/Qwen2.5-7B@master | model | Qwen/Qwen2.5-7B | master | Apache-2.0 | resolved | 2 |

## 三、合并血缘边

| 来源 | 边类型 | 目标 | 证据等级 |
| --- | --- | --- | --- |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct-AWQ@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | A |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct-AWQ@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | B |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | A |

## 四、统计

- 节点类型分布：`{'model': 3}`
- 边类型分布：`{'derived_from': 3}`

## 免责声明

本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。
