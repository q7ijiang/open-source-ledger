# GitHub 最新代码同步与深度流水线验证报告

生成时间：2026-09-30 17:17 +08:00

仓库：`C:\Users\Qijiang\Documents\GitHub\open-source-ledger`

## 1. Git 同步结果

### 1.1 原始仓库状态

初始检查结果如下：

- 当前分支：`main`
- 本地 HEAD：`b508585c4da5354cd5e38909607eaba55fe5d1e2`
- 当前跟踪关系：`main...origin/main`
- 已跟踪文件没有本地修改
- 未跟踪内容主要是本次待验证的两个新模块和已生成产物：
  - `extract_edges.py`
  - `evidence_enricher.py`
  - `outputs/*.json`
  - `work/.deps/`
  - `work/verify_new_modules.py`

执行 `git stash push -u` 时，Git 在创建 `.git/index.lock` 时被当前桌面沙箱拒绝：

```text
error: Unable to create '.git/index.lock': Permission denied
error: could not write index
```

因此：

- 没有创建 stash
- 没有执行成功原始的 `git pull origin main`
- 没有产生 Git 冲突
- 没有执行 `git stash pop`
- 没有修改队友模块，也没有修改原始 BOM

该拒绝发生在 Git 元数据目录写权限层，不是仓库合并冲突。后续改用 GitHub 官方 API 和 codeload 精确获取 `main` 源码归档，避免用旧工作区伪造“已拉取”。

### 1.2 远端最新提交

验证过程中远端 `main` 继续前进了 3 个提交。最终再次确认：

- 远端分支：`main`
- 远端最终 HEAD：`6843e6bf9850808c19468928001f1aa53d3b52d1`
- 对应短 SHA：`6843e6b`
- 远端在最后一次确认时没有再变化

新增提交如下：

| SHA | 作者 | 时间 | 内容 |
|---|---|---|---|
| `6843e6b` | q7ijiang | 2026-09-30 17:12 +08:00 | Merge PR #3：合入真实 HF BOM 血缘提取工具与模块 8/9/10 验证产物 |
| `3376c95` | member-b | 2026-09-25 14:23 +08:00 | 新增 `work/extract_hf_lineage.py`，更新模块 8 路书 |
| `27943e2` | member-b | 2026-09-25 14:27 +08:00 | 新增 `out/` 下模块 8/9/10 端到端和真实数据验证产物 |

`6843e6b` 合入的文件：

- `docs/modules/08-build-graph.md`
- `work/extract_hf_lineage.py`
- `out/events.json`
- `out/graph_t0.json`
- `out/graph_t1.json`
- `out/hf_lineage/assets.json`
- `out/hf_lineage/edges.json`
- `out/hf_lineage/graph.json`
- `out/propagated.json`

更早的队友提交仍包括：

| SHA | 作者 | 内容 |
|---|---|---|
| `e211b7e` | member-b | 模块 4 支持 Debian 复合表达式并扩展许可证规则 |
| `d7ee865` | member-b | 实现 Delta 检测模块 9 |
| `d0324b8` | member-b | 实现风险传播和路径证书模块 10 |

### 1.3 实际用于验证的源码

由于原始 `.git` 不可写，最终验证使用：

- GitHub API 返回的精确提交 `6843e6b`
- codeload 下载的 `6843e6b` 官方源码归档
- 隔离目录：`work/latest-main-6843e6b/open-source-ledger-6843e6b`
- 将本地未提交的新模块 `extract_edges.py` 和 `evidence_enricher.py` 复制到该隔离源码目录

进一步比较确认：`6843e6b` 中 `build_graph.py`、`delta_engine.py`、`propagation_engine.py`、`license_db.py`、`bom_adapter.py`、`entity_resolver.py` 与本地 `b508585` 对应文件内容一致，仅工作区换行差异；新增提交主要增加 `work/extract_hf_lineage.py`、模块 8 文档及 `out/` 验证产物。

## 2. 队友模块实际接口清单

### 2.1 `build_graph.py`（模块 8）

输入：

