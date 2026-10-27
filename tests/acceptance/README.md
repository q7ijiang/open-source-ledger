# AI 离线验收生成

本目录生成 AI 证据层的离线验收包，不访问网络。产品用户入口只有 Project 与 Diff；Model 产物用于内部调查和回归测试。

- `generate_ai_acceptance.py` 从 `tests/fixtures/ai/` 读取固定 ModelScope 原文、Mock AI 响应和语义 Diff 数据；
- 内部模型调查输出模型条款画像；
- Project 用户入口输出远程 API 使用上下文；
- Diff 用户入口输出同名 `qwen-research` 从“允许商用”收紧为“禁止商用”的 C 级语义变化；
- HTML 页面可直接打开，节点详情会显示逐字引文、置信度、待确认状态和证据缺口。

运行：

```powershell
python tests/acceptance/generate_ai_acceptance.py --output outputs/ai_acceptance
```

默认输出目录从本文件所在仓库根目录推导；也可以使用 `--output` 指定任意位置。生成结果只用于能力验收，不构成法律意见。
