# -*- coding: utf-8 -*-
"""模块 10：风险传播回归测试。"""

import json

import delta_engine as de
import propagation_engine as pe
from build_graph import build_graph
from conftest import MODELSCOPE_FIXTURES


def load(name):
    return json.loads((MODELSCOPE_FIXTURES / name).read_text(encoding="utf-8"))


def build_fixture_graphs():
    graph_before = build_graph(load("scenario_t0_assets.json"), load("scenario_t0_edges.json"))
    graph_after = build_graph(load("scenario_t1_assets.json"), load("scenario_t1_edges.json"))
    return graph_before, graph_after


def run_pipeline():
    events = de.detect_delta(
        load("scenario_t0_assets.json"),
        load("scenario_t1_assets.json"),
        load("scenario_t0_edges.json"),
        load("scenario_t1_edges.json"),
    )
    graph_before, graph_after = build_fixture_graphs()
    return pe.propagate(events, graph_before, graph_after), events


def index_affected(result):
    """按 (种子, 变更类型) 索引受影响资产事件（不含种子自身）。"""
    index = {}
    for event in result["events"]:
        if event["path"]:
            index.setdefault((event["seed"], event["change_type"]), {})[
                event["path"][0]["source"]
            ] = event
    return index


def test_license_change_propagates_downstream():
    """基座模型许可证变更 -> 下游微调模型受影响（A 级证据路径）。"""
    result, _ = run_pipeline()
    affected = index_affected(result)

    seed_events = affected[("model:LLM-Research/Meta-Llama-3.1-8B-Instruct", "license_changed")]
    # Qwen2.5-7B-Instruct 通过 A 级 derived_from 边受影响 -> RISK_CONFIRMED
    finetuned = seed_events["model:Qwen/Qwen2.5-7B-Instruct"]
    assert finetuned["path"][0]["edge_type"] == "derived_from"
    assert finetuned["evidence_level"] == "A"
    assert finetuned["decision"] == "RISK_CONFIRMED"

    # Qwen-Image-2.1 路径含一条 B 级边 -> weakest link = B -> RISK_POTENTIAL
    serving = seed_events["model:Qwen/Qwen-Image-2.1"]
    assert len(serving["path"]) == 2
    assert serving["evidence_level"] == "B"
    assert serving["decision"] == "RISK_POTENTIAL"


def test_path_direction_from_affected_to_seed():
    """路径步骤方向：受影响资产 -> ... -> 种子（与接口约定示例一致）。"""
    result, _ = run_pipeline()
    affected = index_affected(result)
    serving = affected[("model:LLM-Research/Meta-Llama-3.1-8B-Instruct", "license_changed")][
        "model:Qwen/Qwen-Image-2.1"]
    steps = serving["path"]
    assert steps[0]["source"] == "model:Qwen/Qwen-Image-2.1"
    assert steps[1]["target"] == "model:LLM-Research/Meta-Llama-3.1-8B-Instruct"
    assert steps[1]["source"] == "model:Qwen/Qwen2.5-7B-Instruct"


def test_cycle_terminates_with_scc_reason():
    """cycle_a 与 cycle_b 成环：传播正常终止并标记 scc_cycle。"""
    result, _ = run_pipeline()
    affected = index_affected(result)
    cycle_a_events = affected[("model:AI-ModelScope/bge-large-zh-v1.5", "license_changed")]
    lib_x = cycle_a_events["model:iic/nlp_structbert_sentiment-classification_chinese-base"]
    assert lib_x["decision"] == "RISK_POTENTIAL"
    cert = next(c for c in result["path_certificates"]
                if c["affected"] == "model:iic/nlp_structbert_sentiment-classification_chinese-base")
    assert cert["termination"] == "scc_cycle"


def test_evidence_downgrade_propagates_as_undetermined():
    """种子证据为 C 级时传播路径取 weakest link 后为 UNDETERMINED。"""
    result, _ = run_pipeline()
    affected = index_affected(result)
    finetuned_events = affected[("model:Qwen/Qwen2.5-7B-Instruct", "evidence_downgrade")]
    serving = finetuned_events["model:Qwen/Qwen-Image-2.1"]
    assert serving["evidence_level"] == "C"
    assert serving["decision"] == "UNDETERMINED"


