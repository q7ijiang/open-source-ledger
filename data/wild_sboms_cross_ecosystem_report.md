# Wild SBOMs 跨生态合并验证报告

## 1. 执行摘要

本次使用 Wild SBOMs 的 57,877 个 CycloneDX JSON 文件补充验证跨生态实体合并。全量扫描已完成，没有使用前 5,000 个文件的降级路径。

核心结果如下：

- 实际扫描文件：57,877 个。
- 顶层无 `components` 数组而跳过的文件：600 个。
- 含同名、不同 purl type 组件对的候选文件：1,817 个。
- 扫描阶段识别出的跨生态组件对：14,706 对。
- 经 `entity_resolver.py` 处理的同名跨生态配对日志：11,427 对。
- 严格模式下自动合并：7 对。
- 窄例外触发：0 对。
- 放宽 `asset_type=model` 限制后自动合并：总数仍为 7 对，新增 0 对。
- 7 条合并记录去重后只对应 1 个独立跨生态关系。
- 官方源核验结果：按独立关系计 `CONFIRMED=1, SUSPECT=0, WRONG=0`；按 7 条文件记录计 `CONFIRMED=7, SUSPECT=0, WRONG=0`。

结论是：Wild SBOMs 确实提供了真实跨生态名称碰撞样本，但当前窄例外几乎无法在普通 package SBOM 中触发；仅取消 `asset_type=model` 也不能增加合并，因为共同有效路径、版本一致和生态白名单仍然是主要限制。现有 URL 信号能够确认一个真实的 Composer/npm 同源项目，但规则本身仍需要收窄，不能把“同仓库 URL”普遍视为同一包实体。

## 2. 任务 1：候选文件筛选

扫描脚本：`scan_cross_ecosystem.py`

扫描输出：`outputs/cross_ecosystem_candidates.json`

实际扫描范围如下：

- JSON 文件总数：57,877。
- 实际扫描文件数：57,877。
- 是否只扫描部分文件：否。
- 已统计组件数：13,143,519。
- 解析跳过文件数：600，原因均为顶层 `components` 不是数组。
- 候选文件数：1,817。
- 扫描阶段跨生态组件对总数：14,706。
- 全量扫描耗时：573.265 秒。

扫描结果比先前静态口径的 1,811 个文件多 6 个。新增文件均由额外的 `maven::npm` 碰撞贡献，典型组合为：

- `pkg:maven/com.acme/stock-java-client@1.0.12`
- `pkg:npm/acme/component@1.0.0`

主要 purl type 组合包括：

- `composer::npm`：5,661 对。
- `npm::pypi`：1,975 对。
- `deb::rpm`：1,617 对。
- `deb::pypi`：1,076 对。
- `pypi::rpm`：831 对。

## 3. 任务 2：现有窄例外规则验证

验证脚本：`work/validate_wild_sboms_merge.py`

验证输出：`outputs/wild_sboms_merge_validation.json`

对全部 1,817 个候选文件调用现有 `entity_resolver.py` 后，结果如下：

| 指标 | 数量 |
|---|---:|
| 成功处理候选文件 | 1,817 |
| 解析或处理失败文件 | 0 |
| 跨生态配对日志 | 11,427 |
| 严格模式自动合并 | 7 |
| 窄例外触发 | 0 |
| `skipped: cross_ecosystem` | 11,404 |
| `skipped: hash_conflict` | 16 |

严格模式的 7 对合并依据全部为“homepage或repository URL相同”，没有一对由模型别名窄例外触发。

窄例外必要条件未满足次数如下，统计口径允许同一配对同时计入多个失败条件：

| 必要条件 | 未满足次数 |
|---|---:|
| 双方 `asset_type=model` | 11,427 |
| 版本一致且非空 | 11,159 |
| 存在共同有效路径 | 11,423 |
| purl 生态属于 `npm/pypi/huggingface` | 9,608 |

