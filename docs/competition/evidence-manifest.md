# 半决赛证据清单

> 用途：把可复核的代码基线、测试、GitHub Actions 运行和待补材料集中到一处。
> 本文件不替代原始日志、Artifact 或 BOM；引用时以原始链接和 SHA 为准。

## 1. 代码基线

| 项目 | 值 |
| --- | --- |
| 仓库 | <https://github.com/q7ijiang/open-source-ledger> |
| 分支 | `main` |
| 原始基线提交 | `16a4cb5ce8c4019a64dc28b82df60993af2cf4a5` |
| 原始基线日期 | 2026-10-29 |
| 半决赛冻结标签 | `v0.1.0-semifinal` |
| 本清单生成时间 | 2026-11-14（Asia/Shanghai） |

本轮证据冻结已提交到 `main`，并由 annotated tag `v0.1.0-semifinal` 固定；具体
commit SHA 以 `git rev-parse "v0.1.0-semifinal^{commit}"` 为准。

工作区仍保留用户已有的、未纳入本次提交的改动：

- `docs/technical_report.md` 已删除；
- `docs/demo/` 未跟踪。

## 2. 自动化测试

```text
python -m pytest -q
189 passed
```

- 运行日期：2026-11-14
- 运行环境：Windows，Python 3.10.11
- 覆盖范围：AI 证据与降级、ModelScope 递归血缘、Project fixtures、Diff 与传播、
  HTML 渲染交互、仓库路径卫生、Action 配置、生成物路径可移植性、真实 AI 证据
  完整性。

原始 `181 passed` 是本次变更前的基线；新增路径可移植性、缓存键稳定性、依赖固定
和真实 AI 证据校验测试后为 `189 passed`。

## 3. GitHub Actions 运行

最近一次在 `main` 基线上成功的 ModelScope License Risk Watch：