- `--assets`：资产 JSON
  - 支持顶层数组
  - 也兼容 `{"assets": [...]}` 和 `{"nodes": [...]}`
  - 实际只依赖 `canonical_id`，并读取 `asset_type`、`name`、`version`、`license`、`snapshot_id`
- `--edges`：边 JSON
  - 支持顶层数组
  - 也兼容 `{"edges": [...]}`
  - 每条边读取 `source`、`target`、`edge_type`、`evidence_level`、`source_field`、`snapshot_id`

输出：

- JSON 对象，包含：
  - `node_count`
  - `edge_count`
  - `scc_count`
  - `nodes`
  - `edges`
  - `canonical_to_scc`
  - `scc`
  - `compressed.nodes`
  - `compressed.edges`

实际图节点字段：

```text
canonical_id, asset_type, name, version, license, snapshot_id, scc_id
```

与 `docs/接口约定.md` 对照：

- 边字段符合约定
- 图节点是资产节点的投影，不包含资产约定的 `purls` 和 `evidence_chain`
- 当前传播引擎不依赖这两个字段，但若其他模块把图节点当作完整资产节点读取，会缺字段

### 2.2 `delta_engine.py`（模块 9）

输入：

- `--before-assets`
- `--before-edges`
- `--after-assets`
- `--after-edges`
- 输入格式与模块 8 的 `load_assets`、`load_edges` 相同

输出：

- 顶层事件数组
- 每个事件字段：
  - `event_id`
  - `seed`
  - `change_type`
  - `before`
  - `after`
  - `path`
  - `evidence_level`
  - `decision`

每个 `before` / `after` 状态：

```text
license, purls, snapshot_id
```

覆盖的变更类型：

- `license_changed`
- `evidence_downgrade`
- `ancestor_added`
- `ancestor_removed`
- `dataset_added`
- `dataset_removed`

与 `docs/接口约定.md` 对照：

- 事件对象必需字段齐全
- `path` 初始为空数组，符合“由传播模块填充”的设计
- 祖先/数据集变更事件的 `seed` 语义与传播引擎冲突，详见第 5 节

### 2.3 `propagation_engine.py`（模块 10）

输入：

- `--events`：模块 9 输出的事件数组
- `--graph-before`：模块 8 输出的 t0 图 JSON
- `--graph-after`：模块 8 输出的 t1 图 JSON

输出：

顶层对象：

```json
{
  "events": [],
  "path_certificates": []
}
```

传播后事件字段沿用事件约定，并补充：

- `path`
- `evidence_level`
- `decision`
- `event_id` 对受影响资产追加 `-pNN`

路径证书字段包括：

```text
certificate_id, event_id, seed, affected, change_type, path,
hop_count, weakest_evidence, decision, termination,
missing_ancestor, path_fingerprint, verified
```

与 `docs/接口约定.md` 对照：

- 传播后事件结构和路径步骤符合约定
- 路径证书对象未在 `docs/接口约定.md` 中定义
- `path_certificates` 是接口扩展，不是约定中的标准对象

### 2.4 `license_db.py`（模块 4）

核心数据：

- `LicenseRule` 冻结 dataclass：
  - `canonical_id`
  - `name_zh`
  - `category`
  - `permissions`
  - `duties`
  - `prohibitions`
  - `risk_level`
  - `is_ai_license`
  - `spdx_like`
  - `note`
- `LICENSE_DB`：24 条许可证规则
- `LICENSE_ALIASES`：常见别名到规范 ID 的映射

主要函数：

| 函数 | 输入 | 输出 |
|---|---|---|
| `normalize_license(name)` | 任意许可证写法 | 规范 ID 或 `None` |
| `split_license_text(text)` | 复合许可证文本 | 许可证项数组 |
| `get_rule(name)` | 许可证名称 | `LicenseRule` 或 `None` |
| `get_triplets(name)` | 许可证名称 | P/D/P 三元组字典或 `None` |
| `classify(name)` | 许可证名称 | 风险类别字符串 |
| `risk_level(name)` | 许可证名称 | 1 至 5 的整数或 `None` |
| `is_ai_license(name)` | 许可证名称 | 布尔值 |
| `evaluate_expression(text)` | 复合表达式 | `items`、`max_risk_level`、`worst_category`、`unknown_items` |
| `compare_direction(old, new)` | 新旧许可证 | 新旧规范信息、方向、是否变严、是否涉及 AI 许可证 |
| `export_db()` | 无 | 规则库 JSON 结构 |

