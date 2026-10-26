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

## AI 语义证据（C 级，待人工确认）

> AI 只解释可精确定位的条款，不修改许可证事实、风险灯色、Delta、decision 或 CI。

| 置信度因子 | 分值 | 含义 |
| --- | --- | --- |
| 基础 | +0.48 | 条款已绑定到来源文档和可定位的逐字原文。 |
| 来源文件类型 | LICENSE +0.15 / README +0.08 / 其他结构化文件 +0.03 | LICENSE 文件对许可证条款证据最强，README 次之。 |
| 原文精确命中 | +0.10 | AI 引用文本能在冻结的 source_bundle 中逐字找到。 |
| 限制措辞 | +0.08 | 原文包含明确的禁止、仅限、不得等限制表达。 |
| SHA256 | +0.03 | 来源文件已计算 SHA256，可与后续快照核对是否变化。 |
| 引文长度 | +0.02 | 引文至少 8 个字符，能够保留必要语境。 |
| 跨文档互证 | 每增加一份文档 +0.02，最多 +0.06 | 同一维度得到多个独立来源支持。 |
| 不确定性 | -0.12 | 结论为有条件允许、未知或未找到，需降低自动置信度。 |

> 置信度是“证据可复核程度”，不是模型自报概率，也不是许可证合规或法律结论概率。最终分数限制在 0.05 至 0.89；所有 C 级结论仍需人工确认。

### Qwen/Qwen2.5-7B-Instruct-AWQ

- AI 状态：`ok`
- **验收模拟**：验收模拟：LICENSE.ACCEPTANCE.md 为注入文本，不代表该模型当前 ModelScope 许可证事实。
- 许可证事实：**Apache-2.0**（AI 不可改写）
- 摘要：验收模拟：旧画像允许商业使用，并要求再分发时保留声明。
| 维度 | AI 语义结论 | 置信度 / 证据等级 / 状态 | 原文文件 | 原文依据 |
| --- | --- | --- | --- | --- |
| 商业使用 | 允许 | 0.78 / C / pending | LICENSE.ACCEPTANCE.md | 验收模拟条款：允许用于商业目的。 |
| 许可证与版权声明保留 | 有条件允许 | 0.59 / C / pending | README.ACCEPTANCE.md | 分发时请保留许可证与版权声明。 |

**置信度构成**

- 商业使用：基础 +0.48 + LICENSE 文件 +0.15 + 原文精确命中 +0.10 + SHA256 +0.03 + 引文长度 +0.02 = 0.78
- 许可证与版权声明保留：基础 +0.48 + README 文件 +0.08 + 原文精确命中 +0.10 + SHA256 +0.03 + 引文长度 +0.02 + 不确定性 -0.12 = 0.59

**未识别维度与证据缺口**

| 维度 | 原因 |
| --- | --- |
| 训练其他模型 | 验收模拟文本未覆盖 |
| 微调版本再分发 | 验收模拟文本未覆盖 |
| 商用授权申请方式 | 验收模拟文本未给出申请方式 |

### Qwen/Qwen2.5-7B

- AI 状态：`ok`
- **验收模拟**：验收模拟：LICENSE.ACCEPTANCE.md 为注入文本，不代表该模型当前 ModelScope 许可证事实。
- 许可证事实：**Apache-2.0**（AI 不可改写）
- 摘要：验收模拟：旧画像允许商业使用，并要求再分发时保留声明。
| 维度 | AI 语义结论 | 置信度 / 证据等级 / 状态 | 原文文件 | 原文依据 |
| --- | --- | --- | --- | --- |
| 商业使用 | 允许 | 0.78 / C / pending | LICENSE.ACCEPTANCE.md | 验收模拟条款：允许用于商业目的。 |
| 许可证与版权声明保留 | 有条件允许 | 0.59 / C / pending | README.ACCEPTANCE.md | 分发时请保留许可证与版权声明。 |

**置信度构成**

- 商业使用：基础 +0.48 + LICENSE 文件 +0.15 + 原文精确命中 +0.10 + SHA256 +0.03 + 引文长度 +0.02 = 0.78
- 许可证与版权声明保留：基础 +0.48 + README 文件 +0.08 + 原文精确命中 +0.10 + SHA256 +0.03 + 引文长度 +0.02 + 不确定性 -0.12 = 0.59

**未识别维度与证据缺口**

| 维度 | 原因 |
| --- | --- |
| 训练其他模型 | 验收模拟文本未覆盖 |
| 微调版本再分发 | 验收模拟文本未覆盖 |
| 商用授权申请方式 | 验收模拟文本未给出申请方式 |

### 项目使用上下文

> 验收模拟：验收模拟：项目上下文只用于验证逐字代码引用和 C 级证据展示。

| 使用方式 | 结论 | 置信度 / 证据等级 / 状态 | 项目文件 | 原文依据 |
| --- | --- | --- | --- | --- |
| 远程 API 调用 | 项目通过 OpenAI-compatible 客户端把已登记的模型标识传给远程推理端点。 | 0.83 / C / pending | inference_client.py | response = client.chat.completions.create(model=model, messages=messages) |
