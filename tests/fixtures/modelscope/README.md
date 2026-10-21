# ModelScope 验证数据（tests/fixtures/modelscope）

本目录存放**验证模块正确性的数据**。分两类：

- **场景夹具**（`scenario_*`）：覆盖模块 8/9/10 的边界情形（SCC 环、缺失祖先、8 类变更事件）；
- **真实快照**（`real_model_licenses.json`）：ModelScope 官方 API 实抓的许可证数据，用于验证模块 4 的识别率。

> 约定：`out/` 与 `outputs/` 已被 `.gitignore` 忽略，**任何"用于验证模块正确性/准确度"的数据都必须放在本目录**，不要留在 `out/`、`outputs/` 里。

---

## 文件清单

| 文件 | 用途 | 数据来源 | 使用方 |
|---|---|---|---|
| `scenario_t0_assets.json` | 场景夹具 t0 快照：6 个模型 + 1 个数据集 | 身份真实、拓扑构造 | `test_build_graph` / `test_delta_engine` / `test_propagation_engine` |
| `scenario_t0_edges.json` | 场景夹具 t0 血缘边（7 条） | 构造 | 同上 |
| `scenario_t1_assets.json` | 场景夹具 t1 快照：6 个模型 + 1 个数据集（训练集换成 v2） | 身份真实、拓扑构造 | 同上 |
| `scenario_t1_edges.json` | 场景夹具 t1 血缘边（7 条，新增基模祖先、移除 legacy 祖先） | 构造 | 同上 |
| `real_model_licenses.json` | 53 个真实 ModelScope 模型的许可证快照 | **ModelScope API 实抓**（2026-10-10） | `test_license_db.py::test_real_data_license_coverage` |

---

## 场景夹具覆盖什么

### 六个模型（身份与许可证均为真实值）

| 角色 | 模型 | 真实许可证 | t1 许可证 | 说明 |
|---|---|---|---|---|
| seed | `LLM-Research/Meta-Llama-3.1-8B-Instruct` | `llama3.1` | `GPL-3.0` | **构造变更点**：触发 `license_changed` |
| finetuned | `Qwen/Qwen2.5-7B-Instruct` | `Apache-2.0` | `Apache-2.0` | 证据等级 A → C，触发 `evidence_downgrade` |
| serving | `Qwen/Qwen-Image-2.1` | `qwen-research` | `qwen-research` | 距 seed 两跳，验证多跳传播 |
| legacy | `ZhipuAI/glm-4-9b-chat` | `Apache-2.0` | `Apache-2.0` | t1 移除其祖先边，触发 `ancestor_removed` |
| cycle_a | `AI-ModelScope/bge-large-zh-v1.5` | `MIT` | `GPL-3.0-only` | **构造变更点**：同时参与 SCC 环 |
| cycle_b | `iic/nlp_structbert_sentiment-classification_chinese-base` | `Apache-2.0` | `Apache-2.0` | 与 cycle_a 互指，形成 2 节点 SCC |
| （仅边） | `Qwen/Qwen2.5-7B` | — | — | 只在 t1 的边里出现 → 缺失祖先场景 |

### 六类变更事件（t0 → t1）

| 事件 | 种子 | 断言要点 |
|---|---|---|
| `license_changed` | seed、cycle_a | 种子证据 A → `RISK_CONFIRMED`；带 `compare_direction` 方向判定 |
| `evidence_downgrade` | finetuned | A → C → `UNDETERMINED` |
| `ancestor_added` | `Qwen/Qwen2.5-7B` | 资产不在 BOM → 证据 C → `UNDETERMINED` |
| `ancestor_removed` | legacy | 边证据 B → `RISK_POTENTIAL` |
| `dataset_added` | `scenario/qwen-sft-data-v2` | 边证据 C → `UNDETERMINED` |
| `dataset_removed` | `scenario/qwen-sft-data-v1` | 边证据 B → `RISK_POTENTIAL` |

### 拓扑（构造，用于边界覆盖）

```
seed ←─ derived_from(A) ─ finetuned ─ trained_on(B/C) → dataset v1/v2
                              ↑ derived_from(B)
                            serving ─ derived_from(B) → legacy
                              └── derived_from(B) → Qwen/Qwen2.5-7B （仅 t1，缺失祖先）
finetuned ─ depends_on(B) → cycle_a ⇄ cycle_b  （SCC 环）
```

t0/t1 均为 **7 个资产 / 7 条边**；t1 建图后为 **8 个节点**（基模由边自动创建）。

---

## 真实性边界（重要，避免误读）

| 内容 | 是否真实 |
|---|---|
| 6 个模型的 namespace / name / purl | ✅ 真实，取自 ModelScope |
| 各模型 t0 许可证 | ✅ 真实，取自 ModelScope API 的 `Data.LicenseName` |
| 两处 t1 许可证变更（`llama3.1→GPL-3.0`、`MIT→GPL-3.0-only`） | ❌ **构造**，ModelScope 上并未发生 |
| 模型之间的依赖关系、SCC 环 | ❌ 构造（真实血缘中不存在环） |
| 数据集 ID（`scenario/...`） | ❌ 构造占位，未在 API 核实 |
| 证据等级（A/B/C）的赋法 | ❌ 按测试需要指定，不代表真实证据来源 |

**为什么要构造**：模块 8/9/10 的关键分支（SCC 成环、缺失祖先、证据降级、数据集增删）在真实 ModelScope 数据里**不会同时出现**，无法用真实快照覆盖；因此保留真实身份、构造拓扑，是这类边界测试的常规做法。

---

## `real_model_licenses.json` 说明

- 53 个真实模型（8 个命名空间），按 `canonical_id` 排序
- 字段：`canonical_id` / `asset_type` / `name` / `version` / `purls` / `license` / `license_evidence_level`
- **34 个有许可证字段，19 个 API 未返回**（保留空值，用于验证"不臆断"策略）
- 许可证分布：`Apache-2.0` 26、`MIT` 3、`llama3.1` 2、`qwen-research` 1、`creativeml-openrail-m` 1、`gemma` 1
- 覆盖验证结论（见 `test_license_db.py`）：
  - 已识别 30/34（≈88%）：Apache-2.0、MIT、gemma（经别名映射到 `Gemma-Terms-of-Use`）
  - 未识别的 3 种、4 条：`llama3.1`、`qwen-research`、`creativeml-openrail-m`
  - 这是**已知边界**（报告 5.7 节"非标协议覆盖边界"），不是回归失败

### 如何重新抓取

```powershell
# 1) 抓真实语料（需联网；ModelScope API 免 key）
python <workspace>\crawl_project_corpus.py --out outputs/project_validation/corpus `
       --max-models 200 --max-depth 3 --seeds-file <workspace>\seeds_expanded.json

# 2) 从语料抽取本文件（只保留真实模型，剔除聚合计数节点）
python <workspace>\gen_ms_fixtures.py
```

> 抓取脚本是任务期的一次性工具，未入库；数据本身已在库内，日常测试不联网。

---

## 维护约定

1. **改夹具必须同步改测试断言**：三个测试文件硬编码了上述 `canonical_id`。
2. **新增真实数据请优先扩充 `real_model_licenses.json`**，而不是塞进场景夹具。
3. **不要把测试产物（`out/`、`outputs/`）提交入库**；需要留档的验证数据放本目录并在此登记。
