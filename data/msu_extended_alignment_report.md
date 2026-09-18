# MSU SBOM 扩展实体对齐验证报告

## 1. 结论摘要

- 数据范围：`D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms` 下全部 995 个 CycloneDX JSON。
- 模块 1：995/995 文件解析成功，共解析 130,089 个组件。
- 模块 2：共形成 20,550 个同名组件配对，其中自动合并 3,971 对，跳过 16,579 对，人工复核区 0 对。
- 置信度分布：`0.95 = 3,371`，`0.85 = 600`。没有产生 `1.0` 哈希合并，也没有发现哈希冲突。
- 重点样本 `sbom_syft_node_lts_cdx.json` 从修复前的 `0` 合并、`126` 跳过，变为 `50` 合并、`76` 跳过，资产数从 `662` 降到 `628`。
- 首轮按“不同版本也可用相同 URL 合并”的宽松解释运行时，主样本出现 `105` 合并，其中 `55` 对是不同版本的仓库 URL 碰撞。加入版本护栏后这些配对不再自动合并，主干样本保留 `50` 对真实合并。
- 未修改任何原始 SBOM 文件。

## 2. 信号可用性

### 2.1 文件级和组件级可用性

| 信号 | 含该信号文件数 | 有该信号组件数 | 实际用途 |
|---|---:|---:|---|
| SHA-1 或 SHA-256 哈希 | 283 | 11,074 | SHA-1 组件 4,668 个，SHA-256 组件 6,406 个；可判相同或冲突 |
| website/distribution URL | 400 | 23,769 | 与同名、同版本一起使用，置信度 0.95 |
| author/maintainer | 100 | 21,878 | 仅 author 字段有值，maintainer 字段为 0；与同名、同版本一起使用，置信度 0.85 |
| A 级具体文件路径 | 600 | 88,402 | 同版本且共享路径时置信度 0.9 |
| B 级 container layerID | 895 | 129,194 | 仅诊断，不参与合并 |

`externalReferences` 中实际出现的 URL 类型主要为：

| 类型 | 含该类型组件数 |
|---|---:|
| `distribution` | 22,869 |
| `website` | 6,238 |
| `issue-tracker` | 400 |
| `other` | 217 |
| `build-meta` | 47 |

作者型字段还被进一步拆分，避免把“发布者”或“供应商”误当成个人作者：

| 字段 | 含该字段文件数 | 含该字段组件数 | 是否参与合并 |
|---|---:|---:|---|
| `author` | 100 | 21,878 | 是 |
| `maintainers` | 0 | 0 | 无数据 |
| `publisher` | 400 | 41,546 | 否，仅统计 |
| `supplier` | 212 | 36,124 | 否，仅统计，适用于 Trivy/OS 包但不属于作者信号 |

抽样 5 个原始 SBOM 时，340 个组件中有 161 个含哈希、85 个含 URL、266 个含作者型字段。后续全量扫描确认标准 `author` 仅出现在 100 个文件中，因此扩展规则能够利用 author，但不能把所有 995 个文件都视为具备作者信息。

### 2.2 位置证据分级

- A 级：具体文件路径，例如 `/usr/lib/python3/dist-packages/requests/__init__.py`。只有同名、同版本且存在共同 A 级路径时才可作为合并依据。
- B 级：`sha256:...`、`LayerDiffID`、`LayerDigest`、`syft:location:0:layerID` 等容器层标识。它们覆盖很广，但同一层的组件并不代表同一实体，所以只写日志，不参与合并。
- C 级：没有位置信息。仅保留为缺失状态。

## 3. 代码修改

### 3.1 `bom_adapter.py`

新增 evidence 提取项：

- `components[].hashes[]`：保留算法和摘要，例如 `{"algorithm":"SHA-256","value":"..."}`。
- `components[].externalReferences[]`：保留 URL 类型和 URL，供对齐器只采用 `website`/`distribution`。
- `author`、`publisher`、`supplier`、`maintainers`：保留原始字段来源，后续只让 author/maintainer 参与合并。
- `LayerDiffID`、`LayerDigest`、`syft:location:0:layerID`：作为 B 级位置证据提取，不再漏掉 Trivy 层信息。

