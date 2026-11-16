> **受控基线声明**：本次 t0 是冻结的受控快照（simulation=true），t1 是真实 ModelScope 扫描结果；本报告不声称现实中发生了该许可证变更。

# AI 模型血缘风险传播报告

> 生成时间：2026-11-15 15:52
> 对比区间：2026-10-27 → 2026-11-15
> 间隔天数：19 天
> 快照：t0 `/home/runner/work/_temp/license-watch/reports/previous_bom.json` → t1 `/home/runner/work/_temp/license-watch/reports/current_bom.json`
> 生成工具：开源账本（深度层）· report_enhanced.py（接口约定 v0.3）

## 一、变更摘要

共检测到 **3** 个变更事件，按类型分布：

- **许可证变更**（`license_changed`）：3 个

| 事件 ID | 类型 | 风险源（seed） | 变更（before → after） | 证据 | 判定 | 审计（merge_status / reason_code / rule_version） |
|---|---|---|---|---|---|---|
| evt-t1-001 | 许可证变更 | Qwen/Qwen-Image-2.1@master | Apache-2.0 → qwen-research | A | RISK_POTENTIAL | merge_status=KEPT_SEPARATE；reason_code=NO_MERGE_CANDIDATE；rule_version=merge-policy-v2 |
| evt-t1-001-p01 | 许可证变更 | Qwen/Qwen-Image-2.1@master | Apache-2.0 → qwen-research | A | RISK_CONFIRMED | merge_status=KEPT_SEPARATE；reason_code=NO_MERGE_CANDIDATE；rule_version=merge-policy-v2 |
| evt-t1-001-p02 | 许可证变更 | Qwen/Qwen-Image-2.1@master | Apache-2.0 → qwen-research | B | RISK_POTENTIAL | merge_status=KEPT_SEPARATE；reason_code=NO_MERGE_CANDIDATE；rule_version=merge-policy-v2 |

## 二、传播路径

每个事件携带从种子到受影响资产的传播路径（weakest link 规则取最弱证据）：

### evt-t1-001-p01 · 许可证变更

- 种子资产：`Qwen/Qwen-Image-2.1@master`
- 传播路径（共 1 跳，最弱证据 A，判定 RISK_CONFIRMED）：

```text
Qwen/Qwen-Image-2.1-Turbo@master —[derived_from / A]→ Qwen/Qwen-Image-2.1@master
```

### evt-t1-001-p02 · 许可证变更

- 种子资产：`Qwen/Qwen-Image-2.1@master`
- 传播路径（共 1 跳，最弱证据 B，判定 RISK_POTENTIAL）：

```text
unsloth/Qwen-Image-2.1-Turbo-FP8@master —[derived_from / B]→ Qwen/Qwen-Image-2.1@master
```


## 三、许可证继承冲突分析

对每个许可证变更事件，比较上游许可证义务（Duty）与下游许可证禁止（Prohibition），检测是否存在继承冲突：

共 **3** 个许可证变更事件，其中检测到继承冲突 **0** 个。

| 事件 ID | 风险源（seed） | 变更（before → after） | 冲突检测 | 冲突类型 | 冲突描述 |
|---|---|---|---|---|---|
| evt-t1-001 | Qwen/Qwen-Image-2.1@master | Apache-2.0 → qwen-research | 无冲突 | `none` | 上游或下游许可证规则未知，无法判定继承冲突 |
| evt-t1-001-p01 | Qwen/Qwen-Image-2.1@master | Apache-2.0 → qwen-research | 无冲突 | `none` | 上游或下游许可证规则未知，无法判定继承冲突 |
| evt-t1-001-p02 | Qwen/Qwen-Image-2.1@master | Apache-2.0 → qwen-research | 无冲突 | `none` | 上游或下游许可证规则未知，无法判定继承冲突 |

## 四、路径证书

共生成 **2** 张路径证书：

| 证书 ID | 受影响资产 | 变更类型 | 跳数 | 最弱证据 | 判定 | 终止原因 | 缺失祖先 | 路径指纹 |
|---|---|---|---|---|---|---|---|---|
| cert-evt-t1-001-01 | Qwen/Qwen-Image-2.1-Turbo@master | 许可证变更 | 1 | A | RISK_CONFIRMED | exhausted | 否 | 5862d8f22d39af5092e5c509fd2677fbbd42f796 |
| cert-evt-t1-001-02 | unsloth/Qwen-Image-2.1-Turbo-FP8@master | 许可证变更 | 1 | B | RISK_POTENTIAL | exhausted | 否 | a421261d81854b2b4a23603a10a4e0f1d09280ff |

## 五、受影响资产（按判定分组）

### 🔴 确认风险（1 项）

| 受影响资产 | 变更类型 | 跳数 | 最弱证据 | 证书 ID |
|---|---|---|---|---|
| Qwen/Qwen-Image-2.1-Turbo@master | 许可证变更 | 1 | A | cert-evt-t1-001-01 |

### 🟠 潜在风险（1 项）

| 受影响资产 | 变更类型 | 跳数 | 最弱证据 | 证书 ID |
|---|---|---|---|---|
| unsloth/Qwen-Image-2.1-Turbo-FP8@master | 许可证变更 | 1 | B | cert-evt-t1-001-02 |

## 六、风险源汇总

| 风险源 | 关联事件数 |
|---|---|
| Qwen/Qwen-Image-2.1@master | 3 |

## 七、AI 语义差异（C 级，待人工确认）

> AI 只比较 t0/t1 BOM 中已固化的条款画像，不回查今天的最新原文，不修改 Delta、风险判定或 CI。

