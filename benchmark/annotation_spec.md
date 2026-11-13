# ModelScope 许可证评测标注规范（v0.1）

> 归属：**B（算法与评测）** ｜ 对应任务：B-02（初稿） ｜ Gate 1 截止：2026-11-16
> 适用文件：`benchmark/model_cases.json`、`benchmark/candidates.csv`，以及后续 dev / validation / sealed test 全部标签
> 实现对齐：`license_db.py`、`risk_evaluator.py`、`modelscope_adapter.py`、`ai_layer/schemas.py`
> 版本：v0.1（2026-11-13，待 A 裁定后升 v1.0）

---

## 0. 这份规范要解决什么

评测要回答的不是"工具跑没跑通"，而是"工具的判断对不对"。要能算准确率，就必须先有**不依赖工具输出**的标准答案（gold label）。

本文档定死 6 个词的含义与边界，它们来自任务书 B-02：

| 标签 | 一句话 |
|---|---|
| 标准许可 | 规则库认识，能归一化到已知许可证 |
| 非标准许可 | 有许可证文本，但规则库不认识 |
| 缺失 | 根本没拿到许可证信息 |
| 冲突 | 拿到了两份以上互相矛盾的 A 级事实 |
| 未解析 | 本该拿到但没拿到（接口失败、上游查不到） |
| 待人工确认 | 不是许可证类别，是处理状态 |

**前 5 个互斥，第 6 个可叠加。** 这条是全文最重要的约定，下文 §2 与 §7 展开。

---

## 1. 标注对象与粒度

| 对象 | 主键 | 记录文件 | 说明 |
|---|---|---|---|
| 模型案例 | `model_id` + `revision` | `model_cases.json` | 一个 ModelScope 仓库坐标，含许可证事实与原文 |
| 项目案例 | `repo` + `head_sha` | `candidates.csv` | 一个 GitHub/GitLab 仓库的固定提交 |
| 使用关系 | `repo` + `head_sha` + `model_id` + `source_file` | `candidates.csv` 行内 | 项目在哪个文件里怎么用这个模型 |

**不标的东西**：聚合计数节点（`name` 含 `(Total:`）、数据集（除非项目训练时显式使用）、纯 README 提及且无代码/配置引用。

---

## 2. 许可证事实类别（5 类，互斥）

判定顺序固定：**先看有没有文本，再看认不认识，再看有没有矛盾，最后看是不是取不到。**

```
有许可证文本吗？
├─ 否 ──> 5. missing        （字段为空、字段是占位符、没有 LICENSE 文件）
└─ 是
   ├─ 有 ≥2 个 A 级来源且互相矛盾吗？
   │   └─ 是 ──> 4. conflict （字段 vs 文件、版本间、多文档）
   ├─ 规则库认识吗？（license_db.get_rule / evaluate_expression）
   │   ├─ 认识 ──> 1. standard
   │   └─ 不认识 ──> 2. nonstandard
   └─ （上述都不成立，但事实链因接口/上游失败而断）
                  ──> 3. unresolved
```

> 注意：`unresolved` 的位置在"取不到"，不在"取到了但不认识"。取到了文本却不认识，一律是 `nonstandard`。

### 2.1 标准许可 `standard`

- **定义**：许可证文本（可能含 `AND`/`OR`/`/` 复合表达式）经 `license_db` 归一后，至少一项命中 `licenses.json` 的 26 条规则之一。
- **判定**：`license_db.evaluate_expression(text)["max_risk_level"] is not None`。
- **记录**：`canonical_id`（取风险最高项）、`risk_level`（1–5）、`category`（6 类之一）。
- **边界**：
  - `gemma` 虽是自定义条款，但规则库有 `Gemma-Terms-of-Use`（risk 4，`ai_restricted`），因此 **`standard`**，不是 `nonstandard`。
  - 复合表达式 `Apache-2.0 AND MIT` → 取最严项（Apache-2.0，risk 2）。

### 2.2 非标准许可 `nonstandard`

