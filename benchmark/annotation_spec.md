# ModelScope 许可证评测标注规范（v0.3）

> 归属：**B（算法与评测）** ｜ 对应任务：B-02 ｜ Gate 1 截止：2026-11-16
> 适用文件：`benchmark/candidates.csv`、`benchmark/negative_cases.csv`、`benchmark/excluded_candidates.csv`、`benchmark/model_cases.json`、`benchmark/evidence/*.json`
> 实现对齐：`license_db.py`、`risk_evaluator.py`、`modelscope_adapter.py`、`ai_layer/schemas.py`
> 版本：v0.3（2026-11-14，按 A 的第二轮意见修订；v0.1→v0.2→v0.3 的变化见 §12）

---

## 0. 这份规范要解决什么

评测要回答的不是"工具跑没跑通"，而是"工具的判断对不对"。要能算准确率，就必须先有**不依赖工具输出**的标准答案（gold label）。

任务书 B-02 给的 6 个词，本文档定死其含义与边界：

| 标签 | 一句话 | 本批是否覆盖 |
|---|---|---|
| 标准许可 | 平台给了可归一化到已知 SPDX 标识的许可 | ✅ 13 |
| 非标准许可 | 已识别的许可文本/条款，但不是 SPDX 标识 | ✅ 3（Gemma / Llama 3.1 / Qwen-Research） |
| 缺失 | 平台许可证字段确实为空 | ✅ 5 |
| 冲突 | 两份以上互相矛盾的 A 级事实 | ❌ 待 B-03 |
| 未解析 | 平台给了占位值（如 `other`），无法判断实际条款 | ✅ 1 |
| 待人工确认 | 不是许可证类别，是处理状态（`needs_human_review`） | ✅ 可叠加 |

另有本版新增的 **`recognized_family_unresolved`**：许可族已识别、版本未给出（如 `CC-BY-NC-ND` 无版本号）。它不是"非标准许可"，单独成一类。

**前 5 个互斥，`needs_human_review` 可叠加。**

---

## 1. 标注对象与粒度

| 对象 | 主键 | 记录文件 | 说明 |
|---|---|---|---|
| 模型案例 | `model_id` + 快照哈希 | `model_cases.json` | 一个 ModelScope 仓库坐标，含许可证原始事实与两层判定 |
| 使用关系（正样本） | `case_id` | `candidates.csv` + `evidence/<case_id>.json` | 项目在哪个文件的**哪条调用**里怎么用这个模型 |
| 负样本 | `case_id` | `negative_cases.csv` + `evidence/<case_id>.json` | 可进指标分母的"看起来像但不是"的调用点 |
| 排除记录 | `exc_id` | `excluded_candidates.csv` | 证据不足、无法判定平台归属，**不进分母** |

**不标的东西**：聚合计数节点（`name` 含 `(Total:`）、数据集（除非项目训练时显式使用）、纯 README 提及且无代码/配置引用、`modelscope/*` 官方仓库。

**判定单位**：不是文件，也不是仓库，而是**一段调用**。文件里出现模型 ID、或文件顶部 `import modelscope`，都不构成使用证据。

---

## 2. 调用级证据包（v0.3 核心）

每个正/负样本在 `evidence/<case_id>.json` 里保存五段，任何一段缺失都不能进正样本：

| 段 | 字段 | 内容 |
|---|---|---|
| 平台 import | `platform.imports` | `from modelscope import ...` / `import modelscope` 的行号与原文；必须早于调用行 |
| 模型 ID 绑定 | `platform.imodel_binding` | `NAME = "<model_id>"`、`def f(self, NAME="<model_id>")`，或模型 ID 的字面行 |
| 调用表达式 | `platform.call` | 括号配平后的完整调用段（`start`/`end`/`expr`），最多 15 行 |
| 条件分支 | `platform.branch` | 调用处在 `try/except`、`if ...` 里时的上文与 `note` |
| 版本 | `platform.revision` | 调用参数里的 `revision=` / `model_revision=`，或 `unspecified` |

每段都带 `sha256`，校验器逐段重算。抽证据的流程：

1. 定位模型 ID 的字面行；
2. 从含 `snapshot_download|pipeline|from_pretrained|AutoModel*` 的那一行起，按括号配平向后取完整调用段；
3. 回溯变量绑定（赋值语句、函数默认参数）；
4. 记录平台 import 行号；
5. 判断调用是否在条件分支里。