### 3.2 `entity_resolver.py`

新增规则及保护：

- 哈希相同：置信度 `1.0`，直接合并。
- 同一算法下哈希不同：状态为 `skipped: hash_conflict`，不再考虑其他信号。
- URL 相同：置信度 `0.95`，但必须同时满足同名和同版本。
- 同名、同版本、同 author/maintainer：置信度 `0.85`，自动合并。
- A 级路径且同名、同版本：沿用置信度 `0.9`。
- 版本不同：除完全相同哈希外，禁止由 URL、作者、位置和其他名称信号自动合并。
- `0.7 <= confidence < 0.85`：标记为 `needs_review`，不参与并查集合并。
- 日志新增哈希、URL、作者、共同位置、A/B/C 位置等级、自动合并标记和人工复核标记。

## 4. 重点样本结果

### 4.1 Syft Node LTS 主样本

| 指标 | 修复前 | 扩展规则首轮 | 加版本护栏后 |
|---|---:|---:|---:|
| 组件数 | 662 | 662 | 662 |
| 去重后组件数 | 662 | 606 | 628 |
| 自动合并对数 | 0 | 105 | 50 |
| 人工复核对数 | 0 | 0 | 0 |
| 跳过对数 | 126 | 21 | 76 |
| 置信度 1.0 | 0 | 0 | 0 |
| 置信度 0.95 | 0 | 99 | 44 |
| 置信度 0.85 | 0 | 6 | 6 |
| 跨版本 URL 碰撞 | 未计算 | 55 | 55 对均被版本护栏拦截 |

修复前跳过分布为 `73 version_mismatch + 3 cross_ecosystem + 50 no_valid_location_match`；加版本护栏后为 `73 version_mismatch + 3 cross_ecosystem`。

关键迭代发现：仓库 URL 是项目级信号，不是版本级信号。Syft 的多个 Node/npm 版本共享同一个 GitHub 仓库，首轮因此把例如 `@npmcli/agent@2.2.2` 与 `3.0.0` 合并，属于错误合并。版本护栏将这个错误挡在自动合并之外。

### 4.2 Trivy Ubuntu Jammy 样本

| 指标 | 修复前 | 扩展后 |
|---|---:|---:|
| 组件数 | 102 | 102 |
| 同名配对总数 | 0 | 0 |
| 自动合并对数 | 0 | 0 |
| 去重后组件数 | 102 | 102 |
| evidence 条数 | 342 | 701 |
| 有哈希组件数 | 未单独记录 | 56 |
| 有 B 级 layerID 组件数 | 0 | 101 |
| 有 URL/author/A 级路径组件数 | 0 | 0/0/0 |

Trivy 样本的模块 1 解析正常；模块 2 执行正常，但该样本没有同名组件，因此无法触发合并规则。Trivy 的主要新增收益是层 ID 和哈希被完整提取，而不是产生合并。

## 5. 全量结果

### 5.1 合并与跳过

| 指标 | 数量 |
|---|---:|
| SBOM 文件数 | 995 |
| 解析成功文件数 | 995 |
| 组件总数 | 130,089 |
| 去重后组件总数 | 127,436 |
| 同名配对总数 | 20,550 |
| 自动合并对数 | 3,971 |
| 人工复核对数 | 0 |
| 跳过对数 | 16,579 |
| 发生自动合并的文件数 | 100 |
| evidence 总条数 | 1,097,903 |

置信度分布：

| 置信度 | 依据 | 对数 |
|---:|---|---:|
| 1.0 | 哈希相同 | 0 |
| 0.95 | 同版本 URL 相同 | 3,371 |
| 0.9 | 同版本 A 级路径相同 | 0 |
| 0.85 | 同名、同版本、同 author/maintainer | 600 |
| 0.7 | 人工复核，不自动合并 | 0 |

跳过原因分布：

