# 最终受控 Run 证据（#40）

本目录冻结 GitHub Actions Run [#40](https://github.com/q7ijiang/open-source-ledger/actions/runs/43731631020)
的关键文件，便于离线复核。

## 1. Run 信息

| 项目 | 值 |
|---|---|
| Run | #40 / `43731631020` |
| 事件 | `workflow_dispatch` |
| 提交 | `639249b92929dfe178cf610492d8afc527fe39b4` |
| 结果 | `failure` |
| 失败原因 | 检测到 `RISK_CONFIRMED`，CI 按设计阻断 |
| 开始 | 2026-11-15T15:45:18Z |
| 结束 | 2026-11-15T15:53:26Z |
| Artifact | `license-watch-evidence` |
| Artifact 大小 | 910,998 bytes |
| Artifact SHA256 | `89a1c4b645bbdafcec8fa454e6b028bbec2d1e26aa60945c635119f179436b0b` |
| Artifact 过期 | 2026-11-29T15:53:21Z |

## 2. 关键结果

```text
受控 t0 恢复：success
首次基线报告：skipped
Compare previous and latest BOM：success
Render project lineage HTML：success
Render diff HTML：success
Detect confirmed license risk：failure（预期）
```

规则层：

```text
许可证变更：3
路径证书：2
RISK_CONFIRMED：1
RISK_POTENTIAL：2
```

时间区间：

```text
2026-10-27 → 2026-11-15
间隔 19 天
```

AI：

```text
status: ready
provider: openai-compatible
model: Qwen/Qwen3.5-27B
模型：4 ok / 2 partial / 0 unavailable
```

目标模型 `Qwen/Qwen-Image-2.1`：

```text
commercial_use    restricted   0.86
derivative_works  conditional  0.74
redistribution    conditional  0.66
```

AI Diff 中，目标模型的“允许 → 受限”标为“条款收紧”；
“未找到 → 有条件”标为“证据新增”，不会被误写成收紧。

## 3. 文件

| 文件 | 说明 |
|---|---|
| `run.json` | Run 元数据、Artifact SHA256、文件哈希 |
| `ai_status.json` | AI 配置探测结果 |
| `baseline_metadata.json` | 受控 t0 来源与哈希 |
| `current_baseline_metadata.json` | 本次真实 t1 基线元数据 |
| `diff_report.md` | 规则 Diff、传播路径、路径证书、AI 语义差异 |
| `diff_report.ai.json` | AI 语义差异 JSON |

HTML 未复制到本目录；完整 HTML 在 Artifact 中：

```text
artifacts/project/lineage.html
artifacts/diff/diff_lineage.html
artifacts/project/echarts.min.js
artifacts/diff/echarts.min.js
```

## 4. 边界

- t0 是显式标记的受控反事实快照，不是现实许可证变更声明。
- 标准 Apache 文本是受控替代文本，不是历史 LICENSE 原文件。
- AI 结论固定为 C 级、`human_review=pending`，不改变规则判定。
- `partial` 表示部分维度有 claim、部分维度有明确 gap，不等于完整覆盖。
- `failure` 是风险阻断生效，不是系统失败。