与接口约定对照：

- 模块 4 不直接读取资产 JSON，不构成 JSON 接口冲突
- 输出结构可作为许可证判断和报告层的内部数据接口
- 实际测试 `MIT -> GPL-3.0-only` 返回 `risk_increased=true`、`strong_copyleft`

### 2.5 最新提交新增的 `work/extract_hf_lineage.py`

该工具是模块 8 的真实数据补充，不属于用户指定的四个队友模块，但它是最新 `main` 的新增内容，会影响后续数据入口选择。

输入：

- `--bom-dir`：默认 `data/hf_models_bom`
- `--output-dir`：默认 `out/hf_lineage`

输出：

- `assets.json`
- `edges.json`
- `graph.json`

实测：

- 读取 9 份真实 HF BOM
- 输出 18 个资产节点
- 输出 12 条边
- 边类型：8 条 `derived_from`，4 条 `trained_on`
- 图：18 节点、12 边、18 个 SCC

风险：

- 18 个资产跨 7 个 `snapshot_id`
- 18 个资产的 `evidence_chain` 全为空数组
- 11 个资产的 `license` 使用空字符串
- 它与 `extract_edges.py` 在“从 BOM 提取血缘边”上职责重叠，但统计口径和证据等级不同

## 3. 两个新模块在最新代码上的验证结果

### 3.1 样本 BOM 标准链路

执行命令：

```powershell
python bom_adapter.py --input data\sample_bom.json --output outputs\assets.json --snapshot-id basic-20260930
python entity_resolver.py --input outputs\assets.json --output outputs\assets_deduplicated.json --log outputs\merge_log.json
python extract_edges.py --input outputs\assets_deduplicated.json --output outputs\edges.json
python build_graph.py --assets outputs\assets_deduplicated.json --edges outputs\edges.json --output outputs\graph_sample.json
python evidence_enricher.py --input outputs\assets_deduplicated.json --output outputs\assets_enriched.json
```

实际结果：

| 步骤 | 实际结果 |
|---|---|
| `bom_adapter.py` | 72 个组件，4 种许可证，141 条证据 |
| `entity_resolver.py` | 72 个资产去重为 71 个；合并 1 对；跳过 1 对 `version_mismatch` |
| `extract_edges.py` | 提取 126 条边；全部为 `depends_on`，证据等级 B；126 条三元组重复被去重；0 个缺失端点 |
| `build_graph.py` | 成功读取边并建图；70 个节点、126 条边、70 个 SCC、0 个环 |
| `evidence_enricher.py` | 71 次远程请求；70 条 A 级成功证据；1 条 C 级网络失败；处理前 2 个无证据资产，处理后 0 个 |

`assets_enriched.json` 校验：

- 顶层为数组
- 71 个资产
- 8 个资产必填字段全部存在
- 210 条证据条目逐项校验 `evidence_chain` 必填字段，全部通过
- 证据等级：209 条 A，1 条 C
- 证据状态：209 条 `ok`，1 条 `network_error`
- 按 API 分布：CycloneDX 139 条、npm 68 条、PyPI 2 条、Hugging Face 1 条
- 所有 `snapshot_id` 均为 `basic-20260930`

但发现一个上游数据问题：

- `entity_resolver.py` 输出仍有重复 `canonical_id`
- 具体为两个 `package:ms`
  - 一个是 `ms@2.0.0`
  - 一个是 `ms@2.1.3`
- 因此 71 条资产记录进入 `build_graph.py` 后只形成 70 个图节点

字段语义问题：

- `bom_adapter.py` 对未知许可证写出空字符串 `""`，不是接口约定要求的 `null`
- 样本结果中 `package:requests` 和 `package:flask` 的 `license` 为 `""`
- 新模块 `evidence_enricher.py` 原样保留了该值；不是补全模块引入的问题

### 3.2 `edges.json` 与 `build_graph.py` 的兼容性

已实际运行 `build_graph.py` 读取 `edges.json`，结果成功：

