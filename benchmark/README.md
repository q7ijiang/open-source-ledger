# B 侧评测基准数据（`benchmark/`）

> 归属：**B（算法与评测）**
> 覆盖任务：B-01（20 候选项目 + 12 模型案例）、B-02（标注规范）、B-04 雏形、B-05 指标草案
> 生成时间：2026-11-13 ｜ Gate 1 截止：2026-11-16
> 配套文档：[`annotation_spec.md`](annotation_spec.md)
> **本版不含任何准确率结论**：数据尚未跑过全量评测，准确率一律待 Gate 2 之后按同一份标签重算。

---

## 0. 这是什么

把"工具能跑"升级为"效果可验证"所需的标准答案（gold label）底座：

- `candidates.csv` —— **项目级**候选池（20 个真实开源项目，固定 commit、具体文件、调用段行号）
- `rejected_candidates.csv` —— **被排除**的候选及其排除证据（25 条，含 A 点名的 13 条）
- `model_cases.json` —— **模型级**事实与期望判定（12 个案例，覆盖 4 类许可证事实）
- `annotation_spec.md` —— 标注口径：标签定义、判别顺序、字段格式
- `validate_benchmark.py` —— 结构、枚举、哈希与一致性自检

所有标签只依据 **ModelScope 官方 API 的 A 级事实 + 规则库**推导，**不参考工具运行输出**，避免标签泄漏。

---

## 1. 文件清单

| 文件 | 用途 | 规模 |
|---|---|---|
| `candidates.csv` | 正样本：项目 × 使用关系 | 20 行 / 20 项目 / 16 个模型家族 |
| `rejected_candidates.csv` | 负样本：被排除的候选与原因 | 25 行 |
| `model_cases.json` | 模型案例与期望判定 | 12 个案例 |
| `annotation_spec.md` | 标注规范 v0.2 | — |
| `validate_benchmark.py` | 自检脚本（CI 可跑） | — |

---

## 2. 平台证据：怎么证明"项目真的用了 ModelScope"

这是本版最重要的改动。**不能用"文件里出现模型 ID + 文件里有 `import modelscope`"来判定**，必须看模型所在的那条**调用语句本身**由谁发起。判定算法（`bench_strict.py`，一次性采集工具，未入库）：

1. 定位含 `snapshot_download` / `pipeline(` / `from_pretrained` / `AutoModel*` / `AutoTokenizer` 且非注释的行；
2. 从该行起按括号配平向后累加，得到完整调用段（最多 15 行，跳过字符串内的括号）；
3. 解析**变量绑定**：`NAME = "<model_id>"`、`def f(self, NAME="<model_id>")` 记入变量表，再在调用段内用 `\bNAME\b` 匹配——否则会漏掉 `snapshot_download(model_id)` 这类间接引用；
4. 按下方优先级给出 `platform_evidence`。

| `platform_evidence` | 含义 | 能否进正样本 |
|---|---|---|
| `modelscope_download` | `snapshot_download(...)` 实际执行，且文件内有 ModelScope 来源 | ✅ 正样本 |
| `modelscope_api` | `modelscope.pipelines.pipeline(...)` 实际执行 | ✅ 正样本 |
| `modelscope_source_selected` | `from_pretrained` 的类来自 `from modelscope import ...`（显式选择 MS 源） | ✅ 正样本 |
| `modelscope_import` | 只有 import，没有可归属的调用 | ❌ 不足 |
| `modelscope_namespace_only` | 仅出现 `AI-ModelScope/...` 之类命名空间或本地路径 | ❌ 负样本 |
| `huggingface_import` | 调用方是 `transformers` / `diffusers` / `huggingface_hub` | ❌ 负样本 |
| `non_modelscope_remote_api` | 走第三方远程 API（如 SiliconFlow） | ❌ 负样本 |
| `local_path_only` | 只从本地目录加载，路径里带 MS 字样 | ❌ 负样本 |
| `mapping_only` | 只在映射表 / 常量表 / 模型注册表里声明 | ❌ 负样本 |
| `ambiguous` / `commented_out` | 证据不足 / 调用被注释 | ❌ 负样本 |

`platform_confidence`：`high` = 调用段内直接出现模型 ID 或已解析的变量绑定；`low` = 依赖跨文件/跨函数推断。

> 本轮据此把 A 点名的 13 条全部降级并写入 `rejected_candidates.csv`，另外拒绝了 12 条审计不通过的候选。

---

## 3. `candidates.csv` 字段

共 37 列，按用途分五组。

**来源定位**

| 列 | 含义 |
|---|---|
| `case_id` | `pc-0001` … |
| `repo` / `repo_url` | `owner/name` 与仓库地址 |
| `head_sha` | 固定提交（采集时刻默认分支 HEAD，40 位） |
| `source_file` / `source_kind` | 命中文件；`code` / `script` / `config` / `docs` |
| `line_start` / `line_end` | 人类可核对的行号区间：模型 ID 字面行与调用段的并集 |
| `matched_text` / `matched_text_sha256` | 调用段原文（空白归一后）及其 SHA-256 |

