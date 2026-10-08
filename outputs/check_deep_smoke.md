# 深度血缘风险传播报告

- 生成时间：2026-10-02T17:11:08Z
- t0 BOM：`data\hf_models_bom\bert-base-uncased_bom.json`
- t1 BOM：`data\hf_models_bom\Qwen2.5-0.5B-Instruct_bom.json`
- 图、Delta 和传播结果均由 `main.py` 调用仓库现有模块函数生成。

## 图谱摘要

| 快照 | snapshot_id | 对齐后资产 | 边 | 图节点 | 图边 | SCC | 循环 SCC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| t0 | t0 | 3 | 1 | 3 | 1 | 3 | 0 |
| t1 | t1 | 2 | 1 | 2 | 1 | 2 | 0 |

## 变更摘要

| 变更类型 | 数量 |
| --- | --- |
| 新增祖先 | 1 |
| 移除训练数据集 | 1 |

## 许可证变更方向

_无数据_

## 风险判定分布

| 判定 | 事件数 |
| --- | --- |
| RISK_POTENTIAL（潜在风险） | 4 |

## 传播事件

| 事件 ID | 变更类型 | 种子资产 | 影响路径 | 跳数 | 证据 | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| evt-t1-001 | 新增祖先 | model:huggingface/Qwen/Qwen2.5-0.5B | 种子自身 | 0 | B | RISK_POTENTIAL（潜在风险） |
| evt-t1-001-p01 | 新增祖先 | model:huggingface/Qwen/Qwen2.5-0.5B | model:huggingface/Qwen/Qwen2.5-0.5B-Instruct@7ae557604adf67be50417f59c2c2f167def9a775 -> model:huggingface/Qwen/Qwen2.5-0.5B | 1 | B | RISK_POTENTIAL（潜在风险） |
| evt-t1-002 | 移除训练数据集 | dataset:huggingface/datasets/wikipedia | 种子自身 | 0 | B | RISK_POTENTIAL（潜在风险） |
| evt-t1-002-p01 | 移除训练数据集 | dataset:huggingface/datasets/wikipedia | model:huggingface/google-bert/bert-base-uncased@86b5e0934494bd15c9632b12f734a8a67f723594 -> dataset:huggingface/datasets/wikipedia | 1 | B | RISK_POTENTIAL（潜在风险） |

## 路径证书

| 证书 ID | 受影响资产 | 变更类型 | 跳数 | 最弱证据 | 判定 | 终止原因 | 缺失祖先 | 路径指纹 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| cert-evt-t1-001-01 | model:huggingface/Qwen/Qwen2.5-0.5B-Instruct@7ae557604adf67be50417f59c2c2f167def9a775 | ancestor_added | 1 | B | RISK_POTENTIAL | exhausted | 否 | 8140bfd9494f55a3655a93653bbfc4c100b3b694 |
| cert-evt-t1-002-01 | model:huggingface/google-bert/bert-base-uncased@86b5e0934494bd15c9632b12f734a8a67f723594 | dataset_removed | 1 | B | RISK_POTENTIAL | exhausted | 否 | 2f98709e05df495ae23c92fd02b294c9b37cec63 |

## 免责声明

本报告是基于结构化证据和血缘图的辅助分析结果，不构成法律意见。