一级原因统计中，11,427 对全部优先归为 `asset_type非model`。这说明候选数据集包含大量普通 package 库组件，而现有窄例外专门面向模型别名，几乎不覆盖真实 package SBOM 场景。

## 4. 任务 3：取消 model 限制后的结果

放宽模式只取消 `asset_type=model` 限制，保留以下条件：

- 版本一致且非空。
- 存在共同有效文件路径。
- 跨生态 purl 类型限定在 `npm/pypi/huggingface`。
- 不同 purl type 默认仍不直接合并。

结果为：

- 跨生态配对总数：11,427。
- 自动合并总数：7。
- 相比严格模式新增合并：0。
- 新增文件：0。

因此不存在“放宽后新增 20 对”可供随机抽样。为遵守不伪造结果的约束，第三方核验改为对严格模式已有的 7 条跨生态合并记录执行；这 7 条记录去重后实际只有一个独立关系，因此官方源只核验一次。

唯一的独立关系是：

- 组件 A：`pkg:composer/nesk/rialto@1.4.0`
- 组件 B：`pkg:npm/%40nesk/rialto@1.4.0`
- 组件名称：`rialto`
- 共同 URL：`https://github.com/nesk/rialto`
- 共同有效路径：无。
- 共同哈希：无。
- 共同作者：无。
- 合并依据：homepage 或 repository URL 相同。
- 置信度：0.95。

该关系出现在以下 7 个 SBOM 文件中：

- `4d4dbc05b2a71d76e7e980e071e6e27e680a539a.json`
- `77aece58c2dccb1214d9600de1ffa61b44e687cc.json`
- `7fdba55b0943b86a5864ac786d578ac33d954ac7.json`
- `959bbc0421abaceb071d127c28ce11c397bc6792.json`
- `e2a0d676b5b38948dc9b09a7a60008cce400f2e3.json`
- `e6078181c88c234a725b2c6cb125d8cf3c8191d1.json`
- `ffee848757d9ac28b0abd2e554c224333a0041c3.json`

## 5. 第三方官方源核验

核验脚本：`work/verify_wild_sboms_merge_pairs.py`

核验输出：`outputs/wild_sboms_independent_verification.json`

核验结论如下：

| 统计口径 | CONFIRMED | SUSPECT | WRONG |
|---|---:|---:|---:|
| 去重后的独立跨生态关系 | 1 | 0 | 0 |
| 原始 7 条文件记录 | 7 | 0 | 0 |

记录级为 7 是因为同一个关系在 7 个 SBOM 文件中重复出现，不代表有 7 份独立证据。

使用的官方或一手证据：

- npm 官方 registry：`https://registry.npmjs.org/%40nesk%2Frialto/1.4.0`
- Packagist 官方元数据：`https://repo.packagist.org/p2/nesk/rialto.json`
- GitHub 源码清单：`https://raw.githubusercontent.com/nesk/rialto/1.4.0/package.json`
- GitHub Composer 清单：`https://raw.githubusercontent.com/nesk/rialto/1.4.0/composer.json`
- GitHub 仓库 API：`https://api.github.com/repos/nesk/rialto`

核验证据：

- npm registry 返回 `@nesk/rialto@1.4.0`，repository 为 `git+https://github.com/nesk/rialto.git`。
- Packagist 返回 `nesk/rialto@1.4.0`，source 为 `https://github.com/nesk/rialto.git`。
- 两个官方包源的包名、版本和仓库身份一致。
- git tag `1.4.0` 下的 `package.json` 包含 `@nesk/rialto@1.4.0`。
- 同一 tag 下的 `composer.json` 包含 `nesk/rialto`；Composer 清单通常不写 `version`，版本由 tag 和 Packagist 元数据提供。
- `github.com/nesk/rialto` 当前跳转到 `rialto-php/rialto`，仓库已归档，但旧仓库地址仍解析到同一项目。
- Packagist 将该包标记为 abandoned，但这不影响 1.4.0 版本的同源关系核验。