**平台证据**：`platform_evidence`、`platform_confidence`（取值见 §2）

**模型事实**：`model_id`、`model_revision`、`model_source_url`、`model_observed_at`、`raw_response_sha256`

**许可证四段**（A 要求的拆分，见 `annotation_spec.md` §2.1）

| 列 | 含义 |
|---|---|
| `license_raw` / `license_name_raw` | `Data.License` / `Data.LicenseName` 原值，不改写 |
| `license_source_field` | 实际生效字段（`Data.LicenseName` 优先，为空则 `Data.License`） |
| `license_observed_at` | 抓取日期 |
| `license_known` / `license_spdx_like` / `license_category` | 规则库是否认识 / 是否 SPDX 式 / 6 类之一 |
| `canonical_license_id` / `risk_level` | 归一 ID 与风险 1–5（仅在 `known=true` 时非空） |
| `pipeline_license_state` | 适配器视角：`standard` / `nonstandard` / `missing` |
| `semantic_license_state` | 语义视角：`standard_spdx` / `recognized_non_spdx` / `nonstandard` / `missing` / `unresolved` |
| `license_class` | `spdx` / `recognized_non_spdx` / `nonstandard` / `missing` / `unresolved` |
| `needs_human_review` | 叠加状态 |

**标注与分组**：`use_type`、`expected_decision`、`candidate_status`、`candidate_role`、`project_group`、`family_group`、`usage_evidence`、`annotator`、`note`

`use_type` 枚举对齐 `ai_layer/schemas.py::PROJECT_USE_TYPES`。**`weight_distribution` 只用于第三方发布 / 上传 / 转售 / 对外提供权重**；`snapshot_download` 属于"获取模型"，不是分发，本批不使用该值。

---

## 4. `rejected_candidates.csv` 字段

`reject_id`、`repo`、`repo_url`、`head_sha`、`model_id`、`source_file`、`line_no`、`platform_evidence`、`evidence_text`、`reject_reason`、`note`、`reviewed_at`、`reviewer`。

`reject_reason` 取值：`huggingface_only`(5)、`ambiguous_platform`(5)、`mapping_only`(4)、`local_path_only`(2)、`commented_out`(3)、`non_modelscope_remote_api`(1)、`namespace_only`(5)。
其中 `commented_out` / `namespace_only` 是在 A 给的四个原因之外补充的，用于描述"调用被注释""只有命名空间"两种情况。

**不删除原始候选的理由**：这些行本身就是"模型 ID 在 ModelScope 上存在，但项目并未从 ModelScope 使用它"的天然负样本，可直接用来测工具会不会误报。

---

## 5. `model_cases.json` 字段

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

- `raw_response_sha256` 是整份 API 响应体的 SHA-256，可据此确认"当时抓到的到底是什么"，而不只是断言字段值。
- Gemma 的表述固定为"**已识别的受限 AI 使用条款**"（`known=true`、`spdx_like=false`、`category=ai_restricted`、`license_class=recognized_non_spdx`），**不得写成"SPDX 标准许可证"**。

---

## 6. 怎么采的（可复现）

1. **模型事实**：`GET https://www.modelscope.cn/api/v1/models/<ns>/<name>`，取 `Data.License` / `Data.LicenseName` / `Data.Revision`，同时保存响应体哈希（2026-11-13 实抓，匿名可访问）。
2. **候选项目**：GitHub 代码检索 5 组查询（`snapshot_download`、`pipeline`、`AutoModel` 等 + `modelscope`），得到 145 个文件 / 89 个 model+repo 对；对原 45 条候选逐条重抓原文复核。
3. **调用段审计**：按 §2 的算法判定平台证据，`modelscope/*` 官方仓库不作为依赖项目。
4. **人工复核**：逐条读上下文判定 `use_type`；剔除 vendored 副本、纯 README 提及、纯注释引用。

> 采集脚本为任务期一次性工具，未入库；数据本身已在库内，日常评测与 CI **不联网**。

---

## 7. 当前统计

**项目池（20）**

| 维度 | 分布 |
|---|---|
| 平台证据 | `modelscope_download` 12、`modelscope_api` 6、`modelscope_source_selected` 2 |
| 使用方式 | `local_inference` 14、`evaluation_only` 2、`fine_tuning` 2、`unknown` 2 |
| 流水线许可证状态 | `standard` 13、`missing` 6、`nonstandard` 1 |
| 语义许可证状态 | `standard_spdx` 13、`missing` 5、`unresolved` 1、`nonstandard` 1 |
| 期望判定 | `SAFE` 12、`UNDETERMINED` 6、`RISK_CONFIRMED` 1、`RISK_POTENTIAL` 1 |
| 分组 | dev 10、validation 5、sealed test 5 |

