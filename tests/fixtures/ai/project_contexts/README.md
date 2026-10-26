# 项目使用上下文夹具

本目录保存 Mock Provider 的固定项目上下文响应。

- `remote_api_ai_response.json`：判断测试项目通过远程 API 使用模型；
- 每条使用方式必须引用 `tests/fixtures/acceptance/project/` 中真实存在的逐字项目代码；
- 夹具不包含真实密钥，分析结果固定为 C 级并等待人工确认。
