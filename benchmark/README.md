# Gate 1 基准数据（B 组：候选池 / 标注 / 指标）

本目录是 Gate 1（11/16 口径冻结）要交的东西：**20 个正样本、5 个负样本、20 条排除记录、13 个模型案例**，以及每条的**调用级证据包**和**平台原始 JSON 快照**。

需要说清楚两件事：

1. 这批数据的用途是"口径 + 可复现证据"，**不是**准确率结论。样本量 20，且均为人工挑选的可用案例，任何准确率数字都不具备统计意义。
2. 正样本的判定单位已经从"文件"下沉到"调用段"。文件里出现模型 ID、或文件顶部有 `import modelscope`，都不足以证明这个模型是通过 ModelScope 加载的。

## 1. 交付物

| 文件 | 内容 | 规模 |
|---|---|---|
| `candidates.csv` | 正样本：源码中确有用 ModelScope 取用模型的调用段 | 20 行 × 50 列 |
| `negative_cases.csv` | 负样本：**可进指标分母**的"看起来像但其实不是"的调用点 | 5 行 × 21 列 |
| `excluded_candidates.csv` | 审计记录：证据不足、无法判定平台归属的候选，**不进分母** | 20 行 × 14 列 |
| `model_cases.json` | 模型案例：平台许可证事实 + 两层判定 | 13 条 |
| `evidence/*.json` | 每个正/负样本一条证据包（import / 绑定 / 调用 / 分支 / 版本） | 25 个 |
| `snapshots/*.json` + `snapshots/index.json` | ModelScope 模型接口原始响应与哈希索引 | 27 个 |
| `annotation_spec.md` | 标注规范 v0.3 | — |
| `validate_benchmark.py` | 结构、枚举、哈希与一致性自检（CI 可跑） | — |

## 2. 判定方法：调用段级证据

对候选仓库的指定文件，按下面的顺序抽证据（`bench_evidence.py`，工作区脚本，不随仓库发布）：

1. **定位模型 ID 的字面行**；
2. 找到包含 `snapshot_download|pipeline|from_pretrained|AutoModel*` 的那一行，**按括号配平**向后取完整调用段（最多 15 行），得到 `(start, end)`；
3. 记录**变量绑定**：`NAME = "<model_id>"` 或 `def f(self, NAME="<model_id>")`；
4. 记录**平台 import 的行号**（必须早于调用行）；
5. 记录**条件分支**：该调用是否处在 `try/except`、`if not is_connect_hf()` 之类的分支里。

`platform_evidence` 的判定优先级：

| 证据 | 含义 |
|---|---|
| `modelscope_download` | `snapshot_download(...)` 且本文件有 modelscope import |
| `modelscope_api` | `pipeline(..., model='<damo/iic 模型>')` 且本文件有 modelscope import |
| `modelscope_source_selected` | `AutoModel*/AutoTokenizer.from_pretrained` 的类来自 `from modelscope import ...` |
| `huggingface_import` | 调用方是 `huggingface_hub` / `transformers` / `diffusers` |
| `commented_out` | 唯一相关调用被注释 |
| `local_path_only` / `mapping_only` / `namespace_only` / `ambiguous` | 不构成使用证据 |

只有前三种能进正样本。`platform_role` 只有两个值：`primary`（直接使用）和 `conditional_fallback`（有条件的回退路径，本批仅 pc-0001）。

### pc-0001 为什么是 conditional_fallback

`jianchang512/ChatTTS-ui` 的 `app.py:52-65`：

```python
try:
    # 优先使用本地模型，不存在再联网检测下载
    huggingface_hub.snapshot_download(repo_id="2Noise/ChatTTS", local_dir=CHATTTS_DIR,
                                      etag_timeout=5, local_files_only=True)
except LocalEntryNotFoundError:
    if not is_connect_hf():
        print("当前从阿里魔塔下载模型...")
        os.environ['HF_ENDPOINT'] = "https://hf-mirror.com"
        from modelscope import snapshot_download
        snapshot_download(model_id='pzc163/chatTTS', local_dir=CHATTTS_DIR)
```