## 3. 平台证据与分流

`platform_evidence` 取值与判定优先级：

| 值 | 判定条件 | 去向 |
|---|---|---|
| `modelscope_download` | `snapshot_download(...)` 且本文件有 modelscope import | 正样本 |
| `modelscope_api` | `pipeline(..., model='...')` 且本文件有 modelscope import | 正样本 |
| `modelscope_source_selected` | `AutoModel*/AutoTokenizer.from_pretrained` 的类来自 modelscope | 正样本 |
| `huggingface_import` | 调用方是 `huggingface_hub` / `transformers` / `diffusers` | **负样本**（能定位到具体行）或排除 |
| `commented_out` | 唯一相关调用被注释 | 负样本或排除 |
| `local_path_only` / `mapping_only` / `namespace_only` / `non_modelscope_remote_api` / `ambiguous` | 不构成使用证据 | **排除**，不进分母 |

`platform_confidence` 只有 `high` / `medium`。`high` 要求"平台 import + 绑定/字面 + 调用"三段齐全；缺任一段最多 `medium`，缺两段进排除。

`platform_role`：

- `primary`：项目直接通过 ModelScope 取用该模型；
- `conditional_fallback`：调用处在"别的平台失败后才回退 ModelScope"的分支里。**仍然是正样本**，但证据包必须带完整分支，且不能把它的分支条件写成"国内/海外"这类想当然的解释。

本批唯一一条 `conditional_fallback` 是 pc-0001：`huggingface_hub.snapshot_download(local_files_only=True)` 优先，抛 `LocalEntryNotFoundError` 且 `is_connect_hf()` 为假时才 `snapshot_download(model_id='pzc163/chatTTS')`。

## 4. 三层许可证状态

| 层 | 字段 | 谁决定 | 取什么值 |
|---|---|---|---|
| 原始层 | `license_raw`、`license_name_raw` | ModelScope 接口 | 原样，不删不改，空就是空串 |
| 管道层 | `pipeline_known/spdx_like/category/canonical_license_id/risk_level/pipeline_license_state/pipeline_decision` | 当前 `licenses.json` + 适配器 | 工具现在会输出什么 |
| 语义层（gold） | `semantic_license_family/version/state/class/risk_level` | 人工按下表 | 事实是什么 |

**gold 只看平台原始字符串，不看规则库是否收录。** 规则库收录与否属于管道层的事，不能反过来定义答案。

| 平台原值（`LicenseName` 优先，否则 `License`） | family | version | state | class | risk |
|---|---|---|---|---|---|
| `apache-2.0` / `Apache License 2.0` | Apache-2.0 | 2.0 | standard_spdx | permissive | 2 |
| `mit` | MIT | — | standard_spdx | permissive | 1 |
| `GPL-3.0` | GPL-3.0 | 3.0 | standard_spdx | strong_copyleft | 4 |
| `CC-BY-NC-ND` | CC-BY-NC-ND | —（平台未给） | **recognized_family_unresolved** | non_commercial | 4 |
| `gemma` | Gemma-Terms-of-Use | — | recognized_non_spdx | ai_restricted | 4 |
| `llama3.1` | Llama-3.1-Community-License | — | recognized_non_spdx | ai_restricted | 4 |
| `other` + `qwen-research` | Qwen-Research-License | — | recognized_non_spdx | ai_restricted | 4 |
| `other`（无 name） | — | — | unresolved | unknown | — |
| 字段为空 | — | — | missing | unknown | — |

三条硬口径：

1. **`other` ≠ missing**。`other` 表示"平台把许可放在别的字段或没结构化"，语义上是 `unresolved`；只有字段**确实为空**才是 `missing`。管道层可以照现状输出 `missing`，但语义层必须分开记。
2. **`CC-BY-NC-ND` ≠ nonstandard**。它是已识别的许可族，缺的只是版本号，记 `recognized_family_unresolved`，决策为 `RISK_POTENTIAL`。
3. **Gemma 与 Llama 3.1 同口径**。两者都是"已识别的受限 AI 条款"，`recognized_non_spdx / ai_restricted / risk 4`，都不能表述成 SPDX 标准许可证。不允许因为规则库收了 Gemma 就把它算 standard、没收 Llama 就算 nonstandard。

