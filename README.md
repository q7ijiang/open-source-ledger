# 开源账本（open-source-ledger）

开源账本面向 AI 模型应用团队，辅助开发者识别并持续规避项目模型供应链中的许可证变更风险。

核心边界：

- 审计对象是**项目直接使用的 ModelScope 模型及其完整上游闭包**。
- 默认不枚举、不评估平台上的全量下游模型；下游风险传播保留为未来研究方向。
- Streamlit 只保留 Project 与 Diff 两个用户入口；单模型调查仅作为内部 CLI 与测试能力。
- AI 是受原文约束的 C 级语义证据层，不修改许可证事实、Delta、风险灯色、decision 或 CI 结果。
- 输入输出路径均来自命令行参数、环境变量或 GitHub Actions 运行目录，不依赖固定本机路径。

## 解决的问题

ModelScope 详情页可以展示模型许可证，但项目仍需要回答：

1. 项目实际使用了哪些模型，来源文件是什么。
2. 这些模型的上游基座模型是谁，上游是否还有父模型。
3. 许可证变更发生后，项目直接模型及其上游闭包中哪些证据发生了变化。
4. 非标准许可证在 LICENSE、README 或使用政策中具体限制了什么。
5. 变化是否能形成可复核的 Markdown、CycloneDX BOM、HTML 图与 CI 证据包。

工具输出用于工程辅助审计，不构成法律意见。

## 用户入口与内部调查

| 模式 | 作用 | 是否进入项目风险闭包 |
|---|---|---|
| Project | 扫描项目中的 ModelScope 模型，递归查询上游闭包，生成 BOM、图和报告 | 是，核心模式 |
| Diff | 比较 t0/t1 BOM 中的许可证事实、血缘与 AI 语义证据 | 是，核心模式 |
| Model（内部 CLI） | 查询单个模型及其上游，并可显示平台提供的下游规模提示 | 否，仅用于调查与测试 |

Streamlit 不提供 Model 用户入口。Project 和 Diff 默认不读取 `SonModels`；内部单模型调查可以保留平台返回的下游规模提示，但这些提示只是计数，不会展开成下游模型身份，也不会参与项目风险判定。

## 上游血缘

血缘提取同时读取 ModelScope 的：

- `Data.BaseModel`
- `lineage.ParentsModels[].Name`

默认递归完整上游闭包，不设置固定的三层深度上限。为防止异常数据或循环导致失控，系统提供：

- 显式 `--max-upstream-depth` 深度限制；
- 默认 `--max-upstream-nodes 128` 节点预算；
- 循环检测、节点预算截断与未解析占位节点；
- `lineage_complete`、`lineage_status`、`unresolved_upstream_models`、`resolved_upstream_count`、`max_depth_seen` 等可审计字段。

## 安装

Python 最低版本为 3.10。

```powershell
python -m pip install -r requirements.txt
```

可选运行测试：

```powershell
python -m pytest -q
```

## 快速开始

### 1. 扫描项目

```powershell
python main.py `
  --project <project-directory> `
  --artifacts-dir <artifacts-directory> `
  --cache-dir <cache-directory> `
  --bom-output <artifacts-directory>/project/t1_bom.json `
  --graph-output <artifacts-directory>/project/graph.json `
  --output <artifacts-directory>/project/report.md
```

CLI 会显式写出 BOM 和图路径，不要求 CI 再搜索 `outputs`。同目录还会生成：

- `assets.json`
- `edges.json`
- `run_context.json`
- `source_bundles/`（启用 AI 时）
- `ai_analysis.json`（启用 AI 时）

### 2. 比较两次快照

```powershell
python main.py `
  --diff `
  --before <t0-bom.json> `
  --after <t1-bom.json> `
  --output <reports-directory>/diff_report.md
```

如果有历史 AI 画像，可加入 `--ai` 生成语义收紧、放宽、证据新增或丢失的复核项。

### 3. 单模型调查

```powershell
python main.py --model <namespace>/<name>
```

