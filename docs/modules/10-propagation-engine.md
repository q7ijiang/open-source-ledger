# 模块 10：风险传播与路径证书（propagation_engine.py）

| 项目 | 内容 |
|---|---|
| 负责人 | B（算法核心） |
| 状态 | 已完成，随 `main` 交付 |
| 对应任务 | 深度部分 · 模块 10 |
| 输入数据 | 模块 9 的变更事件 + 模块 8 的 t0/t1 血缘图 |
| 关联测试 | `tests/test_propagation_engine.py`（10 项） |
| 配套模块 | `risk_evaluator.py`（单模型/项目级 P/D/P 判定，供 `--model`/`--project` 直接调用） |

## 一句话摘要

从每个变更事件的种子出发做**反向 BFS**，把所有下游衍生资产标记为受影响，并按「最弱证据链」给出判定，输出带 **SHA-1 路径指纹**的路径证书；`MAX_DEPTH=10` 与 SCC/`visited` 双重防环，终止原因可区分"走到尽头 / 触顶 / 遇环"。

## 输入

| 输入 | 说明 |
|---|---|
| `events[]` | 模块 9 产出；每条必须有 `seed` / `change_type` / `evidence_level` |
| `graph_before` / `graph_after` | 模块 8 建好并做过 SCC 压缩的图 |

## 输出

`propagate()` 返回 `{"events": [...], "path_certificates": [...]}`。

路径证书字段：

| 字段 | 含义 |
|---|---|
| `certificate_id` / `event_id` | 证书与来源事件 |
| `seed` | 变更起源的上游资产 |
| `affected` | 受影响的下游资产 |
| `path[]` | 路径步骤，顺序为 **受影响资产 → … → 种子** |
| `hop_count` | 跳数 |
| `weakest_evidence` | 整条链最弱证据等级 |
| `decision` | 该受影响资产的判定 |
| `termination` | `exhausted` / `max_depth` / `scc_cycle` |
| `missing_ancestor` | 路径上是否出现缺失祖先 |
| `path_fingerprint` | 路径步骤序列的 SHA-1，40 位 |
| `verified` | 是否通过一致性校验 |

## 为什么要做

1. 许可证变更的影响是**沿供应链传导**的：上游改成非商用，下游微调/量化/服务全部受约束，但平台只做单点提醒。
2. 传统 SCA 只回答"你用了什么"，不回答"上游变了会传染到谁"。
3. 合规审计需要**可复核的证据链**，不能只给一个结论；因此每条受影响记录都附完整路径与指纹。

## 具体怎么做

### 步骤 1：反向 BFS

```
FUNCTION propagate(events, graph_before, graph_after):
    FOR EACH event IN events:
        seed ← event.seed
        visited ← {seed}; queue ← [(seed, [])]
        WHILE queue 非空:
            (node, path) ← queue.pop()
            IF len(path) >= MAX_DEPTH: 标记 max_depth; BREAK
            FOR EACH 反向邻边 (下游 → node):
                IF 下游 ∈ visited: 标记 scc_cycle; CONTINUE
                新路径 ← path + [step]
                证据 ← weakest(event.evidence_level, 各跳 evidence_level)
                产出证书(affected=下游, seed, weakest_evidence=证据,
                         decision=DECISION_BY_EVIDENCE[证据], termination, fingerprint)
                queue.append((下游, 新路径))
```

`DECISION_BY_EVIDENCE = {A: RISK_CONFIRMED, B: RISK_POTENTIAL, C: UNDETERMINED}`。

### 步骤 2：最弱证据链

路径可信度 = 路径上最弱的一环。一条链只要有一跳是 C 级，整条结论就是灰灯。这符合审计直觉：证据链强度由最弱环节决定。

### 步骤 3：三重防环

1. `visited` 集合：同一节点不重复入队；
2. `MAX_DEPTH=10`：路径长度上限；
3. SCC 压缩：环内节点已折叠成单点，环内不可能无限走。

三条同时失效才会死循环；当前 8 节点上游闭包验收和单独构造环场景均已验证终止。

### 步骤 4：路径指纹

对路径步骤序列（`source`/`target`/`edge_type`）取 SHA-1，得到 40 位指纹。同一路径任何时候重算都得到同一指纹，可用于跨次运行比对与「证书未被篡改」的校验。

## 配套：risk_evaluator.py（单模型判定）

`--model` / `--project` 走的是"不需要两版 BOM"的路径，因此另有 `risk_evaluator.py`：

- `evaluate_model_risk(assets, edges)` → 每节点判定 + 整体判定（取最严）；
- 判定口径：许可证自身风险等级主导，证据等级在模糊档细分：

| 许可证风险等级 | 证据 A | 证据 B | 证据 C |
|---|---|---|---|
| 1–2 宽松 | SAFE | SAFE | SAFE |
| 3 弱 copyleft / AI 限制 | RISK_CONFIRMED | RISK_POTENTIAL | UNDETERMINED |
| 4–5 强·网络 copyleft | RISK_CONFIRMED | RISK_CONFIRMED | RISK_CONFIRMED |
| 非标协议（规则库不认识） | RISK_POTENTIAL | RISK_POTENTIAL | UNDETERMINED |
| 无许可证 | UNDETERMINED | UNDETERMINED | UNDETERMINED |

四态与报告口径一致：`SAFE`（绿）/ `UNDETERMINED`（灰）/ `RISK_POTENTIAL`（黄）/ `RISK_CONFIRMED`（红）。

## 验证

| 验证项 | 数据 | 结论 |
|---|---|---|
| 单跳传播 | `scenario_t0/t1`（seed → finetuned） | 路径 1 跳，证据 A，`RISK_CONFIRMED` ✓ |
| 多跳传播 | 同上（seed → finetuned → serving） | 路径 2 跳，证据 B，`RISK_POTENTIAL` ✓ |
| 路径方向 | 同上 | `steps[0].source` 是受影响资产，`steps[1].target` 是种子 ✓ |
| 遇环终止 | `cycle_a ⇄ cycle_b` | 证书 `termination == "scc_cycle"` ✓ |
| 证据降级 | `evidence_downgrade` 事件 | 证据 C → `UNDETERMINED` ✓ |
| 当前上游场景 | Qwen t0/t1 冻结快照 | 1 个种子 → 3 个传播后事件 → **2 份路径证书** ✓ |
| 上游闭包 | 8 节点 / 9 边 | 无项目外下游节点，传播终止原因可审计 ✓ |

## 已知边界

- **深度上限会截断真实路径**：`MAX_DEPTH=10` 在真实数据上未被触及（实测最长 4 跳），但在多层转包供应链中可能截断；此时证书 `termination == "max_depth"`，需与"真正走到尽头"（`exhausted`）区分。
- **只沿已固化的边传播**：`--diff` 模式只读 BOM 内的 `pedigree.ancestors`，不联网；因此**历史 BOM 缺血缘字段时传播会漏**。
- **平台全量下游不在项目闭包内**：项目模式和 Diff 不读取 `SonModels`，因此不会把平台下游计数当作可传播资产。
- **证据分级衡量"是否转手"，不衡量"源头是否错误"**：A 级只表示该值由平台 API 原样给出。