```text
资产节点：70
血缘边：126
SCC 分量：70（含 0 个环）
```

结论：

- `extract_edges.py` 输出的纯边数组可以被 `build_graph.py` 正确读取
- 边字段完整，没有缺字段
- 样本边的所有端点都能在资产集合中找到
- 唯一的节点数差异来自上游重复 `canonical_id`，不是边格式问题

### 3.3 现有回归测试

隔离环境没有预装 `pytest`，且安装 `pytest` 时网络下载长时间阻塞，已中止。测试文件没有 pytest fixture 或参数化用例，因此改用 Python 直接导入并执行全部无参数 `test_*` 函数：

- 通过：39
- 失败：0

覆盖：

- `test_build_graph.py`
- `test_delta_engine.py`
- `test_license_db.py`
- `test_propagation_engine.py`

## 4. 深度流水线串联结果

### 4.1 测试快照选择

使用两份真实 HF BOM：

- t0：`data/hf_models_bom/all-MiniLM-L6-v2_bom.json`
- t1：`data/hf_models_bom/bert-base-uncased_bom.json`

选择原因：

- t0 有 22 个组件
- t1 有 3 个组件
- t0 同时包含 `derived_from`、`trained_on`、`depends_on`
- 能触发新增和移除事件

### 4.2 每一步实际输出

| 步骤 | 输出 | 实际结果 |
|---|---|---|
| `bom_adapter.py` -> t0 | `outputs/assets_t0.json` | 22 个资产，1 条证据 |
| `bom_adapter.py` -> t1 | `outputs/assets_t1.json` | 3 个资产，1 条证据 |
| `extract_edges.py` -> t0 | `outputs/edges_t0.json` | 23 条边：1 条 `derived_from`、1 条 `trained_on`、21 条 `depends_on`；1 个缺失祖先节点 |
| `extract_edges.py` -> t1 | `outputs/edges_t1.json` | 3 条边：0 条 `derived_from`、1 条 `trained_on`、2 条 `depends_on`；0 个缺失端点 |
| `build_graph.py` -> t0 | `outputs/graph_t0.json` | 23 个节点、23 条边、23 个 SCC、0 个环 |
| `build_graph.py` -> t1 | `outputs/graph_t1.json` | 3 个节点、3 条边、3 个 SCC、0 个环 |
| `delta_engine.py` | `outputs/events.json` | 26 个事件 |
| `propagation_engine.py` | `outputs/certificates.json` | 26 个传播后事件、0 张路径证书 |

t0 的缺失祖先：

```text
model:MiniLM-L6-H384-uncased
```

`build_graph.py` 已按设计自动创建该节点，但节点无资产元数据，供传播层判定缺失祖先。

Delta 事件分布：

```text
ancestor_added:   2
ancestor_removed: 22
dataset_added:    1
dataset_removed:  1
```

判定分布：

```text
RISK_POTENTIAL:  23
RISK_CONFIRMED:   2
UNDETERMINED:     1
```

事件对象校验：

- 26 个事件的 8 个必填字段全部存在
- `before` / `after` 的状态字段全部存在
- `path` 全部为空数组，这是模块 9 的初始状态
- 没有 `license_changed` 或 `evidence_downgrade`，因为所选两份 BOM 没有相同资产上可比较的许可证变更

### 4.3 传播结果与根因诊断

原样执行 `propagation_engine.py` 时：

```text
种子事件：26
传播后事件：26
路径证书：0
```

也就是说，深度命令链路全部退出成功并生成了文件，但风险传播没有产生任何受影响资产。

根因是事件种子方向：

- `delta_engine.py` 对边新增/移除事件设置 `seed = edge["source"]`
- 图方向是“下游资产 -> 上游祖先/数据集”
- 传播引擎从 seed 沿反向边查找依赖者
- 当前 seed 是模型本身，模型没有上游依赖者，所以反向 BFS 立即终止
- 正确语义应是：祖先/数据集发生变化，从 `edge["target"]` 向依赖它的资产传播

为了确认这不是传播引擎本身的路径算法错误，执行了一次不改队友代码的诊断：

