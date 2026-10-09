# ModelScope 血缘风险传播可视化 — 交付报告（C 模块）

> 生成时间：2026-10-09
> 负责人：成员 C（数据 + 渲染 + 可视化）
> 数据源：ModelScope（魔搭社区）真实 API 数据（`outputs/modelscope_validation/` 6 份原始 JSON）

## 一、交付物清单

| 产物 | 路径 | 说明 |
|---|---|---|
| 交互式风险血缘图 | `outputs/modelscope_validation/ms_risk_lineage.html` | **双击即可打开**（ECharts 已本地化，离线可用），数据内嵌 |
| 渲染截图 | `outputs/modelscope_validation/ms_risk_lineage.png` | 浏览器实际渲染效果（验收预览） |
| 可视化数据 | `outputs/modelscope_validation/ms_viz/graph_t1.json` / `events.json` / `certificates.json` / `viz_data.json` | build_graph → delta → propagation 全链路产物 |
| 生成脚本 | `outputs/modelscope_validation/gen_ms_viz.py` / `build_viz_html.py` / `ms_risk_lineage_template.html` | 数据生成与 HTML 注入可复现 |
| 合规清单 | `outputs/modelscope_validation/ms_t1_合规清单.md` | report_basic v3 渲染（绿灯出表） |

## 二、数据来源与口径

- **输入**：`data/test_scenarios/ms_t0_bom.json` / `ms_t1_bom.json`（7 组件 CycloneDX 1.7，基于 ModelScope 真实 API JSON 构造）
- **血缘边**：pedigree.ancestors 递归展开，`derived_from`；边端点 = **版本化 canonical_id**（接口约定 v0.3：`asset_type:ecosystem/ns/name@version`）
- **证据等级**：B 级（CycloneDX 工具产物口径，与 docs/接口约定.md 一致，不与 HF 口径混用）
- **非标协议**：`qwen-research` / `qwen-data-license`（ModelScope 官方 LicenseName / License=other），license_db 未识别 → **判黄灯 RISK_POTENTIAL，不报错**（组长 10-08 对 B 的容错要求，C 数据侧已验证）
- **聚合降维**：Qwen-Image-2.1 官方血缘为聚合计数（Adapters 1968 / Finetunes 21 / Quantizations 26，实时数据与组长 test_report.md 中旧快照 1873 有自然漂移），图中以代表节点呈现衍生链路，避免绘制死节点

## 三、可视化设计（对照组长 10-08 五条硬性验收标准）

| 组长验收标准 | 实现情况 | 验证 |
|---|---|---|
| ① 合规不画图 / 风险必画图，高风险警告色、潜在风险警示色、安全浅色/灰，**禁止全是蓝色圆圈** | 风险血缘图：高风险 **红**（#f56c6c）、潜在风险 **黄**（#e6a23c）、安全 **浅灰**（#d3d7de）；合规场景为绿色表格（页面下方"合规判定表"，安全行绿底） | ✅ 浏览器实测 |
| ② 节点文字不可截断，悬浮/点击显示全名+版本 | 节点标签直接显示完整模型名（如 `Qwen-Image-2.1-Finetune-Demo`）；tooltip 显示全名 + 版本 + 许可 + 判定 + 证据等级 | ✅ 实测无 `Qwen-Imag...` 截断 |
| ③ 点风险节点弹面板显示 A/B/C 证据等级与原始值；点风险连线显示 path_certificates（谁传染谁） | 点击节点 → 右侧面板显示证据链（`[B] components[].licenses` 原始值 `qwen-research` + 来源 cyclonedx）+ merge_status；点击连线 → 显示证据等级 + **⚠ 传播路径提示 + path_certificates（判定 RISK_POTENTIAL、路径明细）** | ✅ 节点/连线均实测 |
| ④ 绿灯出表红灯出图（合规 10 秒内出中文表格） | 页面含合规判定表（模型名/版本/许可/判定，安全行绿色）；"红灯出图"即血缘图本体 | ✅ 实测 |
| ⑤ 交付 = 交互 Web Demo（链接/截图）+ 中文报告 + 全部产物进仓库 | HTML（本地双击打开）+ 本报告 + PNG 截图；推送待用户确认后执行 | ✅ 产物就绪 |

## 四、交互说明

- **悬浮节点**：tooltip 显示完整模型名、版本、类型、许可证、判定、证据等级
- **点击节点**：右侧"证据链与传播详情"面板显示该资产证据链（证据等级 + 原始值 + 来源字段）与合并状态
- **点击连线**：显示血缘边方向、证据等级；若位于传播路径上，红色加粗高亮并列出 **path_certificates**（谁传染谁）
- **拖动/缩放**：力导向图可拖拽节点、滚轮缩放（roam）

## 五、本次链路数据（t0 → t1）

- t1 血缘图：**7 节点 / 2 条 derived_from 边**（Finetune-Demo→Qwen-Image-2.1、Quantized-Demo→Finetune-Demo，证据 B）
- 变更事件：**2 个**（Finetune-Demo 未声明→qwen-research【S1】；Finetune-Data 未声明→qwen-data-license【S4】），均 RISK_POTENTIAL
- 传播：**path_certificates = 1**，种子 = edge.target（上游变化资产 Finetune-Demo@master），判定 RISK_POTENTIAL

## 六、待办与说明

1. `main.py --project ./test_project` / `--diff`（MS 分支）全链路测通：**等待组长推送 `work/extract_modelscope_lineage.py`**（见待发消息记录）
2. 本批产物（HTML/数据/脚本/报告/截图）已就绪，推送 GitHub 待用户确认
3. 已知边界：t1 血缘边仅 2 条 derived_from（数据集节点未入边）；如需展示 trained_on 数据集边可在 BOM modelCard 补 datasets 引用后重跑 gen_ms_viz.py
