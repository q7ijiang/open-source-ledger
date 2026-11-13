# ModelScope 许可证评测标注规范（v0.2）

> 归属：**B（算法与评测）** ｜ 对应任务：B-02 ｜ Gate 1 截止：2026-11-16
> 适用文件：`benchmark/model_cases.json`、`benchmark/candidates.csv`、`benchmark/rejected_candidates.csv`
> 实现对齐：`license_db.py`、`risk_evaluator.py`、`modelscope_adapter.py`、`ai_layer/schemas.py`
> 版本：v0.2（2026-11-13，按 A 的 review 修订；v0.1 的口径变化见 §12）

---

## 0. 这份规范要解决什么

评测要回答的不是"工具跑没跑通"，而是"工具的判断对不对"。要能算准确率，就必须先有**不依赖工具输出**的标准答案（gold label）。

任务书 B-02 给的 6 个词，本文档定死其含义与边界：

| 标签 | 一句话 | 本批是否覆盖 |
|---|---|---|
| 标准许可 | 规则库认识，能归一化到已知许可证 | ✅ |
| 非标准许可 | 有许可证文本，但规则库不认识 | ✅ |
| 缺失 | 根本没拿到许可证信息 | ✅ |
| 冲突 | 拿到了两份以上互相矛盾的 A 级事实 | ❌ 待 B-03 |
| 未解析 | 本该拿到但没拿到（接口失败、上游查不到） | ✅ |
| 待人工确认 | 不是许可证类别，是处理状态 | ✅ |

**前 5 个互斥，第 6 个可叠加。**

---

## 1. 标注对象与粒度

| 对象 | 主键 | 记录文件 | 说明 |
|---|---|---|---|
| 模型案例 | `model_id` + `model_revision` | `model_cases.json` | 一个 ModelScope 仓库坐标，含许可证事实与原文 |
| 项目案例 | `repo` + `head_sha` | `candidates.csv` | 一个 GitHub 仓库的固定提交 |
| 使用关系 | `repo` + `head_sha` + `model_id` + `source_file` + `line_start` | `candidates.csv` 行内 | 项目在哪个文件的哪条调用里怎么用这个模型 |
| 排除记录 | `repo` + `model_id` | `rejected_candidates.csv` | 为什么这条候选不能算正样本 |

**不标的东西**：聚合计数节点（`name` 含 `(Total:`）、数据集（除非项目训练时显式使用）、纯 README 提及且无代码/配置引用、`modelscope/*` 官方仓库。

---

## 2. 三层状态模型（本版核心改动）

v0.1 把"有没有许可证"和"是什么许可证"压成一个 `license_status`，导致 `other` 这类占位符无法同时表达"管线产出缺失"与"语义其实不明"。v0.2 拆成三个独立字段，**各自回答一个问题**：

| 字段 | 回答的问题 | 取值 |
|---|---|---|
| `license_raw` / `license_name_raw` | 平台**原样**返回了什么 | 原值，不删不改，空就是空串 |
| `pipeline_license_state` | **适配器**会产出什么 | `standard` / `nonstandard` / `missing` |
| `semantic_license_state` | 这批数据**语义上**是什么 | `standard_spdx` / `recognized_non_spdx` / `nonstandard` / `missing` / `unresolved` / `conflict` |

三者可以不一致，而且**允许**不一致：这正是要测的东西。

典型例子（`ZhipuAI/glm-4-9b-chat`）：

| 字段 | 值 | 理由 |
|---|---|---|
| `license_raw` | `other` | API 原值 |
| `license_name_raw` | `""` | API 原值 |
| `pipeline_license_state` | `missing` | `other` 在 `_GENERIC_LICENSE_VALUES` 里，适配器返回 `(None, None)` |
| `semantic_license_state` | `unresolved` | 平台说了"other"，即"另有约定但没写"，不能断言为"没有" |
| `needs_human_review` | `true` | 语义待人工读条款 |

> **v0.1 的错误**：把 `License=other` 一律记成 `missing`，等于替平台断言"没有许可证"。v0.2 起 `other` 的**语义**状态是 `unresolved`，`missing` 只留给"字段真的为空"。

### 2.1 标准许可 `standard`

- **定义**：许可证文本经 `license_db.evaluate_expression` 归一后，至少一项命中 `licenses.json` 的 26 条规则。
- **再分两类**（用 `license_spdx_like` / `license_class` 区分）：