- 读取原始 `events.json`
- 按 Delta 的排序规则重新关联新增/移除边
- 只在内存和诊断输出中将边变更事件的 `seed` 改为 `edge["target"]`
- 调用原始 `propagation_engine.propagate`

诊断结果：

```text
修正事件：26
传播后事件：52
路径证书：26
非空路径事件：26
终止原因：全部 exhausted
```

这证明：

- 传播引擎的反向 BFS、证据聚合和证书生成逻辑可以工作
- 当前深度流水线的问题位于模块 9 的事件种子语义，而不是模块 10 的遍历实现
- `extract_edges.py` 提供的边方向与模块 8/10 的图方向是一致的

### 4.4 最新队友批量血缘工具补充验证

执行：

```powershell
python work\extract_hf_lineage.py --bom-dir data\hf_models_bom --output-dir outputs\hf_lineage_recheck
```

实际结果：

```text
真实 BOM 数：9
资产节点：18
血缘边：12
SCC 分量：18
边类型分布：derived_from=8, trained_on=4
```

结构上没有缺必填字段，但它不是 t0/t1 快照流水线：

- 18 个资产分布在 7 个不同 `snapshot_id`
- `evidence_chain` 全为空
- 11 个 `license` 为空字符串

因此该工具适合演示全局真实 HF 血缘图，不应直接替代两个新模块的逐快照输入链路。

## 5. 发现的接口冲突和修正建议

### 5.1 高优先级：Delta 边变更事件 seed 方向错误

- 模块：`delta_engine.py`
- 字段：`seed`、`before`、`after`
- 当前实际：
  - 祖先/数据集新增或移除时，`seed = edge["source"]`
  - `before` / `after` 也取边起点资产的状态
- 接口语义期望：
  - 边终点 `edge["target"]` 才是发生新增/移除变化的祖先或数据集
  - 传播应从该变化资产开始，反向找到受影响的下游资产
- 影响：
  - 当前深度流水线命令能跑完
  - 但 26 个事件传播后仍是 26 个事件，路径证书为 0
  - 祖先新增/移除风险没有实际扩散到模型或下游资产
- 建议：
  - 改 `delta_engine.py`
  - 对 `ancestor_added`、`ancestor_removed`、`dataset_added`、`dataset_removed` 使用 `edge["target"]` 作为 `seed`
  - `before` / `after` 应取目标资产的变更前后状态
  - 可增加 `changed_ref` 或类似字段，保留被变更资产的明确引用
  - 不建议在 `propagation_engine.py` 里猜测事件原本对应的边

### 5.2 高优先级：同一名称不同版本产生重复 canonical_id

- 模块：`bom_adapter.py`，并与 `entity_resolver.py` 有关
- 字段：`canonical_id`
- 当前实际：
  - `bom_adapter.py` 生成 `package:ms`
  - 两个版本 `2.0.0` 和 `2.1.3` 被判为 `version_mismatch`，没有合并
  - 两条记录仍然都保留 `canonical_id = package:ms`
- 接口期望：
  - `canonical_id` 在一次分析范围内稳定且唯一
  - 不同版本如果不能合并，就应有不同的唯一标识
- 影响：
  - `assets_deduplicated.json` 有 71 条记录，但只有 70 个唯一 `canonical_id`
  - `build_graph.py` 会合并同名 ID，导致独立资产节点丢失
- 建议：
  - 优先改 `bom_adapter.py`，对不能合并的不同版本生成版本限定 ID，例如 `package:npm/ms@2.0.0`
  - 或由 `entity_resolver.py` 在版本冲突时输出唯一 ID
  - 同时更新 `docs/接口约定.md`，明确 `canonical_id` 的版本化规则

### 5.3 中优先级：图节点不满足完整资产节点字段

- 模块：`build_graph.py`
- 字段：`purls`、`evidence_chain`
- 当前实际：
  - `graph_to_dict()` 输出的节点只有 `canonical_id`、`asset_type`、`name`、`version`、`license`、`snapshot_id`、`scc_id`
  - 丢失资产节点的 `purls` 和 `evidence_chain`
- 接口期望：
  - 如果图节点声明为资产节点，则应按 `docs/接口约定.md` 保留资产必填字段
