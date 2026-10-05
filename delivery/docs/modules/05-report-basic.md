# 模块 5：中文清单生成

| 项目 | 内容 |
|---|---|
| 负责人 | C |
| 状态 | 已完成 |
| 完成日期 | 2026-09-20（对应分工 9/21–9/23，提前完成） |
| 对应任务 | 基础部分 · 模块 5 |

## 一句话摘要

把 CycloneDX BOM 转成中文《开源及第三方资源使用清单》Markdown，标注高风险项与证据来源，供基础层演示与验收。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| `data/test_scenarios/sample_bom.json` | C 构造的共享测试夹具（12 组件） | 覆盖双 purl 模型、GPL/AGPL 高风险、无许可证等场景 |
| 任意 cdxgen BOM | cdxgen 扫描 | 如 `data/sample_bom.json`（A 的 72 组件版） |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| `report_basic.py` | 根目录 | 清单生成脚本，可独立运行 |
| `data/basic_report_sample.md` | data | 示例输出（12 资产） |

## 为什么要做

1. 项目定位之一就是"面向学生/小团队一键生成中文合规清单"，模块 5 是基础层的对外出口。
2. A/B 的解析、对齐、规则库最终都要落到可读的清单上，模块 5 是基础层链路终点。
3. 让非技术验收方（老师、组长）能直接看到产出。

## 具体怎么做

1. 解析 BOM `components`，逐组件提取 name / version / purl / license / evidence / externalReferences。
2. 内置简化实体对齐：同名不同 purl 合并（保留双来源），同名不同版本不合并。
3. 内置许可证分级：GPL/AGPL/SSPL 高风险、宽松许可低风险、无许可证"待人工确认"。
4. 渲染 Markdown 表格：资源名称、版本、许可证、风险、来源链接、证据位置、来源生态 + 免责声明。

```powershell
python report_basic.py --bom data/test_scenarios/sample_bom.json -o data/basic_report_sample.md
```

## 验证

- 12 个组件全部出现在清单中；bert 双 purl 只出现一次（或标注来源上下文）。
- GPL/AGPL 组件带高风险提示；无许可证组件输出"待人工确认"，不编造许可证。
- 表格末尾有免责声明；退出码 0。

## 与上游的对接（替换内置简化逻辑）

| 内置函数 | 待替换为 |
|---|---|
| `merge_entities()` | 模块 2 `entity_resolver.py`（A） |
| `_extract_source_urls()` | 模块 3 `evidence_enricher.py`（A） |
| `classify_license()` | 模块 4 `license_db.py`（B） |

对接口径见代码文件底部 `ASSET_SCHEMA`，A/B 交付后无需改渲染骨架。
