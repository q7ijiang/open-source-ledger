# extract_edges.py 依赖清理最终报告

生成日期：2026-10-03

## 1. work/verify_new_modules.py 的处理决定

### 脚本用途

`work/verify_new_modules.py` 是一个早期接口断言脚本，主要做了三类检查：

- 读取 `outputs/assets_enriched.json`、`outputs/edges.json` 及 t0/t1、图、事件等生成产物；
- 校验资产、证据链、边和事件字段是否满足旧接口约定；
- 在 `validate_synthetic_edges()` 中直接调用 `extract_edges()`，检查通用提取器能否生成 `derived_from`、`trained_on` 和 `depends_on` 三类边，并检查重复边统计。

### 脚本性质

它是早期一次性验证脚本，不是正式测试：

- 位于 `work/`，没有纳入 `tests/`；
- 断言依赖特定生成产物和固定数字，如 `offline_network_errors == 71`、t0 零边、t1 单边；
- 合成边检查绑定的是已经退出主线的通用 `extract_edges`，尤其强制要求 `depends_on`；
- `tests/` 共 59 个测试，未引用该脚本的函数或断言。

### Git 状态

- `.gitignore` 未忽略 `work/verify_new_modules.py`，只忽略 `work/.deps/`。
- 通过只读解析 `.git/index` 检查，该文件不在当前索引中，因此当前检出状态下不是已跟踪文件，也不能作为当前分支的已提交文件处理。
- 为遵守约束，本次未执行任何 `git` 命令。
- 仓库已有 `outputs/github_sync_validation_report.md` 也将其列为当时未跟踪的新脚本。

### 决定与理由

决定删除整个 `work/verify_new_modules.py`，不进行改写。

理由：

- 其主要接口断言服务于已被主线替代的通用 `extract_edges` 工作流；
- 硬编码产物数量和旧边类型，不适合作为长期测试；
- 正式测试、构建图、Delta 和传播模块已有独立测试覆盖相关下游接口；
- 当前主线只保留 HF 模型的 `derived_from` 和 `trained_on`，不再使用通用 `depends_on`，保留该脚本会继续反向约束已退役功能。

全仓库 Python 文件检查未发现任何其他模块导入 `work.verify_new_modules` 或 `verify_new_modules`。

## 2. extract_edges 的删除前引用位置

遍历全部 `.py` 文件，包括隐藏和被忽略目录，删除前的引用如下：

| 文件 | 行号 | 引用方式 |
| --- | ---: | --- |
| `work/verify_new_modules.py` | 2 | 文档字符串提到 `extract_edges.py` |
| `work/verify_new_modules.py` | 16 | `from extract_edges import extract_edges` 导入函数 |
| `work/verify_new_modules.py` | 143 | `edges, stats = extract_edges(assets)` 调用函数 |
| `extract_edges.py` | 12 | 文档字符串中的命令行用法 |
| `extract_edges.py` | 456 | `extract_edges()` 函数定义 |
| `extract_edges.py` | 605 | 文件自身 `main()` 内部调用 `extract_edges()` |

除 `extract_edges.py` 自身外，唯一外部 Python 依赖是 `work/verify_new_modules.py`。删除该验证脚本后再次搜索，已无其他 Python 文件导入或调用 `extract_edges`。

历史报告 `outputs/extract_edges_removal_report.md`、`outputs/github_sync_validation_report.md` 和 `outputs/merge_rule_competition_ready.md` 仍有文字记录和旧命令示例，但它们不是运行时 Python 引用。

## 3. 文件删除结果

已按先处理后删除的顺序执行：

1. 删除 `work/verify_new_modules.py`。
2. 再次检查全仓库 Python 引用，未发现其他外部依赖。
3. 删除 `extract_edges.py`。

删除后检查：

```text
verify_new_modules_exists=False
extract_edges_exists=False
```

额外确认：

```text
importlib.util.find_spec("extract_edges")
结果：None
```

当前目录下仍可能保留 Python 自动生成的 `__pycache__/extract_edges.cpython-310.pyc`，它属于被忽略的缓存文件，不是可导入源码，`find_spec` 确认无法再解析到 `extract_edges` 模块。

## 4. 验证结果

### 基础模式

实际执行：

```text
python main.py --mode basic --input data/sample_bom.json --output outputs/check_basic_after_removal.md
```

结果：

- 退出码：0
- 输出文件：`outputs/check_basic_after_removal.md`
- BOM 解析资产数：72
- 实体对齐后资产数：71
- HF 血缘边数：0
- 支持远程证据的 purl 数：71
- 网络失败降级数：71
- 处理前无证据资产：2
- 处理后无证据资产：0
- 报告正常生成，并明确标注通用 `depends_on` 边已移除。

网络请求在当前环境均降级为 `network_error`，但入口正常完成，不影响本次删除验证。

### 测试

实际执行：

```text
python -m pytest tests -q
```

结果：

```text
59 passed in 0.59s
```

退出码：0。

`work/verify_new_modules.py` 已被删除，因此没有改写版可运行；仓库中也没有其他调用它的脚本。

## 5. 建议提交的文件

建议提交：

- `work/verify_new_modules.py` 的删除
- `extract_edges.py` 的删除
- `outputs/extract_edges_removal_final_report.md`
- `outputs/check_basic_after_removal.md`，作为本次基础模式验证产物

注意：只读检查当前 `.git/index` 时，`work/verify_new_modules.py` 和 `extract_edges.py` 均不在索引中，因此在本机当前检出状态下它们属于未跟踪文件。若另一分支或远端仓库已将这两个文件纳入版本控制，则应在相应环境中提交这两个删除动作；若当前分支本来就未跟踪它们，则代码层面的 Git 变化只有验证报告和验证输出。

未修改任务限制中的以下文件：

- `main.py`
- `bom_adapter.py`
- `entity_resolver.py`
- `evidence_enricher.py`
- `build_graph.py`
- `delta_engine.py`
- `propagation_engine.py`
- `license_db.py`
- `work/extract_hf_lineage.py`

## 6. 是否需要通知 B

不需要 B 紧急修改代码，但建议同步告知 `extract_edges.py` 已退役。

`work/extract_hf_lineage.py` 已提供当前主线所需的对应能力：

- 从 `pedigree.ancestors` 提取 `derived_from`；
- 从 `modelCard.modelParameters.datasets` 提取 `trained_on`；
- 返回 `(assets, edges)`，供 `main.py` 合并资产和构建血缘图。

它没有通用 `extract_edges` 的以下旧能力：

- 从 BOM `dependencies` 提取 `depends_on`；
- 返回旧版 `duplicate_count` 等通用提取统计。

这两项能力已不属于当前 Hugging Face 模型血缘主线，因此不需要为删除 `extract_edges.py` 而在 `extract_hf_lineage.py` 中补实现。若后续重新需要通用包依赖血缘，应作为新需求单独设计，而不要恢复旧脚本耦合。

## 7. 约束遵守情况

- 未执行任何 `git` 命令。
- 只删除了 `work/verify_new_modules.py` 和 `extract_edges.py`。
- 未修改受限模块。
- 基础模式与测试均为实际运行结果。
- 最终报告使用中文。
