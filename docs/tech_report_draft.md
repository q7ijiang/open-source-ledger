# 面向 ModelScope 生态的 AI 模型血缘许可证变更风险传播工具

## 技术报告（初稿）

| 项目 | 内容 |
|---|---|
| 项目名称 | 面向 ModelScope 生态的 AI 模型血缘许可证变更风险传播工具 |
| 项目代号 | 开源账本（open-source-ledger） |
| 项目周期 | 2026-09-18 至 2026-10-16 |
| 报告版本 | v0.1 初稿 |
| 报告日期 | 2026-10-18 |
| 数据源边界 | 当前生产链路 100% 聚焦阿里云 ModelScope 生态 |
| 文档状态 | 技术报告初稿，可用于内部评审、答辩准备与后续定稿 |

> 数据边界声明：当前主分支的生产链路已经完成数据源收敛，模型扫描、项目扫描、血缘抽取、风险判定与时间对比均以 ModelScope 为目标生态。仓库中的历史验证材料不参与当前运行时数据路由。`--model` 在 ModelScope 详情接口返回 404 或网络探测失败时不会回退到其他模型平台，而是给出明确错误，避免形成假成功。

## 摘要

AI 模型的许可证风险正在从“单个组件是否采用受限协议”演变为“血缘链上的许可证义务能否被下游继承”。传统软件成分分析工具擅长识别静态依赖和许可证标识，却难以回答“上游基座模型的许可证变更会影响哪些派生模型、影响路径是什么、路径证据是否充分”。平台系谱图能够展示派生、微调、量化等关系，但通常以静态数量或平台内可视化为中心，缺少时间化差异检测、证据分级和工程化阻断能力。

针对上述问题，本项目构建了一套面向 ModelScope 生态的 AI 模型血缘许可证变更风险传播工具。系统采用 A/B/C 三层可插拔架构：A 层负责 ModelScope 数据适配、实体标识、聚合降维与 CycloneDX BOM 导出；B 层负责许可证 P/D/P 规则、Parse-Determine-Propagate 判定流水线、证据分级、Delta 检测与反向风险传播；C 层负责红黄绿灰可视化、时间轴对比、Streamlit 交互和 GitHub Action 自动化。核心算法与数据源解耦，数据源变化被限制在适配器边界内，算法层不依赖特定平台的字段结构。

工程成果方面，系统支持 `--model`、`--project`、`--diff` 与 `--mode basic` 等入口，能够生成中文审计报告、交互式血缘图和可离线复核的 CycloneDX 1.7 BOM。Qwen-Image-2.1 案例表明，许可证从 Apache-2.0 变更为 qwen-research 后，平台血缘接口聚合出的 2000 余个下游适配器可被压缩为带 `count` 属性的风险节点，避免图谱规模失控。177 节点真实语料测试得到红 1、黄 4、灰 143、绿 29 的四态分布，灰色占比 80.8%，客观反映了当前模型元数据缺失和证据不足的现状。当前测试集实跑结果为 86 passed，达到“85+ 测试全绿”的阶段目标；离线断网渲染、时间轴传播和 GitHub Action 风险阻断均已完成验证。

**关键词：** ModelScope；AI 模型血缘；许可证传播；CycloneDX；证据分级；软件成分分析；风险可视化

## 目录

