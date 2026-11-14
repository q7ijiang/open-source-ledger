# 第三方组件、数据与资源声明

本文件说明“开源账本”仓库中直接分发或依赖的第三方软件、数据和外部服务。它用于
比赛材料与公开演示的可追溯性，不构成法律意见，也不替代各项目自身的 LICENSE。

本仓库自身代码以 Apache License 2.0 发布，全文见 [`LICENSE`](LICENSE)。

## 1. 随仓库分发的第三方代码

| 组件 | 版本 | 许可证 | 位置 | 说明 |
| --- | --- | --- | --- | --- |
| Apache ECharts | 5.4.3 | Apache-2.0 | `echarts.min.js` | 离线 HTML 血缘图渲染；文件头保留 Apache ASF 许可声明。 |
| zrender | 5.4.4 | BSD-3-Clause | 打包在 `echarts.min.js` 内 | ECharts 的渲染依赖，版权归 Baidu Inc.。 |

`echarts.min.js` 来自 Apache ECharts 官方发行包，未修改其许可证头。若需重新分发，
请同时保留 ECharts 与 zrender 的版权和许可声明。

项目源码中的以下文件为自研代码，不在第三方声明范围内：`main.py`、`app.py`、
`render_graph.py`、`render_diff.py`、`ai_layer/`、`tests/` 等。

## 2. Python 运行时依赖

`requirements.txt` 固定了半决赛验收使用的版本。下表列出直接依赖及其许可证；
传递依赖（如 numpy、pandas、pyarrow、protobuf、tornado 等）由 pip 解析并随
各自发行包分发，其许可证以对应发行包内的 `LICENSE` / `METADATA` 为准。

| 包 | 固定版本 | 许可证 | 用途 |
| --- | --- | --- | --- |
| networkx | 3.4.2 | BSD-3-Clause | 血缘图、可达性、SCC 与传播计算 |
| matplotlib | 3.10.9 | Matplotlib License（PSF 风格 BSD 兼容条款） | 图表与静态图输出 |
| pytest | 9.1.1 | MIT | 自动化测试 |
| python-dotenv | 1.2.4 | BSD-3-Clause | `.env` 配置读取 |
| requests | 2.34.2 | Apache-2.0 | ModelScope API 与文件下载 |
| streamlit | 1.54.0 | Apache-2.0 | Project / Diff 交互界面 |

Python 标准库按 CPython 的 PSF License 使用。

## 3. 外部平台与数据

### 3.1 ModelScope

- 本工具通过 ModelScope 公开 API 与模型仓库页面读取模型元数据、LICENSE、README、
  提交历史和上游血缘。
- 仓库不包含 ModelScope 平台代码，也不包含任何模型权重。
- 模型、数据集、模型卡和 LICENSE 文本的权利归各自发布者所有；每个模型的许可证
  以其 ModelScope 仓库中的 LICENSE / README 为准。
- 工具输出中保留来源 URL、抓取时间和 SHA256，用于复核；这不等同于对平台数据
  完整性或持续可用性的保证。
- 使用 ModelScope API 时仍需遵守平台的服务条款和访问频率限制。

### 3.2 CycloneDX

- 本工具使用 CycloneDX BOM 作为输出格式，不复制或修改 CycloneDX 规范代码。
- CycloneDX 规范仓库采用 Apache License 2.0：
  <https://github.com/CycloneDX/specification>。

### 3.3 AI 服务

- AI 语义证据层只调用运行方显式配置的 OpenAI-compatible 服务，不内置服务地址、
  模型权重或供应商 SDK。
- 模型选择、服务条款、数据处理与计费由运行方与其服务提供方约定。
- `AI_API_KEY`、`MODELSCOPE_API_KEY` 不写入报告、BOM、AI JSON 或 Artifact。

## 4. 展示材料中的第三方内容

### 4.1 Qwen 许可证原文摘录

`tests/fixtures/projects/qwen_image_license_tightening/` 与
`docs/demo/qwen-image-2.1-license-case.md` 中包含 Qwen Research License 的短句
摘录，仅用于许可证条款审计演示和逐字引文校验。原文权利归 Qwen 团队/相应权利人
所有；本项目不主张对这些文本的著作权，也不将摘录解释为对模型的再许可。

相关公开来源：

- <https://www.modelscope.cn/models/Qwen/Qwen-Image-2.1>
- <https://www.modelscope.cn/api/v1/models/Qwen/Qwen-Image-2.1>

### 4.2 字体与图标

- HTML 报告使用系统中文字体（如 Microsoft YaHei）和通用 sans-serif / monospace
  字体栈，不随仓库分发字体文件。
- 仓库未引入第三方图标库；界面中的颜色、圆点和箭头由 CSS / ECharts 绘制。

### 4.3 比赛与演示材料

PPT、视频、截图和答辩文档如使用第三方图片、模板、音乐或字体，应在最终提交前
单独核对授权，并在本文件补充来源。当前仓库不包含可提交的半决赛 PPT 或视频。

## 5. 无模型权重声明

本仓库不包含 ModelScope 模型权重、数据集文件或推理产物。测试夹具只保存模型
标识、许可证文本、API 响应和构造的 BOM/图数据；这些文件不授予任何模型使用权。

## 6. 复核方式

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python tests/acceptance/generate_ai_acceptance.py --output <acceptance-directory>
```

依赖版本变更时，应同步更新本文件、`requirements.txt` 和比赛证据清单。

如发现遗漏或版本不符，请通过仓库 Issue 提交具体组件、版本、来源 URL 和许可证
证据，以便复核。