真实逻辑是 **HF 缓存优先 → 本地缓存缺失（`LocalEntryNotFoundError`）且 HF 不可达（`is_connect_hf()` 为假）才回退 ModelScope**，不是"国内走魔搭、海外走 HF"。所以它保留为正样本，但标 `conditional_fallback`，证据包里带完整的 `try/except` 段落。

## 3. 正样本（20 条）

| case | repo | model | platform | role | revision | license | state | decision | group |
|---|---|---|---|---|---|---|---|---|---|
| pc-0001 | jianchang512/ChatTTS-ui | pzc163/chatTTS | MS download | conditional_fallback | — | Apache-2.0 | standard_spdx | SAFE | dev |
| pc-0002 | LYiHub/mad-professor-public | opendatalab/PDF-Extract-Kit-1.0 | MS download | primary | — | — | missing | UNDETERMINED | dev |
| pc-0003 | Henry-23/VideoChat | ZhipuAI/glm-4-voice-tokenizer | MS download | primary | — | — | missing | UNDETERMINED | dev |
| pc-0004 | duma-repo/ai_code_reader | ZhipuAI/chatglm3-6b | MS download | primary | v1.0.0 | — | missing | UNDETERMINED | dev |
| pc-0005 | X-D-Lab/MindChat | X-D-Lab/MindChat-Qwen2-4B | MS download | primary | — | GPL-3.0 | standard_spdx | RISK_CONFIRMED | validation |
| pc-0006 | opendatalab/OmniDocBench | topdktu/unirec-0.1b | MS download | primary | — | Apache-2.0 | standard_spdx | SAFE | dev |
| pc-0007 | Kedreamix/Linly-Dubbing | AI-ModelScope/XTTS-v2 | MS download | primary | — | — | unresolved | UNDETERMINED | validation |
| pc-0008 | xxw1995/chatglm3-finetune | ZhipuAI/chatglm3-6b | MS download | primary | v1.0.0 | — | missing | UNDETERMINED | dev |
| pc-0009 | ZJU-OmniAI/Data-Copilot | Shanghai_AI_Laboratory/internlm-chat-7b | MS download | primary | v1.0.2 | — | missing | UNDETERMINED | validation |
| pc-0010 | ali-vilab/VGen | damo/i2vgen-xl | MS api | primary | v1.1.3 | CC-BY-NC-ND | recognized_family_unresolved | RISK_POTENTIAL | validation |
| pc-0011 | tyxsspa/AnyText | damo/cv_anytext_text_generation_editing | MS api | primary | v1.1.3 | Apache-2.0 | standard_spdx | SAFE | validation |
| pc-0012 | aigc-apps/sd-webui-EasyPhoto | bubbliiiing/cv_retinafce_recognition | MS api | primary | v1.0.3 | Apache-2.0 | standard_spdx | SAFE | sealed_test |
| pc-0013 | yeyupiaoling/Whisper-Finetune | iic/punc_ct-transformer_cn-en-common-vocab471067-large | MS api | primary | v2.0.4 | Apache-2.0 | standard_spdx | SAFE | sealed_test |
| pc-0014 | TencentQQGYLab/ELLA | damo/mplug_visual-question-answering_coco_large_en | MS api | primary | — | Apache-2.0 | standard_spdx | SAFE | sealed_test |
| pc-0015 | XGenerationLab/xiyan_mcp_server | XGenerationLab/XiYanSQL-QwenCoder-3B-2502 | MS source_selected | primary | — | Apache-2.0 | standard_spdx | SAFE | sealed_test |
| pc-0016 | datawhalechina/easy-vecdb | AI-ModelScope/bge-large-zh-v1.5 | MS source_selected | primary | — | MIT | standard_spdx | SAFE | dev |
| pc-0017 | gzhuuser/fortune_teller | AI-ModelScope/bge-large-zh-v1.5 | MS download | primary | master | MIT | standard_spdx | SAFE | dev |
| pc-0018 | shehuiwojiege/open-llms-next-web | AI-ModelScope/bge-large-zh-v1.5 | MS download | primary | — | MIT | standard_spdx | SAFE | dev |
| pc-0019 | huashoupopi/rework | AI-ModelScope/bge-large-zh-v1.5 | MS download | primary | — | MIT | standard_spdx | SAFE | dev |
| pc-0020 | Jiturine/web_crawler | iic/nlp_structbert_sentiment-classification_chinese-base | MS api | primary | — | Apache-2.0 | standard_spdx | SAFE | sealed_test |

