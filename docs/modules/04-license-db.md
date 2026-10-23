# 模块 4：AI 许可证规则库（license_db.py）

| 项目 | 内容 |
|---|---|
| 负责人 | B（算法核心） |
| 状态 | 已完成，随 `main` 交付 |
| 对应任务 | 基础部分 · 模块 4 |
| 数据源 | ModelScope 官方 API（`Data.LicenseName` / `Data.License`），证据等级 A |
| 关联测试 | `tests/test_license_db.py`（16 项） |

## 一句话摘要

内置 **26 条**许可证规则与 **137 条**别名映射，覆盖宽松、弱/强 copyleft、网络 copyleft 与 AI 专用限制六类；能把 ModelScope 返回的许可证文本（含大小写变体、非 SPDX 名称、`AND/OR/WITH` 复合表达式）归一为 1–5 风险等级与类别，并支持变更前后的方向判定。

## 输入

| 输入 | 来源 | 形态 |
|---|---|---|
| 许可证文本 | 模块 1/3 产出的资产 `license` 字段（原始值来自 ModelScope `Data.LicenseName`） | `Apache-2.0`、`mit`、`qwen-research`、`llama3.1`、`Apache-2.0 AND MIT` 等 |
| 变更前后许可证对 | 模块 9 的 `before` / `after` | 两个字符串，用于方向判定 |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| 规则库 | `license_db.py` | 26 条规则 + `evaluate_expression()` / `get_rule()` / `compare_direction()` |
| 规则快照 | `licenses.json` | 纯 JSON，供报告层与外部工具复用 |
| 命令行 | `python license_db.py --list/--show/--compare/--export` | 人工核查与导出 |

`evaluate_expression()` 返回结构：

```json
{ "max_risk_level": 2, "worst_category": "permissive",
  "items": [{ "canonical_id": "Apache-2.0", "risk_level": 2, "category": "permissive" }],
  "unknown_items": [] }
```

## 为什么要做

1. 通用 SPDX 库不认识 AI 生态的厂商协议（`qwen-research`、`llama3.1`、`Creativeml-OpenRAIL-M`），直接查表会漏判。
2. 平台返回的许可证写法不统一：大小写混用（`mit`）、带空格（`Apache License 2.0`）、复合表达式（`Apache-2.0 AND MIT`）。
3. 下游两个模块都依赖它：模块 5/11（中文清单与报告）取风险等级，模块 10 与 `risk_evaluator` 取判定依据。

## 具体怎么做

### 步骤 1：按官方文本提炼 P/D/P 三元组

对每条许可证提炼 Permission（可用）、Duty（必须）、Prohibition（禁止），并给出 **1–5 风险等级**（1 最宽松、5 最严格）与类别：

| 类别 | 条数 | 典型许可证 | 风险等级 |
|---|---:|---|---|
| `permissive` 宽松 | 11 | MIT、Apache-2.0、BSD-3-Clause | 1–2 |
| `public_domain` 公有领域 | 2 | CC0-1.0、Unlicense | 1 |
| `weak_copyleft` 弱 copyleft | 5 | MPL-2.0、LGPL-3.0 | 3 |
| `strong_copyleft` 强 copyleft | 3 | GPL-3.0、GPL-2.0 | 4 |
| `network_copyleft` 网络 copyleft | 1 | AGPL-3.0 | 5 |
| `ai_restricted` AI 专用限制 | 4 | Gemma-Terms-of-Use、Llama-2-Community-License、CC-BY-NC-4.0、OpenRAIL-M | 3–4 |

### 步骤 2：别名表兜住平台写法

137 条别名把变体映射到规则，例如 `Apache License 2.0` / `apache 2.0` → `Apache-2.0`，`mit` / `mit license` → `MIT`。**别名只做写法归一，不改变语义**。

### 步骤 3：复合表达式拆解

用伪代码表达求值顺序：

```
FUNCTION evaluate_expression(text):
    IF text 为空:                RETURN {risk: null, unknown: []}
    IF 含 AND / OR / WITH:       逐个子项递归求值，按"取最严"合并
    key ← 归一化(text)            # 小写、去多余空格
    IF key 命中别名表:            RETURN 对应规则
    ELSE:                       RETURN {risk: null, unknown: [原文]}
```

### 步骤 4：方向判定（供模块 9 使用）

`compare_direction(old, new)` 比较变更前后，返回 `direction`（宽松→严格 / 严格→宽松 / 同级不变 / 新增 / 移除 / 未知）与 `risk_increased`、`ai_involved` 两个布尔字段。

## 验证

| 验证项 | 数据 | 结论 |
|---|---|---|
| 真实模型许可证识别率 | `tests/fixtures/modelscope/real_model_licenses.json`（53 个真实模型，34 个有许可证） | **30/34 ≈ 88.2%** |
| 已识别 | Apache-2.0(26)、MIT(3)、gemma(1) | 全部归一正确 |
| 未识别（已知边界） | `llama3.1`(2)、`qwen-research`(1)、`creativeml-openrail-m`(1) | 显式进入 `unknown_items`，不误判 |
| 复合表达式 | `AND` / `OR` / `WITH` / 空串 | 不崩溃，按最严合并 |

## 已知边界

- **非标厂商协议不做强行归类**：`qwen-research` 等读不出授权边界，规则库返回"未知"，由 `risk_evaluator` 按证据等级判黄/灰。这是有意的保守设计——误判比漏判代价大。
- **别名表是人工维护的**：平台若出现新写法，需要新增别名，否则会落到"未知"。
- **规则语义基于公开文本归纳**，不构成法律意见。