通过 `--artifacts-dir` 可指定产物根目录；通过 `--max-upstream-depth` 可限制上游深度。内部模型调查的产物位于 `<artifacts-dir>/models/<safe-model-name>/`。

### 4. 生成可交互 HTML

```powershell
python render_graph.py --input <graph.json> --output <lineage.html>
python render_diff.py --before <t0-bom.json> --after <t1-bom.json> --output <diff.html>
```

## AI 语义证据

AI 不是无约束的“模型许可问答”，也不只是对非标准许可证做补充查询。它嵌入三条核心链路：

1. **条款证据抽取**：只读取 ModelScope 官方详情、LICENSE、README 等冻结原文；每条结论必须给出文件路径和逐字引文。
2. **项目使用上下文**：从项目源码、配置和说明文件中提取远程 API、本地推理、权重分发、微调或衍生发布等实际使用方式。
3. **同名许可证语义 Diff**：比较 t0/t1 固化画像，识别许可证名称未变但条款收紧、放宽、条件变化或证据丢失。

Agent 返回的引文必须在输入文档中精确命中，否则丢弃。AI 结论统一为 C 级证据，并保持 `human_review=pending`。置信度是可复核程度，不是法律正确概率，也不是模型自报分数。

AI 默认关闭，服务地址没有固定默认值。配置示例见 `.env.example`：

```dotenv
AI_ENABLED=true
AI_PROVIDER=openai-compatible
AI_MODEL=<open-weight-model-id>
AI_BASE_URL=<your-openai-compatible-endpoint>
AI_API_KEY=<your-key>
AI_TIMEOUT=60
AI_MAX_CONTEXT_CHARS=24000
```

如果 `AI_BASE_URL` 未配置或服务不可用，系统写入 `status=unavailable` 的 AI 证据，规则审计、BOM 和 Diff 仍继续完成。

运行示例：

```powershell
python main.py --project <project-directory> --ai
python main.py --model <namespace>/<name> --ai
python main.py --diff --before <t0-bom.json> --after <t1-bom.json> --output <diff.md> --ai
```

详细口径见 [AI 能力说明](docs/AI能力说明.md)。

## GitHub Actions

仓库提供：

- 根目录 `action.yml`：供其他项目以 composite Action 调用。
- `.github/workflows/license-watch.yml`：示例定时扫描 Workflow。

Action 的特征：

- 运行、缓存、报告和图产物均从 `${RUNNER_TEMP}` 派生；
- 必须显式提供扫描路径：手动触发填写 `project_path`，定时任务和 PR 使用仓库变量
  `LEDGER_PROJECT_PATH`；未配置时明确失败，不会猜测或自扫描仓库根目录；
- 扫描时显式传入 artifacts、cache、BOM、graph 和 report 路径；
- 规则判定为 `RISK_CONFIRMED` 时仍阻断流水线；
- 生成 `artifacts/project/lineage.html` 和 `artifacts/diff/diff_lineage.html`，随
  Artifact 一起上传；
- 完整上传报告、BOM、source bundle、AI JSON、graph、assets 和 edges；
- AI 是常驻辅助证据位：每次运行写 `reports/ai_status.json`；`AI_BASE_URL`、
  `AI_MODEL`、`AI_API_KEY` 齐全时自动调用，缺失时降级为 `unavailable` 并继续
  规则审计；`AI_ENABLED=false` 可显式关闭；
- AI 默认最多分析 6 个模型、超时 180 秒；可通过 `AI_MAX_MODELS`、`AI_TIMEOUT`、
  `AI_MAX_CONTEXT_CHARS` 调整，避免对所有上游模型串行调用导致超时；
- AI 可用时 Project 和 Diff 都会带上 `--ai`，报告中出现 C 级 AI 语义段；
- API Key 仅从 Secrets 读取，不写入审计产物。

示例配置：

