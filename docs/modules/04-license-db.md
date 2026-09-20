# 模块 4：AI 许可证规则库

| 项目 | 内容 |
|---|---|
| 负责人 | B |
| 状态 | 待验收 |
| 完成日期 | 2026-09-20 |
| 对应任务 | 基础部分 · 模块 4 |

## 一句话摘要

内置 24 种常见开源 / AI 专用许可证的 P/D/P 三元组，能识别 Llama-2、OpenRAIL-M、Gemma 等非 SPDX 的 AI 专用许可证，兼容 Debian copyright 的 `;` 分隔复合表达式，并判断许可证变更方向（宽松 → 严格）。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| 许可证名称（字符串） | 模块 1 输出的资产列表 `license` 字段 / 人工输入 | 可能是 SPDX 标识、别名、原始名称或 `;` 分隔的复合表达式，如 `llama2`、`MIT/X11`、`GPL-2.0; LGPL-2.0` |
| 变更前后两个许可证 | 模块 9 的 before/after | 用于比较风险方向 |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| 规则库代码 | `license_db.py` | 24 种许可证规则 + 查询/比较/导出接口 |
| 规则库导出 | `licenses.json` | 纯 JSON 结构，供中文清单、增强层报告引用 |
| 命令行工具 | `python license_db.py --list/--show/--compare/--export` | 人工查询与验证 |

## 为什么要做

1. 很多合规清单只做"是否开源"的粗判，无法回答"这个许可证允许我商用吗、要求我开源吗、禁止我做什么"。
2. AI 生态大量使用非 SPDX 许可证（Llama 2 Community License、OpenRAIL-M、Gemma Terms of Use），通用 SPDX 库无法识别，会被漏判或误判。
3. 模块 5（中文清单）和模块 10（风险传播）都要依赖许可证规则做风险标注和方向判断。

## 具体怎么做

### 步骤 1：按官方文本提炼 P/D/P 三元组

对每种许可证阅读官方许可文本，提炼三类信息：
- **Permission（许可）**：允许做的事，如商用、修改、分发；
- **Duty（义务）**：必须做的事，如保留版权声明、附带许可证全文；
- **Prohibition（禁止）**：不能做的事，如不得用输出训练其他模型。

每种许可证同时给 1–5 的风险等级（1 最宽松，5 最严格），并标记是否为 AI 专用许可证。

### 步骤 2：设计名称归一化

`normalize_license()` 处理别名与变体：
- 大小写、空白归一化；
- 常见别名表：`Expat`→MIT、`GPL v3 or later`→GPL-3.0-only、`llama2`→Llama-2-Community-License 等；
- 每个 canonical_id 自动注册为自身别名，保证查询不会自相矛盾；
- 无法识别的名称返回 `None`，交由报告层标为"待人工确认"。

### 步骤 3：实现多许可证表达式评估

`evaluate_expression()` 支持 `;`、`,`、`AND`、`OR` 连接的许可证表达式，取最严格项作为资产整体风险。注意 `GPL v2 or later` 中的 `or later` 不会被误拆。

### 步骤 4：实现变更方向判断

`compare_direction(old, new)` 输出 `宽松→严格 / 严格→宽松 / 同级不变 / 新增许可证 / 许可证移除 / 未知`，并标记是否涉及 AI 专用许可证。

### 步骤 5：兼容真实数据（Debian 复合表达式）

真实 BOM（如 `data/assets_real_final.json`）的 `license` 字段大量使用 `;` 分隔的复合表达式（如 `GPL-2.0; LGPL-2.0; public-domain`）。单值接口（`get_rule`/`classify`/`risk_level`/`is_ai_license`）对复合表达式自动拆解并取最严格项；表达式内无法识别的冷门片段如实暴露在 `evaluate_expression().unknown_items` 中，交报告层标"待人工确认"。

## 得到了什么

- 24 种许可证规则（15 种基础 + 9 种真实数据扩展），每种含完整 P/D/P 三元组；
- 风险等级覆盖 1–5，类别覆盖宽松、公有领域、弱/强/网络 copyleft、AI 受限、文档 copyleft；
- 真实数据覆盖：`data/assets_real_final.json` 的 90 个含许可证资产 **100% 可识别**（get_rule 语义）；表达式层仅剩 14 个 Debian 冷门标注片段（如 `same-as-rest-of-p11kit`、`configure`）留在 unknown_items 中待人工确认；
- 例：`compare_direction("llama2", "Apache-2.0")` → `严格→宽松`，`ai_involved: true`。

## 暴露了什么问题

| 问题 | 影响 | 交给哪个模块解决 |
|---|---|---|
| 许可证名称写法极不统一（含 `???`、`GPL-2 with Linux-syscall-note exception`、`__AUTO_PERMISSIVE__` 等噪音） | 归一化无法覆盖全部变体 | 模块 4 已用别名表 + 例外条款兜底正则处理常见变体；模块 5 对剩余未识别项统一标"待人工确认"，不静默处理 |
| 同一资产可能有多个许可证（Debian `;` 分隔） | 单值比较会失真 | 模块 4 已支持表达式评估取最严格项；模块 10 传播时按最严格项判定 |
| Debian 版权文件的冷门标注（`same-as-rest-of-p11kit`、`noderivs` 等）无对应许可证文本 | 无法判断风险 | 保留在 `unknown_items`，模块 5 标"待人工确认" |

## 如何验证

1. `python license_db.py --list`：确认 24 种许可证齐全，AI 专用 3 种标记"是"。
2. `python license_db.py --show llama2`：确认 P/D/P 三元组完整。
3. `python license_db.py --compare MIT GPL-3.0`：应输出 `宽松→严格`。
4. `python license_db.py --show "GPL-2.0; LGPL-2.0"`：复合表达式返回最严格项（GPL-2.0-only）。
5. `python -m pytest tests/test_license_db.py`：回归测试全部通过（含真实数据覆盖率断言 ≥ 90%）。

## 相关文件

| 文件 | 路径 |
|---|---|
| 规则库代码 | `license_db.py` |
| 规则库导出 | `licenses.json` |
| 回归测试 | `tests/test_license_db.py` |

## 给队友的话

- 对 A：`license_db.compare_direction(before.license, after.license)` 可直接用于模块 13 的 deep 模式汇总；真实数据（如 `data/assets_real_final.json`）的复合表达式已可直接消费。
- 对 C：中文清单生成时调用 `get_triplets(license)` 取 P/D/P（复合表达式返回最严格项）；表达式内冷门片段用 `evaluate_expression(license)["unknown_items"]` 标"待人工确认"，不要编造。
- 对 C：增强层报告需要"宽松→严格"文案时，直接用 `compare_direction` 的 `direction` 字段。
