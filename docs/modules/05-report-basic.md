# 模块 5：中文清单生成

| 项目 | 内容 |
|---|---|
| 负责人 | C |
| 状态 | 已完成（v2 接口对齐 2026-10-05） |
| 完成日期 | 2026-09-20（对应分工 9/21–9/23，提前完成）；v2：2026-10-05 |
| 对应任务 | 基础部分 · 模块 5 |

## 一句话摘要

把 CycloneDX BOM（或资产 JSON）转成中文《开源及第三方资源使用清单》Markdown，标注高风险项与证据来源，供基础层演示与验收；v2 起去重与许可证分级接入 entity_resolver / license_db，字段对齐 main.py，可被 main.py 直接 import。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| CycloneDX BOM（JSON） | cdxgen 扫描 / 共享夹具 | 如 `data/sample_bom.json`（72 组件）、`data/test_scenarios/sample_bom.json` |
| 资产 JSON | `bom_adapter.convert_bom` / `entity_resolver` 输出 | `--assets` 模式直接渲染 |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| `report_basic.py` | 根目录 | 清单生成脚本（v2），可独立运行 |
| `data/basic_report_sample.md` | data | 示例输出 |

## 为什么要做

1. 项目定位之一就是"面向学生/小团队一键生成中文合规清单"，模块 5 是基础层的对外出口。
2. A/B 的解析、对齐、规则库最终都要落到可读的清单上，模块 5 是基础层链路终点。
3. 让非技术验收方（老师、组长）能直接看到产出。

## 具体怎么做（v2）

1. 依赖仓库根目录模块：`bom_adapter`（BOM→资产）、`entity_resolver`（去重）、`license_db`（许可证规则）。
2. `--bom` 模式：`bom_adapter.convert_bom()` → `entity_resolver.deduplicate_assets()` → `render_report()`。
3. `--assets` 模式：直接读资产 JSON 数组渲染（main.py 快照产物）。
4. 许可证评估全部走 `license_db`：`evaluate_expression` → 风险等级 1–5 / 类别中文 / AI 专用标记 / 未识别项。
5. 渲染列对齐 main.py 资产字段：canonical_id、asset_type（模型/软件包/数据集/仓库/框架）、name、version、license、risk_level、category_zh、最佳证据（evidence_chain 最低等级 A/B/C）、来源链接（evidence_chain[].source_url）、purl。

```powershell
python report_basic.py --bom data/sample_bom.json -o 开源合规清单.md   # BOM 直出
python report_basic.py --assets assets_deduplicated.json -o 清单.md     # 资产直读
```

## main.py 接入

```python
import report_basic
md = report_basic.render_report(
    snapshot["assets"], bom_path=str(snapshot["path"]),
    snapshot_id=snapshot["snapshot_id"], raw_count=len(snapshot["raw_assets"]),
    merge_log=snapshot["merge_log"], evidence_summary=snapshot["evidence_summary"],
    edges=snapshot["edges"],
)
```

## 验证

- `data/sample_bom.json`（72 组件）→ **71 资产**：bert 双 purl 由 entity_resolver 合并（置信度 0.9）；MIT=风险 1、Apache-2.0=风险 2 用 license_db 正确分级；2 个待确认。
- 完整链路模拟（bom_adapter → entity_resolver → `--assets`）与 `--bom` 结果一致。
- 真实项目 BOM（licenses 缺失）正常渲染为"待确认"，不报错。
- 表格末尾有免责声明；退出码 0。

## 与上游的对接（已接入）

| 项目 | v1（内置简化版） | v2（对接正式模块） |
|---|---|---|
| 实体去重 | `merge_entities()` | `entity_resolver.deduplicate_assets()` |
| 许可证分类 | `classify_license()` | `license_db`（evaluate_expression / risk_level / CATEGORY_ZH / is_ai_license） |
| 字段口径 | 自有 ASSET_SCHEMA | 对齐 main.py 快照资产格式 |

## 已知限制

1. 独立 `--bom` 模式不调用 `evidence_enricher`（未拉取该文件时），来源链接显示"本地证据"；main.py 完整链路由 evidence_enricher 补全。
2. 实体对齐行为以 `entity_resolver` 规则为准（同名同版本+共同位置/URL/哈希合并；跨生态仅模型别名窄例外；版本不同不合并）。
3. `canonical_id` 当前为 `asset_type:name`；模块 2 版本化升级后自动生效，渲染不感知。