1. [项目背景与问题定义](#1-项目背景与问题定义)
2. [需求分析与目标](#2-需求分析与目标)
3. [系统总体架构](#3-系统总体架构)
4. [数据管道层（A 层）设计与实现](#4-数据管道层a-层设计与实现)
5. [算法引擎层（B 层）设计与实现](#5-算法引擎层b-层设计与实现)
6. [交付与验证层（C 层）设计与实现](#6-交付与验证层c-层设计与实现)
7. [系统测试与验证](#7-系统测试与验证)
8. [竞品对比与创新点](#8-竞品对比与创新点)
9. [局限性与未来工作](#9-局限性与未来工作)
10. [团队分工与项目管理](#10-团队分工与项目管理)
11. [总结](#11-总结)

## 1 项目背景与问题定义

### 1.1 真实案例：Qwen-Image-2.1 许可证变更

2026 年 9 月 20 日，Qwen-Image-2.1 在 ModelScope 发布。与上一代采用 Apache-2.0 的许可证状态相比，该模型变更为仅限非商业用途的 qwen-research 协议。该变化并非普通的文本替换：在模型生态中，基座模型、微调模型、适配器、量化版本和下游应用之间存在持续的血缘关系，上游许可证义务会沿派生关系向下游传导。对于已经基于上一代模型构建商业产品或内部服务的团队，许可证变更会直接影响再分发、商用部署、模型托管和衍生模型发布。

ModelScope 的血缘接口将该模型的下游关系聚合为 Adapters、Finetunes、Quantizations 等类别，并返回类别数量而非完整节点列表。项目抓取的不同时间点中，Adapters 计数出现 1873、2315 等数值，说明平台实时统计存在自然漂移；但无论采用哪个快照，下游适配器规模均处于“2000 余个”的量级。若按真实节点逐一展开，图谱会快速膨胀，前端渲染、离线存储和传播计算均会承受不必要压力。因此，本项目不将“2000+”简单理解为一个静态数字，而将其视为一个需要保留规模语义、又必须控制计算复杂度的聚合风险域。

![图 1-1 Qwen-Image-2.1 许可证变更与下游影响示意](figures/fig1-1-qwen-case.png)

图 1-1 说明：基座模型许可证变更后，风险沿派生、微调与量化关系向下游传播；平台聚合计数用于表达下游规模。

### 1.2 从组件合规到链条合规

传统软件成分分析通常以组件为中心，输出依赖清单、许可证字段、漏洞列表和策略告警。该方法适用于“项目直接或间接依赖了哪些包”的场景，但对 AI 模型生态存在三个结构性缺口。

第一，许可证风险具有继承性。一个微调模型即使自身声明为 Apache-2.0，也不意味着它可以脱离基座模型的非商业限制独立商用。许可证字段之间存在语义约束，派生关系的方向决定义务如何传递。

第二，平台系谱图以展示为主。平台可以告诉用户“存在多少个派生模型”，却不一定提供可离线复核的路径证据、时间化差异检测和 CI 阻断。静态数量不能回答“本次变更新增了哪些受影响资产”。

第三，模型卡和许可证文本高度非标准化。字段名称、协议别名、复合表达式、长文本补充条款同时存在。单纯依赖字符串相等判断会产生漏报，单纯依赖大模型生成判断又会削弱可追溯性。工程系统需要在自动化和证据审计之间取得平衡。

### 1.3 公开研究与项目调研数据

项目前期调研材料引用了两项公开研究统计：在相关模型血缘样本中，36.8% 的血缘关系存在许可证不兼容；非商业限制在派生链中的保留率仅 20.7%。前者说明许可证冲突并非边缘现象，后者说明上游限制在多次转手、适配和再发布后容易发生语义衰减。两项数据用于说明问题规模，不用于替代针对具体模型的法律判断。

> 数据口径说明：36.8% 与 20.7% 来自项目组整理的公开研究统计，正式论文或答辩定稿应补充可核验的篇名、作者、年份与 DOI。本报告不将这两项数据表述为本项目自测结果。

### 1.4 传统工具的能力边界

传统 SCA 工具的核心对象是软件包和依赖边。它们能够高效处理 PyPI、npm、Maven 等生态中的包级依赖，却通常不具备以下能力：

- 将 ModelScope 的 `SonModels`、`ParentsModels` 等平台字段归一化为跨生态可理解的资产与边。
- 区分“官方字段搬运”“工具推导”和“启发式推断”三类证据。
- 对同一实体的两个 BOM 快照执行版本化 Delta 检测。
- 沿反向血缘执行路径传播，并输出可审计的路径证书。
- 在没有网络的环境中，Diff 的血缘读取与传播计算仅依赖 BOM 内固化祖先；可选证据补全在超时后降级，不阻断分析。

因此，本项目将问题定义为：**在 ModelScope 模型生态中，构建一条从平台数据摄入、许可证判定、血缘传播到交付阻断的可追溯链路，使许可证变更能够被及时识别、被解释、被复核，并能够进入自动化工程流程。**

## 2 需求分析与目标

### 2.1 功能需求

| 编号 | 功能 | 命令入口 | 输入 | 输出 | 验收要点 |
|---|---|---|---|---|---|
| F1 | 单模型血缘扫描 | `python main.py --model Qwen/Qwen-Image-2.1` | ModelScope 命名空间/模型名 | `assets.json`、`edges.json`、`graph.json`、`report.md` | 正确提取许可证、聚合节点与血缘边 |
| F2 | 项目级扫描 | `python main.py --project <path>` | 项目目录、配置或 BOM 中的模型标识 | 合并图与中文报告 | 识别多个 ModelScope 模型并按标识去重 |
| F3 | 时间化差异分析 | `python main.py --diff --before t0.json --after t1.json` | 两个 CycloneDX BOM | Delta 事件、传播证书、Markdown 报告 | 仅使用 BOM 内祖先，风险判定可复核 |
| F4 | 基础清单模式 | `python main.py --mode basic --input bom.json` | 单个 CycloneDX BOM | 中文开源及第三方资源清单 | 标注风险、证据和人工核对项 |
| F5 | 深度模式 | `python main.py --mode deep --before t0.json --after t1.json` | 两个 BOM | 深度传播报告 | 事件、路径和判定统计完整 |
| F6 | 交互式演示 | `streamlit run app.py` | 模型名、项目路径或两个 BOM | 交互图与报告下载 | 三种模式可切换，结果可复现 |
| F7 | CI 自动阻断 | GitHub Action | 仓库代码与 API Key Secret | Artifact、Job 状态 | 出现 `RISK_CONFIRMED` 时阻断 |

### 2.2 非功能需求

| 维度 | 要求 | 设计响应 |
|---|---|---|
| 平台无关性 | 核心算法不绑定 ModelScope 字段 | A 层适配器输出统一 Schema，B 层只消费资产与边 |
| 离线可运行 | 时间对比不依赖当前平台状态 | 血缘边固化进 `pedigree.ancestors`，Diff 不重拉祖先；证据补全超时降级 |
| 可解释性 | 每个判定能够回溯证据与路径 | 证据等级、来源字段、路径证书、判定原因同时保留 |
| 确定性 | 同一输入产生同一分析结果 | 快照标识固定、边去重、规则版本化、路径指纹稳定 |
| 自动化 | 能够进入 PR 和定时任务 | Composite Action、Cache、Artifact、非零退出码阻断 |
| 安全性 | API Key 不进入仓库与 Artifact | GitHub Secrets 注入，Fork PR 默认跳过 |
| 可扩展性 | 新数据源和新规则可增量接入 | 适配器接口、规则库、证据等级、渲染器分别扩展 |
| 可用性 | 非技术验收人员能够阅读 | 中文报告、红黄绿灰图例、表格化摘要 |

### 2.3 目标与非目标

项目目标是建立一个可解释、可离线复核、可进入工程流程的模型血缘许可证风险传播系统。非目标包括：替代执业法律意见、对所有非标许可证做最终定性、在不掌握训练数据的情况下推断完整数据集血缘、以及为平台上的每一个下游模型无条件拉取详情。

## 3 系统总体架构

### 3.1 架构原则

系统遵循四项架构原则。

1. **数据源可插拔，核心算法平台无关。** ModelScope 的详情接口、血缘接口和字段命名由 A 层消化。B 层接收的是统一资产节点、血缘边、事件和快照，不直接读取平台原始响应。
2. **证据先于结论。** 每个许可证、每条血缘边和每个路径证书都携带证据等级与来源字段。判定结果必须能够回溯到输入证据。
3. **聚合与展开分离。** 对平台只提供计数的下游类别使用聚合节点；对需要逐节点分析的项目级扫描保留可展开路径。聚合节点不参与精细时间对比。
4. **离线边界清晰。** 在线扫描负责获取当下状态，BOM 导出负责冻结状态，`--diff` 负责比较两个已冻结状态。时间对比不依赖平台今天的接口返回。

![图 3-1 系统总体架构](figures/fig3-1-architecture.png)

图 3-1 说明：A 层将 ModelScope 数据转换为统一 Schema；B 层完成规则判定与传播；C 层完成报告、图形、交互和 CI 交付。

### 3.2 三层职责划分

| 层级 | 名称 | 核心职责 | 主要模块 | 输出 |
|---|---|---|---|---|
| A 层 | 数据适配层 | 平台 API 摄入、字段映射、标识生成、实体对齐、聚合降维、BOM 导出 | `modelscope_adapter.py`、`bom_adapter.py`、`entity_resolver.py`、`export_bom.py` | 资产、边、图、BOM |
| B 层 | 算法引擎层 | 许可证规则、证据分级、四态判定、Delta 检测、反向传播、路径证书 | `license_db.py`、`risk_evaluator.py`、`delta_engine.py`、`propagation_engine.py` | 事件、证书、判定 |
| C 层 | 交付与验证层 | 报告、渲染、时间轴、交互、测试数据、CI | `report_basic.py`、`report_enhanced.py`、`render_graph.py`、`render_diff.py`、`app.py`、`action.yml` | Markdown、HTML、PNG、Action 结果 |

### 3.3 数据流转

```text
ModelScope Detail API ─┐
ModelScope Lineage API ─┼─> A 层适配器
项目源码/配置/BOM ──────┘        │
                                 ├─> 统一资产节点 assets
                                 ├─> 统一血缘边 edges
                                 └─> CycloneDX 1.7 BOM
                                           │
t0 BOM ────────────────────────────────────┤
t1 BOM ────────────────────────────────────┘
                                           │
                                           v
                                  B 层快照解析与建图
                                           │
                              Delta 事件检测（8 类）
                                           │
                              反向 BFS + weakest link
                                           │
                                  路径证书与四态判定
                                           │
                                           v
                         C 层 Markdown / HTML / PNG / CI 阻断
```

![图 3-2 系统数据流转](figures/fig3-2-dataflow.png)

图 3-2 说明：原始平台响应只在 A 层出现；B 层输入为稳定 Schema；C 层只消费结构化结果。

### 3.4 统一数据契约

| 字段 | 作用 | 约束 |
|---|---|---|
| `entity_key` | 跨版本稳定实体键 | `asset_type:ecosystem/namespace/name`，不含版本 |
| `canonical_id` | 版本化唯一标识 | `entity_key@version`，无版本时与实体键相同 |
| `purls` | 标准资产定位 | 优先使用 Package URL；聚合节点允许为空 |
| `license` | 许可证原文或规范化值 | 未知时为 `null`，不写空字符串 |
| `evidence_chain` | 证据列表 | 每条包含等级、来源、字段、时间、状态和原值 |
| `snapshot_id` | 快照标识 | `t0`、`t1`、`modelscope-<ns>__<name>` 等 |
| `merge_status` | 对齐状态 | `MERGED`、`REVIEW`、`KEPT_SEPARATE`、`UNDETERMINED` |
| `decision` | 判定结果 | `RISK_CONFIRMED`、`RISK_POTENTIAL`、`UNDETERMINED`、`SAFE` |
| `count` | 聚合规模 | 仅用于聚合节点，表示该类下游或祖先的数量 |

### 3.5 部署形态

系统提供三种部署形态。命令行形态适合开发者和审计人员；Streamlit 形态适合演示与交互验收；GitHub Action 形态适合在用户仓库中定时扫描、生成 Artifact 并阻断高风险变更。三种形态复用同一套 `main.py` 与算法模块，避免出现“演示逻辑”和“生产逻辑”两套实现。

## 4 数据管道层（A 层）设计与实现

### 4.1 ModelScope 数据摄入

A 层通过 ModelScope 官方详情接口和血缘接口获取模型信息。请求层统一处理 `{Code, Data}` 信封，解析 `Data` 字段；详情接口 404 表示模型不存在，血缘接口 404 或 405 表示该模型没有可用血缘。网络异常在模型模式中转为明确错误，不回退到其他平台；在项目扫描中则过滤无效候选并生成空结果说明，避免静默假绿。

许可证提取优先读取 `Data.LicenseName`，其次读取 `Data.License`。`other`、`none`、`unknown` 等通用类别不视为具体许可证，防止把“未知”当作有效协议。标准别名被归一化为 SPDX 或项目规则库标识，非标协议保留原始名称。

### 4.2 字段映射与命名空间

平台文档字段与实际响应存在差异。项目中实测命名空间位于 `Data.Path`，而不是文档示例中的 `Namespace`。A 层采用 `Path -> Namespace -> Organization.Name` 的优先级提取命名空间，确保 PURL 与 canonical_id 不丢失组织信息。

| 统一字段 | ModelScope 来源 | 处理规则 |
|---|---|---|
| `name` | `Path` + `Name` 或 `Organization.Name` + `Name` | 生成可读的 `namespace/name` |
| `namespace` | `Path`、`Namespace`、`Organization.Name` | 按优先级兜底 |
| `version` | `Revision` | 缺失时保留空值，由标识生成器处理 |
| `license` | `LicenseName`、`License` | 优先具体协议名，过滤通用占位值 |
| `source_url` | 详情接口 URL | 写入证据链，便于复核 |
| `evidence_chain` | 官方字段原值 | 许可证字段标 A 级证据 |
| `snapshot_id` | 扫描上下文 | 模型级或 `t0/t1` 快照 |
| `entity_key` | 标识生成器 | 去除版本，跨快照稳定 |
| `canonical_id` | 标识生成器 | 附加版本，当前快照内唯一 |

![图 4-1 ModelScope 字段映射与标识生成](figures/fig4-1-field-mapping.png)

图 4-1 说明：原始字段在适配器内完成归一化，算法层不感知 `Data.Path` 等平台细节。

### 4.3 标识符生成：PURL 与 canonical_id

系统同时维护 PURL 与内部标识。PURL 用于跨工具交换和 CycloneDX 组件定位，内部标识用于图算法与跨版本对齐。

以 Qwen-Image-2.1 为例：

```text
entity_key  = model:modelscope/Qwen/Qwen-Image-2.1
canonical_id = model:modelscope/Qwen/Qwen-Image-2.1@master
purl         = pkg:modelscope/Qwen/Qwen-Image-2.1@master
```

内部标识分为两段。`entity_key` 是跨版本稳定键，用于判断“同一个模型换了版本”；`canonical_id` 是版本化键，用于图节点、事件 seed 和路径证书。PURL 中的 qualifiers 只作为审计信息保留，不进入主键，避免同一模型因镜像或查询参数不同被拆分为多个节点。对于没有真实 PURL 的聚合节点，BOM 导出时会从 canonical_id 构造稳定 PURL，以保证 `pedigree.ancestors` 在离线 Diff 时仍能恢复边。

### 4.4 聚合降维：解决 2000+ 节点图谱爆炸

ModelScope 血缘接口返回的是 `SonModels`、`ParentsModels` 等分组计数，例如 Adapters、Finetunes、Quantizations。若为每个下游模型单独拉取详情，一次扫描将产生数千次请求，并生成难以阅读和存储的图。A 层采用“聚合节点 + count 属性”的降维方式：

- 每个血缘类别生成一个聚合节点。
- 节点名称保留类别与 `Total` 数值，例如 `Qwen/Qwen-Image-2.1 · 适配 (Total: 2315)`。
- 节点携带 `aggregate: true` 与 `count: 2315`。
- 聚合节点到当前模型的边标记为 `derived_from`，证据等级为 B，因为边由官方计数推导，而非逐模型直接证明。
- B 层对聚合节点输出 `UNDETERMINED`，不以缺失许可证为由将其判为安全。

某次真实快照中，Adapters 为 2315、Finetunes 为 22、Quantizations 为 26，总计 2363 个派生模型；另一次快照中 Adapters 为 1873。计数变化说明平台数据具有实时性，系统通过 snapshot_id 与 BOM 时间戳保留时点语义。

![图 4-2 聚合降维与 count 属性](figures/fig4-2-aggregation.png)

图 4-2 说明：聚合节点保留风险域规模，同时避免将 2000+ 节点全部展开。

### 4.5 BOM 导出：CycloneDX 1.7

`export_bom.py` 将 assets 与 edges 导出为 CycloneDX 1.7 BOM。设计目标不是生成“仅供展示的 JSON”，而是生成可再次输入系统的时间快照。

| BOM 位置 | 写入内容 | 作用 |
|---|---|---|
| `specVersion` | `1.7` | 固定标准版本，便于工具互操作 |
| `metadata.timestamp` | 带时区偏移的 RFC 3339 时间 | 支撑对比区间和快照排序 |
| `components[].bom-ref` | `canonical_id` | 与内部图节点稳定对应 |
| `components[].type` | 模型、数据集、包等映射 | 保留资产类型 |
| `components[].purl` | 真实 PURL 或内部兜底 PURL | 离线恢复祖先边 |
| `components[].licenses` | SPDX id 或原始 name | 保留标准与非标协议 |
| `components[].licenses[].evidence_level` | A/B/C | 导出证据等级 |
| `components[].licenses[].evidence_chain` | 完整证据链 | 支撑复核 |
| `components[].properties` | decision、risk_level、count、snapshot_id 等 | 固化判定上下文 |
| `components[].pedigree.ancestors` | 祖先引用、PURL、证据等级、来源字段 | 离线 Diff 的核心输入 |
| `dependencies` | `depends_on` 关系 | 保留普通依赖语义 |

BOM 中 `pedigree.ancestors` 是时间对比的关键。它把“扫描时刻看到的血缘”固化到快照内部，使后续 `--diff` 不需要重新请求平台血缘，也不会把历史快照替换为今天的最新关系。

### 4.6 工程踩坑与修复

| 问题 | 现象 | 根因 | 修复与验证 |
|---|---|---|---|
| 路径覆盖命名空间 | PURL 缺少组织名或命名空间错误 | 实际响应中组织位于 `Data.Path`，与文档示例不一致 | 采用 `Path -> Namespace -> Organization.Name` 优先级，并用真实 Qwen 响应验证 |
| 时间戳缺少时区偏移 | BOM 时间无法稳定解析，跨时区比较出现偏差 | 直接使用本地时间或省略 offset | 改为带时区的 RFC 3339 时间戳，增加动态时区断言测试 |
| 空许可证被写成空字符串 | 下游将空值误判为已声明 | 字段清洗不统一 | 统一转为 `null`，未知节点进入灰灯 |
| 聚合节点没有 PURL | Diff 无法从祖先恢复聚合边 | 平台聚合类别不是真实模型 | 从 canonical_id 构造稳定内部 PURL，保留 `aggregate` 与 `count` 属性 |
| 实时计数漂移 | 样例数量与历史报告不一致 | ModelScope 数据实时变化 | 以快照为单位记录，报告中注明抓取时点，不将动态值写死为算法常量 |
| 回退导致假成功 | 模型无法检索时命令仍以 0 退出 | 旧逻辑静默返回 | 改为显式错误，GitHub Action 检查 BOM 是否存在 |

## 5 算法引擎层（B 层）设计与实现

### 5.1 P/D/P 的两种含义

本项目中的 P/D/P 具有两层含义，需要在工程上严格区分。

第一层是**许可证语义三元组**：Permission（允许）、Duty（义务）、Prohibition（禁止）。规则库将常见开源许可证和 AI 专用协议抽象为三元组，用于比较许可证方向、解释义务增量和识别非商业限制。

第二层是**判定流水线**：Parse（解析）、Determine（判定）、Propagate（传播）。Parse 将非标字段和复合表达式转成统一语义；Determine 结合许可证规则与证据等级输出四态结果；Propagate 沿血缘关系把种子事件传播到受影响资产。

![图 5-1 Parse-Determine-Propagate 流水线](figures/fig5-1-pdp-pipeline.png)

图 5-1 说明：许可证语义与证据等级在 Determine 阶段汇合，Propagate 阶段使用最弱证据规则。

### 5.2 Parse：解析非标字段

Parse 阶段处理三类输入。

1. **标准许可证标识**：MIT、Apache-2.0、BSD-3-Clause、GPL 等，通过规则库和别名表归一化。
2. **复合表达式**：使用分号、逗号、`AND`、`OR` 连接的表达式被拆分为单项，并取风险最高项作为整体判定依据。`GPL v2 or later` 等语义片段不会被错误拆开。
3. **非标协议与长文本**：qwen-research、qwen-data-license 等名称在规则库未知时保留原文，不强行映射到某个 SPDX 标识，也不直接生成法律结论。

规则库内置 24 种许可证规则，覆盖宽松许可、弱 copyleft、强 copyleft、网络 copyleft、数据集许可和 AI 专用受限协议。每条规则包含 canonical_id、类别、P/D/P 三元组、风险等级、是否 AI 专用和说明字段。

### 5.3 Determine：四态判定

判定结果设置为四种状态，而不是简单的“安全/不安全”。

| 判定 | 中文含义 | 典型条件 | 工程行为 |
|---|---|---|---|
| `RISK_CONFIRMED` | 高风险（红） | 已知强限制许可证且有充分证据；或证据充分的明确冲突 | 进入阻断，用于 PR 失败 |
| `RISK_POTENTIAL` | 潜在风险（黄） | 非标协议有原文但规则库未知；或中等证据支持的限制性条款 | 人工复核，不自动放行 |
| `UNDETERMINED` | 待确认（灰） | 无许可证、缺失祖先、C 级推断、聚合节点 | 保留风险空缺，不判定为安全 |
| `SAFE` | 安全（绿） | 宽松许可证且证据满足要求 | 正常展示，不阻断 |

判定矩阵如下：

| 许可证识别状态 | 证据 A | 证据 B | 证据 C 或缺失 |
|---|---|---|---|
| 已知宽松许可（MIT、BSD、Apache-2.0） | 绿 | 绿，保留证据 | 灰 |
| 已知强限制许可（GPL、AGPL、AI 受限协议） | 红 | 黄 | 灰 |
| 已知弱 copyleft 或限制等级 3 | 红 | 黄 | 灰 |
| 非标协议有原文，如 qwen-research | 黄 | 黄 | 灰 |
| 无许可证或聚合节点 | 灰 | 灰 | 灰 |

![图 5-2 四态判定矩阵](figures/fig5-2-decision-matrix.png)

图 5-2 说明：风险等级与证据等级是两个正交维度，不能相互替代。

### 5.4 核心创新：证据分级机制

系统将证据分为 A、B、C 三级。

| 等级 | 定义 | 典型来源 | 不是 |
|---|---|---|---|
| A | 搬运 | ModelScope 官方 API 直接返回的 `LicenseName`、仓库 LICENSE 原值 | 不是“已通过法律审查”，也不是“风险一定高” |
| B | 推导 | 工具基于官方数据计算的聚合边、BOM 结构化字段、依赖关系 | 不是无依据猜测 |
| C | 推断或降级 | 模型卡文本正则推断、同名启发式、网络失败后的降级证据 | 不是可以直接放行的结论 |

证据分级解决了一个常见误区：**“证据确凿”不等于“风险很高”**。例如，qwen-research 由 ModelScope 官方字段直接返回，属于 A 级证据；但规则库尚不掌握其完整条款，因此判定为黄灯，而不是红灯。相反，一个缺失许可证的聚合节点即使来自官方接口，也会因为无法判断具体义务而进入灰灯。

同样，GPL-3.0 的 A 级证据意味着“许可证文本与字段明确”，并不意味着“证据等级高所以风险低”。系统将“来源可信度”和“风险严重度”拆成两个维度，在报告中分别展示。

### 5.5 Propagate：Delta 检测与反向传播

Propagate 阶段以快照差异为种子，沿血缘图反向寻找受影响资产。

Delta 检测支持以下事件：

| 事件类型 | 含义 |
|---|---|
| `license_changed` | 同一 canonical_id 的许可证发生变化 |
| `evidence_downgrade` | 同一字段的证据等级下降 |
| `version_changed` | 同一 entity_key 换版本 |
| `version_upgraded` | 从无版本引用升级为带版本 |
| `ancestor_added` | 新增祖先边 |
| `ancestor_removed` | 移除祖先边 |
| `dataset_added` | 新增训练数据关系 |
| `dataset_removed` | 移除训练数据关系 |

事件 seed 的方向是传播正确性的关键。对于边变更事件，seed 必须指向 `edge.target`，即上游变化资产；若错误指向 `edge.source`，传播会沿相反方向进行，导致路径证书为 0。项目在阶段验收中修复了该 P0 问题，真实链路证书从 0 恢复到 12。

建图使用 `MultiDiGraph`，同一对节点之间允许并行边。出现环时通过强连通分量（SCC）识别，并在传播访问集中保证终止。路径证据采用 weakest link 规则：整条路径取各步骤与种子事件中最弱的一级。同一对节点存在多条边时，先取证据最弱的一条；同等级时按 `derived_from > trained_on > depends_on` 选择。

每份路径证书包含：

- 事件 ID、seed、受影响资产和变更类型。
- 完整路径步骤、跳数与最弱证据。
- 四态判定与终止原因。
- 缺失祖先标记。
- SHA-1 路径指纹与验证状态。

### 5.6 离线时间对比

离线时间对比的关键不是“把网络请求做得更快”，而是**把时间语义固定在 BOM 内**。在线模型扫描可以获取当前血缘；导出 BOM 后，`pedigree.ancestors` 成为该快照不可变的事实来源。`--diff` 的血缘读取与传播计算只使用两个 BOM 中的资产、祖先和证据，该子流程不发起平台血缘请求，也不使用今天的平台状态重写历史关系。对支持 PURL 的资产，证据补全可发起受超时约束的元数据查询；查询失败会记录 C 级降级证据，冻结的血缘边与传播路径保持不变。

该设计带来四项工程收益：

1. **可复现。** 相同 t0/t1 BOM 在任何时间、任何网络状态下产生相同传播路径。
2. **可审计。** 报告中每个祖先都能追溯到源 BOM 的组件和证据字段。
3. **可在 CI 中运行。** 定时任务恢复缓存快照并生成新快照；血缘传播子流程不依赖平台在线状态。
4. **可比较。** 版本、许可证、证据降级和祖先变化均在同一时间坐标下解释。

### 5.7 177 节点真实语料测试

项目使用 177 节点真实语料验证四态判定分布：

| 判定 | 节点数 | 占比 |
|---|---:|---:|
| 红灯 `RISK_CONFIRMED` | 1 | 0.6% |
| 黄灯 `RISK_POTENTIAL` | 4 | 2.3% |
| 灰灯 `UNDETERMINED` | 143 | 80.8% |
| 绿灯 `SAFE` | 29 | 16.4% |
| 合计 | 177 | 100.0% |

灰色占比 80.8% 是本次测试最重要的结果之一。它并非算法失效，而是客观数据缺失的直接体现：大量真实模型没有可识别的许可证字段、许可证文本不在规则库中、祖先节点只有引用而没有元数据，或者证据只能降级为 C。系统没有为了“报告好看”把这些节点强制归为绿色，而是保留不确定性，提示人工复核。

从风险治理角度看，灰色节点需要被纳入补证队列。一个拥有 143 个灰色节点的资产域不能被宣称为“低风险”，只能被宣称为“当前证据不足”。这一口径比简单的红黄绿三色更接近真实审计场景。

## 6 交付与验证层（C 层）设计与实现

### 6.1 通用血缘渲染器

`render_graph.py` 直接读取 A 层产出的 `graph.json`，不依赖固定输出目录。渲染器从节点的 `decision` 字段读取判定，并自动映射颜色：

| 判定 | 颜色 | 图例 |
|---|---|---|
| `RISK_CONFIRMED` | 红色 | 高风险 |
| `RISK_POTENTIAL` | 黄色 | 潜在风险 |
| `SAFE` | 绿色 | 安全 |
| `UNDETERMINED` | 灰色 | 待确认 |

图形采用森林分层布局：基座模型位于上层，聚合节点位于其下方；真实模型使用圆形，聚合节点使用矩形，数据集使用菱形。与风险节点相连的边以红色加粗显示，表示风险传播方向。点击节点可以查看 canonical_id、许可证、证据链、merge_status 和 reason_code；点击边可以查看边类型、来源字段和路径证书。

![图 6-1 通用血缘风险图](figures/fig6-1-risk-graph.png)

图 6-1 说明：颜色由 decision 自动决定，渲染器不包含平台特判。

### 6.2 ECharts 本地化与离线渲染

渲染模板通过 `ECHARTS_SRC` 变量注入脚本路径。构建阶段优先查找仓库内 `echarts.min.js`，复制到输出目录，并以 `./echarts.min.js` 相对路径加载。只有在开发环境缺少本地资源时才回退 CDN；正式交付要求本地资源随 HTML 一并存在。

离线渲染验证使用 Chrome DevTools Protocol 将网络条件设为 offline，再加载本地 HTML。页面中的节点、边、图例、点击面板和风险颜色均由本地脚本与内嵌 JSON 完成，不依赖远程 API。验证重点包括：页面非空、图形节点数量正确、风险边可见、节点点击后面板能够显示证据链。

### 6.3 时间轴 Diff 渲染器

`render_diff.py` 将两个快照并排展示：左侧为 t0 基线，右侧为 t1 当前状态，中间列出 Delta 事件。点击事件后，下方显示对应的路径证书，包括受影响资产、传播链、跳数、最弱证据和判定。

时间轴视图解决三个阅读问题：第一，用户能够直观看到同一资产在两个时点的状态差异；第二，传播路径不再只存在于文字表格中；第三，风险阻断可以定位到具体事件与证书。

![图 6-2 t0 到 t1 的时间轴传播图](figures/fig6-2-timeline-diff.png)

图 6-2 说明：左 t0、右 t1，中间事件列表与下方证书共同支持时间化复核。

### 6.4 Streamlit 交互界面

`app.py` 提供三种模式：

| 模式 | 用户输入 | 后端动作 | 输出 |
|---|---|---|---|
| 单模型 | ModelScope 模型名 | 调用 `main.py --model`，再调用 `render_graph.py` | 交互图与中文报告 |
| 项目 | 项目目录 | 调用 `main.py --project`，合并多个模型血缘 | 合并图与项目报告 |
| 时间对比 | 上传 t0/t1 BOM | 调用 `main.py --diff`，再调用 `render_diff.py` | 时间轴图与传播报告 |

Streamlit 不重写数据管道逻辑，只通过子进程调用现有入口。这样能够保证演示界面与命令行结果一致，也降低维护两套逻辑的风险。

![图 6-3 Streamlit 三模式交互界面](figures/fig6-3-streamlit.png)

图 6-3 说明：单模型、项目和时间对比共用同一套后端能力。

### 6.5 GitHub Action：定时扫描与风险阻断

Action 以 Composite Action 和用户工作流两种方式提供。标准流程如下：

1. 检出用户仓库，检出工具仓库。
2. 校验 `MODELSCOPE_API_KEY` Secret。
3. 安装 Python 依赖。
4. 从 Actions Cache 恢复上一份 BOM。
5. 扫描当前项目并生成 t1 BOM。
6. 若无历史 BOM，建立首次基线并跳过 Diff。
7. 若有历史 BOM，运行 `--diff` 并检查报告中的 `RISK_CONFIRMED`。
8. 检出风险时以非零退出码阻断 Job。
9. 上传 `diff_report.md` 与 `watch_report.md` 作为 Artifact。
10. 仅在风险检查通过后推进 BOM 基线缓存。

检测逻辑会排除报告末尾固定说明表中的 `RISK_CONFIRMED`，避免说明文字本身触发误报。若项目未生成 BOM，Action 给出警告并跳过 Diff，不把“没有扫描到模型”伪装成安全。Fork PR 无法读取仓库 Secret，工作流默认跳过并提示原因，避免通过 `pull_request_target` 执行不可信代码。

![图 6-4 GitHub Action 自动扫描与阻断](figures/fig6-4-github-action.png)

图 6-4 说明：风险失败时报告仍上传，基线不推进，修复后重新运行。

## 7 系统测试与验证

### 7.1 测试策略

测试覆盖从数据解析到交付渲染的主要边界：

| 测试域 | 关键内容 | 目标 |
|---|---|---|
| BOM 解析 | 组件、许可证、证据、祖先字段 | 输入不丢字段，空值处理一致 |
| 实体解析 | PURL 坐标、版本、合并状态 | 同一实体可对齐，冲突不误合并 |
| 许可证规则 | 别名、复合表达式、方向比较 | 规则可解释，未知项保留 |
| 图构建 | 多边、缺失祖先、SCC | 图结构稳定，环可终止 |
| Delta 检测 | 版本、许可证、证据、边变化 | 事件 seed 与字段正确 |
| 风险传播 | weakest link、路径证书、深度限制 | 路径可复现，缺失祖先降级 |
| BOM 导出 | 时间戳、ancestors、properties | 导出后可再次 Diff |
| Diff 与渲染 | 区间、决策着色、离线资源 | 输出可阅读、可断网打开 |

当前测试集执行结果：

```text
........................................................................ [ 83%]
..............                                                           [100%]
86 passed in 216.65s (0:03:36)
```

阶段里程碑记录为“85+ 测试全绿”。当前实跑为 86 passed，说明新增测试在保持全绿的前提下进入测试集。

![图 7-1 测试金字塔](figures/fig7-1-test-pyramid.png)

图 7-1 说明：单元测试覆盖算法边界，端到端测试覆盖命令入口和真实样例。

### 7.2 端到端验证

| 场景 | 输入 | 验证结果 |
|---|---|---|
| 单模型扫描 | `Qwen/Qwen-Image-2.1` | 4 个图节点、3 条边、3 个聚合节点；某次快照聚合 2363 个派生模型 |
| 项目扫描 | `example/multi_model_project` | 多个 ModelScope 模型合并，资产与边按标识去重 |
| 规范模型 | `Qwen/Qwen2.5-7B-Instruct` | 标准 Apache-2.0 证据进入绿灯，聚合节点保持灰灯 |
| 时间对比 | `ms_t0_bom.json` → `ms_t1_bom.json` | 检测许可证变更事件，生成传播证书与报告 |
| 深度夹具 | `t0_bom.json` → `t1_bom.json` | 多类事件、SCC 环、缺失祖先和路径证书均可复现 |
| BOM 往返 | assets/edges → BOM → Diff | `pedigree.ancestors` 可恢复边，时间戳可解析 |

### 7.3 CDP 离线断网验证

离线验证不依赖在线模型接口。测试步骤为：先生成包含本地 ECharts 的 HTML；再通过 Chrome DevTools Protocol 开启 offline 网络模拟；最后加载 HTML 并检查页面节点、风险颜色、图例、点击事件和路径证书。

验证通过的标准包括：

- 页面脚本不产生远程依赖错误。
- 节点数量与 graph.json 一致。
- 红、黄、绿、灰四类节点颜色正确。
- 风险路径边为红色加粗。
- 点击节点可以展示证据链。
- 断网状态与联网状态下的图结构一致。

### 7.4 GitHub Action 自动化验证

Action 的验证分为首次运行和后续运行。首次运行没有历史缓存，系统生成基线报告，不执行 Diff；后续运行恢复历史 BOM，执行 Diff，并将新的 BOM 作为基线。出现 `RISK_CONFIRMED` 时 Job 失败，Artifact 仍上传，Cache 不推进。该行为保证风险修复后重新运行时，比较基线仍然是上一次安全通过的版本。

### 7.5 验证结论与剩余风险

测试表明，系统能够覆盖 ModelScope 模型扫描、项目扫描、BOM 往返、时间对比、离线渲染和 CI 阻断的主路径。剩余风险主要来自外部数据，而不是工程流程：平台计数实时漂移、部分模型卡缺少许可证、非标协议文本不在规则库中、数据集血缘未被完整结构化。上述问题在报告中以灰色节点和局限性章节显式保留。

## 8 竞品对比与创新点

### 8.1 竞品定位

| 维度 | LCC 类许可证合规工具 | OpenSCA | FOSSA | 本项目 |
|---|---|---|---|---|
| 核心对象 | 许可证文本与组件义务 | 软件依赖与漏洞/许可证 | 商业 SCA 与策略治理 | AI 模型血缘与许可证传播 |
| 关系模型 | 组件级为主 | 依赖树为主 | 依赖图与策略 | 派生、训练、依赖的统一血缘 |
| 时间化分析 | 有限 | 依赖版本差异 | 版本与策略差异 | t0/t1 BOM + Delta + 传播证书 |
| 非标协议 | 依赖人工或规则扩展 | 以包生态为主 | 商业规则库 | 灰区保留 + 证据分级 + 人工复核 |
| 平台适配 | 通用代码仓库 | 多包生态 | 多包生态 | ModelScope 专用适配器，核心平台无关 |
| AI 模型语义 | 弱 | 弱 | 弱 | 强，支持模型、数据集、聚合节点 |
| 离线能力 | 依产品部署方式 | 依产品部署方式 | 云服务为主 | 本地 HTML、BOM Diff、离线证据 |
| CI 阻断 | 支持 | 支持 | 支持 | 支持，并区分首次基线、风险失败与缓存推进 |

### 8.2 “点”与“链”的差异

传统工具回答“这个组件使用了什么许可证”。本项目回答四个连续问题：

1. 这个模型的上游是谁。
2. 上游许可证何时发生了变化。
3. 变化沿哪些路径影响下游。
4. 每条路径的证据是否足以支持阻断。

因此，本项目的差异化不在“再做一个许可证清单”，而在“把许可证判断嵌入血缘链和时间链”。点级工具的输出是清单，链级工具的输出是事件、路径、证书和阻断。

### 8.3 创新点

**动态风险折叠。** 平台返回的 2000+ 下游模型通过聚合节点表达，同时保留 count 属性。系统既不一味展开导致图谱爆炸，也不丢失规模语义。

**非标灰区保留。** qwen-research 等未知协议不会被强制映射为 Apache-2.0 或 GPL，也不会被误判为安全。系统保留原值、证据和人工复核入口。

**可追溯证据链。** 每个许可证、边和路径都带有来源字段、证据等级、时间与原始值。路径证书使用指纹固定传播结果，支持后续复核。

**数据源适配器架构。** ModelScope 字段差异被限制在 A 层。B 层不读取平台原始响应，新增数据源只需实现适配器与 Schema 映射。

**离线时间对比。** 通过 BOM 内 `pedigree.ancestors` 固化历史关系，使时间对比可复现、可在 CI 中运行。

**自动化风险阻断。** Action 将风险检查放入 PR 和定时任务，风险存在时阻断并保留报告，风险通过后才推进基线。

## 9 局限性与未来工作

### 9.1 局限性

**非标协议覆盖边界。** 规则库无法穷尽所有厂商协议、补充条款和长文本例外。qwen-research 等协议即使有官方字段，也需要人工或法律审查。

**聚合节点不适合精细时间对比。** 聚合节点表达“某类下游共有多少”，不表达每个具体模型的版本、许可证和边。它可以用于风险提示，不能替代逐模型审计。

**证据分级衡量“是否转手”，不衡量“源头是否正确”。** A 级表示字段由官方接口直接搬运，不表示官方字段本身一定完整、准确或符合特定业务场景。

**数据集血缘尚未完全打通。** 当前时间对比主要依赖 `derived_from` 与 BOM 内祖先。`trained_on`、数据集卡片、训练配方和数据处理链尚未形成与模型同等成熟的离线证据链。

**平台计数存在漂移。** 同一模型在不同时间抓取会呈现不同 `Total`。系统通过快照记录时点，但不能将两个不同时点的计数直接解释为模型新增或删除。

**法律判断边界。** 工具输出是工程辅助审计，不构成法律意见，也不能替代针对司法辖区、商业模式和分发方式的专业法律审查。

### 9.2 未来工作

1. **扩展数据源适配器。** 在保持 B 层平台无关的前提下，增加更多模型托管平台、企业内部模型仓库和数据集目录。
2. **引入受控 LLM 辅助解析。** 对长文本协议生成结构化候选条款，但必须保留原文引用、模型版本、置信度和人工确认环节。
3. **建设社区规则库。** 将非标协议、厂商条款、版本差异和判定理由以可审核方式维护，形成规则版本与回归样本。
4. **打通数据集与训练关系。** 将 `trained_on`、数据卡字段、数据处理脚本和模型卡证据纳入同一快照。
5. **增加路径优化。** 当前反向 BFS 保证可达性与 weakest link，未来可研究“证据最优路径”和“风险最短路径”的多目标选择。
6. **完善评测体系。** 建立跨模型、跨协议、跨证据等级的金标准样本，评估漏报率、误报率和人工复核成本。

## 10 团队分工与项目管理

### 10.1 角色分工

| 角色 | 职责 | 主要交付 |
|---|---|---|
| A：数据管道与架构 | ModelScope 适配器、BOM 解析、实体对齐、标识生成、证据补全、BOM 导出、GitHub Action、全流程集成 | 统一 Schema、A 层代码、BOM、Action |
| B：算法核心与判定 | 许可证规则、P/D/P 三元组、图构建、Delta 检测、风险传播、路径证书 | 规则库、B 层引擎、算法测试 |
| C：交付渲染与测试数据 | 中文报告、通用渲染、时间轴视图、Streamlit、基础与深度测试数据、验证产物 | 报告模板、HTML/PNG、测试语料 |

### 10.2 通过统一 Schema 解耦

三方协作不通过“互相调用内部函数”实现，而通过 JSON Schema 和命令入口解耦。A 层交付 assets、edges、graph 和 BOM；B 层交付 events、propagated 和 certificates；C 层只消费稳定字段。接口约定升级到 v0.3 后，新增 `entity_key`、`decision`、`merge_status`、`direction` 和 `path_certificates`，三方仍可在各自分支独立测试。

| 边界 | 上游 | 下游 | 稳定契约 |
|---|---|---|---|
| A → B | 资产、边、图 | 规则判定、Delta、传播 | 资产节点、血缘边、snapshot_id |
| B → C | 事件、证书、判定 | 报告、渲染、Action | events、path_certificates、decision |
| C → 用户 | Markdown、HTML、PNG | 审计人员、PR 流程 | 中文报告、颜色图例、Artifact |

### 10.3 Git 协作轨迹

项目使用主分支、功能分支和 Pull Request 进行协作。Git 历史中包含数据管道、算法、渲染、时间戳修复、Action 交付等独立提交，并保留 PR 合并记录。当前统计为 108 次提交、4 个贡献者身份，主要合并轨迹覆盖 `dev-B`、`Prolimoon-patch-1`、`fix/diff-frozen-bom-lineage`、`fix/b-evidence-dedup-interval` 等分支。

项目管理采用周目标、每日同步、接口变更记录和验收清单。关键 P0 问题（边事件 seed 方向、时间戳时区、BOM 导出、离线血缘）均有独立提交和回归测试，避免在集成阶段通过口头约定掩盖接口不一致。

## 11 总结

本项目围绕 ModelScope 生态中的 AI 模型许可证变更风险，构建了一条从平台数据到工程阻断的完整链路。系统没有把许可证合规简化为静态字段匹配，而是将资产标识、血缘关系、时间快照、证据等级和传播判定组合为可解释的分析对象。

三层架构使数据源与算法核心解耦：A 层负责把 ModelScope 的实时结构转换为稳定数据，B 层负责在证据约束下判定与传播，C 层负责把结果转化为可读、可交互、可自动化的交付物。Qwen-Image-2.1 案例验证了 2000+ 下游适配器的聚合表达；177 节点语料验证了灰区保留与四态判定；86 项测试、离线渲染和 GitHub Action 验证了工程可用性。

项目的核心价值在于把“许可证是否变化”推进为“变化沿哪条血缘链影响谁、证据是否充分、能否进入自动化流程”。在模型生态持续扩张、协议持续分化和下游派生持续增长的背景下，这一能力比单点许可证清单更接近真实治理需求。

## 参考文献

[1] 项目组. AI 模型许可证兼容性与血缘限制公开研究数据汇编[R]. 2026. 说明：用于 36.8% 与 20.7% 两项调研数据的量级引用，正式定稿需补充原始论文条目与 DOI。

[2] CycloneDX. CycloneDX Bill of Materials Specification 1.7[EB/OL]. https://cyclonedx.org/specification/overview/.

[3] Package URL Project. Package URL Specification[EB/OL]. https://github.com/package-url/purl-spec.

[4] SPDX. SPDX License List[EB/OL]. https://spdx.org/licenses/.

[5] ModelScope. ModelScope 模型与血缘 API[EB/OL]. https://www.modelscope.cn/.

[6] GitHub. GitHub Actions Documentation[EB/OL]. https://docs.github.com/actions.

[7] NetworkX. NetworkX Documentation[EB/OL]. https://networkx.org/documentation/stable/.

[8] Apache Software Foundation. Apache ECharts Documentation[EB/OL]. https://echarts.apache.org/.

[9] CycloneDX. Machine Learning Bill of Materials[EB/OL]. https://cyclonedx.org/capabilities/mlbom/.

[10] Open Source Security Foundation. Software Component Verification Standard[EB/OL]. https://scvs.owasp.org/.

## 附录 A 主要命令

### A.1 单模型扫描

```bash
python main.py --model Qwen/Qwen-Image-2.1
```

### A.2 项目扫描

```bash
python main.py --project example/multi_model_project
```

### A.3 基础清单

```bash
python main.py --mode basic --input data/sample_bom.json
```

### A.4 深度模式

```bash
python main.py --mode deep --before data/test_scenarios/ms_t0_bom.json --after data/test_scenarios/ms_t1_bom.json
```

### A.5 时间对比

```bash
python main.py --diff \
  --before data/test_scenarios/ms_t0_bom.json \
  --after data/test_scenarios/ms_t1_bom.json \
  --output outputs/ms_diff/report.md
```

### A.6 渲染图

```bash
python render_graph.py \
  --input outputs/Qwen__Qwen-Image-2.1/graph.json \
  --output outputs/Qwen__Qwen-Image-2.1/lineage.html
```

### A.7 时间轴渲染

```bash
python render_diff.py \
  --before data/test_scenarios/ms_t0_bom.json \
  --after data/test_scenarios/ms_t1_bom.json \
  --output outputs/ms_diff/diff_lineage.html
```

### A.8 测试

```bash
python -m pytest -q
```

## 附录 B 字段速查

| 字段 | 示例 |
|---|---|
| `snapshot_id` | `t0`、`t1`、`modelscope-Qwen__Qwen-Image-2.1` |
| `entity_key` | `model:modelscope/Qwen/Qwen-Image-2.1` |
| `canonical_id` | `model:modelscope/Qwen/Qwen-Image-2.1@master` |
| `purl` | `pkg:modelscope/Qwen/Qwen-Image-2.1@master` |
| `evidence_level` | `A`、`B`、`C` |
| `decision` | `RISK_CONFIRMED`、`RISK_POTENTIAL`、`UNDETERMINED`、`SAFE` |
| `edge_type` | `derived_from`、`trained_on`、`depends_on` |
| `change_type` | `license_changed` 等 8 类 |
| `termination` | `exhausted`、`max_depth`、`scc_cycle` |
| `path_fingerprint` | SHA-1 路径指纹 |

## 附录 C 术语表

| 术语 | 含义 |
|---|---|
| AI 模型血缘 | 模型之间由派生、微调、量化、训练或依赖形成的关系 |
| 风险传播 | 上游许可证或证据变化沿血缘影响下游资产的过程 |
| 证据等级 | 对判断来源可靠性与转换程度的 A/B/C 分级 |
| weakest link | 路径中最弱证据决定整条路径证据等级 |
| 聚合节点 | 用 count 表达一类下游或祖先规模的节点 |
| 四态判定 | 红、黄、灰、绿四种工程判定状态 |
| 路径证书 | 记录 seed、路径、证据、判定与终止原因的可审计对象 |
| 离线时间对比 | 在两个已固化 BOM 之间执行差异与传播分析 |

---

> **免责声明：** 本报告和工具输出均为基于证据的辅助审计，不构成法律意见，也不能替代针对具体许可证、司法辖区和业务模式的执业法律审查。
