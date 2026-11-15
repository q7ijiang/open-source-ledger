# 受控 t0（真实 AI 画像）

本目录保存一次重新构造的受控 t0，用于演示：

```text
controlled t0（Apache 回放）
  -> 真实扫描 ModelScope 得到 t1（qwen-research）
  -> Diff
  -> 许可证变更、传播路径、路径证书
```

## 1. 构造方式

1. 对 `example/qwen_image_controlled_project` 做真实 Project 扫描，得到 observed_current；
2. 复制 observed_current 的真实血缘结构；
3. 只把祖先 `Qwen/Qwen-Image-2.1` 的许可证回放为 Apache-2.0；
4. Apache 文本使用仓库根部 `LICENSE` 中的标准 Apache-2.0 全文；
5. 对受控 LICENSE + 历史 README 调用真实 `Qwen/Qwen3.5-27B`，生成 t0 的 C 级 AI 画像；
6. 其他模型沿用 observed_current 中同一轮真实 AI 结果；
7. 写入 `t0_bom.json`，并在 BOM 属性中标记受控/模拟来源。

生成脚本：

```powershell
python scripts/prepare_controlled_baseline.py `
  --observed-bom out/controlled-baseline/observed_bom.json `
  --template-bom tests/fixtures/projects/qwen_image_license_tightening/upstream/t0_bom.json `
  --current-bundle out/controlled-baseline/observed/projects/qwen_image_controlled_project/source_bundles/Qwen__Qwen-Image-2.1.json `
  --historical-bundle tests/fixtures/projects/qwen_image_license_tightening/upstream/evidence/qwen-image-2.1.historical-apache.json `
  --apache-license LICENSE `
  --output docs/competition/controlled-baseline/t0_bom.json
```

## 2. 受控边界

- 历史 ModelScope 仓库只保存了 README 元数据：

  ```text
  license: Apache License 2.0
  ```

- 没有保存当时的 Apache LICENSE 原文件。
- 因此本目录的 Apache LICENSE 文本是**标准 Apache-2.0 全文的受控替代文本**，不是历史原文件。
- BOM 中已标记：

  ```text
  controlled_baseline=true
  simulation=true
  controlled_source=true
  synthetic_document=true
  not_historical_original=true
  ```

- 不得将本 t0 表述为“ModelScope 历史 LICENSE 原样存在”。

## 3. AI 结果

- Provider：`openai-compatible`
- Model：`Qwen/Qwen3.5-27B`
- 目标模型 `Qwen/Qwen-Image-2.1`：`ai_status=ok`
- 主要 claim：

  ```text
  commercial_use    allowed   0.80
  distribution      allowed   0.78
  modification      allowed   0.78
  patent_license    allowed   0.78
  ```

- 未形成引用的维度保留为具体 gap，例如：

  ```text
  training_other_models
  fine_tuned_redistribution
  commercial_license_request
  ```

每个 gap 都记录 `missing`（缺什么）和 `searched_sources`（查了哪些文件）。

## 4. 文件

| 文件 | 说明 |
| --- | --- |
| `t0_bom.json` | 受控 t0 BOM |
| `t1_observed_bom.json` | 同一轮真实扫描得到的 t1 快照 |
| `manifest.json` | 构造来源、Apache 文本哈希、AI provider、claims、gaps |
| `diff_report.md` | 与真实 t1 的 Diff 结果 |
| `diff_report.ai.json` | AI 语义差异 JSON |

`diff_report.md` 中：

- 规则层检测到 3 个许可证变更事件、2 张路径证书；
- AI 层把 `允许 → 受限` 标为“条款收紧”；
- 把 `允许 → 未找到明确条款` 标为“证据丢失”，不误写成条款收紧。

## 5. 复现 Diff

```powershell
python main.py --diff `
  --before docs/competition/controlled-baseline/t0_bom.json `
  --after docs/competition/controlled-baseline/t1_observed_bom.json `
  --output docs/competition/controlled-baseline/diff_report.md `
  --ai
```

真实 t1 快照也保存在本目录，便于离线复现同一份 Diff。
