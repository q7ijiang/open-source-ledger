# AI 模型血缘风险传播报告

> 生成时间：2026-10-09 23:45
> 快照：t0 `E:\开源账本\open-source-ledger\data\test_scenarios\ms_t0_bom.json` → t1 `E:\开源账本\open-source-ledger\data\test_scenarios\ms_t1_bom.json`
> 生成工具：开源账本（深度层）· report_enhanced.py（接口约定 v0.3）

## 一、变更摘要

共检测到 **2** 个变更事件，按类型分布：

- **许可证变更**（`license_changed`）：2 个

| 事件 ID | 类型 | 风险源（seed） | 变更（before → after） | 证据 | 判定 | 审计（merge_status / reason_code / rule_version） |
|---|---|---|---|---|---|---|
| evt-t1-001 | 许可证变更 | Qwen/Qwen-Image-2.1-Finetune-Data@v1 | Qwen/Qwen-Image-2.1-Finetune-Data@v1 → qwen-data-license | B | RISK_POTENTIAL | merge_status=KEPT_SEPARATE；reason_code=NO_MERGE_CANDIDATE；rule_version=merge-policy-v2 |
| evt-t1-002 | 许可证变更 | Qwen/Qwen-Image-2.1-Finetune-Demo@master | Qwen/Qwen-Image-2.1-Finetune-Demo@master → qwen-research | B | RISK_POTENTIAL | merge_status=KEPT_SEPARATE；reason_code=NO_MERGE_CANDIDATE；rule_version=merge-policy-v2 |

## 二、传播路径

事件均未携带血缘路径（path 为空）。

## 三、许可证继承冲突分析

对每个许可证变更事件，比较上游许可证义务（Duty）与下游许可证禁止（Prohibition），检测是否存在继承冲突：

共 **2** 个许可证变更事件，其中检测到继承冲突 **0** 个。

| 事件 ID | 风险源（seed） | 变更（before → after） | 冲突检测 | 冲突类型 | 冲突描述 |
|---|---|---|---|---|---|
| evt-t1-001 | Qwen/Qwen-Image-2.1-Finetune-Data@v1 | Qwen/Qwen-Image-2.1-Finetune-Data@v1 → qwen-data-license | 无冲突 | `none` | 上游或下游许可证规则未知，无法判定继承冲突 |
| evt-t1-002 | Qwen/Qwen-Image-2.1-Finetune-Demo@master | Qwen/Qwen-Image-2.1-Finetune-Demo@master → qwen-research | 无冲突 | `none` | 上游或下游许可证规则未知，无法判定继承冲突 |

## 四、路径证书

未生成任何路径证书（path_certificates 为空，path_certificates 数为 0）。

## 五、受影响资产（按判定分组）

无路径证书，无法分组。

## 六、风险源汇总

| 风险源 | 关联事件数 |
|---|---|
| Qwen/Qwen-Image-2.1-Finetune-Data@v1 | 1 |
| Qwen/Qwen-Image-2.1-Finetune-Demo@master | 1 |

## 七、证据等级与判定说明

| 等级 | 定义（接口约定 v0.3） |
|---|---|
| A | 官方或权威元数据直接证明（PyPI / npm / Hugging Face API 许可证字段、仓库 LICENSE 文件） |
| B | 工具产物或结构化依赖证据（CycloneDX BOM、lockfile、模型卡结构化字段） |
| C | 推断、启发式或降级证据（同名对齐、模型卡文本推断、API 失败降级） |

| 判定 | 含义 |
|---|---|
| RISK_CONFIRMED | 路径上所有边证据等级为 A，规则明确适用 |
| RISK_POTENTIAL | 路径上存在 B 级边，规则可能适用 |
| UNDETERMINED | 路径上存在 C 级边、缺失祖先或冲突字段 |

> 口径（接口约定 v0.3）：血缘边证据等级按实际来源标注（A=官方数据，B=工具产物，C=推断）；例如 Hugging Face 官方 API 直接返回的模型卡元数据为 A，CycloneDX BOM 等工具产物为 B，推断、启发式或降级证据为 C。
> 风险传播使用 weakest link 规则：路径证据等级取路径中最低等级；`UNDETERMINED` 不是“无风险”，而是“证据不足以判定”。

---

> **免责声明**：本报告由开源账本自动生成，基于证据的辅助审计，不构成法律意见，也不能替代针对具体许可证、司法辖区和业务模式的执业法律审查。
