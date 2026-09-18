# Hugging Face 真实模型 BOM 验证报告

- 验证日期：2026-09-18
- cdxgen：12.8.4，Node.js 24.21.0
- Python：3.13.9
- 输入方式：`pkg:huggingface/<namespace>/<model>`
- BOM 目录：`outputs/hf_models_bom/`
- 约束：未修改既有 MSU 和 Wild SBOMs 的验证结果。

## 1. 结论摘要

本次实际生成 9 个真实 Hugging Face 模型 BOM。其中 8 个模型至少包含 `pedigree.ancestors` 或 `modelCard.modelParameters.datasets` 之一；`meta-llama/Llama-2-7b-chat-hf` 作为优先候选的负对照，没有返回这两类字段，随后用量化模型 `TheBloke/Llama-2-7B-Chat-GGUF` 作为替代，并成功建立了到 `meta-llama/Llama-2-7b-chat-hf` 的祖先关系。

模块 1 可以稳定解析全部 BOM。模块 2 对每个 BOM 都未发现同名且不同 purl 的模型组件，因此窄例外没有触发。直接 Hugging Face 模型扫描只为模型本体生成一个 `pkg:huggingface/...` 组件，没有同时生成同名 PyPI 或 npm 包装组件；模型证据也只有 identity，不包含共同有效文件路径。因此本批数据能够验证血缘字段可用性和模块 2 的保守行为，但不能证明跨生态窄例外的正例路径。

官方 `https://huggingface.co/api/...` 在当前环境连接超时。执行时仅将 cdxgen 的元数据 API 请求重写到 `https://hf-mirror.com/api/...`，BOM 中的官方 Hugging Face URL 和 `pkg:huggingface/...` purl 保持不变。该镜像仅为运行环境替代路径，报告中的具体模型、版本、祖先和数据集均来自真实 API 响应，没有手工伪造。

## 2. 实际成功生成 BOM 的模型

| Hugging Face 模型 | BOM 文件 | 固定版本 | 血缘概况 |
|---|---|---|---|
| `google-bert/bert-base-uncased` | `bert-base-uncased_bom.json` | `86b5e0934494bd15c9632b12f734a8a67f723594` | 无祖先，modelCard 有数据集 |
| `sentence-transformers/all-MiniLM-L6-v2` | `all-MiniLM-L6-v2_bom.json` | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | 有祖先，有数据集 |
| `cross-encoder/stsb-roberta-base` | `stsb-roberta-base_bom.json` | `d576534b67143e2c70ee9966d7fdbf5835728d13` | 有祖先，有数据集 |
| `cross-encoder/nli-deberta-v3-base` | `nli-deberta-v3-base_bom.json` | `6c749ce3425cd33b46d187e45b92bbf96ee12ec7` | 有祖先，有数据集 |
| `HuggingFaceTB/SmolLM2-135M-Instruct` | `SmolLM2-135M-Instruct_bom.json` | `12fd25f77366fa6b3b4b768ec3050bf629380bac` | 有祖先，无数据集字段 |
| `Qwen/Qwen2.5-0.5B-Instruct` | `Qwen2.5-0.5B-Instruct_bom.json` | `7ae557604adf67be50417f59c2c2f167def9a775` | 有祖先，无数据集字段 |
| `bartowski/Qwen2.5-0.5B-Instruct-GGUF` | `Qwen2.5-0.5B-Instruct-GGUF_bom.json` | `41ba88dbac95fed2528c92514c131d73eb5a174b` | 两级祖先，量化模型 |
| `meta-llama/Llama-2-7b-chat-hf` | `Llama-2-7b-chat-hf_bom.json` | `f5db02db724555f92da89c216ac04704f23d4590` | 负对照，祖先和数据集字段均为空 |
| `TheBloke/Llama-2-7B-Chat-GGUF` | `Llama-2-7B-Chat-GGUF_bom.json` | `191239b3e26b2882fb562ffccdd1cf0f65402adb` | 祖先指向 `meta-llama/Llama-2-7b-chat-hf` |

扫描过程全部返回退出码 0，单模型 cdxgen 耗时约为 3.65 秒到 5.06 秒。

## 3. 模块 1 解析结果

模块 1 通过 `outputs/bom_adapter.py` 逐文件运行。耗时包含 Python 进程启动和文件写入。

