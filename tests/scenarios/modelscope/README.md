# ModelScope 上游血缘与 BOM 场景测试

本目录位于 `tests/scenarios/modelscope/`，不是仓库根目录。

## 测试目的

验证项目直接使用模型的识别、ModelScope 递归上游闭包、异常血缘处理以及 CycloneDX ML-BOM 导出。当前产品边界是“项目中直接使用的模型 + 上游来源闭包”，不枚举或评估 ModelScope 全量下游模型。

AI 仅生成 C 级条款语义证据供人工复核，不改变规则判定、风险颜色、Delta 或 CI 结果。

## 文件与覆盖范围

| 文件 | 覆盖内容 |
| --- | --- |
| `test_project_scanner_scope.py` | 项目模式只保留代码中的直接使用关系，排除文档中仅被提及的模型 |
| `test_modelscope_recursive_lineage.py` | 双来源父模型解析、去重、循环检测、节点预算和项目模式范围 |
| `test_export_bom.py` | BOM 标准字段、上游依赖、许可证、证据链和往返完整性 |

## 测试数据

- `tests/fixtures/modelscope/recursive_lineage/`：递归上游查询、异常血缘和深度边界的合成夹具。
- `tests/fixtures/projects/qwen_image_license_tightening/upstream/`：当前 Diff 主验收场景，包含 8 个具体模型和 9 条 `pedigree.ancestors` 边。
- 该场景的直接模型是 `unsloth/Qwen-Image-2.1-Turbo-FP8` 与 `OpenGVLab/InternVL3-8B-Instruct`，上游可追溯到 `Qwen/Qwen-Image-2.1`、InternViT 和 `Qwen/Qwen2.5-7B`。
- 旧的 `data/test_scenarios/ms_*_bom.json` 与 `project_*_bom.json` 已退役。前者以下游微调/量化为核心；后者包含与当前边界冲突的 `lineage.SonModels` 聚合域和 Adapter 夹具。其冻结血缘、缺失祖先和渲染覆盖已迁移到 Qwen 上游场景测试。
- 项目识别和 BOM 导出测试也会在测试临时目录中现场生成输入，避免依赖历史导出文件。

## 运行方式

```powershell
python -m pytest tests/scenarios/modelscope -q
```

## 真实性边界

- `t0` 是冻结的历史重建快照，不是测试运行时发起的实时 ModelScope 请求。
- `t1` 的许可证收紧是 `simulation=true` 的受控推演；它验证工具在真实上游关系上的处理能力，不代表模型供应方在测试当天刚发生该变更。
- 历史依据只表述为：Qwen-Image-2.1 仓库早期 README 元数据曾声明 Apache License 2.0；后续新增 LICENSE 文件为 Qwen Research License，README 许可证字段也更新为 `qwen-research`。
- 递归上游测试验证查询策略和审计能力，不代表 ModelScope 一定完整公开所有上游关系。
- 项目模式不承诺获得全量下游模型名；下游风险传播不纳入当前产品边界。
