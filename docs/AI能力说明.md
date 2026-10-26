# AI 能力说明

## 1. 定位

AI 是受原始文档约束的旁路语义证据层，不替代规则审计：

```text
ModelScope 官方事实与冻结文档
  -> source_bundle（A 级来源）
  -> AI analysis_bundle（C 级语义证据）
  -> 规则 decision_bundle（保持独立）
  -> Markdown / BOM / HTML / CI artifact
```

- AI 不得修改许可证名称、风险灯色、Delta、decision 或 CI。
- AI 默认关闭，只有显式传入 `--ai` 或设置 `AI_ENABLED=true` 才运行。
- AI 缺少服务地址、请求失败或返回不合格引文时，只写入 `status=unavailable` 或证据缺口，不阻断规则链。
- 当前数据口径只使用 ModelScope，不回退到其他模型社区。
- 服务地址没有固定默认值，必须由运行方显式配置。

## 2. 三种模式中的职责

| 模式 | 架构地位 | AI 输入 | AI 产出 |
|---|---|---|---|
| Project | 核心入口 | 项目源码、配置、说明文件，以及项目模型及其上游的官方文档 | 远程 API、本地推理、权重分发、微调、衍生发布等实际使用方式 |
| Diff | 核心入口 | t0/t1 BOM 中固化的许可证事实、血缘和 AI 画像 | 同名许可证下的语义收紧、放宽、条件变化、证据新增或丢失 |
| Model | 调查视图 | 单个 ModelScope 模型的 LICENSE、README、使用政策与结构化文本 | 条款状态、逐字原文、条件、例外、冲突、置信度和证据缺口 |

Model 模式不会成为项目风险闭包的一部分。项目模式默认只关注项目直接使用的模型及其完整上游闭包，不枚举平台上的全量下游模型。

## 3. AI 为什么不是通用接口套壳

通用聊天工具可以帮助用户查询许可证，但本项目的 AI 层承担的是审计流水线中的可复核证据职责：

1. AI 输入被限制为当前 ModelScope 快照中的冻结原文，不自由浏览互联网。
2. 每条 claim 必须引用 `source_path` 和逐字 `quote`；引文不能在原文中精确命中时会被丢弃。
3. 每条结论固定标为 C 级证据，并保持 `human_review=pending`。
4. 项目上下文必须引用项目文件中的逐字依据，不能根据项目名猜测用途。
5. Diff 读取 t0/t1 BOM 中冻结的历史画像，不回查“今天最新”的文档，避免时间对比被当前网络内容污染。
6. AI 结果无法覆盖 A 级许可证事实，也无法直接触发红黄绿灰或 CI 阻断。

因此，即使两个许可证名称完全相同，系统仍能保留条款级变化证据；如果原文没有形成可引用结论，则保留“证据不足”而不是猜测允许。

## 4. 上游范围

项目模式使用 ModelScope：

- `Data.BaseModel`
- `lineage.ParentsModels[].Name`

默认递归完整上游闭包，不设置固定三层上限。可显式使用 `--max-upstream-depth` 限制深度，并使用 `--max-upstream-nodes` 控制节点预算。

触发预算截断、接口缺失或循环时，结果会记录：

- `lineage_complete`
- `lineage_status`
- `lineage_truncation_reason`
- `unresolved_upstream_models`
- `lineage_cycles`
- `resolved_upstream_count`
- `max_depth_seen`

未解析父模型保留占位节点，避免把“没有查到”误写为“没有上游”。

## 5. 证据等级

- A：ModelScope 官方 API 字段，或从 ModelScope 官方仓库取得的 LICENSE / README 原文。
- B：工具基于 A 级事实生成的派生结构，例如血缘边、聚合节点和 BOM 映射。
- C：AI 条款抽取、项目上下文、语义 Diff、启发式或失败降级结果。

示例：

```text
许可证：qwen-research
AI 语义结论：疑似包含非商业使用限制
原文依据：“该模型仅限研究用途，不得用于商业目的。”
证据等级：C
置信度：0.86
处理状态：等待人工确认
```

`疑似` 不表示系统没有找到原文，而是表示 AI 结论仍属于需要人工解释的语义证据。最终许可证名称仍以 A 级事实为准。

## 6. 多证据、条件、例外与冲突

同一维度允许保留多条逐字证据，例如 LICENSE 与 README 同时支持一个结论。

