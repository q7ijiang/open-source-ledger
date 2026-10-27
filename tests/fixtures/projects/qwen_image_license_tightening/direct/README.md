# 场景一：项目直接使用 Qwen-Image-2.1

本目录用于演示“项目直接使用的模型发生许可证变化”。

## 证据边界

- 2026-09-15 至 2026-09-17，ModelScope 的 `README.md` 元数据将许可证写作
  `license: Apache License 2.0`，对应提交 `72900d004951bd845d7a4a77d566562eadd37c3f`。
- 2026-09-18 新增 `LICENSE`，内容为 Qwen Research License，对应提交
  `4b1751dd4e00f6c1a097c5a80d05e6521cea1c39`。
- 2026-09-20 `README.md` 改为 `license: other` 和
  `license_name: qwen-research`，对应提交 `c64b6eace0507982fa3f4828461b201d836d625a`。
- 历史快照只重建 README 元数据，没有保存或虚构 Apache-2.0 LICENSE 文件。
- 这不是“同一个 Apache LICENSE 文本被改写”的声明。

## 文件

- `project/`：演示项目的源码和配置。
- `evidence/`：历史 README、当前 ModelScope source bundle 和边界说明。
- `t0_bom.json`：Apache License 2.0 元数据时点的重建快照。
- `t1_bom.json`：读取当前 Qwen Research License 原文的快照。
- `diff_report.md`：Delta、路径证书和 AI 语义差异。
- `diff_graph.html`：可离线打开的交互验收页面。
- `ai_analysis.json`：冻结的 AI 条款画像和项目上下文。

## 规模

- t0：1 个资产，0 条边。
- t1：1 个资产，0 条边。

直接模式没有下游项目节点可传播，风险落在项目直接依赖本身；预期看到许可证
名称变化和 AI 提取出的非商业限制。所有 AI 结论均为 C 级并处于人工复核状态。