本次样本只涉及 Composer 和 npm。用户指定的 PyPI 与 Debian 官方源在本样本中不适用；核验脚本已经实现 `pypi`、`deb` 和 `dpkg` 的路由，可在未来出现对应样本时使用。

## 6. 规则评估与修正建议

是否需要进一步修正：需要。

主要判断如下：

1. 当前窄例外不能代表普通 package SBOM 的跨生态场景。常见 Wild SBOMs 组件大多是 `asset_type=package`，不是 `model`，因此模型别名规则天然不会触发。
2. 只删除 `asset_type=model` 限制没有意义。版本一致性、共同有效路径和 npm/pypi/huggingface 白名单仍使新增合并为 0。
3. 不应把“同名 + 同版本 + 同仓库 URL”直接扩展为通用自动合并规则。单体仓库、文档站和共享 homepage 都可能让不同包指向同一 URL。
4. 本次 7 对虽然经官方源确认，但证据来自现有 URL 规则，不是窄例外。建议把 URL 触发的跨生态合并降为复核候选，除非官方 registry 或源仓库清单能够证明两个包属于同一项目。
5. 可以增加受控的“跨生态项目映射”信号，例如 npm 与 Composer 元数据同时指向同一源码仓库，且两个源仓库清单在相同 tag 中互相存在或明确引用。该信号应附版本护栏，并保留官方链接和 manifest 摘要。
6. 建议保留“版本一致”硬护栏。Wild SBOMs 中有 11,159 对未满足版本一致且非空，版本不应被 URL 或作者信号覆盖。
7. 建议区分“名称相同”和“命名空间相同”。当前包名可能经过 scope 和 namespace 归一化，跨生态合并时仍需保留原始 purl，防止同名不同命名空间被错误折叠。

## 7. 可直接用于技术报告的验证段落

为补充数据集只出现 `npm::npm` 配对的不足，本文在 Wild SBOMs 的 57,877 个 CycloneDX JSON 文件上进行了全量跨生态实体对齐验证。扫描共发现 1,817 个候选文件，包含 14,706 对同名但 purl type 不同的组件。使用现有实体解析器处理后，11,427 对进入跨生态判定，严格模式自动合并 7 对，窄例外触发 0 对。窄例外的四个必要条件中，11,427 对均不满足双方 `asset_type=model`，11,423 对缺少共同有效文件路径，11,159 对版本不一致或缺失，9,608 对不属于 `npm/pypi/huggingface` 允许集合。仅取消 `asset_type=model` 限制后，自动合并总数仍为 7 对，新增为 0 对，说明版本与路径约束同样是主要瓶颈。7 对现有合并去重后仅对应一个关系，即 `pkg:composer/nesk/rialto@1.4.0` 与 `pkg:npm/%40nesk/rialto@1.4.0`。该关系经 npm registry、Packagist、GitHub tag 下的 `package.json` 与 `composer.json` 独立核验，结果为 `CONFIRMED`。按独立关系统计，核验结果为 `CONFIRMED=1, SUSPECT=0, WRONG=0`。结果表明，Wild SBOMs 能提供真实跨生态碰撞样本，但当前模型别名窄例外无法覆盖普通 package 场景；规则若从模型扩展到更多生态，应引入官方 registry 或同源仓库清单作为受控证据，而不能仅依赖同名和相同 URL 自动合并。

## 8. 产出文件

- `scan_cross_ecosystem.py`
- `outputs/cross_ecosystem_candidates.json`
- `work/validate_wild_sboms_merge.py`
- `outputs/wild_sboms_merge_validation.json`
- `work/verify_wild_sboms_merge_pairs.py`
- `outputs/wild_sboms_independent_verification.json`
- `outputs/wild_sboms_cross_ecosystem_report.md`