分布：

- 平台证据：`modelscope_download` 12 / `modelscope_api` 6 / `modelscope_source_selected` 2
- 使用方式：`local_inference` 15 / `unknown` 3 / `evaluation_only` 2
- 版本：`call_literal` 8 / `unspecified` 11 / `call_variable_resolved_none` 1
- 许可证（gold）：`standard_spdx` 13 / `missing` 5 / `unresolved` 1 / `recognized_family_unresolved` 1
- 决策：`SAFE` 12 / `UNDETERMINED` 6 / `RISK_CONFIRMED` 1 / `RISK_POTENTIAL` 1
- 分组：dev 10 / validation 5 / sealed_test 5

## 4. 负样本（5 条，可进指标分母）

| case | repo | model | 位置 | basis | scope |
|---|---|---|---|---|---|
| neg-0001 | liuliu/swift-diffusion | Qwen/Qwen-Image-2.1 | `examples/qwen_image21/setup.py:31` | other_platform_explicit | repo_platform |
| neg-0002 | john-rocky/coreai-model-zoo | Qwen/Qwen-Image-2.1 | `conversion/qwenimage21/perturb_ref.py:18` | other_platform_explicit | repo_platform |
| neg-0003 | muzishen/IMAGDressing | stabilityai/sd-vae-ft-mse | `app.py:52` | other_platform_explicit | repo_platform |
| neg-0004 | datawhalechina/tiny-universe | Qwen/Qwen2.5-Omni-3B | `content/download.py:7` | modelscope_call_commented_out | call_site |
| neg-0005 | langjinyi/Ada-AI-Assistant | AI-ModelScope/bge-large-zh-v1.5 | `models/downloader.py:22` | modelscope_call_commented_out | call_site |

只有这 5 条进指标分母，原因是它们都满足"**能指出一行代码，且这一行确实不用 ModelScope**"：

- neg-0001/0002 用 `huggingface_hub.snapshot_download` / 自封装的 `hf_snapshot()` 从 HF 取；
- neg-0003 用 diffusers 的 `AutoencoderKL.from_pretrained` 直接吃 HF 模型 ID；
- neg-0004 唯一的 ModelScope 引用被注释；
- neg-0005 同文件里 bge 的 `snapshot_download` 被注释，实际运行的是下一行下载 chatTTS 的调用。

`negative_scope` 区分两种负样本：`repo_platform`（整个仓库用别的平台）和 `call_site`（同一仓库里有 ModelScope，但**这个模型**的调用点已失效）。后者才是最容易骗过"文件级"判定的情况。

## 5. 排除记录（20 条，只用于审计，不进分母）

| reason | 数量 | 含义 |
|---|---|---|
| `ambiguous` | 5 | 模型 ID 出现，但无法判定由哪个平台发起加载 |
| `mapping_only` | 4 | 只出现在下载源/模型映射表里，不是调用 |
| `namespace_only` | 5 | 只有 ModelScope 命名空间下的模型名，未见调用 |
| `local_path_only` | 3 | 只有本地路径（路径名里恰好含 `AI-ModelScope`） |
| `commented_out` | 2 | 相关调用被注释，且同文件另有其它平台逻辑，归属无法排除 |
| `non_modelscope_remote_api` | 1 | 只在 config 里出现 SiliconFlow 模型名，未定位调用点 |

其中 `exc-0015`（`macaqueedmai-wq/Hear-You-Are---Software`）在缓存里定位不到具体文件行，`location_status=unlocated`，行号留空——**不留 0**，避免和"第 0 行"混淆。

## 6. 模型案例（13 条）

在 12 条基础上补了 **mc-0013 `Qwen/Qwen-Image-2.1`**：平台 `Data.License=other`、`Data.LicenseName=qwen-research`，用于覆盖"平台给了自定义许可名"的情况。