- 影响：
  - 当前 `propagation_engine.py` 只依赖 `asset_type`，所以本次运行未阻塞
  - 后续如果从图 JSON 重建资产并做证据分析，会丢失证据链
- 建议：
  - 改 `build_graph.py`，在图节点中保留 `purls` 和 `evidence_chain`
  - 或在文档中明确图节点是资产投影，并禁止下游把它当完整资产节点使用

### 5.4 中优先级：路径证书格式未纳入接口约定

- 模块：`propagation_engine.py`
- 字段：`path_certificates`
- 当前实际：
  - 输出为对象 `{ "events": [...], "path_certificates": [...] }`
  - 证书包含路径、终止原因、缺失祖先、指纹、验证状态等字段
- 接口期望：
  - `docs/接口约定.md` 只定义了资产、血缘边和事件对象，没有定义路径证书
- 影响：
  - 集成方无法从约定文档判断 `certificates.json` 的顶层结构和证书必填字段
- 建议：
  - 优先更新 `docs/接口约定.md`，增加路径证书对象
  - 如果集成方期望 `certificates.json` 是纯数组，则需要另行约定；当前实现不是纯数组

### 5.5 中优先级：最新队友血缘工具与新模块职责重叠

- 模块：`work/extract_hf_lineage.py`
- 字段：`assets.json`、`edges.json`
- 当前实际：
  - 批量读取 9 份 BOM，合并为 18 个资产和 12 条边
  - 资产分布在 7 个 `snapshot_id`
  - 18 条 `evidence_chain` 为空，11 个 `license` 为空字符串
- 接口期望：
  - 资产列表应服务于明确的快照比较
  - 未知许可证应为 `null`
  - 同一流水线应明确由谁负责边提取
- 影响：
  - 与 `extract_edges.py` 功能重叠
  - 如果直接把两个工具的边合并，可能产生重复边、不同证据等级和不同语义分类
- 建议：
  - 将该工具定位为“全量真实 HF 血缘演示”，不要作为 t0/t1 Delta 输入
  - 或增加逐 BOM/逐快照输出模式
  - 明确 `extract_edges.py` 与 `work/extract_hf_lineage.py` 的边界
  - 统一空许可证为 `null`

### 5.6 低优先级：未知 version 和 license 使用空字符串

- 模块：`bom_adapter.py`
- 字段：`version`、`license`
- 当前实际：
  - `version` 使用空字符串
  - `license` 使用空字符串
- 接口期望：
  - 未知值写 `null`
- 影响：
  - 当前下游大多能用 `clean_text()` 兼容
  - 严格按 JSON Schema 或接口约定验收时会判为语义不一致
- 建议：
  - 改 `bom_adapter.py`
  - 无版本时写 `version = None`
  - 无许可证时写 `license = None`
  - 更新相关测试断言

## 6. 结论

在最终确认的 `main@6843e6b` 上：

1. `extract_edges.py` 可以正确串联上游资产文件，并输出 `build_graph.py` 能直接读取的边数组。
2. `evidence_enricher.py` 可以处理去重资产并输出满足资产接口必填字段的证据链。
3. 样本链路从 `bom_adapter.py` 到 `evidence_enricher.py` 实测可以跑通，格式校验通过。
4. 深度命令链路从 BOM 到 `certificates.json` 全部退出成功，但语义上没有真正完成风险传播：
   - `delta_engine.py` 生成了 26 个事件；
   - `propagation_engine.py` 输出了 26 个传播后事件；
   - 路径证书为 0；
   - 根因是边变更事件的 seed 被设置为下游起点，而不是发生变化的祖先或数据集终点。
5. 在仅对事件 seed 做诊断性修正后，传播引擎可以生成 26 张路径证书，说明传播算法本身可工作。

最终判定：

- **命令层面：深度流水线可以端到端执行。**
- **结果层面：当前 `main` 上还不能视为验收通过，因为祖先/数据集变更没有产生路径证书。**
- 新模块本身与 `build_graph.py` 的主要边接口兼容；需要优先修复的是模块 9 的事件 seed 语义，其次修复 `canonical_id` 唯一性并补齐图节点和证书格式约定。
