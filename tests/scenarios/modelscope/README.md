# ModelScope 扫描与 BOM 场景测试

## 测试目的

验证项目直接使用模型的识别、ModelScope 递归上游闭包、异常血缘处理以及 CycloneDX ML-BOM 导出。该场景关注项目中实际使用的模型及其上游，不枚举 ModelScope 全量下游模型。

## 文件与覆盖范围

| 文件 | 覆盖内容 |
| --- | --- |
| `test_project_scanner_scope.py` | 项目模式只保留代码中的直接使用关系，排除文档中仅被提及的模型 |
| `test_modelscope_recursive_lineage.py` | 双来源父模型解析、去重、循环检测、节点预算和项目模式范围 |
| `test_export_bom.py` | BOM 标准字段、上游依赖、许可证、聚合节点 PURL 和往返完整性 |

## 测试数据

- `tests/fixtures/modelscope/recursive_lineage/`：递归上游查询与异常血缘夹具。
- `tests/fixtures/modelscope/scenario_t0_*` / `scenario_t1_*`：血缘、Delta 与传播测试共用的边界场景。
- `tests/fixtures/projects/`：项目扫描、真实 ModelScope 快照与许可证变更场景夹具。
- 项目识别和 BOM 导出测试也会在测试临时目录中现场生成输入，避免依赖历史导出文件。

## 运行方式

```powershell
python -m pytest tests/scenarios/modelscope -q
```

## 真实性边界

- `t0` 数据是冻结的 ModelScope 观测快照，不是每次测试时的实时请求。
- `t1` 数据用于表达人为构造的许可证或血缘变更，必须保留 `simulation=true` 标记。
- 递归上游测试验证查询策略和审计能力，不代表 ModelScope 一定完整公开所有上游关系。
- 项目模式不承诺获得全量下游模型名；下游风险传播不纳入当前产品边界。
