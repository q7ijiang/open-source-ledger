# 项目 ModelScope 模型血缘扫描报告

- 项目路径：`tests\fixtures\projects\real_modelscope\full_project`
- 生成时间：2026-10-26T12:54:27Z
- 识别模型数：**7**
- 扫描范围：**仅项目直接使用模型及其上游闭包；默认不枚举下游模型**
- 合并血缘图节点数：**18**，边数：**22**
- SCC 强连通分量：**18**
- 本报告生成：**成功**（流水线耗时 21.5s）

## 一、项目识别出的 ModelScope 模型（来源文件）

| 模型 | 命名空间 | 名称 | 来源文件 |
| --- | --- | --- | --- |
| Qwen/Qwen2.5-14B-Instruct-AWQ | Qwen | Qwen2.5-14B-Instruct-AWQ | config/config.json<br>model_registry.py<br>README.md |
| Qwen/Qwen2.5-7B-Instruct-AWQ | Qwen | Qwen2.5-7B-Instruct-AWQ | config/config.json<br>model_registry.py<br>README.md |
| Qwen/Qwen2.5-Coder-7B-Instruct-AWQ | Qwen | Qwen2.5-Coder-7B-Instruct-AWQ | config/config.json<br>model_registry.py<br>README.md |
| OpenGVLab/InternVL3-8B-Instruct | OpenGVLab | InternVL3-8B-Instruct | config/config.json<br>model_registry.py<br>README.md |
| Qwen/Qwen2.5-Math-7B-Instruct | Qwen | Qwen2.5-Math-7B-Instruct | config/config.json<br>model_registry.py<br>README.md |
| LLM-Research/gemma-3-4b-it | LLM-Research | gemma-3-4b-it | config/config.json<br>model_registry.py<br>README.md |
| BAAI/bge-m3 | BAAI | bge-m3 | model_registry.py<br>README.md |

## 二、合并血缘图节点

| canonical_id | 类型 | 名称 | 版本 | 许可证 | 血缘状态 | 上游深度 |
| --- | --- | --- | --- | --- | --- | --- |
| model:modelscope/Qwen/Qwen2.5-14B-Instruct-AWQ@master | model | Qwen/Qwen2.5-14B-Instruct-AWQ | master | Apache-2.0 | complete | 0 |
| model:modelscope/Qwen/Qwen2.5-14B-Instruct@master | model | Qwen/Qwen2.5-14B-Instruct | master | Apache-2.0 | resolved | 1 |
| model:modelscope/Qwen/Qwen2.5-14B@master | model | Qwen/Qwen2.5-14B | master | Apache-2.0 | resolved | 2 |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct-AWQ@master | model | Qwen/Qwen2.5-7B-Instruct-AWQ | master | Apache-2.0 | complete | 0 |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | model | Qwen/Qwen2.5-7B-Instruct | master | Apache-2.0 | resolved | 1 |
| model:modelscope/Qwen/Qwen2.5-7B@master | model | Qwen/Qwen2.5-7B | master | Apache-2.0 | resolved | 2 |
| model:modelscope/Qwen/Qwen2.5-Coder-7B-Instruct-AWQ@master | model | Qwen/Qwen2.5-Coder-7B-Instruct-AWQ | master | Apache-2.0 | complete | 0 |
| model:modelscope/Qwen/Qwen2.5-Coder-7B-Instruct@master | model | Qwen/Qwen2.5-Coder-7B-Instruct | master | Apache-2.0 | resolved | 1 |
| model:modelscope/Qwen/Qwen2.5-Coder-7B@master | model | Qwen/Qwen2.5-Coder-7B | master | Apache-2.0 | resolved | 2 |
| model:modelscope/OpenGVLab/InternVL3-8B-Instruct@master | model | OpenGVLab/InternVL3-8B-Instruct | master | Apache-2.0 | complete | 0 |
| model:modelscope/OpenGVLab/InternVL3-8B-Pretrained@master | model | OpenGVLab/InternVL3-8B-Pretrained | master | Apache-2.0 | resolved | 1 |
| model:modelscope/OpenGVLab/InternViT-300M-448px-V2_5@master | model | OpenGVLab/InternViT-300M-448px-V2_5 | master | MIT | resolved | 2 |
| model:modelscope/OpenGVLab/InternViT-300M-448px@master | model | OpenGVLab/InternViT-300M-448px | master | MIT | resolved | 3 |
| model:modelscope/Qwen/Qwen2.5-Math-7B-Instruct@master | model | Qwen/Qwen2.5-Math-7B-Instruct | master | Apache-2.0 | complete | 0 |
| model:modelscope/Qwen/Qwen2.5-Math-7B@master | model | Qwen/Qwen2.5-Math-7B | master | Apache-2.0 | resolved | 1 |
| model:modelscope/LLM-Research/gemma-3-4b-it@master | model | LLM-Research/gemma-3-4b-it | master | gemma | complete | 0 |
| model:modelscope/google/gemma-3-4b-pt@master | model | google/gemma-3-4b-pt | master | gemma | resolved | 1 |
| model:modelscope/BAAI/bge-m3@master | model | BAAI/bge-m3 | master | MIT | complete | 0 |

