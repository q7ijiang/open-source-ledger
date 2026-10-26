# AI 模型血缘风险传播报告

> 生成时间：2026-10-26 22:46
> 对比区间：2026-10-26 → 2026-10-26
> 间隔天数：0 天
> 快照：t0 `tests\fixtures\projects\real_modelscope\snapshots\full\scenarios\direct_license_change\t0_bom.json` → t1 `tests\fixtures\projects\real_modelscope\snapshots\full\scenarios\direct_license_change\t1_bom.json`
> 生成工具：开源账本（深度层）· report_enhanced.py（接口约定 v0.3）

## 一、变更摘要

共检测到 **1** 个变更事件，按类型分布：

- **许可证变更**（`license_changed`）：1 个

| 事件 ID | 类型 | 风险源（seed） | 变更（before → after） | 证据 | 判定 | 审计（merge_status / reason_code / rule_version） |
|---|---|---|---|---|---|---|
| evt-t1-001 | 许可证变更 | Qwen/Qwen2.5-7B-Instruct-AWQ@master | Apache-2.0 → qwen-research | A | RISK_POTENTIAL | merge_status=KEPT_SEPARATE；reason_code=NO_MERGE_CANDIDATE；rule_version=merge-policy-v2 |

## 二、传播路径

事件均未携带血缘路径（path 为空）。

## 三、许可证继承冲突分析

对每个许可证变更事件，比较上游许可证义务（Duty）与下游许可证禁止（Prohibition），检测是否存在继承冲突：

共 **1** 个许可证变更事件，其中检测到继承冲突 **0** 个。

| 事件 ID | 风险源（seed） | 变更（before → after） | 冲突检测 | 冲突类型 | 冲突描述 |
|---|---|---|---|---|---|
| evt-t1-001 | Qwen/Qwen2.5-7B-Instruct-AWQ@master | Apache-2.0 → qwen-research | 无冲突 | `none` | 上游或下游许可证规则未知，无法判定继承冲突 |

## 四、路径证书

未生成任何路径证书（path_certificates 为空，path_certificates 数为 0）。

## 五、受影响资产（按判定分组）

无路径证书，无法分组。

## 六、风险源汇总

| 风险源 | 关联事件数 |
|---|---|
| Qwen/Qwen2.5-7B-Instruct-AWQ@master | 1 |

## 七、证据等级与判定说明

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
- **验收模拟**：验收模拟：LICENSE.ACCEPTANCE.md 为注入的收紧条款，不代表该模型当前 ModelScope 许可证事实。
- 许可证事实：**qwen-research**（AI 不可改写）
- 摘要：验收模拟：新画像仅限研究用途，商业使用受限，需要人工确认。
| 维度 | AI 语义结论 | 置信度 / 证据等级 / 状态 | 原文文件 | 原文依据 |
| --- | --- | --- | --- | --- |
| 商业使用 | 禁止 | 0.86 / C / pending | LICENSE.ACCEPTANCE.md | 验收模拟条款：仅限研究用途，不得用于商业目的。 |
| 许可证与版权声明保留 | 有条件允许 | 0.59 / C / pending | README.ACCEPTANCE.md | 分发时请保留许可证与版权声明。 |

**置信度构成**

- 商业使用：基础 +0.48 + LICENSE 文件 +0.15 + 原文精确命中 +0.10 + 限制措辞 +0.08 + SHA256 +0.03 + 引文长度 +0.02 = 0.86
- 许可证与版权声明保留：基础 +0.48 + README 文件 +0.08 + 原文精确命中 +0.10 + SHA256 +0.03 + 引文长度 +0.02 + 不确定性 -0.12 = 0.59

**未识别维度与证据缺口**

| 维度 | 原因 |
| --- | --- |
| 训练其他模型 | 验收模拟文本未覆盖 |
| 微调版本再分发 | 验收模拟文本未覆盖 |
| 商用授权申请方式 | 验收模拟文本未给出申请方式 |

### 语义 Diff

> 验收模拟：以下语义差异不代表真实世界许可证已经变更。

| 模型 | 维度 | 语义变化 | 复核优先级 | t0 原文 | t1 原文 |
| --- | --- | --- | --- | --- | --- |
| Qwen/Qwen2.5-7B-Instruct-AWQ | 商业使用 | 允许 → 禁止 | high | 验收模拟条款：允许用于商业目的。 | 验收模拟条款：仅限研究用途，不得用于商业目的。 |