`expected_decision` 由语义层唯一推出：

```
missing / unresolved → UNDETERMINED
recognized_family_unresolved / nonstandard → RISK_POTENTIAL
risk_level <= 2 → SAFE
其余 → RISK_CONFIRMED
```

## 5. 版本（revision）口径

`requested_revision` **只能来自项目调用本身**，配 `revision_source`：

| `revision_source` | 含义 | 要求 |
|---|---|---|
| `call_literal` | 调用参数里写死的版本（`revision='v1.0.2'`、`model_revision='v1.1.3'`） | 该字面值必须能在证据包里找到 |
| `call_variable_resolved_none` | 传的是变量，回溯到函数默认值 `None`（不锁版本） | 要记录变量绑定行与函数签名行 |
| `call_variable_resolved_value` | 传的是变量，回溯到具体字面值 | 同上 |
| `call_variable_unresolved` | 传的是变量，回溯不到值 | `needs_human_review=true` |
| `unspecified` | 调用没有版本参数 | 留空 |

**禁止**把平台接口返回的 `Data.Revision`（ModelScope 全是 `master`）填进 `requested_revision`。它是 `api_revision`，含义是"平台默认分支"，不是项目请求的版本。

反例（v0.2 的错误）：pc-0004 / 0008 / 0009 / 0010 / 0011 / 0012 / 0013 都写了 `master`，实际源码分别写了 `v1.0.0` / `v1.0.0` / `v1.0.2` / `v1.1.3` / `v1.1.3` / `v1.0.3` / `v2.0.4`。只有 pc-0017 的源码真的写了 `revision="master"`。

## 6. 使用方式（use_type）

只按**这一处调用**能证明的行为标，不外推：

| 值 | 判定 | 本批 |
|---|---|---|
| `local_inference` | 调用段直接加载/推理（`pipeline(...)`、`from_pretrained(...)`，或下载后同仓库有加载逻辑） | 15 |
| `evaluation_only` | 只在评测脚本里加载模型跑指标 | 2 |
| `fine_tuning` | 有训练调用证据（`Trainer`、`train()`、微调脚本） | 0 |
| `weight_distribution` | **对外分发/上传/转售/提供权重** | 0 |
| `unknown` | 只有下载，加载路径不明确 | 3 |

两条禁令：

- `snapshot_download` 不是 `weight_distribution`。它只是"获取模型"。
- pc-0013 是标点模型的本地推理（`pipeline(task=Tasks.punctuation, ...)`），不是 fine_tuning；pc-0008 只有 `download_model.py` 的下载证据，不能据此判微调。

`use_type_basis` 必须写清依据（例如"调用段为 pipeline 推理"），与 `use_type` 一起人工复核。

## 7. 正 / 负 / 排除的分流

| 文件 | 进不进指标分母 | 条件 |
|---|---|---|
| `candidates.csv` | 进（正样本） | platform 为三种 `modelscope_*` 之一，证据五段齐全 |
| `negative_cases.csv` | 进（负样本） | 能指出**具体一行**，且这一行确实不用 ModelScope |
| `excluded_candidates.csv` | **不进** | 定位不到调用行，或平台归属无法判定 |

**`ambiguous` 不得当负样本，也不得进分母。** 把"证据不足"混进负样本会人为抬高准确率。

负样本字段：

- `negative_basis`：`other_platform_explicit`（明确用别的平台）/ `modelscope_call_commented_out`（ModelScope 调用被注释）；
- `negative_scope`：`repo_platform`（整仓库用别的平台）/ `call_site`（同仓库有 ModelScope，但这个模型的调用点已死）；
- `negative_confidence`：`high` / `medium`；
- `line_no`：**必须 ≥ 1**，且该行必须有模型 ID 或调用表达式；不允许写 0。

负样本与正样本的调用区间不得重叠（同一文件同一行区间不能既算正又算负）。

## 8. 排除记录

`excluded_candidates.csv` 的 `exclusion_reason` 六类：`ambiguous` / `mapping_only` / `local_path_only` / `namespace_only` / `commented_out` / `non_modelscope_remote_api`。

`location_status`：`located`（能给出文件与行）/ `unlocated`（缓存里定位不到）。`unlocated` 的行号留空，**不写 0**，避免和"第 0 行"混淆。