- **定义**：有可读的许可证文本，但规则库未收录，无法归一。
- **判定**：`has_text and evaluate_expression(text)["max_risk_level"] is None`。
- **当前已知的 3 个实例**：`qwen-research`、`llama3.1`、`creativeml-openrail-m`（来自 53 个真实模型的实测语料）。
- **处理约定**：不臆断、不强制映射成 Apache 或 GPL；保留原值，按证据等级降级（见 §4）。
- **反例（易错）**：`other`、`none`、`unknown`、`noassertion`、`not found` **不是** nonstandard，见 §2.3。

### 2.3 缺失 `missing`

- **定义**：没有任何可用的许可证事实。
- **判定**，满足任一即可：
  1. 适配器输出的 `license` 为 `null` 或空串；
  2. API 字段命中占位符集合 `_GENERIC_LICENSE_VALUES = {"", "other", "none", "unknown", "noassertion", "not found"}`，且无其他来源；
  3. 仓库内无 LICENSE / COPYING 文件，README 中也没有可用声明。
- **关键约定**：**占位符一律记 `missing`，不记 `nonstandard`。** 理由：`modelscope_adapter.license_name_of()` 在 `Data.LicenseName` 为空时会读 `Data.License`，但命中占位符即返回 `(None, None)`，管线对该模型的实际产出就是"无许可证、无证据链"。标注必须与事实来源一致，不能把适配器已丢弃的值重新算作"非标协议"。
  > **口径已定（2026-11-13）**：占位符记 `missing`，**不改动适配器**。本批 12 个模型案例按此口径标注。
- **实例**：`ZhipuAI/glm-4-9b-chat` 当前返回 `Data.License="other"`、`Data.LicenseName=""` → **`missing`**（不是 `nonstandard`）。
- **禁止**："缺失"不等于"允许使用"。缺失的期望判定是 `UNDETERMINED`，不是 `SAFE`。

### 2.4 冲突 `conflict`

- **定义**：存在两个及以上 **A 级**来源，对同一维度给出互斥事实，且无法用"版本不同/重命名"解释。
- **典型形态**：
  - API 字段 `Data.License` 与仓库 `LICENSE` 文件不一致（`license_field_file_conflict`）；
  - 同一模型不同 `Revision` 的许可证不同（必须按 revision 分别标注，不得合并）；
  - 元数据字段互相矛盾（`metadata_file_conflict`）。
- **处理**：进人工裁定队列，由 A 裁定；裁定前不得进入自动准确率分母的"可判定"子集（单独统计）。
- **反例**：`Data.License` 为空而 `LICENSE` 文件有内容 → **不是冲突**，是"字段缺失但有文件证据"，按文件事实标 `standard`/`nonstandard`，来源字段记为文件路径。

### 2.5 未解析 `unresolved`

- **定义**：事实在本该获取的链路上失败，而不是"平台说明没有"。
- **判定**，满足任一即可：
  - 上游模型无法解析：`modelscope_lineage` 输出 `unresolved_upstream_models` 非空；
  - API 调用失败：`status = network_error` / `unavailable` / HTTP 非 200；
  - 文件读取失败（仓库不可达、路径 404）。
- **与 `missing` 的区别**：`missing` = 查到了，平台就是没写；`unresolved` = 没查成，不知道有没有。
- **处理**：期望判定 `UNDETERMINED`，且必须带 `unresolved_reason`，**不得计入"识别率"的分子或分母**，单独统计"未解析率"。

---

## 3. 证据等级（引用实现，不另立口径）

| 等级 | 定义 | 本项目中的来源 |
|---|---|---|
| A | ModelScope 官方 API 字段原值，或官方仓库 LICENSE/README 原文 | `Data.License` / `Data.LicenseName` / 冻结文件 |
| B | 由 A 级事实派生的结构 | 血缘边、canonical_id、BOM 映射、跨版本比对 |
| C | AI 抽取、项目上下文、语义 Diff、启发式、失败降级 | `ai_layer` 全部结论 |

标注规则：**标签必须建立在 A 级事实上**；只有 C 级支撑的判断不得写成确定标签，必须叠加 `needs_human_review`。

---

## 4. 期望判定的推导（四态）

