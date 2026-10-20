##模块 1 路书的完整内容

# 模块 1：BOM 解析

| 项目 | 内容 |
|---|---|
| 负责人 | A |
| 状态 | 已完成 |
| 完成日期 | 2026-09-18 |
| 对应任务 | 基础部分 · 模块 1 |

## 一句话摘要

把 cdxgen 生成的 CycloneDX BOM，转换成项目自定义的统一资产列表，供后续所有模块使用。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| `sample_bom.json` | cdxgen 扫描 `test-project/` 生成 | CycloneDX 格式的原始 BOM |
| `test-project/` | 我们自己构造的模拟项目 | 包含 Python 包、npm 包、ModelScope 模型三类资产 |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| `bom_adapter.py` | 代码 | 解析 BOM 并转换格式的脚本 |
| `assets.json` | 输出 | 统一格式的资产列表，72 条资产 |

## 为什么要做

1. **cdxgen 的原始格式不能直接用**：它输出的是通用 CycloneDX 结构，字段分散，没有我们项目定义的 `canonical_id` 和 `evidence_chain`。
2. **后续模块依赖统一数据格式**：模块 2（实体对齐）、模块 3（证据补全）、模块 5（中文清单）都需要 `assets.json` 作为输入。
3. **三人协作需要统一语言**：A、B、C 之间用 JSON 交换数据，`assets.json` 就是标准格式。

## 具体怎么做

### 步骤 1：构造模拟项目

创建 `test-project/`，包含：
- `requirements.txt`：requests、flask
- `package.json`：express
- `model_usage.py`：声明 `Qwen/Qwen2.5-0.5B-Instruct` 等 ModelScope 模型标识

### 步骤 2：用 cdxgen 扫描

```bash
cdxgen -t python -t npm -t ai --evidence --no-install-deps --json-pretty -o sample_bom.json .
```

### 步骤 3：手动补全模型信息

cdxgen 从源码短别名扫描模型时，license、version、purl 不完整。手动补全为：
- purl: `pkg:modelscope/Qwen/Qwen2.5-0.5B-Instruct@master`
- license: `Apache-2.0`
- version: `master`

### 步骤 4：写 `bom_adapter.py` 解析

读取 `sample_bom.json`，提取每个组件的 `name`、`version`、`purl`、`licenses`、`evidence.occurrences[].location`，按接口约定转换成资产节点格式，输出 `assets.json`。

## 得到了什么

`assets.json` 包含 72 条资产：
- 70 条 `package`（Python 包 + npm 包）
- 2 条 `model`（Qwen2.5-0.5B-Instruct 的两个 purl 变体）

每条资产的格式：

```json
{
  "canonical_id": "package:express",
  "asset_type": "package",
  "name": "express",
  "version": "4.22.3",
  "purls": ["pkg:npm/express@4.22.3"],
  "license": "MIT",
  "evidence_chain": [
    {
      "evidence_level": "B",
      "source_api": "cyclonedx",
      "source_url": null,
      "source_field": "components[].licenses",
      "status": "ok",
      "raw_value": "MIT"
    }
  ],
  "snapshot_id": "basic-20260918"
}
```

## 暴露了什么问题

| 问题 | 影响 | 交给哪个模块解决 |
|---|---|---|
| `Qwen2.5-0.5B-Instruct` 出现两次（pypi 和 npm 各一次） | 同一个模型重复，清单会有两条 | 模块 2：跨生态实体对齐 |
| `evidence_chain` 只有本地文件位置，没有远程 URL | 证据链不完整，无法直接点回原文 | 模块 3：证据链补全 |
| 模型资产的 license、version 需手动补全 | 不自动，依赖人工 | 后续考虑从 ModelScope API 自动补全 |

## 如何验证

1. 打开 `assets.json`，搜索 `Qwen2.5-0.5B-Instruct`，确认出现两次。
2. 检查每条资产是否包含 `canonical_id`、`asset_type`、`name`、`version`、`purls`、`license`、`evidence_chain`、`snapshot_id`。
3. 检查 `requests`、`flask`、`express` 是否都在列表中。
4. 重新运行 `bom_adapter.py`，输出应一致。

## 相关文件

| 文件 | 路径 |
|---|---|
| BOM 解析脚本 | `bom_adapter.py` |
| 原始 BOM | `sample_bom.json` |
| 资产列表 | `assets.json` |
| 测试项目 | `test-project/` |

## 给队友的话

- B：`assets.json` 里的 `license` 字段可以直接用，但需要结合你的 `license_db.py` 判断风险方向。
- C：`assets.json` 可以直接作为中文清单生成的数据源，但注意 `Qwen2.5-0.5B-Instruct` 目前有重复，等模块 2 完成后用 `assets_deduplicated.json`。
```