```yaml
- uses: q7ijiang/open-source-ledger@main
  with:
    project_path: .
    api_key: ${{ secrets.MODELSCOPE_API_KEY }}
    ai_base_url: ${{ vars.AI_BASE_URL }}
    ai_model: ${{ vars.AI_MODEL }}
    ai_api_key: ${{ secrets.AI_API_KEY }}
```

### 受控 t0 演示

当现实中还没有发生许可证变更时，可以手动把一份冻结的受控 t0 写入 Actions Cache：

1. 运行 `Seed Controlled Baseline`，默认使用
   `docs/competition/controlled-baseline/t0_bom.json`；
2. 立即运行 `ModelScope License Risk Watch`，`project_path` 填
   `example/qwen_image_controlled_project`；
3. 第二次运行会恢复受控 t0，扫描真实 t1，并生成许可证变更、传播路径和路径证书。

受控 t0 会在 Artifact 的 `baseline_metadata.json` 中标记
`controlled_baseline=true`、`simulation=true`。t1 是真实 ModelScope 扫描结果；
t0 是受控反事实，不是对现实许可证变更的声明。Seed 与 scan 之间不要插入其他
会保存缓存的成功运行，否则可能恢复较新的真实基线。

受控 t0 已用同一真实 AI（`Qwen/Qwen3.5-27B`）生成 C 级画像；t0 与 t1 使用同一
provider / prompt，因此 AI 语义 Diff 可比较。t0 的 Apache 文本是标准 Apache-2.0
全文的受控替代文本，不是历史原文件；BOM 和 Artifact 中均保留
`controlled_source`、`synthetic_document`、`not_historical_original` 标记。
未形成逐字引文的维度会保留具体 gap（缺什么、查了哪些文件），不会被推断为安全。

### 人工接受已确认风险

如果 `license-watch` 因 `RISK_CONFIRMED` 失败，而团队已经人工评估并决定接受
该风险，可以手动运行：

```text
Promote Accepted Baseline
```

需要填写：

- `source_run_id`：发生风险的 `license-watch` Run ID；
- `reason`：接受该风险的理由；
- `confirm=true`：明确确认。

该 Workflow 会下载源 Run 的 `current_bom.json`，写入 `risk_accepted=true`、
`promoted_by`、`promotion_reason` 和 `source_bom_sha256`，再保存为下一次的 t0。

边界：

- 原失败 Run 不会变绿；
- 下一次 `license-watch` 才使用这份已接受基线；
- 这不是“风险已修复”，而是“风险已知并接受”；
- 受控演示如果还要重复，需要重新运行 `Seed Controlled Baseline`。

## 离线验收

```powershell
python tests/acceptance/generate_ai_acceptance.py --output <acceptance-directory>
```

验收包不访问网络，包含内部模型调查、项目和 Diff 三类分析产物的 Markdown、HTML、BOM 与 AI JSON；产品用户入口仍只有 Project 与 Diff。每类测试夹具位于 `tests/fixtures/`，对应目录附有 README。

## 测试与可复现性

```powershell
python -m py_compile modelscope_lineage.py main.py build_graph.py export_bom.py bom_adapter.py ai_layer\config.py ai_layer\schemas.py ai_layer\service.py
python -m pytest -q
```

测试覆盖递归上游闭包、循环与预算截断、BOM 血缘字段往返、多证据精确引文、跨文档冲突、AI 不可用降级、路径卫生和 Action 配置。

## 证据等级

- A：ModelScope 官方 API 字段，或从 ModelScope 官方仓库取得的 LICENSE / README 原文。
- B：工具从 A 级事实推导出的血缘边、稳定标识和 BOM 映射。
- C：AI 条款抽取、项目使用上下文、语义 Diff、启发式或失败降级结果，必须人工确认。

## 第三方组件与资源

仓库分发 ECharts/zrender，并依赖 Python 包、ModelScope 数据和可选的
OpenAI-compatible 服务。版本、许可证、来源与模型权重边界见
[第三方组件与资源声明](THIRD_PARTY_NOTICES.md)。

## 免责声明

本工具提供基于证据的辅助审计，不构成法律意见。