| `license_class` | `license_spdx_like` | 含义 | 例 |
|---|---|---|---|
| `spdx` | `true` | 可对应 SPDX 标识的标准许可证 | MIT、Apache-2.0、GPL-3.0、LGPL-3.0 |
| `recognized_non_spdx` | `false` | 规则库**认识**，但不是 SPDX 式标准许可证，是厂商自定义条款 | `Gemma-Terms-of-Use`、`Llama-2-Community-License` |

- **Gemma 的固定表述**：`known=true`、`spdx_like=false`、`category=ai_restricted`、`license_class=recognized_non_spdx`，写作"**已识别的受限 AI 使用条款**"，**不得**表述为"SPDX 标准许可证"。它的 `pipeline_license_state` 仍是 `standard`（管线认识它），`semantic_license_state` 是 `recognized_non_spdx`。
- **复合表达式** `Apache-2.0 AND MIT` → 取最严项（Apache-2.0，risk 2）。
- **记录**：`canonical_license_id`（风险最高项）、`risk_level`（1–5）、`license_category`（6 类之一）。

### 2.2 非标准许可 `nonstandard`

- **定义**：有可读的许可证文本，但规则库未收录，无法归一（`max_risk_level is None`）。
- **当前实例**：`llama3.1`、`qwen-research`、`creativeml-openrail-m`、`CC-BY-NC-ND`。
- **处理**：不臆断、不强制映射成 Apache 或 GPL；保留原值，`canonical_license_id` 留空，`needs_human_review=true`。
- **反例**：`other`、`none`、`unknown`、`noassertion`、`not found` **不是** nonstandard（见 §2.3）。

### 2.3 缺失 `missing` / 未解析 `unresolved`

**先分清"平台说没有"和"我们没拿到"**：

| 情形 | `pipeline_license_state` | `semantic_license_state` |
|---|---|---|
| `Data.License` 与 `Data.LicenseName` 都为空串 | `missing` | `missing` |
| 字段只有占位符（`other`/`none`/`unknown`/`noassertion`/`not found`） | `missing` | `unresolved` |
| API 非 200 / 网络失败 / 上游 404 | `unresolved` | `unresolved` |

- `missing` 的期望判定是 `UNDETERMINED`，**不是** `SAFE`；"缺失"不等于"允许使用"。
- `unresolved` 必须带原因（HTTP 状态、错误类型），**不计入识别率分母**。
- **不改适配器**：口径是"按适配器现状标注"，`other` 被过滤是**被测行为**，不是要修的 bug。若 A 决定改适配器，本节与 §2 的对应行同步改。

### 2.4 冲突 `conflict`（本批未覆盖）

- **定义**：两个及以上 **A 级**来源对同一维度给出互斥事实，且无法用"版本不同/重命名"解释。
- **典型形态**：`Data.License` 与仓库 `LICENSE` 不一致；同一模型不同 `Revision` 许可证不同；元数据字段互相矛盾。
- **处理**：进人工裁定队列，由 A 裁定；裁定前**不进**自动指标分母，单独统计。
- **反例**：`Data.License` 为空但 `LICENSE` 文件有内容 → 不是冲突，按文件事实标 `standard`/`nonstandard`，`license_source_field` 记为文件路径。

### 2.5 判别顺序（照此实现，不要跳步）

```
API 调用成功吗？
├─ 否 ──> unresolved
└─ 是
   ├─ license_raw 与 license_name_raw 均为空 ──> missing
   ├─ 有效值命中占位符集合 ──> pipeline=missing / semantic=unresolved
   ├─ 规则库认识 ──> standard（再按 spdx_like 分 spdx / recognized_non_spdx）
   └─ 规则库不认识 ──> nonstandard
```

---

## 3. 证据等级

### 3.1 事实证据（沿用实现口径）

| 等级 | 定义 | 来源 |
|---|---|---|
| A | ModelScope 官方 API 字段原值，或官方仓库 LICENSE/README 原文 | `Data.License` / `Data.LicenseName` / 冻结文件 |
| B | 由 A 级事实派生的结构 | 血缘边、canonical_id、BOM 映射、跨版本比对 |
| C | AI 抽取、项目上下文、语义 Diff、启发式、失败降级 | `ai_layer` 全部结论 |

标注规则：**标签必须建立在 A 级事实上**；只有 C 级支撑的判断不得写成确定标签，必须叠加 `needs_human_review`。

### 3.2 平台证据（项目侧，v0.2 新增）