排除记录的作用是审计留痕：说明"这条候选我们看过、为什么不用"，同时它们本身是天然的难负样本池，扩池时可重新审。

## 9. 快照与哈希

- 每个被标模型都保存一份 ModelScope 接口原始响应（`snapshots/<owner>__<name>.json`，`sort_keys`、缩进固定），索引在 `snapshots/index.json`，含 `snapshot_sha256`。
- **完整响应哈希会随 Downloads/Stars 变化，不能单独作为可复核证据**，所以快照必须落盘，哈希只用于校验"落盘文件没被改过"。
- 可复核的字段是：`license_raw`、`license_name_raw`、`api_revision`，校验器逐条与快照原文比对。
- 同一模型出现在多条记录里时，必须共享同一份快照事实（同 `snapshot_sha256`、同许可原值、同语义状态）。

## 10. 分组

同一项目、同一 fork、同一模型家族必须同组；t0/t1 必须同组。`project_group` 与 `family_group` 分列，`family_group` 用于防止同一模型家族跨 dev/validation/sealed 泄漏。

本批：dev 10 / validation 5 / sealed_test 5。sealed_test 在标注阶段不看，只在最终评测时打开。

## 11. 机器可查的一致性规则

`validate_benchmark.py` 强制以下规则，任何一条不满足即失败：

1. 列与枚举完整；
2. 证据包五段齐全且哈希可复算；
3. `requested_revision` 与证据一致（`call_literal` 能在证据里找到该值；除 pc-0017 外禁 `master`）；
4. 快照落盘、`snapshot_sha256` 与文件一致、许可原值与快照原文一致；
5. 同一模型的多条记录共享同一份快照事实；
6. gold 由内置 `LICENSE_GOLD` 表推出（不看规则库），`expected_decision` 唯一推出，风险等级与许可类型匹配；
7. 正样本必须是 `modelscope_*`，负/排除不能是，三个集合互斥；
8. 负样本行号 ≥ 1，正负调用点区间不重叠；
9. 同一模型家族不跨组；
10. Gemma 与 Llama 3.1 语义口径一致（管道层允许不同）。

## 12. 版本变更

| 版本 | 变更 | 原因 |
|---|---|---|
| v0.1 | 单一 `license_status`；`platform_evidence` 只有 import/无 import 两档 | 初版 |
| v0.2 | 拆 raw / pipeline / semantic 三层；`platform_evidence` 扩到 11 值；`weight_distribution` 收紧；Gemma 不称 SPDX | A 第一轮 review：`other` 不能当 missing、`snapshot_download` 不是分发、Gemma 是受限条款 |
| v0.3 | 新增调用级证据包五段；新增 `recognized_family_unresolved`；新增 `revision_source`；正/负/排除三分流；`platform_role=conditional_fallback`；gold 与规则库解耦；负样本行号 ≥1 与调用点分离 | A 第二轮 review：revision 必须来自调用、CC-BY-NC-ND 不是 nonstandard、gold 不能由规则库定义、ambiguous 不能进分母、证据要覆盖 import+绑定+调用+分支 |

## 13. 边界样例

| 情形 | 判定 |
|---|---|
| 文件顶部 `import modelscope`，模型用 `transformers` 加载 | 不是正样本（`huggingface_import`） |
| `snapshot_download(model_id)` 后没有加载代码 | 正样本，`use_type=unknown` |
| 模型名只出现在下载源映射表 `DownloadSource.MODELSCOPE` | 排除（`mapping_only`） |
| 路径字符串里含 `AI-ModelScope`，实际读本地目录 | 排除（`local_path_only`） |
| 调用被 `#` 注释，文件里也没有别的 ModelScope 调用 | 负样本（`commented_out`，`call_site`） |
| 调用被注释，但同文件另有 live 的 ModelScope 调用 | 排除（`ambiguous`） |
| `pipeline(model='damo/...')` 但文件无 modelscope import | 排除（`ambiguous`） |
| 平台 `License=other`、`LicenseName=""` | `unresolved`，`needs_human_review=true` |
| 平台 `License=other`、`LicenseName=qwen-research` | `recognized_non_spdx / ai_restricted / 4` |
| 平台 `License=CC-BY-NC-ND` 无版本 | `recognized_family_unresolved / non_commercial / 4` |
