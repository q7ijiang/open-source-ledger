# 开源及第三方资源使用清单

> 生成时间：2026-10-09 01:01
> 生成工具：开源账本（基础层）· report_basic.py（v3：ModelScope 渲染适配）
> 数据源：**ModelScope**
> 输入 BOM：`E:\开源账本\open-source-ledger\data\test_scenarios\ms_t1_bom.json`
> 快照 ID：`basic-20261009`

## 一、统计摘要

- BOM 解析资产数：**7**
- 实体对齐后资产数：**7**
- 候选配对日志数：**0**
- 高风险许可证资产（风险等级 ≥ 4）：**0**
- AI 专用许可证资产：**0**
- 待人工确认（未声明或未识别）：**4**

## 二、P/D/P 判定结论

- 判定结果：🟢 安全 **3** 个 / 🟡 潜在风险 **4** 个 / 🔴 风险 **0** 个
- 输出方式：存在 🟡/🔴 资产，需配合 **风险血缘图**（--model / --diff）查看传播路径，本清单附判定依据。

### 模型判定表

| 模型名 | 版本 | 许可 | 判定结果 | 判定依据 |
| --- | --- | --- | --- | --- |
| accelerate | 0.33.0 | Apache-2.0 | 🟢 安全 | 宽松/公有领域许可证，常规合规 |
| transformers | 4.44.2 | Apache-2.0 | 🟢 安全 | 宽松/公有领域许可证，常规合规 |
| torch | 2.3.0 | BSD-3-Clause | 🟢 安全 | 宽松/公有领域许可证，常规合规 |
| Qwen-Image-2.1 | master | qwen-research（未识别） | 🟡 潜在风险 | 许可证未声明或规则库未识别（如 qwen-research 等非标协议），需人工核对官方文本 |
| Qwen-Image-2.1-Finetune-Data | v1 | qwen-data-license（未识别） | 🟡 潜在风险 | 许可证未声明或规则库未识别（如 qwen-research 等非标协议），需人工核对官方文本 |
| Qwen-Image-2.1-Finetune-Demo | master | qwen-research（未识别） | 🟡 潜在风险 | 许可证未声明或规则库未识别（如 qwen-research 等非标协议），需人工核对官方文本 |
| Qwen-Image-2.1-Quantized-Demo | master | qwen-research（未识别） | 🟡 潜在风险 | 许可证未声明或规则库未识别（如 qwen-research 等非标协议），需人工核对官方文本 |

## 三、许可证风险分布

| 风险等级 | 资产数 |
| --- | --- |
| 1（低风险（宽松/公有领域）） | 1 |
| 2（低风险（宽松+额外义务）） | 2 |
| None（待人工确认） | 4 |

### 许可证类别分布

| 许可证类别 | 资产数 |
| --- | --- |
| 宽松许可 | 3 |
| 未知 / 待人工确认 | 4 |

## 四、重点资产（高风险 / AI 专用）

未发现风险等级 ≥ 4 或 AI 专用许可证的资产。

## 五、资产明细

| canonical_id | 类型 | 名称 | 版本 | 许可证 | 风险 | 类别 | 最佳证据 | 来源链接 | purl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| package:pypi/accelerate@0.33.0 | 软件包 | accelerate | 0.33.0 | Apache-2.0 | 2（🟢 低） | 宽松许可 | B | 未提供 URL（本地证据） | pkg:pypi/accelerate@0.33.0 |
| package:pypi/transformers@4.44.2 | 软件包 | transformers | 4.44.2 | Apache-2.0 | 2（🟢 低） | 宽松许可 | B | 未提供 URL（本地证据） | pkg:pypi/transformers@4.44.2 |
| package:pypi/torch@2.3.0 | 软件包 | torch | 2.3.0 | BSD-3-Clause | 1（🟢 低） | 宽松许可 | B | 未提供 URL（本地证据） | pkg:pypi/torch@2.3.0 |
| dataset:modelscope/Qwen/Qwen-Image-2.1-Finetune-Data@v1 | 数据集 | Qwen-Image-2.1-Finetune-Data | v1 | qwen-data-license（未识别） | 待人工确认 | 未知 / 待人工确认 | B | [链接](https://modelscope.cn/datasets/Qwen/Qwen-Image-2.1-Finetune-Data) | pkg:modelscope/Qwen/Qwen-Image-2.1-Finetune-Data@v1 |
| model:modelscope/Qwen/Qwen-Image-2.1-Finetune-Demo@master | 模型 | Qwen-Image-2.1-Finetune-Demo | master | qwen-research（未识别） | 待人工确认 | 未知 / 待人工确认 | B | [链接](https://modelscope.cn/models/Qwen/Qwen-Image-2.1-Finetune-Demo) | pkg:modelscope/Qwen/Qwen-Image-2.1-Finetune-Demo@master |
| model:modelscope/Qwen/Qwen-Image-2.1-Quantized-Demo@master | 模型 | Qwen-Image-2.1-Quantized-Demo | master | qwen-research（未识别） | 待人工确认 | 未知 / 待人工确认 | B | [链接](https://modelscope.cn/models/Qwen/Qwen-Image-2.1-Quantized-Demo) | pkg:modelscope/Qwen/Qwen-Image-2.1-Quantized-Demo@master |
| model:modelscope/Qwen/Qwen-Image-2.1@master | 模型 | Qwen-Image-2.1 | master | qwen-research（未识别） | 待人工确认 | 未知 / 待人工确认 | B | [链接](https://modelscope.cn/models/Qwen/Qwen-Image-2.1) | pkg:modelscope/Qwen/Qwen-Image-2.1@master |

## 六、待人工确认

| canonical_id | 原始许可证字段 | 未识别项 |
| --- | --- | --- |
| dataset:modelscope/Qwen/Qwen-Image-2.1-Finetune-Data@v1 | qwen-data-license | qwen-data-license |
| model:modelscope/Qwen/Qwen-Image-2.1-Finetune-Demo@master | qwen-research | qwen-research |
| model:modelscope/Qwen/Qwen-Image-2.1-Quantized-Demo@master | qwen-research | qwen-research |
| model:modelscope/Qwen/Qwen-Image-2.1@master | qwen-research | qwen-research |

## 七、风险说明

- 风险等级 1–5 来自 license_db 规则库：1–2 低风险（宽松/公有领域）；3 中风险（弱 copyleft / AI 受限）；4–5 高风险（强 copyleft / 网络 copyleft）。
- 🔴 高：许可证含传染性或强约束条款（GPL/AGPL/SSPL 等），使用/分发前必须核对义务。
- ⚪ 待确认：组件未声明许可证，或存在规则库无法识别的许可证写法，需人工核对官方文本。
- AI 专用许可证（Llama 2 社区许可、OpenRAIL-M、Gemma 条款等）非 SPDX，义务条款需重点人工核对。
- ModelScope 场景：非标协议（如 qwen-research）不在规则库中，一律判定为潜在风险（黄灯），需人工核对官方许可文本后确认。

---

> **免责声明**：本清单由开源账本自动生成，基于证据的辅助审计，不构成法律意见，也不能替代针对具体许可证、司法辖区和业务模式的执业法律审查。