判"项目是否真的通过 ModelScope 使用该模型"，必须看**模型所在的那条调用语句**，不能看文件里有没有 `import modelscope`。字段 `platform_evidence` 取值与判定算法见 `README.md` §2；只有以下三值可进正样本：

`modelscope_download`、`modelscope_api`、`modelscope_source_selected`。

其余（`modelscope_import`、`modelscope_namespace_only`、`huggingface_import`、`non_modelscope_remote_api`、`local_path_only`、`mapping_only`、`ambiguous`、`commented_out`）一律进 `rejected_candidates.csv`，并保留证据原文。

---

## 4. 期望判定的推导（四态）

标注出的是**事实**，`decision` 是由规则表推导的**期望输出**，两者分开存。推导口径与 `risk_evaluator.py` 一致：

| 事实 | 风险等级 | 证据 | 期望判定 |
|---|---|---|---|
| `standard_spdx` | 1–2（宽松） | 任意 | `SAFE` |
| `standard_spdx` | 4–5（强/网络 copyleft） | 任意 | `RISK_CONFIRMED` |
| `standard_spdx` | 3（弱 copyleft） | A | `RISK_CONFIRMED` |
| `standard_spdx` | 3 | B | `RISK_POTENTIAL` |
| `standard_spdx` | 3 | C | `UNDETERMINED` |
| `recognized_non_spdx` | 按规则库 risk | 任意 | 按 risk 走上面的分级（Gemma risk 4 → `RISK_CONFIRMED`） |
| `nonstandard` | — | A / B | `RISK_POTENTIAL` |
| `nonstandard` | — | C | `UNDETERMINED` |
| `missing` | — | 任意 | `UNDETERMINED` |
| `unresolved` | — | 任意 | `UNDETERMINED` |
| `conflict` | — | 任意 | 不计入自动指标，人工裁定 |

> 判定键名固定 `SAFE` / `RISK_POTENTIAL` / `RISK_CONFIRMED` / `UNDETERMINED`，与渲染层四色字典一致，**不要写成 `RISK_SAFE`**。

---

## 5. 使用方式 `use_type`（项目侧）

枚举对齐 `ai_layer/schemas.py::PROJECT_USE_TYPES`，只能取以下 7 值：

| 值 | 中文 | 判定线索 |
|---|---|---|
| `remote_api` | 远程 API 调用 | `base_url`、`api_key`、DashScope、OpenAI 兼容客户端、SiliconFlow |
| `local_inference` | 本地推理 | 权重落到本地后由本项目加载运行（`from_pretrained`、`pipeline(`） |
| `weight_distribution` | **对外**分发权重 | 上传/发布/转售/提供下载，或把权重打进自己的发行物 |
| `fine_tuning` | 微调训练 | sft / lora / trainer 脚本 |
| `derivative_release` | 衍生模型发布 | 发布合并、蒸馏产物 |
| `evaluation_only` | 仅评测 | benchmark/eval 脚本跑分 |
| `unknown` | 未分类 | 只有配置引用而无调用证据，或用途在该文件内无法判断 |

**v0.1 的错误**：把 `snapshot_download` 一律标成 `weight_distribution`。v0.2 起明确：

- `snapshot_download` 是"**获取**模型"，不是分发；下载后本地跑 → `local_inference`，只下载不加载 → `unknown`（并在 `note` 说明）。
- `weight_distribution` 仅用于"本项目对外提供该权重"的情形；本批 20 条**没有**这一类。

一条使用关系必须能指到 `source_file` 的具体行号；否则 `use_type=unknown` 并叠加 `needs_human_review`。

---

## 6. 标注字段

### 6.1 模型案例 `benchmark/model_cases.json`

```json
{
  "case_id": "mc-0007",
  "model_id": "LLM-Research/gemma-3-4b-it",
  "source_url": "https://www.modelscope.cn/models/LLM-Research/gemma-3-4b-it",
  "observed_at": "2026-11-13",
  "model_revision": "master",
  "raw_response_sha256": "5b39bf5a…",
  "source_field": "Data.License",
  "raw_value": "gemma",
  "raw_license": "gemma",
  "raw_license_name": "",
  "known": true,
  "spdx_like": false,
  "category": "ai_restricted",
  "canonical_license_id": "Gemma-Terms-of-Use",
  "risk_level": 4,
  "license_class": "recognized_non_spdx",
  "pipeline_license_state": "standard",
  "semantic_license_state": "recognized_non_spdx",
  "expected_decision": "RISK_CONFIRMED",
  "needs_human_review": true,
  "note": "Gemma Terms of Use：已识别的受限 AI 使用条款，未归入 SPDX 标准许可证"
}
```

