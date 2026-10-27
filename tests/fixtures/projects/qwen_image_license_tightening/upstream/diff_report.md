# AI 模型血缘风险传播报告

> 生成时间：2026-10-27 19:20
> 对比区间：2026-10-27 → 2026-10-27
> 间隔天数：0 天
> 快照：t0 `tests\fixtures\projects\qwen_image_license_tightening\upstream\t0_bom.json` → t1 `tests\fixtures\projects\qwen_image_license_tightening\upstream\t1_bom.json`
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

| 模型 | 维度 | 语义变化 | 复核优先级 | AI 置信度（t0 → t1） | 旧原文 | 新原文 |
|---|---|---|---|---|---|---|
| Qwen/Qwen-Image-2.1 | 商用授权申请方式 | 未找到明确条款 → 有条件允许 | low | — → 0.66 | — | b. You shall not use the Materials for any commercial purpose without obtaining a separate commercial license from us. If you wish to use the Materials commercially, you shall request a license from us at model-business@notice.qwencloud.com. |
| Qwen/Qwen-Image-2.1 | 商业使用 | 证据不足 → 禁止 | high | 0.59 → 0.86 | license: Apache License 2.0 | a. You are granted a non-exclusive, worldwide, non-transferable and royalty-free limited license under our intellectual property or other rights owned by us embodied in the Materials to use, reproduce, distribute, copy, create derivative works of, and make modifications to the Materials FOR NON-COMMERCIAL PURPOSES ONLY. |
| Qwen/Qwen-Image-2.1 | 微调版本再分发 | 未找到明确条款 → 有条件允许 | low | — → 0.66 | — | d. You may add your own copyright statement to your modifications and may provide additional or different license terms and conditions for use, reproduction, or distribution of your modifications, or for any such derivative works as a whole, provided your use, reproduction, and distribution of the work otherwise complies with the terms and conditions of this Agreement. |
| Qwen/Qwen-Image-2.1 | 修改与衍生 | 未找到明确条款 → 有条件允许 | low | — → 0.66 | — | b. You shall cause any modified files to carry prominent notices stating that you changed the files; |
| Qwen/Qwen-Image-2.1 | 许可证与版权声明保留 | 未找到明确条款 → 有条件允许 | low | — → 0.66 | — | c. You shall retain in all copies of the Materials that you distribute the following attribution notices within a "Notice" text file distributed as a part of such copies: "Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, Copyright (c) 2026 Hangzhou Tongyi Laboratory Technology Co., Ltd. All Rights Reserved."; and |
| Qwen/Qwen-Image-2.1 | 再分发 | 未找到明确条款 → 有条件允许 | low | — → 0.66 | — | Subject to Section 2 (Grant of Rights), you may distribute copies or make the Materials, or derivative works thereof, available as part of a product or service that contains any of them, with or without modifications, and in Source or Object form, provided that you meet the following conditions: |
| Qwen/Qwen-Image-2.1 | 训练其他模型 | 未找到明确条款 → 有条件允许 | low | — → 0.66 | — | b. If you use the Materials or any outputs or results therefrom to create, train, fine-tune, or improve an AI model that is distributed or made available, you shall prominently display “Built with Qwen” or “Improved using Qwen” in the related product documentation. |

### AI 置信度构成

| 模型 | 维度 | t0 构成 | t1 构成 | t1 原文 SHA256 |
|---|---|---|---|---|
| Qwen/Qwen-Image-2.1 | 商用授权申请方式 | — | base +0.48 + exact_quote +0.10 + license_file +0.15 + quote_context +0.02 + source_sha256 +0.03 + uncertain_state -0.12 | 604f3cd83aee7258c588f3cd7720a4a85c6c33d5db360ec9119a95a8b8037073 |
| Qwen/Qwen-Image-2.1 | 商业使用 | base +0.48 + exact_quote +0.10 + quote_context +0.02 + readme +0.08 + source_sha256 +0.03 + uncertain_state -0.12 | base +0.48 + exact_quote +0.10 + license_file +0.15 + quote_context +0.02 + restriction_wording +0.08 + source_sha256 +0.03 | 913180202374ef31b67fe7db7520b81dbce6d066a652e4bb21dec11f0e24d7a6 |
| Qwen/Qwen-Image-2.1 | 微调版本再分发 | — | base +0.48 + exact_quote +0.10 + license_file +0.15 + quote_context +0.02 + source_sha256 +0.03 + uncertain_state -0.12 | 7ebc41ea077fca7ef4fb5d30f9a5b0ba61e00da45669faddf021e4614ce7273b |
| Qwen/Qwen-Image-2.1 | 修改与衍生 | — | base +0.48 + exact_quote +0.10 + license_file +0.15 + quote_context +0.02 + source_sha256 +0.03 + uncertain_state -0.12 | 3ca44bbf10976843f30f6b6cbcf6938681b2da23d0e9616125a7d91816f7782e |
| Qwen/Qwen-Image-2.1 | 许可证与版权声明保留 | — | base +0.48 + exact_quote +0.10 + license_file +0.15 + quote_context +0.02 + source_sha256 +0.03 + uncertain_state -0.12 | dd5271267fd48b7dc69ccea1638ec556744479f1dce2db9bd8f5a94f18b83371 |
| Qwen/Qwen-Image-2.1 | 再分发 | — | base +0.48 + exact_quote +0.10 + license_file +0.15 + quote_context +0.02 + source_sha256 +0.03 + uncertain_state -0.12 | 392e11e45e37ac421840f4c69e2bc023e0f0540dc909a603948e9552620a6558 |
| Qwen/Qwen-Image-2.1 | 训练其他模型 | — | base +0.48 + exact_quote +0.10 + license_file +0.15 + quote_context +0.02 + source_sha256 +0.03 + uncertain_state -0.12 | b062018cb9c1f37db79dafa82a51516906c39482ac56fd411985fdb47dfccd11 |

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
