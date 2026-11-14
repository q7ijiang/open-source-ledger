# 项目 ModelScope 模型血缘扫描报告

- 项目路径：`tests\fixtures\projects\real_modelscope\smoke_project`
- 生成时间：2026-11-14T12:24:51Z
- 识别模型数：**1**
- 扫描范围：**仅项目直接使用模型及其上游闭包；默认不枚举下游模型**
- 合并血缘图节点数：**3**，边数：**3**
- SCC 强连通分量：**3**
- 本报告生成：**成功**（流水线耗时 3.4s）

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
- 许可证事实：**apache-2.0**（AI 不可改写）
- 摘要：The model Qwen/Qwen2.5-7B-Instruct-AWQ is licensed under the Apache License, Version 2.0 (apache-2.0). This license permits commercial use, modification, and distribution of the Work and Derivative Works, subject to attribution and notice retention conditions.
| 维度 | AI 语义结论 | 置信度 / 证据等级 / 状态 | 原文文件 | 原文依据 |
| --- | --- | --- | --- | --- |
| 商业使用 | 允许 | 0.8 / C / pending | LICENSE | 2. Grant of Copyright License. Subject to the terms and conditions of<br>      this License, each Contributor hereby grants to You a perpetual,<br>      worldwide, non-exclusive, no-charge, royalty-free, irrevocable<br>      copyright license to reproduce, prepare Derivative Works of,<br>      publicly display, publicly perform, sublicense, and distribute the<br>      Work and such Derivative Works in Source or Object form. |
| 商业使用 | 允许 | 0.8 / C / pending | README.md | license: apache-2.0 |
| 训练其他模型 | 允许 | 0.78 / C / pending | LICENSE | "Derivative Works" shall mean any work, whether in Source or Object<br>      form, that is based on (or derived from) the Work and for which the<br>      editorial revisions, annotations, elaborations, or other modifications<br>      represent, as a whole, an original work of authorship. |
| 训练其他模型 | 允许 | 0.78 / C / pending | LICENSE | 2. Grant of Copyright License. Subject to the terms and conditions of<br>      this License, each Contributor hereby grants to You a perpetual,<br>      worldwide, non-exclusive, no-charge, royalty-free, irrevocable<br>      copyright license to reproduce, prepare Derivative Works of,<br>      publicly display, publicly perform, sublicense, and distribute the<br>      Work and such Derivative Works in Source or Object form. |

**置信度构成**

- 商业使用：基础 +0.48 + LICENSE 文件 +0.15 + 原文精确命中 +0.10 + SHA256 +0.03 + 引文长度 +0.02 + 跨文档互证 +0.02 = 0.8
- 训练其他模型：基础 +0.48 + LICENSE 文件 +0.15 + 原文精确命中 +0.10 + SHA256 +0.03 + 引文长度 +0.02 = 0.78

**未识别维度与证据缺口**

| 维度 | 原因 |
| --- | --- |
| 微调版本再分发 | 证据不足 |
| 商用授权申请方式 | 证据不足 |

### Qwen/Qwen2.5-7B-Instruct

- AI 状态：`ok`
- 许可证事实：**apache-2.0**（AI 不可改写）
- 摘要：该模型采用 Apache License Version 2.0 许可。允许商业使用、修改、分发及创建衍生作品（包括用于训练其他模型），需遵守保留版权声明等条件。
| 维度 | AI 语义结论 | 置信度 / 证据等级 / 状态 | 原文文件 | 原文依据 |
| --- | --- | --- | --- | --- |
| 商业使用 | 允许 | 0.8 / C / pending | LICENSE | Apache License<br>                           Version 2.0, January 2004 |
| 商业使用 | 允许 | 0.8 / C / pending | README.md | license: apache-2.0 |
| 商业使用 | 允许 | 0.8 / C / pending | LICENSE | 2. Grant of Copyright License. Subject to the terms and conditions of<br>      this License, each Contributor hereby grants to You a perpetual,<br>      worldwide, non-exclusive, no-charge, royalty-free, irrevocable<br>      copyright license to reproduce, prepare Derivative Works of,<br>      publicly display, publicly perform, sublicense, and distribute the<br>      Work and such Derivative Works in Source or Object form. |
| 训练其他模型 | 允许 | 0.78 / C / pending | LICENSE | 2. Grant of Copyright License. Subject to the terms and conditions of<br>      this License, each Contributor hereby grants to You a perpetual,<br>      worldwide, non-exclusive, no-charge, royalty-free, irrevocable<br>      copyright license to reproduce, prepare Derivative Works of,<br>      publicly display, publicly perform, sublicense, and distribute the<br>      Work and such Derivative Works in Source or Object form. |

**置信度构成**

- 商业使用：基础 +0.48 + LICENSE 文件 +0.15 + 原文精确命中 +0.10 + SHA256 +0.03 + 引文长度 +0.02 + 跨文档互证 +0.02 = 0.8
- 训练其他模型：基础 +0.48 + LICENSE 文件 +0.15 + 原文精确命中 +0.10 + SHA256 +0.03 + 引文长度 +0.02 = 0.78

**未识别维度与证据缺口**

| 维度 | 原因 |
| --- | --- |
| 微调版本再分发 | 证据不足 |
| 商用授权申请方式 | 证据不足 |

### Qwen/Qwen2.5-7B

- AI 状态：`no_evidence`
- 许可证事实：**apache-2.0**（AI 不可改写）
- 摘要：The model Qwen/Qwen2.5-7B is licensed under Apache License, Version 2.0 (apache-2.0). This license permits commercial use, modification, and distribution subject to standard attribution requirements.
_无通过原文校验的条款项。_

**未识别维度与证据缺口**

| 维度 | 原因 |
| --- | --- |
| 训练其他模型 | 证据不足 |
| 商业使用 | 引文未在指定原文中精确命中 |
| 修改与衍生 | 引文未在指定原文中精确命中 |
| distribution | 引文未在指定原文中精确命中 |
| 微调版本再分发 | 证据不足 |
| 商用授权申请方式 | 证据不足 |

### 项目使用上下文

| 使用方式 | 结论 | 置信度 / 证据等级 / 状态 | 项目文件 | 原文依据 |
| --- | --- | --- | --- | --- |
| 本地推理 | The project imports vLLM and instantiates an LLM object with a specific model ID for local execution. | 0.83 / C / pending | app.py | from vllm import LLM<br><br>CHAT_MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"<br><br><br>def build_chat_model():<br>    return LLM(model=CHAT_MODEL, quantization="awq") |

## 免责声明

本报告基于 ModelScope 官方 API 的结构化证据与血缘图的辅助分析结果，不构成法律意见。