标注出的是**事实**，`decision` 是由规则表推导的**期望输出**，两者分开存。推导口径与 `risk_evaluator.py` 一致：

| 事实类别 | 风险等级 | 证据 | 期望判定 |
|---|---|---|---|
| standard | 1–2（宽松） | 任意 | `SAFE` |
| standard | 4–5（强/网络 copyleft） | 任意 | `RISK_CONFIRMED` |
| standard | 3（弱 copyleft / AI 受限） | A | `RISK_CONFIRMED` |
| standard | 3 | B | `RISK_POTENTIAL` |
| standard | 3 | C | `UNDETERMINED` |
| nonstandard | — | A / B | `RISK_POTENTIAL` |
| nonstandard | — | C | `UNDETERMINED` |
| missing | — | 任意 | `UNDETERMINED` |
| unresolved | — | 任意 | `UNDETERMINED` |
| conflict | — | 任意 | 不计入自动指标，人工裁定 |

> 判定键名固定为 `SAFE` / `RISK_POTENTIAL` / `RISK_CONFIRMED` / `UNDETERMINED`，与渲染层四色字典一致，**不要写成 `RISK_SAFE`**。

---

## 5. 使用方式 `use_type`（项目侧）

枚举对齐 `ai_layer/schemas.py::PROJECT_USE_TYPES`，标注时只能取以下 7 值：

| 值 | 中文 | 代码线索 |
|---|---|---|
| `remote_api` | 远程 API 调用 | `base_url`、`api_key`、`DashScope`、OpenAI 兼容客户端 |
| `local_inference` | 本地推理 | `from_pretrained`、`AutoTokenizer`、`pipeline(` |
| `weight_distribution` | 模型权重分发 | `snapshot_download`、权重打包/上传 |
| `fine_tuning` | 微调训练 | `sft`、`lora`、`trainer` |
| `derivative_release` | 衍生模型发布 | 发布合并/蒸馏产物 |
| `evaluation_only` | 仅评测 | benchmark/eval 脚本 |
| `unknown` | 未分类 | 只有配置引用而无调用证据 |

一条使用关系必须能指到 `source_file` 的具体行号；否则 `use_type=unknown` 并叠加 `needs_human_review`。

---

## 6. 标注字段（可直接被脚本消费）

### 6.1 模型案例 `benchmark/model_cases.json`

```json
{
  "schema_version": "b-benchmark/model-case/v1",
  "case_id": "mc-0001",
  "model_id": "ZhipuAI/glm-4-9b-chat",
  "revision": "master",
  "observed_at": "2026-11-13",
  "fact": {
    "license_status": "missing",
    "license_name": null,
    "canonical_id": null,
    "risk_level": null,
    "category": null,
    "evidence_level": "A",
    "evidence_source_field": "Data.License",
    "raw_api": {"License": "other", "LicenseName": ""},
    "api_status": 200
  },
  "expected_decision": "UNDETERMINED",
  "needs_human_review": true,
  "review_reason": "API 仅返回占位符 other，按通用占位值过滤后无许可证事实",
  "trap": "api_placeholder",
  "annotator": "B",
  "second_annotator": null,
  "adjudicated_by": null
}
```

### 6.2 候选项目 `benchmark/candidates.csv`

列定义见 `benchmark/README.md`；必填列：
`case_id, repo, repo_url, head_sha, model_id, source_file, line_no, use_type, license_status, expected_decision, needs_human_review, annotator, note`

---

## 7. 待人工确认 `needs_human_review`（叠加状态）

以下任一成立即置 `true`，并在 `review_reason` 写清触发条件：

1. 证据等级为 C（AI 结论、启发式、降级结果）；
2. 期望判定为 `UNDETERMINED`；
3. `license_status ∈ {conflict, unresolved}`；
4. 许可证为 `nonstandard`（规则库无覆盖，需人工读条款）；
5. `use_type = unknown`（没有调用证据，只有配置或 README 提及）。

该字段只表示"需要人看一眼"，**不影响**该样本是否进入准确率分母；分母规则见 §9。

---

## 8. 标注流程与分歧处理

