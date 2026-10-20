# 开源及第三方资源使用清单

> 生成时间：2026-09-20 18:02
> 输入 BOM：urn:uuid:1b8c9a4e-3f6d-4a2b-9c7e-5d1f8a3b2c0d
> 生成工具：开源账本（基础层）· report_basic.py

## 一、统计摘要

- 资产总数（去重后）：**11**
- 高风险许可证资产：**2**
- 待人工确认（未声明许可证）：**3**
- 跨生态合并去重资产：**1**

## 二、资产明细

| 资源名称 | 版本 | 许可证 | 风险 | 来源链接 | 证据位置 | 来源生态 |
|---|---|---|---|---|---|---|
| bert-base-uncased（bert） | — | 未声明<br>待人工确认｜模型未声明许可证，不得默认猜测（模型卡缺失≠无许可证）<br><small>pkg:npm/ai/bert-base-uncased；pkg:pypi/ai/bert-base-uncased</small> | ⚪ 待确认 | 未提供 URL（本地证据 L1） | model_usage.py#L3 | npm、PyPI |
| Qwen2.5-0.5B-Instruct | master | Apache-2.0<br>低风险｜宽松许可证<br><small>pkg:modelscope/Qwen/Qwen2.5-0.5B-Instruct@master</small> | 🟢 低 | [链接](https://www.modelscope.cn/models/Qwen/Qwen2.5-0.5B-Instruct) | — | ModelScope |
| agpl-gateway | 1.3.0 | AGPL-3.0-only<br>高风险｜传染性许可证（AGPL 类）：网络服务方式使用同样触发开源义务<br><small>pkg:pypi/agpl-gateway@1.3.0</small> | 🔴 高 | 未提供 URL（本地证据 L1） | requirements.txt#L8 | PyPI |
| axios | 1.7.2 | MIT<br>低风险｜宽松许可证<br><small>pkg:npm/axios@1.7.2</small> | 🟢 低 | [链接](https://www.npmjs.com/package/axios/v/1.7.2) | package-lock.json#L45 | npm |
| legacy-toolkit | 2.1.0 | GPL-3.0-only<br>高风险｜传染性许可证（GPL 类）：分发或修改时需遵守开源义务，可能影响整体分发方式<br><small>pkg:npm/legacy-toolkit@2.1.0</small> | 🔴 高 | [链接](https://www.npmjs.com/package/legacy-toolkit/v/2.1.0) | package-lock.json#L210 | npm |
| lodash | 4.17.21 | MIT<br>低风险｜宽松许可证<br><small>pkg:npm/lodash@4.17.21</small> | 🟢 低 | [链接](https://www.npmjs.com/package/lodash/v/4.17.21) | package-lock.json#L120 | npm |
| private-utils | 0.1.0 | 未声明<br>待人工确认｜未声明许可证，需向提供方核实<br><small>pkg:npm/private-utils@0.1.0</small> | ⚪ 待确认 | 未提供 URL（本地证据 L1） | package-lock.json#L300 | npm |
| requests | 2.32.3 | Apache-2.0<br>低风险｜宽松许可证<br><small>pkg:pypi/requests@2.32.3</small> | 🟢 低 | [链接](https://pypi.org/project/requests/2.32.3/)；[链接](https://github.com/psf/requests) | requirements.txt#L1 | PyPI |
| torch | 2.3.0 | BSD-3-Clause<br>低风险｜宽松许可证<br><small>pkg:pypi/torch@2.3.0</small> | 🟢 低 | [链接](https://pypi.org/project/torch/2.3.0/) | requirements.txt#L5 | PyPI |
| urllib3 | 2.2.1 | MIT<br>低风险｜宽松许可证<br><small>pkg:pypi/urllib3@2.2.1</small> | 🟢 低 | [链接](https://pypi.org/project/urllib3/2.2.1/) | requirements.txt#L2 | PyPI |
| Qwen-Image-2.1-Finetune-Data | v1 | 未声明<br>待人工确认｜未声明许可证，需向提供方核实<br><small>pkg:modelscope/Qwen/Qwen-Image-2.1-Finetune-Data@v1</small> | ⚪ 待确认 | [链接](https://www.modelscope.cn/datasets/Qwen/Qwen-Image-2.1-Finetune-Data) | — | ModelScope |

## 三、风险说明

- 🔴 高：许可证含传染性或强约束条款，使用/分发前必须核对义务（详见各条提示）。
- ⚪ 待确认：组件未声明许可证，或声明为非 SPDX 的 AI 专用条款，需人工核对官方文本。

---

> **免责声明**：本清单由开源账本自动生成，基于证据的辅助审计，不构成法律意见，也不能替代针对具体许可证、司法辖区和业务模式的执业法律审查。