| 项目 | 值 |
| --- | --- |
| Workflow | ModelScope License Risk Watch |
| Run | [#26](https://github.com/q7ijiang/open-source-ledger/actions/runs/42590975785) |
| 事件 | `schedule` |
| 结果 | `success` |
| 提交 | `16a4cb5ce8c4019a64dc28b82df60993af2cf4a5` |
| 开始 | 2026-11-09T09:07:37Z |
| 结束 | 2026-11-09T09:16:06Z |
| Artifact | `license-watch-evidence` |
| Artifact 大小 | 19,533 bytes |
| Artifact SHA256 | `5bf1d1b73b3b5506b8fe3d853d6fc43aa8c5786162872aa360720a868b4e1c43` |
| Artifact 过期时间 | 2026-11-23T09:16:01Z |

必须如实说明的边界：

- 该 Run 成功完成了项目扫描、BOM 生成、基线报告和 Artifact 上传。
- `Compare previous and latest BOM` 步骤被 **skipped**，因为缓存中没有恢复历史 BOM。
- Run #25（2026-11-02）同样跳过了 Diff。
- 该 Run 未配置真实 AI 服务，因此 Artifact 中的 AI 证据不能表述为真实模型调用。
- Artifact 尚未下载并固化到本地；公开演示前应下载并记录其内容清单与校验值。

### 3.1 已定位并修复的 CI 缺陷

原缓存键是：

```text
license-watch-<repo>-<ref>-<UTC 日期>
restore-keys: license-watch-<repo>-<ref>-<UTC 日期>-
```

日期进入 `prefix` 后，跨天运行无法命中前一天缓存，所以每次都被当作首次运行，
Diff 永远 skipped。这会让“持续监测”在 Actions 中失效。

工作区已改为稳定前缀：

```text
license-watch-<repo>-<ref>
restore-keys: license-watch-<repo>-<ref>-
```

并新增回归测试，禁止日期再次进入缓存前缀。该修复尚未在 GitHub 上运行验证；
下次 `workflow_dispatch` 必须确认 `Compare previous and latest BOM` 为 success，
而不是 skipped，才能把 CI Diff 作为比赛证据。


## 4. 依赖与第三方资源

| 文件 | SHA256 |
| --- | --- |
| `requirements.txt` | `a847f7e72c8a2d597c35e02a9f6cffec956a883d515ed86b70af960afbb5104f` |
| `THIRD_PARTY_NOTICES.md` | `99bc2f49b00c2ef54095c59489b77c0e08128c0a48f82ec0ac10a3af374dae67` |
| `portable_paths.py` | `d31614ea5888889f8da9f17f95259139a29a334326999905b165f4393822707d` |
| `README.md` | `9241b01d1297f14fcc06a1380335938c0e53a6fba86429f42a57ce2d55ed6dc0` |

依赖固定为：

```text
networkx==3.4.2
matplotlib==3.10.9
pytest==9.1.1
python-dotenv==1.2.4
requests==2.34.2
streamlit==1.54.0
```

## 5. 路径卫生

已确认仓库内测试夹具的 `.json`、`.html`、`.md` 不再包含：

```text
C:\Users\
C:\\Users\\
C:/Users/
/Users/
/home/
```

渲染器 `render_graph.py` / `render_diff.py` 在嵌入 HTML 前统一清洗
`source_file`、`project_path` 等字段；回归测试同时检查单层与 JSON 转义后的双层
反斜杠形式。

## 6. 真实 AI 运行

已完成一次真实 OpenAI-compatible 开放权重模型调用，证据目录见
[`real-ai/README.md`](real-ai/README.md)。

| 项目 | 值 |
| --- | --- |
| 调用时间（UTC） | 2026-11-14T12:22:12Z 至 2026-11-14T12:24:51Z |
| Endpoint | `https://api-inference.modelscope.cn/v1` |
| Model ID | `Qwen/Qwen3.5-27B` |
| Provider | `openai-compatible` |
| 输入项目 | `tests/fixtures/projects/real_modelscope/smoke_project` |
| 直接模型 | `Qwen/Qwen2.5-7B-Instruct-AWQ` |
| 上游闭包 | `Qwen/Qwen2.5-7B-Instruct` → `Qwen/Qwen2.5-7B` |

关键结果：

- 2 个模型画像为 `ok`，4 条条款 claim 通过逐字校验；
- 1 个模型 `Qwen/Qwen2.5-7B` 为 `no_evidence`，保留 6 个证据缺口；
- 项目上下文识别为 `local_inference`，置信度 0.83；
- 所有 claim 为 C 级、`human_review=pending`；
- AI 未改变 A 级许可证事实，BOM 中三个模型仍为 `Apache-2.0`。

冻结文件：

| 文件 | SHA256 |
| --- | --- |
| `real-ai/ai_analysis.json` | `71c0a492ada894232b6068bb9c9f1fae31355ccc226f5f20c15a2bd68072353a` |
| `real-ai/bom.json` | `e6e32baafe641102756945499e455f3208f55181e86f41bcc6f32bb99322e54c` |
| `real-ai/report.md` | `ed485deb5c11d4b977cdcb7d8ec5a9ff27d537cbdefa5386ebb00318ba067300` |
| `real-ai/source_bundles/Qwen__Qwen2.5-7B-Instruct-AWQ.json` | `6555ed3427cf7f529abd6e674f5836eb15d6f4487703dd7e68e0f884a289f719` |
| `real-ai/verification.json` | `e1ac561aa68f211a3b34fdc54ea4ab805a90887884a9e4507859342e908b3248` |

边界：这是真实模型调用，但输入项目是固定夹具，不是生产仓库扫描；不能据此宣称
所有 ModelScope 模型结论都正确，也不能把 `no_evidence` 当成安全。

## 7. 待补材料

- [x] 真实 AI 运行与 `ai_analysis.json` 冻结。
- [ ] 推送缓存键修复后，用 `workflow_dispatch` 验证 `Compare previous and latest BOM`
      为 success；需要至少两次运行（第一次建基线，第二次执行 Diff）。
- [ ] 半决赛 PPT（匿名检查：无学校、校徽、学院、指导教师、导师项目名称）。
- [ ] 6 分钟以内、无剪辑、无快进、全员出镜的答辩视频。
- [ ] 最新一次成功 Actions Run 的 Artifact 下载与内容清单。
- [ ] 比赛 release/tag（建议在最终提交后创建 `v0.1.0-semifinal`）。
- [ ] 最终提交前重新运行完整测试并更新本清单。

## 8. 复核命令

```powershell
python -m pytest -q
python -m py_compile portable_paths.py render_graph.py render_diff.py
python tests/acceptance/generate_ai_acceptance.py --output <acceptance-directory>
```

Actions 证据可通过公开 API 复核：

```text
https://api.github.com/repos/q7ijiang/open-source-ledger/actions/runs/42590975785
https://api.github.com/repos/q7ijiang/open-source-ledger/actions/runs/42590975785/artifacts
```
