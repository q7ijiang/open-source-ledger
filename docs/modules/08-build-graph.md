# 模块 8：血缘图构建

| 项目 | 内容 |
|---|---|
| 负责人 | B |
| 状态 | 待验收 |
| 完成日期 | 2026-09-20 |
| 对应任务 | 深度部分 · 模块 8 |

## 一句话摘要

用 networkx 把资产与血缘边构建成有向图，支持 derived_from / trained_on / depends_on 三类边，并做强连通分量（SCC）压缩，输出凝聚图供 Delta 检测与风险传播使用。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| 资产列表 JSON | 模块 1/2 输出，如 `assets.json` | 接口约定的资产节点数组 |
| 血缘边 JSON | 深度测试数据 / 模型卡片解析 | 接口约定的血缘边数组（source/target/edge_type/evidence_level） |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| 血缘图代码 | `build_graph.py` | 建图 + SCC 压缩 + 序列化 |
| 图结构 JSON | 如 `out/graph_t0.json` | 节点、边、SCC、压缩后节点与边 |

## 为什么要做

1. 许可证变更的风险不是孤立的：基座模型换许可证，下游微调模型、依赖它的服务都会受影响，需要一张可遍历的血缘图。
2. 血缘关系可能成环（A 依赖 B、B 依赖 A），直接遍历会死循环；SCC 压缩把环折叠成超节点，保证传播安全终止。
3. 模块 9（Delta 检测）、模块 10（风险传播）都以图结构为输入，统一图格式是三模块协作的基础。

## 具体怎么做

### 步骤 1：构建图

`build_graph(assets, edges)`：
- 使用 `networkx.MultiDiGraph`，同一对节点间的多条并行边（如同时 derived_from 与 depends_on）全部保留；
- 节点属性：asset_type / name / version / license / snapshot_id；
- 边指向但资产列表中没有的节点会被自动创建（无元数据）——这正是"缺失祖先"场景，供模块 10 判定 UNDETERMINED。

### 步骤 2：SCC 压缩

`compress_scc(graph)`：
- 用 `strongly_connected_components` 找强连通分量，按节点数从大到小排序；
- 输出 `canonical_to_scc`（canonical_id → scc_id）和凝聚图；
- 凝聚图节点含 `members`、`size`、`is_cycle`（size > 1）；凝聚边按 weakest link 聚合并行边证据。

### 步骤 3：序列化

`graph_to_dict()` 输出完整 JSON：`nodes`、`edges`、`canonical_to_scc`、`scc`、`compressed.{nodes,edges}`，并附统计（node_count / edge_count / scc_count）。

## 得到了什么

以 t1 测试快照为例（7 个资产 + 7 条边）：
- 图含 8 个节点（Qwen2.5-7B 由边自动创建，标记为缺失祖先）；
- 识别出 1 个 SCC 环：`example-parser ↔ lib-x`；
- 压缩图边证据按 weakest link 正确聚合。

## 真实数据验证（2026-09-25 首版；2026-10-01 版本化对齐 v0.3）

配合 A 的真实 HF 模型 BOM（`data/hf_models_bom/`，9 份 CycloneDX），新增血缘提取工具 `work/extract_hf_lineage.py`，把 `pedigree.ancestors`（→ `derived_from`）与 `modelCard.modelParameters.datasets`（→ `trained_on`）转为接口约定格式并建图：

```
python work/extract_hf_lineage.py --bom-dir data/hf_models_bom --output-dir out/hf_lineage
```

结果（v0.3，canonical_id 已版本化）：
- **18 个资产节点（含缺失祖先自动补建）、12 条血缘边（8 derived_from + 4 trained_on）**；
- canonical_id 为版本化格式（如 `model:huggingface/meta-llama/Llama-2-7b-chat-hf@f5db02...`），由 `bom_adapter.build_asset_identifiers()` 生成，不再手拼；
- 资产节点补齐 `entity_key / merge_status / reason_code / rule_version / purls / evidence_chain / hashes`；
- **边证据等级 B**（源数据是 HF 官方模型卡字段，但载体是 cdxgen 产出的 CycloneDX BOM，按接口约定 v0.2「工具产物或结构化依赖证据」归为 B 级——两个口径不混用）；
- 祖先引用版本补齐：GGUF 等派生模型的 `pedigree.ancestors` 引用不带版本时，若全局存在同 entity_key 的带版本主模型，则对齐到该版本化 ID（演示 18 节点/12 边保持）；
- 18 个 SCC 分量（真实 HF 血缘为 DAG，无环，符合预期）；
- HF 特化能力全部保留：递归展开 pedigree.ancestors、数据集 purl 归一化、`?repository_url=...` query 剥离、缺失祖先自动补建。

图节点字段（v0.3 起）：
`canonical_id / entity_key / asset_type / name / version / purls / license / evidence_chain / snapshot_id / merge_status / reason_code / rule_version / hashes / scc_id`——下游传播可直接取到证据链与合并状态。

## 暴露了什么问题

| 问题 | 影响 | 交给哪个模块解决 |
|---|---|---|
| 边引用资产可能不在 BOM 资产列表中 | 祖先元数据缺失 | 模块 10 对缺失祖先强制 UNDETERMINED |
| 同一对资产可能有多条不同类型边 | 路径选择需要明确规则 | 模块 10 选边：先取证据最弱，同等级按 derived_from > trained_on > depends_on |
| 真实 BOM 的模型卡片数据集 ref 常带 URL 参数 | canonical_id 需剥离参数 | 已由 `bom_adapter.parse_purl_identity` 处理（`?repository_url=...` 不进入 id） |

## 如何验证

1. `python build_graph.py --assets tests/fixtures/deep_t1_assets.json --edges tests/fixtures/deep_t1_edges.json --output out/graph_t1.json`。
2. 打开输出 JSON，确认节点数、边数、SCC 数与统计一致。
3. `python work/extract_hf_lineage.py`：真实数据建图可复现（统计同上）。
4. `python -m pytest tests/test_build_graph.py`：回归测试全部通过。

## 相关文件

| 文件 | 路径 |
|---|---|
| 血缘图代码 | `build_graph.py` |
| 血缘提取工具（真实数据） | `work/extract_hf_lineage.py` |
| 测试夹具 | `tests/fixtures/deep_t0/t1_*.json` |
| 回归测试 | `tests/test_build_graph.py` |

## 给队友的话

- 对 A：模块 13 集成时，`build_graph.py` 的 `load_assets/load_edges/build_graph` 可直接 import，无需重新解析。
- 对 C：深度测试数据（t0/t1 BOM）只需保证资产列表和血缘边符合接口约定，`build_graph` 会处理其余。
- 对 A/C：图 JSON 的 `scc` 字段已内置在输出中，传播引擎会优先复用，避免重复计算。