1. **双人独立标注**：B 标 dev/validation，C 独立标 sealed test（C-05）。
2. **分歧**：交由 A 裁定（A 负责争议）；裁定结果写入 `adjudicated_by` 与 `gold_label`。
3. **预测冻结**：模型输出在 frozen 时间点保存后，才解锁 sealed test 标签。
4. **禁止**：用 sealed test 标签调规则、调提示词、调置信度；任何此类修改必须按任务书要求提交"修改原因 / 影响范围 / 修改前后指标 / 是否使用 sealed test / 回归测试"。

---

## 9. 数据分组与泄漏防护

- 同一项目、其 fork、同一模型家族（如 `Qwen/Qwen2.5-*`）必须落在同一组；
- t0 与 t1 必须同组；
- 目标规模：~40 个项目 / 20–30 个模型案例，dev : validation : sealed ≈ 6 : 2 : 2；
- **分母口径**（指标计算时）：
  - 模型识别率：分母 = `license_status ∈ {standard, nonstandard, missing}` 的案例（排除 `unresolved`）；
  - 未解析率：`unresolved` 单独统计，不进识别率分母；
  - 冲突案例单独统计，人工裁定后才计入。

---

## 10. 边界样例（本轮实测，可直接做回归样本）

| # | 输入 | 事实 | 正确标签 | 易错点 |
|---|---|---|---|---|
| 1 | `ZhipuAI/glm-4-9b-chat`：`License="other"`, `LicenseName=""` | 占位符被适配器过滤 | `missing` | 误标成 `nonstandard` |
| 2 | `Qwen/Qwen-Image-2.1`：`LicenseName="qwen-research"` | 规则库无此规则 | `nonstandard` | 误标成 `missing`（有文本就不是缺失） |
| 3 | `LLM-Research/gemma-3-4b-it`：`License="gemma"` | 规则库有 `Gemma-Terms-of-Use`(risk 4) | `standard` | 误标成 `nonstandard`（"看起来非标"） |
| 4 | `LLM-Research/Meta-Llama-3.1-8B-Instruct`：`License="llama3.1"` | 规则库无此规则 | `nonstandard` | 误标成 `standard`（"llama 是常见协议"） |
| 5 | `iic/nlp_structbert-...`：`License="Apache License 2.0"` | 别名归一成功 | `standard` | 误标成 `nonstandard`（写法不规范≠非标） |
| 6 | 字段有 `MIT`，仓库 `LICENSE` 是 `GPL-3.0` | 两个 A 级来源矛盾 | `conflict` | 直接选一个当答案 |
| 7 | 上游父模型 API 404 | 没查成 | `unresolved` | 误标成 `missing`（"没有"≠"没查到"） |

> 说明：本轮实测发现 ModelScope 的 `Data.LicenseName` 在多数模型上为空，真实信号在 `Data.License`。因此 `evidence_source_field` 必须如实记录是 `Data.LicenseName` 还是 `Data.License`，不得统一写成前者的默认值。

---

## 11. 一致性校验（建议纳入 CI）

1. `license_status` 与 `license_name`/`raw_api` 自洽：`missing` 时不得有 `canonical_id`；`standard` 时必须有 `canonical_id` 且 `risk_level ∈ 1..5`。
2. `expected_decision` 必须能由 §4 规则表从 `(license_status, risk_level, evidence_level)` 唯一推出。
3. `needs_human_review` 必须满足 §7 的任一触发条件，不允许随手置 `true`/`false`。
4. 同一 `model_id` 出现多个 `revision` 时，必须分别标注，不得合并成一行。

---

## 12. 已知局限

- 规则库当前 26 条、覆盖 6 类；非标协议只能保留原文，不能给出法律结论。
- `Data.LicenseName` 与 `Data.License` 的优先级问题：现有适配器优先 `LicenseName`，实测多数为空，实际等价于读 `License`。此行为需 A 确认是否变更；若变更，本规范 §2.3 的占位符规则需同步。
- 冲突判定目前只覆盖"字段 vs 文件"，跨 revision 的冲突需人工比对，暂无自动化。
