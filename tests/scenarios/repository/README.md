# 仓库与自动化配置场景测试

## 测试目的

验证仓库中的 GitHub Actions、运行时脚本和示例配置不写死本机路径、AI 服务地址或输出位置，保证工作流可在 GitHub Runner 和不同开发环境中复用。

## 文件与覆盖范围

| 文件 | 覆盖内容 |
| --- | --- |
| `test_repository_hygiene.py` | Actions 输出变量、Runner 临时目录、AI 端点配置和机器专属主目录检查 |

## 检查对象

- `.github/workflows/license-watch.yml`
- `action.yml`
- `.env.example`
- `README.md`
- `docs/AI能力说明.md`
- 运行时 Python 模块和 `ai_layer/` 配置

## 运行方式

```powershell
python -m pytest tests/scenarios/repository -q
```

## 真实性边界

- 这些测试是静态仓库约束检查，不等同于 GitHub Actions 的真实远端运行结果。
- `127.0.0.1` 或本机模型服务地址不得作为默认交付配置，真实服务由环境变量注入。
- 静态检查通过不代表第三方 API、模型服务或网络在特定 Runner 上一定可用。