必填：`case_id`、`model_id`、`source_url`、`observed_at`、`model_revision`、`raw_response_sha256`、`source_field`、`raw_value`、`raw_license`、`raw_license_name`、`known`、`spdx_like`、`category`、`license_class`、`pipeline_license_state`、`semantic_license_state`、`expected_decision`、`needs_human_review`、`note`。

`raw_response_sha256` 是整份 API 响应体的哈希，用于证明"当时抓到的到底是什么"，而非仅断言字段值。

### 6.2 候选项目 `benchmark/candidates.csv`

字段表见 `README.md` §3。必填列：
`case_id, repo, repo_url, head_sha, source_file, source_kind, line_start, line_end, matched_text, matched_text_sha256, platform_evidence, platform_confidence, model_id, model_revision, model_source_url, model_observed_at, license_raw, license_name_raw, license_source_field, license_observed_at, raw_response_sha256, license_known, license_spdx_like, license_category, canonical_license_id, risk_level, pipeline_license_state, semantic_license_state, license_class, needs_human_review, use_type, expected_decision, candidate_status, candidate_role, project_group, family_group, usage_evidence, annotator, note`

约定：

- `matched_text` 先做空白归一（`" ".join(text.split())`）再算 `matched_text_sha256`，避免换行/缩进差异导致哈希不稳定；
- `line_start` / `line_end` = 模型 ID 字面行与调用段的并集区间，保证人类能 `git show <sha>:<file>` 逐字核对；
- `candidate_status` 本批全为 `positive`；负样本在 `rejected_candidates.csv`，不混入本表。

### 6.3 排除记录 `benchmark/rejected_candidates.csv`

必填：`reject_id, repo, model_id, source_file, line_no, platform_evidence, evidence_text, reject_reason, note, reviewed_at, reviewer`。

`reject_reason` 枚举：`huggingface_only`、`local_path_only`、`mapping_only`、`non_modelscope_remote_api`、`ambiguous_platform`、`commented_out`、`namespace_only`。前四类来自 A 的 review，后三类是本轮审计补充。

---

## 7. 待人工确认 `needs_human_review`（叠加状态）

以下任一成立即置 `true`，并在 `note` 写清触发条件：

1. 证据等级为 C；
2. 期望判定为 `UNDETERMINED`；
3. `semantic_license_state ∈ {conflict, unresolved}`；
4. 许可证为 `nonstandard` 或 `recognized_non_spdx`（需人工读条款）；
5. `use_type = unknown`；
6. `platform_confidence = low`。

该字段只表示"需要人看一眼"，**不影响**样本是否进入准确率分母。

---

## 8. 标注流程与分歧处理

1. **双人独立标注**：B 标 dev/validation，C 独立标 sealed test（C-05）。
2. **分歧**：交 A 裁定，结果写入 `adjudicated_by` 与 `gold_label`。
3. **预测冻结**：模型输出在 frozen 时间点保存后，才解锁 sealed test 标签。
4. **禁止**：用 sealed test 标签调规则、调提示词、调置信度；任何此类修改须提交"修改原因 / 影响范围 / 修改前后指标 / 是否使用 sealed test / 回归测试"。

---

## 9. 数据分组与泄漏防护

- 同一项目、其 fork、同一模型家族必须同组；t0 与 t1 同组；
- 家族是**不可再分的最小单位**，分组按家族整组填充，不允许拆家族凑比例；
- 目标规模：~40 个项目 / 20–30 个模型案例，dev : validation : sealed ≈ 6 : 2 : 2；
- **分母口径**：
  - 平台识别准确率：正样本 + `rejected_candidates.csv` 全量；
  - 模型识别率：分母 = `semantic_license_state ∈ {standard_spdx, recognized_non_spdx, nonstandard, missing}`（排除 `unresolved`）；
  - 未解析率单独统计，不进识别率分母；
  - 冲突案例单独统计，人工裁定后才计入。

---

## 10. 边界样例（本轮实测，可直接做回归样本）

