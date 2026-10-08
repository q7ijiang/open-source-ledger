# extract_edges.py 依赖处理报告

## 1. main.py 的依赖分析

### 原调用位置

原 `main.py` 中与 `extract_edges` 相关的位置如下：

- 顶部文档说明：基础链路最后一步为 `extract_edges.extract_edges`。
- `_build_snapshot()`：函数内执行 `import extract_edges`。
- `_build_snapshot()`：在 BOM 解析、实体对齐和证据补全之后执行：

```python
edges, edge_stats = extract_edges.extract_edges(enriched)
```

- `_render_basic_report()`：读取 `edges` 和 `edge_stats`，生成“血缘边统计”章节。
- `run_deep()`：通过 `_build_snapshot()` 取得 `edges`，随后交给 `build_graph.build_graph()` 和 `delta_engine.detect_delta()`。

因此，实际使用它的函数是 `_build_snapshot()`，并通过该函数间接影响基础报告和完整深度链路。

### 它原来做什么

通用提取器 `extract_edges.extract_edges()` 从资产和原始 BOM 中生成三类边：

| 边类型 | 来源 | 原证据等级 |
|---|---|---|
| `derived_from` | `pedigree.ancestors` | A |
| `trained_on` | `modelCard.modelParameters.datasets` | A |
| `depends_on` | BOM `dependencies.dependsOn` | B |

基础报告使用边数、边类型分布和提取统计。深度链路使用边构建血缘图，并由 Delta 引擎检测祖先和训练数据集变化。

### 去掉后的影响

- 基础链路：资产解析、实体对齐、证据补全和许可证清单本身不依赖边，可以继续运行；需要移除或改写原来的边统计章节。
- 深度链路：如果完全移除且不替换，图会缺少 HF 血缘边，`ancestor_*` 和 `dataset_*` 变更无法正常检测和传播。
- 通用 `depends_on`：该边不属于当前 HF 模型血缘主线。移除后，包依赖关系不再进入基础报告和深度图。

### HF 主线是否需要

需要 HF 血缘边，但不需要通用 `depends_on` 边。深度链路依赖 `derived_from` 和 `trained_on`，因此不能采用完全置空边的方案 A。

## 2. 选择的方案和理由

采用方案 B：在 `main.py` 中改为调用 `work/extract_hf_lineage.py` 的 `extract()`。

理由：

1. HF 专用提取器已经生成标准字段的 `derived_from` 和 `trained_on` 边，符合 `docs/接口约定.md`。
2. 深度模式确实使用血缘边建图和检测祖先、数据集变化。
3. 当前主线聚焦 Hugging Face 模型血缘，不需要通用 BOM 的 `depends_on`。
4. `main.py` 增加 HF 模型 BOM 判断，只有首组件是 HF 模型组件时才调用 HF 提取器，避免把普通包 BOM 误判为模型血缘。
5. HF 提取器自动补齐的缺失祖先或数据集节点会合并进快照，边仍可指向有效资产。

## 3. main.py 修改前后对比

### 修改前

```python
import extract_edges

...
edges, edge_stats = extract_edges.extract_edges(enriched)
return {
    ...
    "assets": enriched,
    "edges": edges,
    "edge_stats": edge_stats,
}
```

基础报告直接读取 `edge_stats`，并显示原始边引用数、去重数、补回关系资产数和悬空端点数。

### 修改后

```python
HF_LINEAGE_EDGE_TYPES = {"derived_from", "trained_on"}

...
from work.extract_hf_lineage import extract as extract_hf_lineage

lineage_assets, lineage_edges = extract_hf_lineage(path)
assets, edges = _extract_hf_edges(path, bom, enriched, snapshot_id)
```

`_extract_hf_edges()` 负责：

- 仅处理首组件为 `machine-learning-model` 且 purl 以 `pkg:huggingface/` 开头的 BOM。
- 只保留 `derived_from` 和 `trained_on`。
- 将边统一为 `source`、`target`、`edge_type`、`evidence_level`、`source_field`、`snapshot_id`。
- 把边和补建节点的 `snapshot_id` 覆盖为当前入口的 `basic-YYYYMMDD`、`t0` 或 `t1`。
- 合并 HF 提取器补建的缺失祖先或数据集节点。

基础报告现在显示“HF 血缘边数”，并在“血缘边统计”章节明确标注：

```text
- 通用依赖关系边（depends_on）：已移除。
```

## 4. extract_edges.py 删除结果

未删除 `extract_edges.py`。

删除前按要求遍历仓库 `.py` 文件，发现仍有其他脚本依赖：

```text
work/verify_new_modules.py:16: from extract_edges import extract_edges
work/verify_new_modules.py:143: edges, stats = extract_edges(assets)
```

该脚本还明确断言通用提取器会输出 `depends_on` 边。根据任务约束中的停止条件：

> 如果有其他模块还在用，报告并停止删除。

因此没有删除 `extract_edges.py`，也没有修改 `work/verify_new_modules.py`。当前状态是：

- `main.py` 已不再依赖 `extract_edges.py`。
- `extract_edges.py` 仍存在，供现有 `work/verify_new_modules.py` 使用。
- 后续若要物理删除，需要先单独处理或退役该验证脚本。

## 5. 验证结果

### 语法检查

```text
python -m py_compile main.py
退出码：0
```

### 基础模式

```text
python main.py --mode basic --input data/sample_bom.json --output outputs/check_basic.md
退出码：0
```

结果：

- 输出文件：`outputs/check_basic.md`
- BOM 解析资产数：72
- 实体对齐后资产数：71
- HF 血缘边数：0
- 中文清单、许可证风险分布、资产清单和待人工确认章节正常。
- 报告明确显示“通用 depends_on 边已移除”。

说明：当前环境网络受限，71 个远程证据请求均降级，但报告仍正常生成，退出码为 0。

### 深度模式

精确 t0/t1 命令未执行，因为仓库中不存在：

```text
data/t0_bom.json
data/t1_bom.json
```

额外使用两份真实 HF 模型 BOM 做深度冒烟验证：

```text
python main.py --mode deep \
  --before data/hf_models_bom/bert-base-uncased_bom.json \
  --after data/hf_models_bom/Qwen2.5-0.5B-Instruct_bom.json \
  --output outputs/check_deep_smoke.md
```

结果：

- 退出码：0
- 输出文件：`outputs/check_deep_smoke.md`
- t0：3 个资产、1 条 HF 血缘边、1 条图边。
- t1：2 个资产、1 条 HF 血缘边、1 条图边。
- Delta 检测到 1 个新增祖先和 1 个移除训练数据集事件。
- 传播后得到 4 个事件，均完成路径证书生成。

### 测试

```text
python -m pytest tests -q
```

结果：

```text
59 passed in 0.57s
退出码：0
```

## 6. 建议提交的文件

建议提交：

- `main.py`
- `outputs/extract_edges_removal_report.md`

可选提交验证产物：

- `outputs/check_basic.md`
- `outputs/check_deep_smoke.md`

不建议提交删除动作：

- `extract_edges.py` 未删除，保持原样。

约束遵守情况：

- 只修改了 `main.py`。
- 只新增了本报告和验证输出。
- 未修改 `extract_edges.py`。
- 未执行任何 `git` 命令。
- 未修改任务中列出的其他模块。