| 模型 | 解析组件数 | `asset_type=model` | 有 `pedigree.ancestors` | 有 modelCard 数据集 | 耗时 |
|---|---:|---:|---:|---:|---:|
| `google-bert/bert-base-uncased` | 3 | 1 | 0 | 1 | 0.0945 秒 |
| `sentence-transformers/all-MiniLM-L6-v2` | 22 | 1 | 1 | 1 | 0.0979 秒 |
| `cross-encoder/stsb-roberta-base` | 2 | 1 | 1 | 1 | 0.0939 秒 |
| `cross-encoder/nli-deberta-v3-base` | 3 | 1 | 1 | 1 | 0.0940 秒 |
| `HuggingFaceTB/SmolLM2-135M-Instruct` | 1 | 1 | 1 | 0 | 0.0954 秒 |
| `Qwen/Qwen2.5-0.5B-Instruct` | 1 | 1 | 1 | 0 | 0.0948 秒 |
| `bartowski/Qwen2.5-0.5B-Instruct-GGUF` | 1 | 1 | 1 | 0 | 0.0956 秒 |
| `meta-llama/Llama-2-7b-chat-hf` | 1 | 1 | 0 | 0 | 0.0934 秒 |
| `TheBloke/Llama-2-7B-Chat-GGUF` | 1 | 1 | 1 | 0 | 0.0922 秒 |

说明：`bom_adapter.py` 的资产记录目前只保存名称、版本、purl、许可证和位置证据，不保存 `pedigree` 与 `modelCard` 原文。本报告的字段统计和完整内容直接从 cdxgen 原始 BOM 提取。

## 4. 模块 2 合并结果

| 模型 | 同名配对 | 同名不同 purl 模型 | 窄例外 | 合并对数 | 置信度分布 | 耗时 |
|---|---:|---:|---|---:|---|---:|
| `google-bert/bert-base-uncased` | 0 | 无 | 未触发 | 0 | 空 | 0.1041 秒 |
| `sentence-transformers/all-MiniLM-L6-v2` | 0 | 无 | 未触发 | 0 | 空 | 0.1061 秒 |
| `cross-encoder/stsb-roberta-base` | 0 | 无 | 未触发 | 0 | 空 | 0.1023 秒 |
| `cross-encoder/nli-deberta-v3-base` | 0 | 无 | 未触发 | 0 | 空 | 0.1069 秒 |
| `HuggingFaceTB/SmolLM2-135M-Instruct` | 0 | 无 | 未触发 | 0 | 空 | 0.1050 秒 |
| `Qwen/Qwen2.5-0.5B-Instruct` | 0 | 无 | 未触发 | 0 | 空 | 0.1036 秒 |
| `bartowski/Qwen2.5-0.5B-Instruct-GGUF` | 0 | 无 | 未触发 | 0 | 空 | 0.1057 秒 |
| `meta-llama/Llama-2-7b-chat-hf` | 0 | 无 | 未触发 | 0 | 空 | 0.1040 秒 |
| `TheBloke/Llama-2-7B-Chat-GGUF` | 0 | 无 | 未触发 | 0 | 空 | 0.1025 秒 |

所有 BOM 都没有形成同名模型候选对，因此也没有 `merged`、`needs_review` 或 skip reason 记录。模块 2 单模型耗时约为 0.102 秒到 0.107 秒。

未触发窄例外的直接原因如下：

1. 每个直接 Hugging Face 模型 BOM 只有一个模型组件，模型 purl 类型均为 `huggingface`。
2. cdxgen 没有从模型卡中的 `library_name=transformers` 或 `library_name=sentence-transformers` 自动生成同名 PyPI 组件。
3. 没有 npm、PyPI、Hugging Face 三者之间的同名异构 purl 组合。
4. 即使后续将两个来源合并，本批模型的 `evidence.identity` 也不包含 occurrence、location、path 或 filepath，不满足“共同有效文件路径”条件。

因此，本批结果验证了模块 2 在缺少跨生态证据时保持保守，不会错误触发合并；它没有覆盖窄例外的正例。要验证正例，需要真实多来源 SBOM，其中同一模型同时存在 `pkg:huggingface/...` 与同名 `pkg:pypi/...` 或 `pkg:npm/...`，版本一致，并且至少有一个共同通过有效性检查的物理文件路径。

## 5. 血缘数据完整性

### 5.1 `pedigree.ancestors` 实际内容

