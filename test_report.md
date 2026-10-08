# ModelScope 数据入口适配 — 验证报告

- 生成时间：2026-10-07
- 验证命令：`python main.py --model Qwen/Qwen-Image-2.1 --output outputs/modelscope_validation/report.md`

## 一、目标与结论

将数据管道的摄入 / 路由层从 Hugging Face 切换到 ModelScope（适配器模式），
不改动核心算法与标识生成逻辑。验证结论：**通过**。

## 二、三个决策点落实

1. **命名空间字段**：实测 ModelScope 详情 API 的命名空间在 `Data.Path`（而非文档的
   `Data.Namespace`），按 `Path → Namespace → Organization.Name` 优先提取，正确生成
   PURL `pkg:modelscope/Qwen/Qwen-Image-2.1@master`。
2. **`--model` 路由**：`run_model()` 增加 `_probe_modelscope()` 探测分支——命中详情 API
   走 ModelScope 流水线；404 判定为 HF 模型走旧链路；网络异常回退 HF 并打印中文提示，
   不抛莫名堆栈错误。
3. **证据等级与聚合节点**：血缘边（官方 API 聚合计数）标 **B**；许可证（非标文本推断，
   如 `qwen-research`）标 **C**；`count` 保留在 `name` 中（如 `适配 (Total: 1873)`）。

## 三、改动清单

新增：

- `modelscope_adapter.py` — 数据入口：Bearer 认证、`{Code, Data}` 信封剥离、
  字段映射、复用 `bom_adapter.build_asset_identifiers` 生成 entity_key / canonical_id。
- `work/extract_modelscope_lineage.py` — 血缘提取 + 建图，聚合降维（不为每个派生
  模型拉取详情，改为带 `count` 的聚合节点）。

修改：

- `evidence_enricher.py` — 增加 `modelscope` purl 支持、Bearer 认证、信封剥离、
  `extract_modelscope_license`。
- `main.py` — `_is_model_bom` 路由、`_extract_model_edges`、`run_model` 探测分支、
  `_render_modelscope_report`。

未修改（核心算法层，**零改动**）：

- `entity_resolver.py`、`delta_engine.py`、`propagation_engine.py`、
  `build_graph.py`、`work/extract_hf_lineage.py`

## 四、运行结果（终端日志摘要）

```text
[extract_modelscope_lineage] 运行：... work\extract_modelscope_lineage.py --model Qwen/Qwen-Image-2.1 --output-dir ...\outputs\modelscope_validation
模型：Qwen/Qwen-Image-2.1
许可证：qwen-research
资产节点：4（含 3 个聚合节点，聚合 1920 个派生/祖先模型）
血缘边：3（derived_from，证据等级 B）
SCC 分量：4
已写入 ...\assets.json / ...\edges.json / ...\graph.json
[visualize_lineage] 运行：... visualize_lineage.py --graph ...\graph.json --output ...\lineage_graph.png
（血缘图节点 4，边 3，hierarchical 布局）
已写入 ...\lineage_graph.png
模型模式报告已写入：outputs\modelscope_validation\report.md
```

## 五、关键提取结果

- 许可证 `qwen-research` 取自 `Data.LicenseName`，证据等级 **C**。
- 3 个聚合节点（官方 API 计数，未逐个展开 1920 个派生模型）：
  - `Adapters` 适配 — 1873
  - `Finetunes` 微调 — 21
  - `Quantizations` 量化 — 26
- 3 条 `derived_from` 边：派生聚合节点 → 当前模型，证据等级 **B**。
- `ParentModels` 为空（该基模型无祖先），故无父边，符合预期。

> 注：Adapters 计数在实时 API 中为 1873（早前落盘的探测快照为 1871），
> 属于 ModelScope 实时数据的自然漂移，非实现问题。

## 六、产出文件（outputs/modelscope_validation/）

- `assets.json` / `edges.json` / `graph.json`
- `lineage_graph.png`
- `report.md`