| 状态 | 对数 | 说明 |
|---|---:|---|
| `skipped: version_mismatch` | 12,188 | 同名但版本不同，不能用 URL/作者/位置自动合并 |
| `skipped: no_valid_location_match` | 3,971 | 包坐标相同但缺少共同 A 级路径 |
| `skipped: cross_ecosystem` | 320 | purl 生态不同且没有命中可覆盖的强信号 |
| `skipped: missing_purl` | 100 | 至少一方缺少 purl，主要在无 purl 的 OS 组件上出现 |

另外，全量数据中有 `4,243` 对“URL 相同但版本不同”的候选被版本护栏标记为不可自动合并。这个数字说明若直接把 homepage/repository URL 当成实体级身份，会产生大规模跨版本误合并。

### 5.2 哈希信号实际效果

- 哈希在 283 个文件中可用，共覆盖 11,074 个组件。
- 全量合并日志中没有产生置信度 `1.0` 的哈希合并。
- 没有出现 `hash_conflict`。
- 这表示当前 MSU 重复组件候选中，哈希虽然可用，但在本批同名配对中没有形成直接命中的共同摘要。该信号保留比当前样本证明的价值更重要，尤其是 Wild SBOMs 可能存在不同生态、不同 purl 但文件摘要完全相同的包。

## 6. 人工核对随机样本

以下 10 对由固定随机种子从实际合并记录中抽取。purl A/B 均省略了相同的无参数基础 purl，仅展示实际区分记录时的 `package-id` 限定 purl。

| 文件 | name | version | purl A | purl B | 合并依据 | 置信度 | 人工判断 |
|---|---|---|---|---:|---:|---|---|---|
| `sbom_syft_node_jod-bookworm_cdx.json` | `@npmcli/agent` | `2.2.2` | `pkg:npm/%40npmcli/agent@2.2.2?package-id=e5aaa014cd0a6a68` | `pkg:npm/%40npmcli/agent@2.2.2?package-id=e4a422721254b40e` | URL 相同 | 0.95 | 真同一实体 |
| `sbom_syft_node_22.11.0-bookworm_cdx.json` | `unique-slug` | `4.0.0` | `pkg:npm/unique-slug@4.0.0?package-id=583ace7227f54fd3` | `pkg:npm/unique-slug@4.0.0?package-id=8b1c47717a6a0bd9` | URL 相同 | 0.95 | 真同一实体 |
| `sbom_syft_node_iron-bookworm_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=b1793c299d41ea2e` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | URL 相同，author 也相同 | 0.95 | 真同一实体 |
| `sbom_syft_node_22.10.0-bookworm_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=b1793c299d41ea2e` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | URL 相同，author 也相同 | 0.95 | 真同一实体 |
| `sbom_syft_node_23.1-bullseye-slim_cdx.json` | `minipass-fetch` | `3.0.5` | `pkg:npm/minipass-fetch@3.0.5?package-id=b507dad53434e3ba` | `pkg:npm/minipass-fetch@3.0.5?package-id=601e929d9e757519` | URL 相同 | 0.95 | 真同一实体 |
| `sbom_syft_node_20.16.0-alpine3.19_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=a40aeaca74a18cab` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | URL 相同，author 也相同 | 0.95 | 真同一实体 |
| `sbom_syft_node_23.1-bookworm_cdx.json` | `mkdirp` | `3.0.1` | `pkg:npm/mkdirp@3.0.1?package-id=3cb751ffc0192fe9` | `pkg:npm/mkdirp@3.0.1?package-id=8164dfc68c384e39` | URL 相同 | 0.95 | 真同一实体 |
| `sbom_syft_node_jod_cdx.json` | `unique-slug` | `4.0.0` | `pkg:npm/unique-slug@4.0.0?package-id=583ace7227f54fd3` | `pkg:npm/unique-slug@4.0.0?package-id=8b1c47717a6a0bd9` | URL 相同 | 0.95 | 真同一实体 |
| `sbom_syft_node_23-bookworm-slim_cdx.json` | `make-fetch-happen` | `13.0.1` | `pkg:npm/make-fetch-happen@13.0.1?package-id=86cfee54d14120b5` | `pkg:npm/make-fetch-happen@13.0.1?package-id=1b5b8486c1293566` | URL 相同 | 0.95 | 真同一实体 |
| `sbom_syft_node_22.5-slim_cdx.json` | `minipass` | `3.3.6` | `pkg:npm/minipass@3.3.6?package-id=e0e6f38d6f2c0d5e` | `pkg:npm/minipass@3.3.6?package-id=e1062d9881f71e7d` | URL 相同，author 也相同 | 0.95 | 真同一实体 |