每条案例都有：`source_url`、`observed_at`、`api_revision`、`snapshot_path` + `snapshot_sha256`（原始 JSON 落盘）、`raw_license` / `raw_license_name`、`semantic_*`（gold）、`pipeline_*`（当前适配器会输出什么）。

## 7. 许可证判定：三层，互不覆盖

| 层 | 字段 | 谁决定 |
|---|---|---|
| 原始层 | `license_raw`、`license_name_raw` | ModelScope 接口原样返回 |
| 管道层 | `pipeline_known/spdx_like/category/canonical_license_id/risk_level/license_state/decision` | 当前 `licenses.json` + 适配器 |
| 语义层（gold） | `semantic_license_family/version/state/class/risk_level` | 人工按下面的表判定 |

**gold 只看平台原始字符串，不看规则库是否收录。** 判定表：

| 平台原值 | family | state | class | risk |
|---|---|---|---|---|
| `apache-2.0` / `Apache License 2.0` | Apache-2.0 | standard_spdx | permissive | 2 |
| `mit` | MIT | standard_spdx | permissive | 1 |
| `GPL-3.0` | GPL-3.0 | standard_spdx | strong_copyleft | 4 |
| `CC-BY-NC-ND`（无版本） | CC-BY-NC-ND | **recognized_family_unresolved** | non_commercial | 4 |
| `gemma` | Gemma-Terms-of-Use | recognized_non_spdx | ai_restricted | 4 |
| `llama3.1` | Llama-3.1-Community-License | recognized_non_spdx | ai_restricted | 4 |
| `other` + `qwen-research` | Qwen-Research-License | recognized_non_spdx | ai_restricted | 4 |
| `other`（无 name） | — | unresolved | unknown | — |
| 字段为空 | — | missing | unknown | — |

三条口径（对应 A 的意见）：

1. **`CC-BY-NC-ND` 不是"非标准许可"**：它是已识别的许可族，只是平台没给版本号，所以新增 `recognized_family_unresolved` 状态，决策为 `RISK_POTENTIAL`，并单独保留 `semantic_license_version=""`。
2. **`other` 不能直接当 missing**：`other` 是"平台把许可放在别的字段里"，`glm-4-9b-chat` / `XTTS-v2` / `internlm2_5-7b-chat` 记 `unresolved`（需人工看上游原文），`internlm-chat-7b` 才是 `missing`（平台字段确实为空）。管道层仍按现状输出 `missing`，两者分开记录。
3. **Gemma 与 Llama 3.1 同口径**：都是"已识别的受限 AI 条款"，`recognized_non_spdx / ai_restricted / risk 4`，都不当 SPDX 标准许可。

`expected_decision` 由语义层唯一推出：`missing/unresolved` → `UNDETERMINED`；`recognized_family_unresolved/nonstandard` → `RISK_POTENTIAL`；risk ≤ 2 → `SAFE`；其余 → `RISK_CONFIRMED`。

## 8. 版本（revision）口径

`requested_revision` **只来自项目调用本身**，并配 `revision_source`：

| revision_source | 含义 | 本批 |
|---|---|---|
| `call_literal` | 调用参数里直接写死的版本，如 `revision='v1.0.2'` | 8 |
| `call_variable_resolved_none` | 传的是变量，已回溯到函数默认值 `None`（即不锁版本） | 1（pc-0018） |
| `unspecified` | 调用没有版本参数，项目不锁版本 | 11 |

`api_revision` 是**平台接口返回的默认分支**（ModelScope 全部是 `master`），不代表项目请求的版本，两者不能混用。上一版把 `master` 填进 `requested_revision` 是错的，本批已全部改掉；唯一保留 `master` 的是 pc-0017，因为它的源码里确实写了 `revision="master"`。

pc-0018 的回溯：`shehuiwojiege/open-llms-next-web` 的 `utils.py:19` 是 `def auto_download(model_type: str, revision: str = None, ...)`，`utils.py:46` 调用 `snapshot_download(model_id, revision=revision, cache_dir=cache_dir)`，默认 `None` → 不锁版本。

