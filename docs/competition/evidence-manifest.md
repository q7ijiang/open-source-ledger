# 半决赛证据清单

> 用途：把可复核的代码基线、测试、最终 Actions Run、受控 t0 和 AI 证据集中到一处。
> 引用时以原始链接、Run 和 SHA 为准。

## 1. 代码基线

| 项目 | 值 |
|---|---|
| 仓库 | <https://github.com/q7ijiang/open-source-ledger> |
| 分支 | `main` |
| 最终 Run 提交 | `639249b92929dfe178cf610492d8afc527fe39b4` |
| 原始基线 | `16a4cb5ce8c4019a64dc28b82df60993af2cf4a5` |
| 半决赛标签 | `v1.1.0-semifinal`（指向本文档所在提交） |
| 清单生成时间 | 2026-11-16（Asia/Shanghai） |

最终 Run 的代码提交是 `639249b`；本清单和证据文件在后续提交中冻结，并以
`v1.1.0-semifinal` 标签固定。

工作区仍保留用户已有的、未纳入提交的 `docs/demo/`。

## 2. 自动化测试

```text
python -m pytest -q
205 passed
```

- 运行日期：2026-11-15
- 环境：Windows，Python 3.10.11
- 覆盖：AI 证据与降级、ModelScope 递归血缘、Project fixtures、Diff 与传播、
  HTML 渲染、仓库路径卫生、Action 配置、AI 缺口、受控 t0、最终 Run 证据。

## 3. 最终 Actions Run

| 项目 | 值 |
|---|---|
| Workflow | ModelScope License Risk Watch |
| Run | [#40](https://github.com/q7ijiang/open-source-ledger/actions/runs/43731631020) |
| Run ID | `43731631020` |
| 事件 | `workflow_dispatch` |
| 提交 | `639249b92929dfe178cf610492d8afc527fe39b4` |
| 结果 | `failure`，检测到 `RISK_CONFIRMED`，CI 阻断生效 |
| 开始 | 2026-11-15T15:45:18Z |
| 结束 | 2026-11-15T15:53:26Z |
| Artifact | `license-watch-evidence` |
| Artifact 大小 | 910,998 bytes |
| Artifact SHA256 | `89a1c4b645bbdafcec8fa454e6b028bbec2d1e26aa60945c635119f179436b0b` |
| Artifact 过期 | 2026-11-29T15:53:21Z |

关键步骤：

```text
Restore previous BOM as t0        success
Create first-run baseline report  skipped
Compare previous and latest BOM   success
Annotate controlled baseline      success
Render project lineage HTML       success
Render diff HTML                  success
Detect confirmed license risk     failure（预期）
Upload license audit evidence     success
```

离线冻结的关键文件见 [`final-run/README.md`](final-run/README.md)。

## 4. 受控 t0 与 Diff

证据目录：[`controlled-baseline/README.md`](controlled-baseline/README.md)

| 项目 | 值 |
|---|---|
| 目标模型 | `Qwen/Qwen-Image-2.1` |
| t0 许可证 | `Apache-2.0` |
| t0 时间戳 | `2026-10-27T11:09:25Z` |
| t0 SHA256（LF） | `ae8749010b8076f2a87d43ea4f4373f6345c2b517b124af2ae864b8b3d775118` |
| t1 快照 SHA256（LF） | `b010b7d2cb74878cecfd1e527ff84d82b1b4a4c2eff336d77db157c056d57b09` |
| Diff 区间 | `2026-10-27 → 2026-11-15`，19 天 |
| 许可证变更事件 | 3 |
| 路径证书 | 2 |
| 判定 | `RISK_CONFIRMED` 1 / `RISK_POTENTIAL` 2 |

t0 明确标记：

```text
controlled_baseline=true
simulation=true
controlled_source=true
synthetic_document=true
not_historical_original=true
```

标准 Apache-2.0 全文仅作为受控替代文本，不声称是历史 LICENSE 原文件。

## 5. AI 证据

| 项目 | 值 |
|---|---|
| Provider | `openai-compatible` |
| Model | `Qwen/Qwen3.5-27B` |
| Endpoint | `https://api-inference.modelscope.cn/v1` |
| 状态 | `ready` |
| 6 个模型 | 4 `ok` / 2 `partial` / 0 `unavailable` |

目标模型 t0：

```text
commercial_use    allowed   0.80
distribution      allowed   0.78
modification      allowed   0.78
patent_license    allowed   0.78
```

目标模型 t1：

```text
commercial_use    restricted   0.86
derivative_works  conditional  0.74
redistribution    conditional  0.66
```

AI Diff 将 `允许 → 受限` 标为“条款收紧”，将一侧无引文的变化标为“证据新增/证据丢失”，不把缺口误写成收紧。

未形成引文的维度保留具体 gap：

- 要确认的问题；
- 缺失的证据；
- 检索来源；
- 校验说明。

真实 AI 的独立证据见 [`real-ai/README.md`](real-ai/README.md)。

## 6. 依赖与第三方资源

依赖固定为：

```text
networkx==3.4.2
matplotlib==3.10.9
pytest==9.1.1
python-dotenv==1.2.4
requests==2.34.2
streamlit==1.54.0
```

第三方组件、数据源、AI 服务和模型权重边界见
[`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md)。

## 7. 路径与边界

- 测试夹具和 HTML 不包含机器用户名路径；
- HTML 打开时需保留同目录 `echarts.min.js`，或使用本地 HTTP 服务；
- `RISK_CONFIRMED` 的 `failure` 是风险阻断，不是系统错误；
- AI 是 C 级证据，不修改许可证、风险灯色、Delta、decision 或 CI；
- 只审计项目直接模型及其上游闭包，不枚举 ModelScope 全量下游；
- 不提供法律意见。

## 8. 待补材料

- [x] 真实 AI 运行与证据冻结；
- [x] 受控 t0 构造与真实 t1 Diff；
- [x] 最终 Run #40 与 Artifact 冻结；
- [x] HTML 和 AI 差异类型；
- [ ] 半决赛 PPT（匿名检查）；
- [ ] 6 分钟内、无剪辑、无快进、全员出镜的答辩视频；
- [ ] 最终 release/tag 推送。

## 9. 复核命令

```powershell
python -m pytest -q
python main.py --diff `
  --before docs/competition/controlled-baseline/t0_bom.json `
  --after docs/competition/controlled-baseline/t1_observed_bom.json `
  --output docs/competition/controlled-baseline/diff_report.md `
  --ai
```

最终 Run：

```text
https://github.com/q7ijiang/open-source-ledger/actions/runs/43731631020
https://api.github.com/repos/q7ijiang/open-source-ledger/actions/runs/43731631020/artifacts
```