def test_dataset_added_propagates_undetermined():
    """新增数据集边（C 级）传播到下游模型为 UNDETERMINED；seed=边 target。"""
    result, _ = run_pipeline()
    affected = index_affected(result)
    dataset_events = affected[("dataset:scenario/qwen-sft-data-v2", "dataset_added")]
    serving = dataset_events["model:Qwen/Qwen-Image-2.1"]
    assert serving["evidence_level"] == "C"
    assert serving["decision"] == "UNDETERMINED"


def test_dataset_removed_propagates_on_before_graph():
    """数据集移除在 t0 图上传播；B 级路径 -> RISK_POTENTIAL；seed=边 target。"""
    result, _ = run_pipeline()
    affected = index_affected(result)
    removed_events = affected[("dataset:scenario/qwen-sft-data-v1", "dataset_removed")]
    serving = removed_events["model:Qwen/Qwen-Image-2.1"]
    assert serving["path"][0]["source"] == "model:Qwen/Qwen-Image-2.1"
    assert serving["evidence_level"] == "B"
    assert serving["decision"] == "RISK_POTENTIAL"


def test_missing_ancestor_event_kept_undetermined():
    """新增祖先指向缺失资产：seed=边 target（缺失祖先），向下游传播为 UNDETERMINED。"""
    result, _ = run_pipeline()
    seed_events = [e for e in result["events"]
                   if e["change_type"] == "ancestor_added"
                   and e["seed"] == "model:Qwen/Qwen2.5-7B"
                   and e["path"] == []]
    assert len(seed_events) == 1
    assert seed_events[0]["decision"] == "UNDETERMINED"
    # 种子为缺失祖先（上游变化资产）-> 反向传播到依赖它的 Qwen-Image-2.1
    propagated = [e for e in result["events"]
                  if e["seed"] == "model:Qwen/Qwen2.5-7B" and e["path"]]
    assert len(propagated) == 1
    affected = propagated[0]
    assert affected["path"][0]["source"] == "model:Qwen/Qwen-Image-2.1"
    assert affected["evidence_level"] == "C"
    assert affected["decision"] == "UNDETERMINED"


def test_certificates_match_propagated_events():
    """每个传播事件都有对应路径证书，且指纹可校验。"""
    result, _ = run_pipeline()
    propagated_events = [e for e in result["events"] if e["path"]]
    assert len(result["path_certificates"]) == len(propagated_events)
    for cert in result["path_certificates"]:
        assert cert["verified"] is True
        expected_fingerprint = pe.path_fingerprint(cert["path"])
        assert cert["path_fingerprint"] == expected_fingerprint
        assert cert["decision"] in {"RISK_CONFIRMED", "RISK_POTENTIAL", "UNDETERMINED"}


def test_seed_event_has_empty_path():
    """种子自身事件 path 为空数组。"""
    result, _ = run_pipeline()
    for event in result["events"]:
        if event["event_id"].endswith("-p01"):
            assert event["path"]
    seed_events = [e for e in result["events"] if e["change_type"] == "license_changed"
                   and e["seed"] == "model:LLM-Research/Meta-Llama-3.1-8B-Instruct"]
    assert seed_events[0]["path"] == []


def test_max_depth_termination():
    """超过最大深度的链路截断并标记 max_depth。"""
    # 构造 12 跳链：n0 <- n1 <- ... <- n11（n11 依赖 n0）
    assets = [
        {"canonical_id": f"package:test/n{i}", "asset_type": "package",
         "name": f"n{i}", "version": "1.0.0", "purls": [], "license": "MIT",
         "evidence_chain": [], "snapshot_id": "t"}
        for i in range(12)
    ]
    edges = [
        {"source": f"package:test/n{i+1}", "target": f"package:test/n{i}",
         "edge_type": "depends_on", "evidence_level": "A",
         "source_field": "requirements.txt", "snapshot_id": "t"}
        for i in range(11)
    ]
    graph = build_graph(assets, edges)
    event = {
        "event_id": "evt-depth-001", "seed": "package:test/n0",
        "change_type": "license_changed", "before": None, "after": None,
        "path": [], "evidence_level": "A", "decision": "RISK_CONFIRMED",
    }
    reached = pe.reverse_bfs(graph, event["seed"], max_depth=3)
    # 深度限制 3：n1..n3 可达，n4 及更远不可达
    assert "package:test/n3" in reached
    assert "package:test/n4" not in reached
