# B 侧评测基准数据（`benchmark/`）

> 归属：**B（算法与评测）**
> 覆盖任务：B-01（20 候选项目 + 10 模型案例）、B-02（标注规范）、B-03/B-04 雏形、B-05 指标草案
> 生成时间：2026-11-13 ｜ Gate 1 截止：2026-11-16
> 配套文档：[`annotation_spec.md`](annotation_spec.md)

---

## 0. 这是什么

把"工具能跑"升级为"效果可验证"所需的标准答案（gold label）底座：

- `model_cases.json` —— **模型级**事实与期望判定（12 个案例，覆盖 5 类许可证事实）
- `candidates.csv` —— **项目级**候选池（20 个真实开源项目，固定 commit、具体文件与行号）
- `annotation_spec.md` —— 标注口径：6 个标签的定义、判别顺序、字段格式

所有标签只依据 **ModelScope 官方 API 的 A 级事实 + 规则库**推导，**不参考工具运行输出**，避免标签泄漏。

---

## 1. 文件清单

| 文件 | 用途 | 规模 |
|---|---|---|
| `candidates.csv` | 候选项目池（项目 × 使用关系） | 20 个项目 / 7 个模型 |
| `model_cases.json` | 模型案例与期望判定 | 12 个案例 |
| `annotation_spec.md` | 标注规范 v0.1 | — |

---

## 2. `candidates.csv` 字段

| 列 | 含义 | 取值 |
|---|---|---|
| `case_id` | 案例编号 | `pc-0001` … |
| `repo` | GitHub 仓库 | `owner/name` |
| `repo_url` | 仓库地址 | URL |
| `head_sha` | **固定提交**（默认分支 HEAD，采集时刻） | 40 位 SHA |
| `model_id` | 被引用的 ModelScope 模型 | `namespace/name` |
| `source_file` | 出现该模型的**来源文件** | 仓库相对路径 |
| `line_no` | 命中行号 | 整数 |
| `use_type` | 项目对模型的使用方式 | `remote_api` / `local_inference` / `weight_distribution` / `fine_tuning` / `derivative_release` / `evaluation_only` / `unknown` |
| `license_status` | 该模型的事实类别 | `standard` / `nonstandard` / `missing` / `conflict` / `unresolved` |
| `expected_decision` | 期望判定 | `SAFE` / `RISK_POTENTIAL` / `RISK_CONFIRMED` / `UNDETERMINED` |
| `needs_human_review` | 是否需人工复核 | `true` / `false` |
| `usage_evidence` | 命中的源码原文（截断） | 文本 |
| `annotator` | 标注人 | `B` |
| `note` | 使用方式判读依据 | 文本 |

`use_type` 枚举与 `ai_layer/schemas.py::PROJECT_USE_TYPES` 对齐；`license_status` 与 `expected_decision` 的定义见 `annotation_spec.md` §2、§4。

---

## 3. `model_cases.json` 字段

```json
{
  "case_id": "mc-0003",
  "model_id": "Qwen/Qwen-Image-2.1",
  "revision": "master",
  "fact": {
    "license_status": "nonstandard",
    "license_name": "qwen-research",
    "canonical_id": null,
    "risk_level": null,
    "category": "unknown",
    "evidence_level": "A",
    "evidence_source_field": "Data.LicenseName",
    "raw_api": {"License": "other", "LicenseName": "qwen-research"},
    "api_status": 200
  },
  "expected_decision": "RISK_POTENTIAL",
  "needs_human_review": true,
  "review_reason": "规则库未收录 'qwen-research'，保留原值，不臆断映射",
  "trap": "LicenseName=qwen-research 优先于 License=other，非标协议"
}
```

- `license_name`：**生效原文值**（未归一）；`canonical_id`：归一后的标准标识（仅 `standard` 有值）。
- `evidence_source_field`：如实记录取自 `Data.LicenseName` 还是 `Data.License`——本批实测中 **`Data.LicenseName` 大多数为空**，真实信号在 `Data.License`。
- `trap`：该案例专门用来卡住的常见误判，写测试时优先覆盖。

---

## 4. 怎么采的（可复现）

1. **模型事实**：ModelScope 官方 API `GET https://www.modelscope.cn/api/v1/models/<ns>/<name>`，取 `Data.LicenseName` / `Data.License` / `Data.Revision`（2026-11-13 实抓，匿名可访问）。
2. **候选项目**：GitHub 代码检索 `"<model_id>"`，逐个取默认分支 HEAD SHA，再取命中文件原文，定位行号与上下文。
3. **复核**：人工逐条读上下文判定 `use_type`；剔除 vendored 副本（如仓库内拷贝的 `ms-swift` / `LLaMA-Factory` 示例）、纯 README 提及、纯注释引用。

> 抓取脚本为任务期一次性工具，未入库；数据本身已在库内，日常评测不联网。