## 9. 使用方式（use_type）

只按**这一处调用**能证明的行为来标，不外推：

- `download_only` + 本地加载证据不足 → `unknown`（pc-0003 / pc-0007 / pc-0008）
- `download_only` 但同仓库有加载逻辑 → `local_inference`
- `snapshot_download` 本身**不是** `weight_distribution`；`weight_distribution` 只指"对外分发/上传/转售权重"
- pc-0013 是标点模型的本地推理，**不是** fine_tuning；fine_tuning 必须要有训练调用证据（本批没有，故该类别为 0）

## 10. 分组

同一项目、同一 fork、同一模型家族必须同组；t0/t1 必须同组。

- dev 10：bge 家族 4 条 + ChatTTS / PDF-Extract-Kit / glm-voice / chatglm3 两条 / unirec
- validation 5：MindChat / XTTS-v2 / internlm / i2vgen-xl / anytext
- sealed_test 5：retinaface / punc-ct / mplug-vqa / XiYanSQL / structbert

## 11. 自检

```bash
python benchmark/validate_benchmark.py
# OK: 20 个正样本、5 个负样本、20 条排除记录、13 个模型案例，共 58 条记录全部通过
```

`validate_benchmark.py` 检查的项目：

1. 列与枚举完整（50 列全在）；
2. 证据包四段齐全：platform import、模型 ID 绑定（或字面行）、调用表达式、（条件回退时）try/except 分支，且各自哈希可复算；
3. `requested_revision` 与调用证据一致（`call_literal` 必须能在证据里找到该字面值；除 pc-0017 外不允许 `master`）；
4. 快照落盘且 `snapshot_sha256` 与文件一致，`license_raw` / `license_name_raw` 与快照原文一致；
5. 同一模型的多条记录共享同一份快照事实（`snapshot_sha256`、许可原值、语义状态）；
6. gold 由 `LICENSE_GOLD` 表推出（不看规则库收录），`expected_decision` 唯一推出，风险等级与许可类型匹配；
7. 正样本必须是 `modelscope_*` 三种证据之一，负样本不能是，排除记录与两者互斥；
8. 负样本行号 ≥ 1，正负样本调用点区间不重叠；
9. 同一模型家族不跨组；
10. Gemma 与 Llama 3.1 语义口径一致（管道层允许不同，见 §12）。

另外做过**变异测试**（`_mut_test.py`，10 个用例）：基线通过；分别改坏 platform_evidence、revision、快照哈希、负样本行号、Gemma 分类、同模型一致性、条件回退分支、正负调用点重叠、Qwen-Image-2.1 的 LicenseName，校验器全部报错并指出具体行。

## 12. 已知缺口（不藏着）

- **管道层还跟不上 gold**：Llama 3.1 的 `llama3.1` 在 `licenses.json` 里没有规则，管道输出 `nonstandard`，而 gold 是 `recognized_non_spdx / ai_restricted`；Gemma 在规则库里，管道输出 `standard / ai_restricted`。两边对"是不是 SPDX"的判断不一致，这是要报给 A 的 pipeline 缺口，不是 gold 的问题。
- **`CC-BY-NC-ND` 没有版本号**，只能记到许可族，不能记成 `CC-BY-NC-ND-4.0`。
- **`other` 的三个模型仍需人工看上游原文**（`needs_human_review=true`）。
- **负样本只有 5 条**：其余 20 条候选根本无法定位到具体调用行，硬凑会把"证据不足"混进"负样本"，所以进 `excluded_candidates.csv`。
- **排除记录里有 1 条未定位**（exc-0015），保留 `unlocated` 状态而不是编一个行号。
- **样本量**：20 正 / 5 负，不够做任何准确率结论；指标要等 B-03 扩池到 40 个项目后再算。

## 13. 下一步

按 A 的要求，**没有先扩到 40 条**。这份材料交上去确认口径后，再做 B-03（扩池）与 B-04（dev/validation/sealed 重新切分）。扩池时会复用 `bench_evidence.py` + `bench_build_v2.py` 的流水线，新增的候选必须先过"调用段级"判定才进正样本。
