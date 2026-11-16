# ModelScope License Risk Watch 使用指南

本指南对应当前 `main` 的实现，适用于在自己的 GitHub 仓库中定时检查项目直接使用的
ModelScope 模型及其上游闭包。BOM 通过 Actions Cache 保存，报告和 HTML 通过
Artifact 上传，不写入用户仓库。

## 一、最小配置

### 1. 配置项目路径

推荐使用 Repository variable：

```text
Settings -> Secrets and variables -> Actions -> Variables
LEDGER_PROJECT_PATH = .
```

`workflow_dispatch` 也可以直接填写 `project_path`，优先级高于变量。

### 2. 配置 ModelScope Key（可选）

公开模型可以匿名访问；私有模型、受限模型或匿名限流时，配置：

```text
Settings -> Secrets and variables -> Actions -> Secrets
MODELSCOPE_API_KEY = <your-key>
```

### 3. 配置 AI（可选）

Repository variables：

```text
AI_ENABLED   = true
AI_BASE_URL  = https://api-inference.modelscope.cn/v1
AI_MODEL     = Qwen/Qwen3.5-27B
AI_TIMEOUT   = 180
AI_MAX_MODELS = 6
```

Repository secret：

```text
AI_API_KEY = <your-ai-key>
```

`AI_ENABLED` 必须是 Repository variable，不是 Secret。

AI 是 C 级语义证据层，不可用时自动降级为规则审计；AI 不改变许可证名称、Delta、
风险灯色、decision 或 CI。

## 二、复制完整 Workflow（推荐）

把本仓库的：

```text
.github/workflows/license-watch.yml
```

复制到用户仓库：

```text
.github/workflows/license-watch.yml
```

工作流会：

1. 拉取用户仓库代码；
2. 把工具仓库 checkout 到 `.ci/open-source-ledger-tool`，再移动到 `RUNNER_TEMP`，
   避免工具自身 fixtures 被当成目标项目模型；
3. 安装 Python 3.10 和固定依赖；
4. 从 Actions Cache 恢复 `latest_bom.json` 作为 t0；
5. 扫描项目并生成 `current_bom.json`；
6. 有历史 BOM 时执行 `--diff`，并检查 `RISK_CONFIRMED`；
7. 生成 `lineage.html` 和 `diff_lineage.html`；
8. 上传 `license-watch-evidence` Artifact；
9. 只有风险检查通过时才保存新的 BOM 基线。

### 手动触发

```text
Actions -> ModelScope License Risk Watch -> Run workflow
project_path: example/qwen_image_controlled_project
```

`project_path` 只填路径，不要带 `project_path:` 前缀。

### 定时触发

```yaml
schedule:
  - cron: '0 2 * * 1'
```

GitHub Actions 的 cron 使用 UTC。`02:00 UTC` 是北京时间 `10:00`。

## 三、使用 composite Action

如果不想复制完整工作流，可以在自己的 Workflow 中调用：

```yaml
name: License Watch

on:
  workflow_dispatch:
  pull_request:
  schedule:
    - cron: '0 2 * * 1'

permissions:
  contents: read

jobs:
  license-watch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: q7ijiang/open-source-ledger@v1.1.0-semifinal
        with:
          project_path: .
          api_key: ${{ secrets.MODELSCOPE_API_KEY }}
          ai_enabled: 'true'
          ai_base_url: ${{ vars.AI_BASE_URL }}
          ai_model: ${{ vars.AI_MODEL }}
          ai_api_key: ${{ secrets.AI_API_KEY }}
          ai_max_models: '6'
          ai_timeout: '180'

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: license-watch-evidence
          path: |
            ${{ runner.temp }}/license-watch/reports
            ${{ runner.temp }}/license-watch/artifacts
          if-no-files-found: warn
          retention-days: 14
```

`action.yml` 的主要输入：

| 输入 | 默认 | 说明 |
|---|---|---|
| `project_path` | `.` | 要扫描的项目路径 |
| `api_key` | 空 | ModelScope Key |
| `ai_enabled` | 空 | 空=自动；`false` 显式关闭 |
| `ai_model` | `Qwen/Qwen3-4B-Instruct-2507` | OpenAI-compatible 模型名 |
| `ai_base_url` | 空 | 不提供固定默认地址 |
| `ai_api_key` | 空 | AI 服务密钥 |
| `ai_timeout` | `180` | 秒 |
| `ai_max_models` | `6` | 最多分析模型数 |
| `ai_max_context_chars` | `24000` | 最大上下文字符数 |
| `max_upstream_depth` | 空 | 空=完整上游闭包 |
| `max_upstream_nodes` | `128` | 上游节点预算 |

