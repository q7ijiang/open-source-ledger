# Qwen-Image-2.1 许可证收紧演示数据

本目录只包含用于演示和回归测试的夹具。事实证据、模拟边界与演示项目
分别保存在每个场景的 `evidence/`、`scenario.json` 和 `project/`。

| 场景 | 项目直接模型 | t0 口径 | t1 口径 |
| --- | --- | --- | --- |
| [direct](direct/README.md) | `Qwen/Qwen-Image-2.1` | 历史 README 元数据重建 | 当前 ModelScope 许可证 |
| [upstream](upstream/README.md) | `unsloth/Qwen-Image-2.1-Turbo-FP8`<br>`OpenGVLab/InternVL3-8B-Instruct` | 当前真实血缘 + 历史许可证反事实重放 | 当前 ModelScope 许可证 |

## 重新生成

在仓库根目录运行：

```powershell
python tests/fixtures/projects/qwen_image_license_tightening/generate_fixtures.py
```

普通生成优先读取已冻结的网络证据，不要求联网。若需要从 ModelScope
重新抓取，显式增加 `--refresh-evidence`。脚本会对关键提交和 LICENSE
哈希做硬性校验，证据漂移时停止生成。

## 事实边界

- 历史 Apache 口径来自 ModelScope README 元数据和提交历史。
- 没有证据声称当时的 Apache LICENSE 文件被原地修改。
- `upstream` 的 t0 必须保持 `simulation=true`，不得用于宣称 Turbo/FP8
  在 Apache 阶段已经发布。