这 10 对均为同名同版本，差异仅来自 `package-id` 或不同安装路径，人工判断没有发现误合并。该抽样结果支持版本护栏后的规则，但不能替代对全部 3,971 对的穷举审计。

## 7. 已知限制

1. `homepage`/repository URL 只能证明项目同一，不能单独证明两个版本属于同一实体；必须加版本边界。
2. `author` 可缺失且可能是 `GitHub Inc.` 这类泛化组织名。只有和同名、同版本一起使用才相对安全。
3. `publisher` 和 `supplier` 虽然覆盖率高，但不属于 author/maintainer，并且容易造成 OS 供应商泛化误合并，因此本轮没有用于自动合并。
4. 哈希信号在 MSU 当前同名配对中未触发；仍需在 Wild SBOMs 上验证跨工具、跨生态的同摘要场景。
5. A 级路径是强位置信号，但同一包在不同目录安装会产生不同路径。当前规则要求共同路径，因此只有少数真正的重复安装会命中。
6. 当前是单 SBOM 内的实体对齐，不是跨 SBOM 时间序列对齐；版本不同的组件应保留为后续 Delta/风险传播所需的不同节点。

## 8. 是否值得推广到 Wild SBOMs

值得推广，但应分层启用：

- 可默认启用：相同哈希直接合并，哈希冲突硬阻断。
- 可条件启用：同名、同版本、同 URL；同名、同版本、同 author；同名、同版本、共同 A 级路径。
- 不应启用：仅 URL 相同就跨版本合并；仅 B 级 layerID 相同就合并；仅 supplier/publisher 相同就合并。
- 建议在 Wild SBOMs 上继续监测每个信号的覆盖率和误合并率，尤其是 URL 规范化、同仓库多包、monorepo、镜像层复用和通用组织作者。

## 9. 技术报告建议表述

本轮使用 MSU SBOM Benchmark 的 995 个真实 Docker CycloneDX SBOM 对扩展实体对齐规则进行了全量验证。模块 1 在 995 个文件上全部解析成功，共得到 130,089 个组件；模块 2 从 20,550 个同名组件配对中自动合并 3,971 对，置信度为 0.95 的 URL 规则命中 3,371 对，0.85 的作者规则命中 600 对。验证也揭示了 homepage/repository URL 是项目级信号而非版本级信号：主样本首轮按 URL 跨版本匹配产生 55 对误合并，加入“除非哈希一致否则版本不同不得合并”的护栏后，主样本保留 50 对真实合并，全量另有 4,243 对同 URL 跨版本候选被拦截。因此该扩展规则在补充哈希、URL、作者和 A 级路径后能够显著提高 MSU 数据上的实体发现能力，但推广到 Wild SBOMs 时必须保留哈希冲突阻断和版本边界，并把 URL/author 视为条件信号而非独立身份。

## 10. 输出文件

- `outputs/assets_real_npm_extended.json`
- `outputs/assets_real_npm_extended_deduplicated.json`
- `outputs/merge_log_real_npm_extended.json`
- `outputs/assets_real_trivy_extended.json`
- `outputs/assets_real_trivy_extended_deduplicated.json`
- `outputs/merge_log_real_trivy_extended.json`
- `outputs/msu_extended_alignment_summary.json`
- `outputs/msu_extended_file_results.json`
- `outputs/msu_extended_signal_availability.json`
- `outputs/msu_extended_merge_samples.json`
