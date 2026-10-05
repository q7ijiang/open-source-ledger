# AI 模型血缘风险传播报告

> 生成时间：2026-10-03 15:07
> 输入事件：`E:\开源账本\module11-report_enhanced\demo_propagated_v03.json` ｜ 路径证书：`E:\开源账本\module11-report_enhanced\demo_propagated_v03.json`
> 快照：t0 `E:\开源账本\test_data\t0_bom.json` → t1 `E:\开源账本\test_data\t1_bom.json`
> 生成工具：开源账本（深度层）· report_enhanced.py（接口约定 v0.3）

## 一、变更摘要

共检测到 **3** 个变更事件，按类型分布：

- **许可证变更**（`license_changed`）：2 个
- **版本升级**（`version_upgraded`）：1 个

| 事件 ID | 类型 | 风险源（seed） | 变更（before → after） | 证据 | 判定 | 审计（merge_status / reason_code / rule_version） |
|---|---|---|---|---|---|---|
| evt-20261011-001 | 许可证变更 | meta-llama/Llama-2-7b@f5db02db724555f92da89c216ac04704f23d4590 | Apache-2.0 → Llama-2-Community | B | RISK_POTENTIAL | merge_status=KEPT_SEPARATE；reason_code=LICENSE_ALIGNED；rule_version=merge-policy-v2 |
| evt-20261011-002 | 许可证变更 | student-org/instruction-dataset@v1 | CC-BY-4.0 → CC-BY-NC-4.0 | B | RISK_POTENTIAL | merge_status=KEPT_SEPARATE；reason_code=LICENSE_ALIGNED；rule_version=merge-policy-v2 |
| evt-20261011-003 | 版本升级 | student-org/llama2-chat-demo@main | student-org/llama2-chat-demo@main → student-org/llama2-chat-demo@e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4 | B | UNDETERMINED | merge_status=MERGED；reason_code=PURL_COORDINATE_EXACT；rule_version=merge-policy-v2 |

## 二、传播路径

每个事件携带从种子到受影响资产的传播路径（weakest link 规则取最弱证据）：

### evt-20261011-001 · 许可证变更

- 种子资产：`meta-llama/Llama-2-7b@f5db02db724555f92da89c216ac04704f23d4590`
- 传播路径（共 2 跳，最弱证据 B，判定 RISK_POTENTIAL）：

```text
meta-llama/Llama-2-7b@f5db02db724555f92da89c216ac04704f23d4590 —[derived_from / B]→ student-org/llama2-finetune-demo@a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0 —[derived_from / B]→ student-org/llama2-chat-demo@e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4
```

### evt-20261011-002 · 许可证变更

- 种子资产：`student-org/instruction-dataset@v1`
- 传播路径（共 1 跳，最弱证据 B，判定 RISK_POTENTIAL）：

```text
student-org/instruction-dataset@v1 —[trained_on / B]→ student-org/llama2-finetune-demo@a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0
```


## 三、路径证书

共生成 **3** 张路径证书：

| 证书 ID | 受影响资产 | 变更类型 | 跳数 | 最弱证据 | 判定 | 终止原因 | 缺失祖先 | 路径指纹 |
|---|---|---|---|---|---|---|---|---|
| cert-001 | student-org/llama2-chat-demo@e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4 | 许可证变更 | 2 | B | RISK_POTENTIAL | reached_leaf | 否 | a1b2...e5f6 |
| cert-002 | student-org/llama2-finetune-demo@a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0 | 许可证变更 | 1 | A | RISK_CONFIRMED | direct_edge | 否 | c3d4...a9b0 |
| cert-003 | student-org/llama2-chat-demo@e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4 | 祖先删除 | 0 | C | UNDETERMINED | missing_ancestor | 是 | e5f6...d3e4 |

## 四、受影响资产（按判定分组）

### 🔴 确认风险（1 项）

| 受影响资产 | 变更类型 | 跳数 | 最弱证据 | 证书 ID |
|---|---|---|---|---|
| student-org/llama2-finetune-demo@a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0 | 许可证变更 | 1 | A | cert-002 |

### 🟠 潜在风险（1 项）

| 受影响资产 | 变更类型 | 跳数 | 最弱证据 | 证书 ID |
|---|---|---|---|---|
| student-org/llama2-chat-demo@e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4 | 许可证变更 | 2 | B | cert-001 |

### ⚪ 无法判定（1 项）

| 受影响资产 | 变更类型 | 跳数 | 最弱证据 | 证书 ID |
|---|---|---|---|---|
| student-org/llama2-chat-demo@e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4 | 祖先删除 | 0 | C | cert-003 |

## 五、风险源汇总

| 风险源 | 关联事件数 |
|---|---|
| meta-llama/Llama-2-7b@f5db02db724555f92da89c216ac04704f23d4590 | 1 |
| student-org/instruction-dataset@v1 | 1 |
| student-org/llama2-chat-demo@main | 1 |

## 六、证据等级与判定说明

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

> 口径（接口约定 v0.3）：Hugging Face 官方 API 返回的模型卡元数据本可为 A，但 BOM 为 CycloneDX 工具产物，**血缘边证据等级统一按 B 级处理**，避免口径混用。
> 风险传播使用 weakest link 规则：路径证据等级取路径中最低等级；`UNDETERMINED` 不是“无风险”，而是“证据不足以判定”。

---

> **免责声明**：本报告由开源账本自动生成，基于证据的辅助审计，不构成法律意见，也不能替代针对具体许可证、司法辖区和业务模式的执业法律审查。
