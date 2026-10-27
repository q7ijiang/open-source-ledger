# 场景二：真实上游血缘上的许可证变化传播

本目录用于演示“项目使用的模型不变，但其上游基座模型许可证变化”。

## 真实血缘

截至快照生成时，ModelScope 返回的真实关系为：

```text
unsloth/Qwen-Image-2.1-Turbo-FP8
  -> Qwen/Qwen-Image-2.1-Turbo
  -> Qwen/Qwen-Image-2.1
```

项目还直接使用 `OpenGVLab/InternVL3-8B-Instruct` 作为无关的文档理解分支。许可证变化从
`Qwen/Qwen-Image-2.1` 向图像生成分支传播，而文档理解分支不应被误标为受影响。

## 时间边界

- t0 的祖先许可证 `Apache License 2.0` 来自 ModelScope 真实历史 README 元数据。
- t1 的祖先许可证 `qwen-research` 和条款原文来自当前 ModelScope。
- 当前 Turbo 与 FP8 模型发布于许可证收紧之后，因此 t0 是
  `simulation=true` 的反事实重放：它复用当前真实血缘，但不声称这些下游
  模型在 Apache 阶段已经存在。
- 历史快照没有保存 Apache LICENSE 文件，只保存 README 元数据与提交证据。

## 文件

- `project/`：使用 FP8 图像模型和 InternVL 文档模型的项目。
- `evidence/`：历史/当前 Qwen-Image-2.1 证据以及真实血缘说明。
- `t0_bom.json`：真实当前血缘 + 历史许可证的模拟基线。
- `t1_bom.json`：真实当前血缘 + 当前许可证。
- `diff_report.md`：Delta、传播事件、路径证书和 AI 语义差异。
- `diff_graph.html`：可离线打开的交互验收页面。
- `ai_analysis.json`：冻结的 AI 条款画像和项目上下文。

## 规模

- t0：8 个资产，9 条边。
- t1：8 个资产，9 条边。

预期传播路径至少覆盖 `Qwen-Image-2.1 -> Turbo -> FP8`。AI 不负责传播，
只解释新增条款、给出逐字原文、原文哈希和置信度分解；传播仍由确定性图算法
生成路径证书。
