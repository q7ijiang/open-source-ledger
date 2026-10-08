# 模块 11：增强层报告

| 项目 | 内容 |
|---|---|
| 负责人 | C |
| 状态 | 已完成（已适配接口约定 v0.3） |
| 完成日期 | 2026-10-03（对应分工 10/8–10/9，提前完成） |
| 对应任务 | 深度部分 · 模块 11 |

## 一句话摘要

消费深度流水线（delta_engine 事件 + propagation_engine 路径证书）的合并输出，渲染中文《AI 模型血缘风险传播报告》，含传播路径、三级判定与路径证书。

## 输入

| 输入 | 来源 | 说明 |
|---|---|---|
| `propagated.json` | B 的 `propagation_engine.py` | `{"events": [...], "path_certificates": [...]}`（v0.3 形态） |
| `data/test_scenarios/t0_bom.json`、`t1_bom.json` | C（模块 12） | 可选，用于资产名可读化 |
| `data/test_scenarios/demo_propagated_v03.json` | C | 演示输入（3 事件 + 3 证书，覆盖三种判定） |

## 输出

| 输出 | 路径 | 说明 |
|---|---|---|
| `report_enhanced.py` | 根目录 | 报告生成脚本 |
| `data/deep_provenance_risk_report_sample.md` | data | 示例报告 |

## 为什么要做

1. 深度部分的对外交付物就是"时间化血缘风险传播报告"，模块 11 是深度链路终点。
2. B 的引擎输出是结构化 JSON，非技术验收方无法直接阅读，需要转成中文报告。
3. 三级判定（RISK_CONFIRMED / RISK_POTENTIAL / UNDETERMINED）需要按 weakest link 规则向用户解释清楚。

## 具体怎么做

1. 读取 propagated.json：`events`（事件，含 before/after 状态对象、path 路径、decision）与 `path_certificates`（证书）。
2. 渲染六个部分：变更摘要（按类型分布 + 审计字段）、传播路径（逐事件逐跳）、路径证书表、受影响资产（按判定分组）、风险源汇总、证据等级与判定说明。
3. 事件类型映射：license_changed / ancestor_added / ancestor_removed / dataset_added / dataset_removed / evidence_downgrade / version_changed / version_upgraded 全部覆盖。

```powershell
python report_enhanced.py --input data/test_scenarios/demo_propagated_v03.json `
  --bom-t0 data/test_scenarios/t0_bom.json --bom-t1 data/test_scenarios/t1_bom.json `
  -o data/deep_provenance_risk_report_sample.md
```

## 验证

- v0.3 演示输入实跑通过：3 事件 / 3 证书，三判定齐备，传播路径逐跳展示。
- 事件 before/after 按对象渲染（license_changed 显示许可证，version_upgraded 显示 canonical_id）。
- 路径证书使用 B 的字段：affected / hop_count / weakest_evidence / termination / missing_ancestor / path_fingerprint。
- 兼容旧用法：`--events` + `--certificates` 分文件输入仍可用。

## 与接口约定 v0.3 的对齐

- HF 血缘边证据等级统一 **B 级**（BOM 为 CycloneDX 工具产物，不混用 A 口径）。
- 事件 schema：`event_id / seed / change_type / before / after / path / evidence_level / decision`。
- 证书 schema：`certificate_id / affected / change_type / hop_count / weakest_evidence / decision / termination / missing_ancestor / path_fingerprint`。
