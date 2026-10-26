# AI 验收固定输入

本目录为三种模式的离线验收提供项目输入：

- `project/app.py`：模拟通过远程推理 API 调用模型；
- `project/README.md`：项目说明，不包含真实凭据或远程服务配置。

生成脚本位于 `tests/acceptance/generate_ai_acceptance.py`，只读取 `tests/fixtures/ai/` 中的固定 ModelScope 与 AI 响应，不访问网络。