---

## 5. 当前统计

**项目池（20）**

| 维度 | 分布 |
|---|---|
| 使用方式 | `local_inference` 8、`weight_distribution` 7、`fine_tuning` 2、`evaluation_only` 1、`remote_api` 1、`unknown` 1 |
| 许可证事实 | `standard` 16、`nonstandard` 4 |
| 期望判定 | `SAFE` 14、`RISK_POTENTIAL` 4、`RISK_CONFIRMED` 2 |
| 模型 | `AI-ModelScope/bge-large-zh-v1.5` 8、`deepseek-ai/DeepSeek-R1-Distill-Qwen-7B` 4、`Qwen/Qwen-Image-2.1` 2、`LLM-Research/Meta-Llama-3.1-8B-Instruct` 2、`LLM-Research/gemma-3-4b-it` 2、`Qwen/Qwen2.5-Coder-7B-Instruct` 1、`iic/nlp_structbert_sentiment-classification_chinese-base` 1 |

**模型案例（12）**

| 许可证事实 | 数量 | 期望判定 |
|---|---|---|
| `standard` | 8 | `SAFE` 7、`RISK_CONFIRMED` 1（gemma） |
| `nonstandard` | 2 | `RISK_POTENTIAL` 2 |
| `missing` | 1 | `UNDETERMINED` 1 |
| `unresolved` | 1 | `UNDETERMINED` 1 |

---

## 6. 真实性边界

| 内容 | 是否真实 |
|---|---|
| 仓库、commit、来源文件、行号 | ✅ 真实，可 `git checkout <head_sha>` 复现 |
| 模型 ID 在 ModelScope 上可解析 | ✅ 真实，2026-11-13 实测（1 个故意留作 `unresolved` 的反例） |
| 模型许可证字段原值 | ✅ 真实，官方 API 原样记录 |
| `use_type` 判读 | ⚠️ 人工判读，依据 `usage_evidence` 列；`unknown` 表示该文件内无调用证据 |
| `expected_decision` | ⚠️ 由规范 §4 规则表**推导**，不是工具真实输出 |
| AI 语义结论（条款级） | ❌ 本批未标注，属 C 级，需 AI 运行后另标 |

---

## 7. 分组草案（B-04，待 A 确认）

约束：同一项目、其 fork、**同一模型家族**必须同组；t0/t1 同组。

| 组 | 项目数 | 模型家族（家族内项目数） |
|---|---|---|
| dev | 10 | `bge-large-zh-v1.5`(8)、`nlp_structbert`(1)、`Qwen2.5-Coder-7B`(1) |
| validation | 6 | `DeepSeek-R1-Distill-Qwen-7B`(4)、`gemma-3-4b-it`(2) |
| sealed test | 4 | `Qwen-Image-2.1`(2)、`Meta-Llama-3.1-8B-Instruct`(2) |

> 7 个模型家族 → 3 组，家族是**不可再分的最小单位**，所以组大小只能是 10/6/4。`Qwen-Image-2.1` 的两个项目必须在同一组（本表放 sealed），不能一边一个。
> B-03 扩到 ~40 个项目时补足到 8–10 个家族，使 sealed test 达到 8 个项目以上。

---

## 8. 指标定义草案（B-05）

| 指标 | 公式 | 分母口径 |
|---|---|---|
| 模型识别率 | 识别正确的案例数 / 可判定案例数 | 排除 `unresolved` |
| 上游闭包解析率 | 成功解析的上游节点 / 应解析节点 | 按模型案例 |
| 循环检出率 | 正确标记 `scc_cycle` 的案例 / 含环案例 | 需构造样本 |
| 条款分类准确率 | 分类正确的 claim / 有标注的 claim | 仅 C 级 AI 结论 |
| 引文命中率 | 逐字命中原文的引文数 / 引文总数 | AI 输出 |
| Delta 准确率 | 事件类型与方向均正确的 / 事件总数 | dev 集 |
| 拒答率 | 输出 `UNDETERMINED` 且人工认定"本可判定"的 / 可判定总数 | 与"证据不足"分开统计 |

---

## 9. 已知局限

1. 项目池 **模型家族偏斜**：`bge` 系占 8/20，因该模型在 GitHub 上被大量 RAG 项目引用；扩池时优先补其他家族。
2. 项目池**星标分布偏斜**：既有 1.9 万星的 `ktransformers`，也有 0–4 星的小仓库；小仓库的价值在于使用方式明确。
3. `use_type` 单文件判读：同一项目其他文件可能有不同用法，当前每项目只标一处，属可接受的简化。
4. 未标注 `conflict` 实例：需要字段与 LICENSE 文件不一致的真实样本，B-03 扩池时专项补充。
5. 许可证事实为 2026-11-13 快照，平台随时可能变更；重跑时须重新抓取并记录 `observed_at`。
