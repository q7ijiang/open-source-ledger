# AI 证据场景测试

## 测试目的

验证 AI 层只生成可追溯的辅助证据，不替代许可证规则判定或人工复核。覆盖模型语义结论、多证据汇总、项目上下文、项目内模型用途识别、语义 Diff、来源包输入以及端到端集成。

## 文件与覆盖范围

| 文件 | 覆盖内容 |
| --- | --- |
| `test_ai_model_profile.py` | 模型许可证条款的 AI 语义画像、原文引用和 C 级证据输出 |
| `test_ai_multi_evidence.py` | 同一维度多证据保留、跨文档冲突与人工复核 |
| `test_ai_project_context.py` | 项目代码上下文识别、敏感信息脱敏和相对路径约束 |
| `test_ai_semantic_diff.py` | 相同许可证名称下的语义收紧、条款新增和证据变化 |
| `test_ai_source_bundle.py` | ModelScope 来源包到 AI 输入的结构化映射及不安全路径过滤 |
| `test_ai_integration.py` | BOM 往返、Diff sidecar、Markdown 置信度说明和 HTML AI 详情 |

## 测试数据

- `tests/fixtures/ai/`：模型画像、多证据、语义 Diff 和项目上下文固定响应。
- `tests/fixtures/acceptance/project/`：用于项目代码证据提取的受控验收项目。

测试默认使用固定响应或回放数据，不要求网络或在线模型服务。真实模型服务通过环境变量配置，不在测试文件中写死地址、凭据或绝对路径。

## 运行方式

```powershell
python -m pytest tests/scenarios/ai -q
```

## 真实性边界

- AI 输出属于 C 级辅助证据，必须保留原文引用、置信度和人工确认状态。
- AI 结果不得覆盖 LICENSE、ModelScope 元数据或规则引擎已经确定的结论。
- 固定响应只验证接口契约和证据处理，不代表任何模型当前的实时许可证。
- 带有 `simulation=true` 的夹具只用于变更场景，不能表述为 ModelScope 的真实变更。