## 四、Artifact 内容

Artifact 名称：

```text
license-watch-evidence
```

目录：

```text
reports/
  ai_status.json
  baseline_metadata.json
  current_baseline_metadata.json
  previous_bom.json
  current_bom.json
  diff_report.md
  diff_report.ai.json
  watch_report.md

artifacts/
  project/graph.json
  project/lineage.html
  project/echarts.min.js
  diff/diff_lineage.html
  diff/echarts.min.js
  projects/<project>/source_bundles/
  projects/<project>/ai_analysis.json
```

HTML 必须和同目录的 `echarts.min.js` 一起使用：

```powershell
cd <解压后的 Artifact>
python -m http.server 8765
```

打开：

```text
http://127.0.0.1:8765/artifacts/project/lineage.html
http://127.0.0.1:8765/artifacts/diff/diff_lineage.html
```

不要只把单个 HTML 拖到浏览器，否则可能空白。

## 五、首次运行与后续运行

### 首次运行

Cache 中没有历史 BOM：

```text
Create first-run baseline report  success
Compare previous and latest BOM   skipped
```

本次 BOM 会作为下一次 t0。若 `RISK_CONFIRMED` 检测不到，则保存缓存。

### 第二次及以后

```text
Restore previous BOM as t0        success
Create first-run baseline report  skipped
Compare previous and latest BOM   success
```

报告包含：

```text
> 对比区间：2026-10-27 → 2026-11-15
```

## 六、风险阻断

如果 `diff_report.md` 在“证据等级与判定说明”之前出现 `RISK_CONFIRMED`，工作流执行：

```text
exit 1
```

结果：

- 当前 Job 失败；
- Artifact 仍上传；
- 新 BOM 不写回 Cache；
- 基线不推进；
- 下一次运行仍从旧 t0 比较。

这个失败是风险阻断生效，不是系统错误。

## 七、受控基线演示

受控 t0 用于演示“历史 Apache → 当前 qwen-research”的项目影响，显式标记：

```text
controlled_baseline=true
simulation=true
synthetic_document=true
not_historical_original=true
```

标准 Apache-2.0 全文只是受控替代文本，不是历史 LICENSE 原文件。

演示顺序：

1. 运行 `Seed Controlled Baseline`，默认写入
   `docs/competition/controlled-baseline/t0_bom.json`；
2. 运行 `ModelScope License Risk Watch`，项目填
   `example/qwen_image_controlled_project`；
3. 预期 `RISK_CONFIRMED`，CI 红色；
4. 下载 Artifact，检查 3 个许可证变更、2 张路径证书和 HTML。

Seed 与 scan 之间不要插入会保存缓存的成功运行，否则可能恢复成较新的真实基线。

## 八、人工接受已确认风险

如果团队已经评估并决定接受风险：

```text
Actions -> Promote Accepted Baseline
```

输入：

```text
source_run_id: 失败 Run ID
reason: 接受理由
confirm: true
```

行为：

- 原失败 Run 不会变绿；
- 该次 t1 写入 Cache，成为下一次 t0；
- 记录 `risk_accepted=true`、审批人、理由和时间；
- 下一次运行只检测新增变化。

## 九、常见问题

### 1. `project_path` 无效

现象：

```text
project_path 不是有效目录
```

处理：填写仓库内相对路径，例如 `example/qwen_image_controlled_project`，或设置
`LEDGER_PROJECT_PATH`。

### 2. 扫描未生成 BOM

检查：

- 项目里是否有可识别的 ModelScope 模型 ID；
- 模型详情 API 是否可访问；
- `MODELSCOPE_API_KEY` 是否有效；
- Artifact 中的 `watch_report.md` 是否列出了候选模型。

### 3. AI 400：special words

工具只把 LICENSE、README、`.md`、`.txt`、`.rst` 送入 AI，并跳过包含
`<|image_pad|>` 等特殊词的文档。若仍出现 400，检查 `ai_status.json` 和 provider
错误中的响应片段。

### 4. HTML 空白

原因通常是只打开了 HTML，没有保留 `echarts.min.js`。解压完整 Artifact，用 HTTP
服务打开。

### 5. 缓存没有命中

首次运行、缓存过期、缓存被删除、分支变化都会导致没有历史 BOM。完成一次成功运行
后再次触发即可。

### 6. Fork PR 被跳过

Fork PR 无法读取 Secrets。不要改用 `pull_request_target` 执行不可信代码；可以让
贡献者从仓库内部分支提交，或由维护者在可信分支运行。