**模型案例（12）**

| 许可证事实 | 数量 | 期望判定 |
|---|---|---|
| `standard_spdx` | 8 | `SAFE` 8（risk 1–2） |
| `recognized_non_spdx` | 1 | `RISK_CONFIRMED` 1（Gemma，risk 4） |
| `nonstandard` | 1 | `RISK_POTENTIAL` 1（Llama 3.1） |
| `missing` | 1 | `UNDETERMINED` 1（glm，`License=other`） |
| `unresolved` | 1 | `UNDETERMINED` 1（模型 API 404） |

> 本批**未覆盖 `conflict`**（字段 vs LICENSE 文件、跨 revision 冲突），B-03 扩池时专项补充。

---

## 8. 分组（B-04 雏形）

约束：同一项目、其 fork、**同一模型家族**必须同组；t0/t1 同组。家族不可再分，按家族整组填充：

| 组 | 行数 | 模型家族 |
|---|---|---|
| dev | 10 | `bge-large-zh-v1.5`(4)、`chatglm3-6b`(2)、`chatTTS`、`PDF-Extract-Kit-1.0`、`glm-4-voice-tokenizer`、`unirec-0.1b` |
| validation | 5 | `MindChat-Qwen2-4B`、`XTTS-v2`、`internlm-chat-7b`、`i2vgen-xl`、`cv_anytext` |
| sealed test | 5 | `cv_retinafce_recognition`、`punc_ct-transformer`、`mplug-vqa`、`XiYanSQL-QwenCoder-3B`、`nlp_structbert` |

`bge` 的 4 个项目全部在 dev、`chatglm3` 的 2 个项目全部在 dev，满足"家族不跨组"。B-03 扩到 ~40 个项目时，按 6:2:2 补足到 8–10 个家族。

---

## 9. 指标定义草案（B-05）

| 指标 | 公式 | 分母口径 |
|---|---|---|
| 平台识别准确率 | 平台证据判定正确的项目 / 正负样本总数 | 正样本 + `rejected_candidates.csv` |
| 模型识别率 | 识别正确的案例数 / 可判定案例数 | 排除 `unresolved` |
| 上游闭包解析率 | 成功解析的上游节点 / 应解析节点 | 按模型案例 |
| 循环检出率 | 正确标记 `scc_cycle` 的案例 / 含环案例 | 需构造样本 |
| 条款分类准确率 | 分类正确的 claim / 有标注的 claim | 仅 C 级 AI 结论 |
| 引文命中率 | 逐字命中原文的引文数 / 引文总数 | AI 输出 |
| Delta 准确率 | 事件类型与方向均正确的 / 事件总数 | dev 集 |
| 拒答率 | 输出 `UNDETERMINED` 且人工认定"本可判定"的 / 可判定总数 | 与"证据不足"分开统计 |

---

## 10. 真实性边界

| 内容 | 是否真实 |
|---|---|
| 仓库、commit、来源文件、行号、调用段原文 | ✅ 真实，可 `git checkout <head_sha>` 逐字复现 |
| 模型 ID 在 ModelScope 上可解析 | ✅ 真实，2026-11-13 实测 |
| 模型许可证字段原值与响应哈希 | ✅ 真实，官方 API 原样记录 |
| `platform_evidence` | ✅ 由调用段审计规则机械判定，规则见 §2 |
| `use_type` | ⚠️ 人工判读，依据 `usage_evidence`；`unknown` = 该文件内无调用证据 |
| `expected_decision` | ⚠️ 由 `annotation_spec.md` §4 规则表**推导**，不是工具真实输出 |
| 准确率 / 覆盖率结论 | ❌ 本批不下任何结论，待 Gate 2 用同一份标签重算 |
| AI 语义结论（条款级） | ❌ 本批未标注，属 C 级，需 AI 运行后另标 |

---

## 11. 已知局限

1. **模型家族偏斜**：`bge` 系占 4/20，因该模型在 GitHub 上被大量 RAG 项目引用；扩池时优先补其他家族。
2. **星标分布偏斜**：从 0 星小仓库到上万星项目都有；小仓库的价值在于调用方式单一、证据干净。
3. **`use_type` 单文件判读**：同一项目其他文件可能有不同用法，当前每项目只标一处，属可接受的简化。
4. **未覆盖 `conflict`**：需要字段与 LICENSE 文件不一致的真实样本，B-03 扩池时专项补充。
5. **平台证据依赖 GitHub 默认分支**：仓库改写历史后行号可能漂移；`head_sha` + `matched_text_sha256` 用于校验漂移。
6. **许可证事实是 2026-11-13 快照**：平台随时可能变更，重跑须重新抓取并更新 `observed_at` / `raw_response_sha256`。
