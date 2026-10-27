# HTML 渲染与 Diff 交互场景测试

## 测试目的

验证项目血缘图、许可证 Diff 图、聚合节点交互和报告窗口在受控数据上的布局与输出。重点覆盖同一模型在 `t0/t1` 中位置稳定、上游层级清晰、风险传播目标可区分以及 AI 状态可查看。

## 文件与覆盖范围

| 文件 | 覆盖内容 |
| --- | --- |
| `test_render_lineage_layout.py` | 上游分层、共享祖先、孤立模型和异常循环下的节点保留 |
| `test_render_graph_interaction.py` | 项目图聚合节点默认折叠和点击展开 |
| `test_render_diff_layout.py` | `t0/t1` 共用坐标、节点位置稳定、AI 状态和报告下载入口 |
| `test_render_diff_decisions.py` | 传播决策优先级、变更目标标注、过滤条件和真实血缘边属性 |
| `test_render_link_details.py` | 节点详情中的 ModelScope 模型主页与原始 API 证据链接 |

## 测试数据

- `tests/fixtures/projects/qwen_image_license_tightening/upstream/`：当前项目 Diff 主验收输入，含 8 个具体模型与 9 条上游血缘边。
- 旧的 `data/test_scenarios/` 下游聚合与 Adapter 夹具已退役；渲染测试不再从生产目录读取历史导出文件。
- `tests/fixtures/projects/real_modelscope/snapshots/full/scenarios/`：直接变更和上游变更验收快照。

## 运行方式

```powershell
python -m pytest tests/scenarios/rendering -q
```

## 真实性边界

- `t0` 是冻结的上游许可证观测，`t1` 是 `simulation=true` 的风险演练数据。
- 图中节点位置用于对照前后快照，不代表模型在真实世界中的供应链位置。
- AI 状态和 AI 详情只展示辅助证据，不改变规则引擎给出的许可证判定。
- 渲染测试验证数据契约和关键交互，不替代人工浏览器验收或多浏览器兼容性测试。