| # | 输入 | 事实 | 正确标签 | 易错点 |
|---|---|---|---|---|
| 1 | `ZhipuAI/glm-4-9b-chat`：`License="other"`, `LicenseName=""` | 占位符被适配器过滤 | pipeline=`missing` / semantic=`unresolved` | 误记成纯 `missing`（替平台断言"没有"），或误标 `nonstandard` |
| 2 | `Qwen/Qwen-Image-2.1`：`LicenseName="qwen-research"` | 规则库无此规则 | `nonstandard` | 误标成 `missing`（有文本就不是缺失） |
| 3 | `LLM-Research/gemma-3-4b-it`：`License="gemma"` | 规则库有 `Gemma-Terms-of-Use`(risk 4) | `standard` + `recognized_non_spdx` | 误标 `nonstandard`，或说成"SPDX 标准许可证" |
| 4 | `LLM-Research/Meta-Llama-3.1-8B-Instruct`：`License="llama3.1"` | 规则库无此规则 | `nonstandard` | 误标 `standard`（"llama 是常见协议"） |
| 5 | `iic/nlp_structbert-...`：`License="Apache License 2.0"` | 别名归一成功 | `standard`（`spdx`） | 误标 `nonstandard`（写法不规范≠非标） |
| 6 | 字段有 `MIT`，仓库 `LICENSE` 是 `GPL-3.0` | 两个 A 级来源矛盾 | `conflict` | 直接选一个当答案 |
| 7 | 上游父模型 API 404 | 没查成 | `unresolved` | 误标 `missing`（"没有"≠"没查到"） |
| 8 | 项目里 `from modelscope import snapshot_download`，但该模型由 `transformers` 的 `from_pretrained` 加载 | 文件级 import ≠ 使用证据 | `platform_evidence=huggingface_import` → 进 rejected | 只看 import 就算正样本 |
| 9 | 项目用 `snapshot_download("X")` 下载后本地推理 | 下载≠分发 | `use_type=local_inference` | 标成 `weight_distribution` |
| 10 | 模型 ID 只出现在 `DownloadSource.MODELSCOPE` 映射表 | 声明≠调用 | `platform_evidence=mapping_only` → 进 rejected | 当成使用证据 |

> 说明：本轮实测发现 ModelScope 的 `Data.LicenseName` 在多数模型上为空，真实信号在 `Data.License`。`license_source_field` 必须如实记录，不得统一写成前者。

---

## 11. 一致性校验（已实现于 `validate_benchmark.py`）

1. `pipeline_license_state=missing` 时 `canonical_license_id` 必须为空、`risk_level` 必须为空；
2. `pipeline_license_state=standard` 时必须有 `canonical_license_id` 且 `risk_level ∈ 1..5`；
3. `semantic_license_state=unresolved` 只允许出现在 `license_raw` 命中占位符或 API 非 200 的行；
4. `expected_decision` 必须能由 §4 规则表从 `(semantic_license_state, risk_level, evidence)` 唯一推出；
5. `needs_human_review` 必须满足 §7 的任一触发条件；
6. 正样本的 `platform_evidence` ∈ {`modelscope_download`, `modelscope_api`, `modelscope_source_selected`}，且 `candidate_status=positive`；
7. `matched_text_sha256` = `sha256(" ".join(matched_text.split()))`；`line_start ≤ line_end`；
8. `model_cases.json` 中每个 `model_id` 在 `candidates.csv` 出现时，两处许可证字段值必须一致；
9. 同一 `family_group` 必须落在同一 `project_group`；
10. 同一 `model_id` 出现多个 `revision` 时必须分别标注，不得合并。

---

## 12. 版本变更（v0.1 → v0.2）

| 项 | v0.1 | v0.2 | 原因 |
|---|---|---|---|
| 许可证状态 | 单一 `license_status` | `raw` / `pipeline` / `semantic` 三层 | `other` 无法同时表达"管线缺失"与"语义不明" |
| Gemma | 记 `standard` | `standard` + `license_class=recognized_non_spdx` | 规则库认识 ≠ SPDX 标准许可证 |
| `snapshot_download` | `weight_distribution` | `local_inference` 或 `unknown` | 下载是获取，不是分发 |
| 平台证据 | 无 | `platform_evidence` 10 值 + 调用段审计 | 文件级 import 会误判 |
| 负样本 | 无 | `rejected_candidates.csv` 25 条 | 保留可复现的排除证据 |
| 事实可核验 | 字段值 | 增加 `raw_response_sha256`、`matched_text_sha256`、行号区间 | 让"当时抓到什么"可验证 |

**已知局限**：规则库 26 条、覆盖 6 类，非标协议只能保留原文，不能给法律结论；`conflict` 尚无实例；平台证据依赖 GitHub 默认分支，仓库改写历史后行号可能漂移（用 `head_sha` + 哈希校验）。
