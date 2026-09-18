# MSU SBOM Benchmark 真实 CycloneDX 验证报告

## 1. 数据来源

### 1.1 仓库内置 `input/` 目录

`D:\datasets\msu-sbom-benchmark\input\projects\SBOM\` 存在，内容如下：

| 文件 | 大小（字节） | 格式 | 规范版本 | 组件数 |
|---|---:|---|---|---:|
| `sbom-trivy-cdx-msusel-pique.json` | 22,564 | CycloneDX | 1.6 | 27 |

该文件是有效 CycloneDX，但为了满足本轮“从 Zenodo 原始 SBOM 中随机选一个”的要求，最终验证使用了下述 Zenodo 文件。

### 1.2 Zenodo 下载

Zenodo 记录：

- 记录地址：`https://zenodo.org/records/15122007`
- 官方 API：`https://zenodo.org/api/records/15122007`
- 下载文件：`docker_sboms.zip`
- 官方大小：17,317,333 字节
- 官方 MD5：`c9a9d3d4ecdedcf44f4d205095e4b813`
- 本机下载路径：`D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms.zip`
- 解压路径：`D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms`
- 解压 JSON 文件数：995

本机常规 curl 请求受 DNS 黑洞和 Windows Schannel 凭据错误影响，无法直接连接 Zenodo。实际下载通过 Python OpenSSL 网络栈连接 Zenodo 官方文件 URL，并完成了大小与 MD5 校验；下载内容与 Zenodo 官方校验值一致。

### 1.3 随机选择的验证文件

从 995 个解压 JSON 中随机抽取并确认：

| 项目 | 值 |
|---|---|
| 文件 | `benchmark-alpine-busybox-ngnix-node-ubuntu\sbom_trivy_ubuntu_jammy-20240111_cdx.json` |
| `bomFormat` | `CycloneDX` |
| `specVersion` | `1.6` |
| `components` | 102 |
| `metadata.component.name` | `ubuntu:jammy-20240111` |

## 2. 模块 1：BOM 解析结果

| 指标 | 实际结果 |
|---|---:|
| 组件数 | 102 |
| 许可证种类数 | 82 |
| 有许可证赋值的组件数 | 102 |
| evidence 数 | 342 |
| 处理耗时 | 0.141946 秒 |
| 状态 | 通过 |

许可证引用总数为 342。数量较多的许可证包括：

| 许可证 | 组件引用数 |
|---|---:|
| `GPL-2.0` | 61 |
| `GPL-3.0` | 38 |
| `LGPL-2.1` | 30 |
| `BSD-3-Clause` | 23 |
| `LGPL-3.0` | 20 |
| `LGPL-2.0` | 18 |
| `public-domain` | 13 |
| `BSD-2-Clause` | 13 |

完整 82 种许可证分布见 `outputs\license_distribution_real_final.json`。

## 3. 模块 2：实体对齐结果

| 指标 | 实际结果 |
|---|---:|
| 输入资产数 | 102 |
| 同名但不同 purl 的原始组件对 | 0 |
| 同名且相同 purl 的重复对 | 0 |
| 合并对数 | 0 |
| 去重后资产数 | 102 |
| 置信度 0.9 合并数 | 0 |
| 置信度 0.7 合并数 | 0 |
| 处理耗时 | 0.138206 秒 |
| 状态 | 执行通过，但没有候选实体触发合并规则 |

该随机 SBOM 中不存在重名组件，因此没有可应用“同名+同 evidence 位置”或“同名+同 version”规则的对象。本轮没有发生误合并，但由于候选对为 0，不能据此推断模块 2 的跨生态合并准确率。

## 4. 模块 1 和模块 2 汇总

| 模块 | 结果 | 说明 |
|---|---|---|
| 模块 1：BOM 解析 | 通过 | 成功解析真实 CycloneDX 1.6，得到 102 个组件、82 种许可证、342 条 evidence |
| 模块 2：实体对齐 | 执行通过，合并未触发 | 102 个资产无重名或重复 purl，输出仍为 102 个，合并日志为空 |

## 5. `bom_adapter.py` 修复说明

为兼容真实 CycloneDX，适配器进行了以下调整：

1. 支持命令行指定输入、输出、快照 ID 和组件数量上限。
2. 支持标准顶层 `components`，并兼容封装结构及嵌套组件。
3. 兼容 `license.id`、`license.name`、`expression` 和字符串许可证。
4. 支持从 `pkg:` 开头的 `bom-ref` 回退提取 purl。
5. 提取标准 occurrence，并兼容 Trivy `FilePath` 和 Syft location/path 属性作为 evidence。
6. 对 PIQUE 质量评估结果给出明确错误，避免把无组件文件误报为解析成功。
7. 增加 UTF-8 输出和可读退出码。

这些修改解决了真实 CycloneDX 与早期手造样本之间的字段和结构差异。

## 6. 已知限制

- 本次随机 SBOM 没有重名组件，因此模块 2 的真实合并路径没有被触发。
- 若技术报告需要验证跨生态合并规则，应再随机抽样或定向选择包含同名异 purl 组件的 SBOM，或增加跨来源同一实体的样本。
- Zenodo 压缩包解压时为适配 Windows 文件名限制，将文件名中的冒号等非法字符替换成了 `_`；文件内容和目录层级未改变。

## 7. 建议写入技术报告的表述

本轮从 MSU SBOM Benchmark 对应的 Zenodo 记录中下载 `docker_sboms.zip`，解压 995 个原始 SBOM 后随机选取一个 CycloneDX 1.6 文件进行验证。模块 1 成功解析 102 个组件、82 种许可证和 342 条 evidence，处理耗时约 0.14 秒；模块 2 正常完成 102 个资产的实体对齐，但该随机样本不含重名或重复 purl 组件，因此合并对数和置信度分布均为 0。本轮验证确认了解析与对齐流程在真实 CycloneDX 数据上的可运行性，但跨生态合并规则仍需使用包含同名异 purl 实体的样本进行专项验证。
