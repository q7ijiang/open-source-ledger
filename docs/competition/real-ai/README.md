# 真实 AI 运行证据（2026-11-14）

本目录保存一次真实的 OpenAI-compatible 开放权重模型调用结果。它是比赛要求的
“至少一次真实 AI 调用”证据，不是 mock/offline 结果。

## 1. 调用信息

| 项目 | 值 |
| --- | --- |
| 调用时间（UTC） | 2026-11-14T12:22:12Z 至 2026-11-14T12:24:51Z |
| 调用时间（Asia/Shanghai） | 2026-11-14 20:22:12 至 20:24:51 |
| Endpoint | `https://api-inference.modelscope.cn/v1` |
| Provider | `openai-compatible` |
| Model ID | `Qwen/Qwen3.5-27B` |
| Prompt version | `modelscope-license-audit-v2` |
| 输入项目 | `tests/fixtures/projects/real_modelscope/smoke_project` |
| 直接模型 | `Qwen/Qwen2.5-7B-Instruct-AWQ` |
| 真实上游闭包 | `Qwen/Qwen2.5-7B-Instruct` → `Qwen/Qwen2.5-7B` |
| 网络状态 | 调用成功；未使用 mock provider |
| 密钥 | 仅在本机进程环境中使用，未写入任何产物 |

## 2. 结果概览

- 2 个模型画像为 `status=ok`，共 4 条通过逐字校验的条款结论：
  - `commercial_use=allowed`，置信度 0.80，来源 `LICENSE`；
  - `training_other_models=allowed`，置信度 0.78，来源 `LICENSE`。
- 1 个模型（`Qwen/Qwen2.5-7B`）为 `no_evidence`，保留 6 个证据缺口，没有猜测。
- 项目使用上下文为 `local_inference`，置信度 0.83，来源 `app.py`。
- 所有 AI claim 仍为 C 级证据、`human_review=pending`。
- AI 未改变 A 级许可证事实：BOM 中三个模型均为 `Apache-2.0`，判定仍由规则链给出。

独立复核结果：上述 4 条 claim 的 `source_path` + `quote` 均能在对应
`source_bundles/` 的 LICENSE 原文中精确命中。

## 3. 文件与 SHA256

| 文件 | 大小 | SHA256 |
| --- | --- | --- |
| `ai_analysis.json` | 24,881 | `71c0a492ada894232b6068bb9c9f1fae31355ccc226f5f20c15a2bd68072353a` |
| `bom.json` | 33,508 | `e6e32baafe641102756945499e455f3208f55181e86f41bcc6f32bb99322e54c` |
| `report.md` | 8,873 | `ed485deb5c11d4b977cdcb7d8ec5a9ff27d537cbdefa5386ebb00318ba067300` |
| `assets.json` | 33,911 | `55d7d946663604d71677adf8be645da7c29b3fdf7dac51bb4cab26816c222a78` |
| `graph.json` | 37,870 | `7703f67c3aaf91e3944358de3ad353259ada553f099823a61cfcea9c85945152` |
| `lineage.html` | 73,866 | `dfa46ee53f407b916cc35551a6cf4a557343b873fb0104e5a4cdf5d70e9aaf9e` |
| `source_bundles/Qwen__Qwen2.5-7B-Instruct-AWQ.json` | 116,576 | `6555ed3427cf7f529abd6e674f5836eb15d6f4487703dd7e68e0f884a289f719` |
| `source_bundles/Qwen__Qwen2.5-7B-Instruct.json` | 82,235 | `fe14964d69feba784524aa703bfa77cfd579168bba58f44043e2829379e2b2a9` |
| `source_bundles/Qwen__Qwen2.5-7B.json` | 75,569 | `50cff06ec93db589bf7862c2504702062177d8d7f3348371d85cffd40a3c379e` |

`verification.json` 记录逐条 claim 的原文命中结果、C 级/待复核状态和各文件 SHA256。
其中 `all_quotes_exact=true`、`all_c_level_pending=true`。

`source_bundles/` 中每个文件都记录了：

- ModelScope 来源 URL；
- `retrieved_at`；
- 文档 SHA256；
- 模型卡、LICENSE、README 和配置文件原文。

## 4. 证据边界

- 这是**真实模型调用**，但输入项目是固定夹具，不是生产仓库扫描。
- 该结果只证明 AI 语义证据链在真实服务下可运行，不证明所有 ModelScope 模型的
  许可证结论都正确。
- `Qwen/Qwen2.5-7B` 的 `no_evidence` 是预期中的降级结果：没有形成可逐字引用的
  条款结论，不得解释为“安全”。
- AI 结论不能替代律师意见，也不改变许可证名称、风险灯色、Delta 或 CI 判定。
- `lineage.html` 中的 ECharts 使用仓库根目录的 `../../../echarts.min.js`，本地打开
  时需要保持目录结构。

## 5. 复现

```powershell
$env:AI_ENABLED = "true"
$env:AI_PROVIDER = "openai-compatible"
$env:AI_MODEL = "Qwen/Qwen3.5-27B"
$env:AI_BASE_URL = "https://api-inference.modelscope.cn/v1"
$env:AI_API_KEY = $env:MODELSCOPE_API_KEY

python main.py `
  --project tests/fixtures/projects/real_modelscope/smoke_project `
  --artifacts-dir out/real-ai/artifacts `
  --ai `
  --ai-max-models 3

python render_graph.py `
  --input out/real-ai/artifacts/projects/smoke_project/graph.json `
  --output out/real-ai/artifacts/projects/smoke_project/lineage.html `
  --report out/real-ai/artifacts/projects/smoke_project/report.md `
  --title "真实 AI 验收 - smoke_project"
```