## 三、合并血缘边

| 来源 | 边类型 | 目标 | 证据等级 |
| --- | --- | --- | --- |
| model:modelscope/Qwen/Qwen2.5-14B-Instruct-AWQ@master | derived_from | model:modelscope/Qwen/Qwen2.5-14B-Instruct@master | A |
| model:modelscope/Qwen/Qwen2.5-14B-Instruct-AWQ@master | derived_from | model:modelscope/Qwen/Qwen2.5-14B@master | B |
| model:modelscope/Qwen/Qwen2.5-14B-Instruct@master | derived_from | model:modelscope/Qwen/Qwen2.5-14B@master | A |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct-AWQ@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | A |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct-AWQ@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | B |
| model:modelscope/Qwen/Qwen2.5-7B-Instruct@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | A |
| model:modelscope/Qwen/Qwen2.5-Coder-7B-Instruct-AWQ@master | derived_from | model:modelscope/Qwen/Qwen2.5-Coder-7B-Instruct@master | A |
| model:modelscope/Qwen/Qwen2.5-Coder-7B-Instruct-AWQ@master | derived_from | model:modelscope/Qwen/Qwen2.5-Coder-7B@master | B |
| model:modelscope/Qwen/Qwen2.5-Coder-7B-Instruct-AWQ@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | B |
| model:modelscope/Qwen/Qwen2.5-Coder-7B-Instruct@master | derived_from | model:modelscope/Qwen/Qwen2.5-Coder-7B@master | A |
| model:modelscope/Qwen/Qwen2.5-Coder-7B-Instruct@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | B |
| model:modelscope/Qwen/Qwen2.5-Coder-7B@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | A |
| model:modelscope/OpenGVLab/InternVL3-8B-Instruct@master | derived_from | model:modelscope/OpenGVLab/InternVL3-8B-Pretrained@master | A |
| model:modelscope/OpenGVLab/InternVL3-8B-Instruct@master | derived_from | model:modelscope/OpenGVLab/InternViT-300M-448px-V2_5@master | B |
| model:modelscope/OpenGVLab/InternVL3-8B-Instruct@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | B |
| model:modelscope/OpenGVLab/InternVL3-8B-Pretrained@master | derived_from | model:modelscope/OpenGVLab/InternViT-300M-448px-V2_5@master | A |
| model:modelscope/OpenGVLab/InternVL3-8B-Pretrained@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | A |
| model:modelscope/OpenGVLab/InternViT-300M-448px-V2_5@master | derived_from | model:modelscope/OpenGVLab/InternViT-300M-448px@master | A |
| model:modelscope/Qwen/Qwen2.5-Math-7B-Instruct@master | derived_from | model:modelscope/Qwen/Qwen2.5-Math-7B@master | A |
| model:modelscope/Qwen/Qwen2.5-Math-7B-Instruct@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | B |
| model:modelscope/Qwen/Qwen2.5-Math-7B@master | derived_from | model:modelscope/Qwen/Qwen2.5-7B@master | A |
| model:modelscope/LLM-Research/gemma-3-4b-it@master | derived_from | model:modelscope/google/gemma-3-4b-pt@master | A |

## 四、统计

- 节点类型分布：`{'model': 18}`
- 边类型分布：`{'derived_from': 22}`

## 免责声明

本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。