| 当前模型 | 祖先链 |
|---|---|
| `google-bert/bert-base-uncased` | 空 |
| `sentence-transformers/all-MiniLM-L6-v2` | `nreimers/MiniLM-L6-H384-uncased` |
| `cross-encoder/stsb-roberta-base` | `FacebookAI/roberta-base` |
| `cross-encoder/nli-deberta-v3-base` | `microsoft/deberta-v3-base` |
| `HuggingFaceTB/SmolLM2-135M-Instruct` | `HuggingFaceTB/SmolLM2-135M` |
| `Qwen/Qwen2.5-0.5B-Instruct` | `Qwen/Qwen2.5-0.5B` |
| `bartowski/Qwen2.5-0.5B-Instruct-GGUF` | `Qwen/Qwen2.5-0.5B-Instruct` -> `Qwen/Qwen2.5-0.5B` |
| `meta-llama/Llama-2-7b-chat-hf` | 空 |
| `TheBloke/Llama-2-7B-Chat-GGUF` | `meta-llama/Llama-2-7b-chat-hf` |

祖先组件带有可直接使用的 Hugging Face purl。`Qwen2.5-0.5B-Instruct-GGUF` 还生成了嵌套的二级祖先链。因此这些字段可以直接输入模块 8 构建模型血缘树。

### 5.2 `modelCard.modelParameters.datasets` 实际内容

| 当前模型 | modelCard 中的数据集引用 |
|---|---|
| `google-bert/bert-base-uncased` | `pkg:huggingface/datasets/wikipedia?repository_url=...` |
| `sentence-transformers/all-MiniLM-L6-v2` | `pkg:huggingface/embedding-data/WikiAnswers?repository_url=...` |
| `cross-encoder/stsb-roberta-base` | `pkg:huggingface/sentence-transformers/stsb?repository_url=...` |
| `cross-encoder/nli-deberta-v3-base` | `pkg:huggingface/stanfordnlp/snli?repository_url=...` |
| 其余模型 | 空 |

原始 Hugging Face 模型卡中的数据集数量多于上述 modelCard 结果。例如：

- `google-bert/bert-base-uncased` 原始字段包含 `bookcorpus` 和 `wikipedia`，BOM 的 modelCard 只保留了 `wikipedia`。
- `cross-encoder/nli-deberta-v3-base` 原始字段包含 `nyu-mll/multi_nli` 和 `stanfordnlp/snli`，BOM 的 modelCard 只保留了 `stanfordnlp/snli`。
- `sentence-transformers/all-MiniLM-L6-v2` 原始字段包含 21 个数据集，BOM 的 modelCard 只保留了 `embedding-data/WikiAnswers`。

数据集信息并未全部丢失。cdxgen 同时写入了模型到数据集的 `dependencies.dependsOn`：

- `bert-base-uncased`：`datasets/bookcorpus`、`datasets/wikipedia`
- `stsb-roberta-base`：`sentence-transformers/stsb`
- `nli-deberta-v3-base`：`nyu-mll/multi_nli`、`stanfordnlp/snli`
- `all-MiniLM-L6-v2`：`s2orc`、`flax-sentence-embeddings/stackexchange_xml`、`ms_marco`、`gooaq`、`yahoo_answers_topics`、`code_search_net`、`search_qa`、`eli5`、`snli`、`multi_nli`、`wikihow`、`natural_questions`、`trivia_qa`、`embedding-data/sentence-compression`、`embedding-data/flickr30k-captions`、`embedding-data/altlex`、`embedding-data/simple-wiki`、`embedding-data/QQP`、`embedding-data/SPECTER`、`embedding-data/PAQ_pairs`、`embedding-data/WikiAnswers`

### 5.3 模块 8 可用性判断

- `pedigree.ancestors`：可直接用于模块 8。组件包含名称、group 和 purl，且支持嵌套祖先。
- `modelCard.modelParameters.datasets`：只能直接使用其中已规范化的数据集引用。单段标识符如 `bookcorpus`、`multi_nli` 没有被完整写入 modelCard。
- `dependencies.dependsOn`：应作为模块 8 的主要数据集边来源，因为它保留了本批模型卡中的完整数据集列表。
- 数据集组件的 `bom-ref` 可以回退为 purl，但 `externalReferences` 对单段数据集可能出现 `datasets/datasets/<name>` 的重复前缀，模块 8 建图时应优先使用依赖 ref，不要仅依赖该外链 URL。
- `meta-llama/Llama-2-7b-chat-hf` 本身没有可用于建图的祖先或数据集字段；其量化替代模型 `TheBloke/Llama-2-7B-Chat-GGUF` 补足了向上的一级血缘。

## 6. 网络、Token 和错误记录

### 6.1 官方 Hugging Face 访问

官方 API 直连失败，具体表现包括：