| 模型 | 维度 | 语义变化 | 变化类型 | 复核优先级 | AI 置信度（t0 → t1） | 旧原文 | 新原文 |
|---|---|---|---|---|---|---|---|
| OpenGVLab/InternVL3-8B-Pretrained | 训练其他模型 | 允许 → 未找到明确条款 | 证据丢失 | high | 0.71 → — | license: apache-2.0 | — |
| OpenGVLab/InternViT-300M-448px-V2_5 | 商业使用 | 允许 → 允许 | 原文变化 | medium | 0.71 → 0.71 | license: mit | This project is released under the MIT License. |
| Qwen/Qwen-Image-2.1 | 商业使用 | 允许 → 受限 | 条款收紧 | high | 0.8 → 0.86 | 2. Grant of Copyright License. Subject to the terms and conditions of<br>      this License, each Contributor hereby grants to You a perpetual,<br>      worldwide, non-exclusive, no-charge, royalty-free, irrevocable<br>      copyright license to reproduce, prepare Derivative Works of,<br>      publicly display, publicly perform, sublicense, and distribute the<br>      Work and such Derivative Works in Source or Object form. | a. You are granted a non-exclusive, worldwide, non-transferable and royalty-free limited license under our intellectual property or other rights owned by us embodied in the Materials to use, reproduce, distribute, copy, create derivative works of, and make modifications to the Materials FOR NON-COMMERCIAL PURPOSES ONLY. |
| Qwen/Qwen-Image-2.1 | derivative_works | 未找到明确条款 → 有条件允许 | 证据新增 | low | — → 0.74 | — | a. You are granted a non-exclusive, worldwide, non-transferable and royalty-free limited license under our intellectual property or other rights owned by us embodied in the Materials to use, reproduce, distribute, copy, create derivative works of, and make modifications to the Materials FOR NON-COMMERCIAL PURPOSES ONLY. |
| Qwen/Qwen-Image-2.1 | 再分发 | 未找到明确条款 → 有条件允许 | 证据新增 | low | — → 0.66 | — | 3. Redistribution<br>Subject to Section 2 (Grant of Rights), you may distribute copies or make the Materials, or derivative works thereof, available as part of a product or service that contains any of them, with or without modifications, and in Source or Object form, provided that you meet the following conditions: |

> “证据新增/证据丢失”表示 t0/t1 一侧没有形成可验证条款，不等于许可证条款本身收紧或放宽；具体缺口见项目报告。

### AI 置信度构成

| 模型 | 维度 | t0 构成 | t1 构成 | t1 原文 SHA256 |
|---|---|---|---|---|
| OpenGVLab/InternVL3-8B-Pretrained | 训练其他模型 | base +0.48 + exact_quote +0.10 + quote_context +0.02 + readme +0.08 + source_sha256 +0.03 | — | — |
| OpenGVLab/InternViT-300M-448px-V2_5 | 商业使用 | base +0.48 + exact_quote +0.10 + quote_context +0.02 + readme +0.08 + source_sha256 +0.03 | base +0.48 + exact_quote +0.10 + quote_context +0.02 + readme +0.08 + source_sha256 +0.03 | 2d06dfef7712ec67fa0f8a2e43a781a8b0378d8dd8f06ea8c48b2be16045600c |
| Qwen/Qwen-Image-2.1 | 商业使用 | base +0.48 + license_file +0.15 + exact_quote +0.10 + source_sha256 +0.03 + quote_context +0.02 + cross_document_support +0.02 | base +0.48 + exact_quote +0.10 + license_file +0.15 + quote_context +0.02 + restriction_wording +0.08 + source_sha256 +0.03 | 913180202374ef31b67fe7db7520b81dbce6d066a652e4bb21dec11f0e24d7a6 |
| Qwen/Qwen-Image-2.1 | derivative_works | — | base +0.48 + exact_quote +0.10 + license_file +0.15 + quote_context +0.02 + restriction_wording +0.08 + source_sha256 +0.03 + uncertain_state -0.12 | 913180202374ef31b67fe7db7520b81dbce6d066a652e4bb21dec11f0e24d7a6 |
| Qwen/Qwen-Image-2.1 | 再分发 | — | base +0.48 + exact_quote +0.10 + license_file +0.15 + quote_context +0.02 + source_sha256 +0.03 + uncertain_state -0.12 | 29cc0ff288e05368fafe0ad0ceb0c0042ccca68e82f4f292c805598b5abc7ab5 |

## 八、证据等级与判定说明

| 等级 | 定义（接口约定 v0.3） |
|---|---|
| A | ModelScope 官方 API 直接返回的字段，或从 ModelScope 官方仓库取得的 LICENSE / README 原文 |
| B | 工具基于 ModelScope 事实生成的派生结构化证据（血缘边、聚合节点、BOM 映射） |
| C | AI 条款抽取、启发式或降级证据；必须保留逐字原文并等待人工确认 |

| 判定 | 含义 |
|---|---|
| RISK_CONFIRMED | 路径上所有边证据等级为 A，规则明确适用 |
| RISK_POTENTIAL | 路径上存在 B 级边，规则可能适用 |
| UNDETERMINED | 路径上存在 C 级边、缺失祖先或冲突字段 |

> 口径：A=ModelScope 官方字段或官方原文；B=工具基于 ModelScope 事实生成的派生结构；C=AI 语义抽取或降级推断。AI 不修改许可证事实、风险灯色、Delta、decision 或 CI。
> 风险传播使用 weakest link 规则：路径证据等级取路径中最低等级；`UNDETERMINED` 不是“无风险”，而是“证据不足以判定”。

---

> **免责声明**：本报告由开源账本自动生成，基于证据的辅助审计，不构成法律意见，也不能替代针对具体许可证、司法辖区和业务模式的执业法律审查。