- `conditions` 记录适用条件，每条条件尽量带原文和路径。
- `exceptions` 记录例外或豁免。
- `evidences` 保留所有通过精确命中校验的原文。
- `evidence_count` 表示该维度通过校验的证据数量。
- `cross_document_support` 表示是否有多个文档互证。
- 同一维度出现不一致状态时写入 `conflicts`，结论标记为 `conflict` 并等待人工确认。

系统不会通过多数投票自动选择“法律上正确的条款”。

## 7. 置信度口径

置信度表示“结论可复核程度”，不是法律正确概率，也不是模型自报概率。

```text
0.48 基础
+0.15 LICENSE 文件；README +0.08；其他结构化文件 +0.03
+0.10 引文在指定文件中精确命中
+0.08 出现明确限制措辞
+0.03 文件带 SHA256
+0.02 引文上下文足够
+最多 0.06 多个文档互证（每个额外文档 +0.02）
-0.12 conditional / unknown / not_found
上限 0.89
```

因此 LICENSE 中逐字命中的明确商业限制为 `0.86`；README 中逐字命中的条件性声明通常保留为 `0.59`。模型返回但原文找不到的引文会被丢弃。

Markdown 和 HTML 会展开每个分数的加项，便于复核 `0.86` 的组成。

## 8. 未识别维度

`证据不足`、`未找到明确条款` 表示给定 ModelScope 原文没有形成可精确引用结论，不代表法律上必然允许。系统固定关注：

- 模型输出能否用于训练其他模型；
- 是否允许再分发微调版本；
- 商用授权申请方式。

这些缺口会进入报告和 HTML，供人工补充合同、邮件授权或厂商补充条款。

## 9. Provider 配置

推荐使用支持 JSON 输出的本地、私有或受控 OpenAI-compatible 服务：

```dotenv
AI_ENABLED=true
AI_PROVIDER=openai-compatible
AI_MODEL=<open-weight-model-id>
AI_BASE_URL=<your-openai-compatible-endpoint>
AI_API_KEY=<your-key>
AI_TIMEOUT=60
AI_MAX_CONTEXT_CHARS=24000
```

- 不提供 `AI_BASE_URL` 的默认 localhost 或其他固定地址。
- `AI_API_KEY` 不写入报告、AI JSON、BOM 或 GitHub artifact。
- `MODELSCOPE_API_KEY` 只用于官方 API 和文件读取。
- 如果启用了 AI 但未配置地址，系统会生成明确原因，审计主链继续完成。

## 10. 运行方式

```powershell
python main.py --project <project-path> --ai
python main.py --model <namespace>/<name> --ai
python main.py --diff --before <t0-bom.json> --after <t1-bom.json> --output <report.md> --ai
```

所有输入输出路径来自命令行参数或调用方配置。项目/模型模式建议显式传入：

- `--artifacts-dir`
- `--cache-dir`
- `--bom-output`
- `--graph-output`

CI 不应通过搜索工具目录或最近修改时间猜测 BOM 路径。

## 11. GitHub Actions

Action 与示例 Workflow：

- 从 `RUNNER_TEMP` 派生运行、报告、缓存和工具目录；
- 显式传入 BOM 与 graph 输出路径；
- AI 仅在 `ai_enabled=true` 且 `AI_BASE_URL`、`AI_MODEL` 均非空时启用；
- 上传 `reports/` 和 `artifacts/`，包含 Markdown、BOM、source bundle、`ai_analysis.json`、graph、assets、edges；
- 规则判定 `RISK_CONFIRMED` 仍会阻断流水线；
- Secrets 不写入审计产物。

## 12. 验收与测试

离线验收包：

```powershell
python tests/acceptance/generate_ai_acceptance.py --output <acceptance-directory>
```

验收只使用 `tests/fixtures/ai/` 固定数据，不访问网络。产物包括模型、项目和 Diff 三套报告、AI JSON、BOM 与 HTML。

运行测试：

```powershell
python -m pytest -q
```

重点覆盖：

- 多证据逐字命中；
- 跨文档互证与冲突；
- 非逐字引文拒绝；
- BOM 中的 AI 画像往返；
- AI 服务缺失时的 `unavailable` 降级；
- 递归上游、循环、节点预算与 BOM 血缘字段往返；
- Action/Workflow 不依赖固定输出目录或本机绝对路径。