- `curl https://huggingface.co/api/...`：`Connection timed out after 20001 milliseconds`
- cdxgen debug 日志：`Connect Timeout Error (attempted address: huggingface.co:443, timeout: 10000ms)`
- 未修改 cdxgen 时，`pkg:huggingface/google-bert/bert-base-uncased` 生成了 0 组件的空 BOM。

### 6.2 替代路径

通过 Node 加载器仅重写 cdxgen 内部元数据请求地址：

```text
https://huggingface.co/api/...
-> https://hf-mirror.com/api/...
```

重写范围不含 BOM 组件 URL、官方 purl 或本地文件内容。使用替代路径后，9 个模型全部生成成功，直接仓库名 `google-bert/bert-base-uncased` 也恢复为 3 组件 BOM，其中包含 1 个模型和 1 个 modelCard 数据集引用。

### 6.3 Token

未发现已配置的 `HF_TOKEN`、`HUGGING_FACE_HUB_TOKEN` 或 `HUGGINGFACE_TOKEN`。本任务只读取公开模型元数据，没有下载权重或受控文件。`meta-llama/Llama-2-7b-chat-hf` 的公开元数据可读取，但其卡片本身没有返回 `base_model` 和 `datasets`，因此未因 token 而跳过 BOM 生成。

### 6.4 cdxgen 非阻塞错误

`--evidence` 的 evinse/atom 后处理在当前 Windows 环境报告过 `Unable to generate reachables slice`、`Unable to generate usages slice` 和 `Unable to identify component evidence`。这些错误没有阻止远程 Hugging Face 组件、purl、pedigree 和 modelCard 的生成；所有目标 BOM 均完整写出。

所有 9 个 BOM 又通过本地 `cdx-validate` 校验，`schemaValid=true` 且 `deepValid=true`。校验器仍返回退出码 3，但该退出码来自 SCVS 等合规评分中的未签名、无应用/库组件等 findings，不是 JSON 结构错误。

## 7. 替代方案与后续建议

1. 模块 2 正例验证应使用真实多来源资产集合，而不是从单个 Hugging Face 模型 BOM 推断。最低条件是同名、版本一致的模型组件同时带有 Hugging Face purl 和 npm/PyPI purl，并共享一个真实有效路径。
2. 如果只需要模型到训练数据集的关系，应优先读取 `dependencies.dependsOn`，再用 `modelCard.modelParameters.datasets` 补充带规范的引用。
3. 如果需要严格还原 Hugging Face 模型卡全部数据集，可读取模型仓库的 `README.md` frontmatter 并通过本地 AI 扫描生成 BOM，避免远程 API 对单段数据集标识符的规范化缺口。
4. 正式报告应把本批结果定位为“真实血缘输入数据验证”和“模块 2 无证据不合并的保守性验证”，不要表述为“跨生态窄例外正例已验证”。

## 8. 可直接用于技术报告的中文段落

本工作从 Hugging Face 选取 9 个真实模型并使用 cdxgen 12.8.4 生成 AI BOM，其中包括基座模型、句子嵌入模型、跨编码器、指令微调模型以及 GGUF 量化模型。由于当前网络无法直连 Hugging Face 官方 API，验证仅将元数据查询切换至兼容镜像，BOM 中的官方模型标识、SHA 版本和 purl 保持不变。结果显示，8 个模型至少提取到 `pedigree.ancestors` 或 `modelCard.modelParameters.datasets` 之一，`Qwen2.5-0.5B-Instruct-GGUF` 形成了两级祖先链，`TheBloke/Llama-2-7B-Chat-GGUF` 形成了到 `meta-llama/Llama-2-7b-chat-hf` 的量化派生关系。模块 1 成功解析全部 BOM；模块 2 未发现同名且同时具有 Hugging Face 与 npm/PyPI purl 的模型组件，因此窄例外没有触发，也未发生自动合并。其原因是直接模型扫描只生成单一 Hugging Face purl，且远程证据没有共同有效文件路径。因此，本批数据可直接作为模块 8 至 10 的模型祖先和数据集关系输入；对于模块 2，本批结果验证了证据不足时保持保守，跨生态窄例外的正例仍需由真实多来源 SBOM 进一步覆盖。

## 9. 交付物

- 9 个模型 BOM：`outputs/hf_models_bom/`
- 中文验证报告：`outputs/hf_models_validation_report.md`
- 结构化验证数据：`work/hf_models_validation_data.json`
- 逐模型模块 1、2 中间结果：`work/hf_models_module_validation/`
- CycloneDX 结构校验日志：`work/hf_validate_logs/`
- cdxgen 扫描日志：`work/hf_scan_logs/`
