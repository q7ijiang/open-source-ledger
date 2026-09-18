# 开源账本（open-source-ledger）

开源账本用于对开源软件、AI 模型和数据集进行中文合规清单生成，并进一步分析时间化血缘风险传播。

项目周期：2026-09-18 至 2026-10-15
项目定位：
1. 基础部分（面向学生/小团队）：一键扫描项目，生成中文《开源及第三方资源使用清单》，标注高风险项，附证据链接。
2. 深度部分（面向合规研究者）：输入两个 CycloneDX BOM，做时间化血缘传播，输出三级判定（RISK_CONFIRMED / RISK_POTENTIAL / UNDETERMINED）和路径证书。

## 团队分工

| 成员 | 负责模块 |
|---|---|
| A（数据管道） | BOM解析、跨生态实体对齐、证据链补全、GitHub Action集成、全流程集成 |
| B（算法核心） | AI许可证规则库、血缘图构建、Delta检测、风险传播 |
| C（交付与验证） | 中文清单生成、测试数据准备、增强层报告、深度测试数据、技术报告、演示视频 |

## 协作工具与文档

- [接口约定](docs/接口约定.md)：所有 JSON 数据结构必须严格遵循此文档。
- [进度追踪](docs/进度追踪.md)：查看各模块负责人、截止日期和当前状态。
- [每日站会模板](docs/每日站会模板.md)：每人每天按固定格式同步进度。
- [每周验收清单](docs/每周验收清单.md)：按周检查交付物和验收标准。
- [分支与代码协作规范](docs/分支与代码协作规范.md)：分支策略、合并规则与代码规范。

## 快速开始

> 基础模式（生成中文合规清单）：
> `python main.py --mode basic --input sample_bom.json --output reports/basic_report.md`

> 深度模式（时间化血缘风险传播）：
> `python main.py --mode deep --before t0_bom.json --after t1_bom.json --output reports/deep_report.md`

## 免责声明

本工具输出为基于证据的辅助审计，不构成法律意见。
