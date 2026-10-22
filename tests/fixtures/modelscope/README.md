# tests/fixtures/modelscope —— ModelScope 测试数据

> 用途：供测试与回归使用的 **ModelScope 真实 API 快照与中间产物**（不是验证报告）。
> 从 `outputs/modelscope_validation/` 迁移而来（2026-10-21），保证清仓库时测试数据不丢失、可离线复现。

## 目录结构

```
modelscope/
├── detail_*.json              ModelScope 模型详情 API 原始快照（Detail）
├── files_*.json               ModelScope 模型文件列表 API 原始快照（Repo Files）
├── lineage_*.json             ModelScope 模型血缘 API 原始快照（Lineage）
├── diff/                      --diff 时间对比验证数据
│   ├── diff_events.json       变更事件（delta 引擎输出）
│   └── diff_certificates.json 路径证书（传播引擎输出）
├── model_exports/             --model/--project 标准导出与判定验证数据
│   ├── Qwen__Qwen-Image-2.1/{bom,graph}.json
│   ├── Qwen__Qwen2.5-7B-Instruct/{bom,graph}.json
│   ├── XingChen-AGI__TeleOCR/{bom,graph}.json
│   ├── multi_model_project/{bom,graph}.json
│   └── test_project/bom.json  --project 扫描输入 BOM（Qwen2.5-7B-Instruct）
├── ms_viz/                    渲染层可视化数据
│   ├── viz_data.json          构造数据版血缘图数据（Qwen-Image-2.1 聚合降维）
│   ├── viz_real_data.json     真实数据版血缘图数据（14 节点 / 11 边）
│   ├── graph_t1.json          t1 快照的图结构（--diff 时间对比用）
│   ├── events.json            diff 变更事件
│   └── certificates.json      路径证书（--diff 传播用）
└── project_extract/           --project 真实项目抽取产物
    ├── assets.json            资产清单（含聚合节点 count）
    ├── edges.json             血缘边
    └── graph.json             建图结果（整体判定）
```

## 各文件验证点

| 文件 | 验证内容 | 对应测试/脚本 |
|---|---|---|
| `lineage_Qwen__Qwen-Image-2.1.json` | ModelScope lineage 接口返回 SonModels（Adapters/Finetunes/Quantizations 聚合计数） | `work/extract_modelscope_lineage.py` |
| `detail_*.json` / `files_*.json` | 模型详情/文件列表字段映射（licenseName、License=other 等） | `modelscope_adapter.py` 解析 |
| `diff/diff_events.json` + `diff_certificates.json` | --diff 全链路：变更事件 + 传播证书（C2 场景：事件 2 / 传播后 8 / 证书 6） | `main.py --diff --before --after` |
| `model_exports/*/bom.json` | 标准 CycloneDX 1.7 导出（含 metadata.timestamp / pedigree.ancestors / decision） | `bom_adapter.py` / `main.py --model/--project` |
| `model_exports/*/graph.json` | 建图判定结果（RISK_CONFIRMED/POTENTIAL/SAFE/UNDETERMINED） | `main.py --model/--project` 渲染层取 decision 着色 |
| `model_exports/test_project/bom.json` | --project 扫描输入 BOM（modelscope 组件类型/Qwen namespace） | `main.py --project test_project` |
| `ms_viz/viz_data.json` | 渲染层森林分层布局 + 风险传播红线 + 形状图例 | `outputs/modelscope_validation/build_viz_html.py` |
| `ms_viz/viz_real_data.json` | 真实数据血缘图（14 节点 / 11 边，主模型黄灯） | `outputs/modelscope_validation/gen_viz_real.py` |
| `project_extract/graph.json` | --project 全链路建图与整体判定（UNDETERMINED/POTENTIAL） | `main.py --project` |
| `ms_viz/events.json` + `certificates.json` | --diff 变更事件 2 / 传播后 8 / 路径证书 6 | `tests/test_diff_*` |

## 使用方式

测试代码统一通过 `tests/conftest.py` 的 `FIXTURES` 定位：

```python
from conftest import FIXTURES
p = FIXTURES / "modelscope" / "lineage_Qwen__Qwen-Image-2.1.json"
```

## 注意事项

- 这些是 **2026-10 期间 ModelScope API 的真实返回快照**，作为离线测试基准；若 ModelScope 字段演进，需重新跑 `test_modelscope.py`（根目录）刷新快照。
- 聚合节点 count 属实时漂移数据，测试只断言结构/判定，不断言具体 count 数值。
- 原始 HTML/PNG 渲染产物保留在 `outputs/modelscope_validation/`，此处只存数据。
