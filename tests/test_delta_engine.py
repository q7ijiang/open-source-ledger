# -*- coding: utf-8 -*-
"""模块 9：Delta 检测回归测试。"""

import json

import delta_engine as de
from conftest import FIXTURES


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def run_delta():
    return de.detect_delta(
        load("deep_t0_assets.json"),
        load("deep_t1_assets.json"),
        load("deep_t0_edges.json"),
        load("deep_t1_edges.json"),
    )


def index_events(events):
    by_type = {}
    for event in events:
        by_type.setdefault(event["change_type"], []).append(event)
    return by_type


def test_six_change_types_covered():
    """夹具应覆盖接口约定的全部六类变更。"""
    events = run_delta()
    types = {event["change_type"] for event in events}
    assert types == {
        "license_changed",
        "ancestor_added",
        "ancestor_removed",
        "dataset_added",
        "dataset_removed",
        "evidence_downgrade",
    }


def test_license_changed_events():
    """许可证变更事件：Llama-2-7b（llama2→GPL-3.0）与 example-parser（MIT→GPL-3.0-only）。"""
    by_type = index_events(run_delta())
    changed = by_type["license_changed"]
    seeds = {event["seed"] for event in changed}
    assert "model:meta-llama/Llama-2-7b" in seeds
    assert "package:pypi/example-parser" in seeds

    llama = next(e for e in changed if e["seed"] == "model:meta-llama/Llama-2-7b")
    assert llama["before"]["license"] == "llama2"
    assert llama["after"]["license"] == "GPL-3.0"
    assert llama["evidence_level"] == "A"
    assert llama["decision"] == "RISK_CONFIRMED"


def test_evidence_downgrade_event():
    """finetuned-model 的许可证证据由 A 降到 C。"""
    by_type = index_events(run_delta())
    downgrades = [e for e in by_type["evidence_downgrade"]
                  if e["seed"] == "model:my-org/finetuned-model"]
    assert len(downgrades) == 1
    assert downgrades[0]["evidence_level"] == "C"
    assert downgrades[0]["decision"] == "UNDETERMINED"


def test_ancestor_added_missing_ancestor_undetermined():
    """serving-model 新增祖先 Qwen2.5-7B 但祖先未出现在 BOM 中 -> UNDETERMINED。"""
    by_type = index_events(run_delta())
    added = [e for e in by_type["ancestor_added"]
             if e["seed"] == "model:my-org/serving-model"]
    assert len(added) == 1
    assert added[0]["evidence_level"] == "C"
    assert added[0]["decision"] == "UNDETERMINED"


def test_dataset_added_and_removed():
    """数据集边新增（new-training-data）与移除（training-data）。"""
    by_type = index_events(run_delta())
    added = [e for e in by_type["dataset_added"]
             if e["seed"] == "model:my-org/finetuned-model"]
    removed = [e for e in by_type["dataset_removed"]
               if e["seed"] == "model:my-org/finetuned-model"]
    assert len(added) == 1 and added[0]["evidence_level"] == "C"
    assert added[0]["decision"] == "UNDETERMINED"
    assert len(removed) == 1 and removed[0]["evidence_level"] == "B"
    assert removed[0]["decision"] == "RISK_POTENTIAL"


def test_ancestor_removed_event():
    """serving-model 移除旧祖先 old-model -> ancestor_removed（B 级证据）。"""
    by_type = index_events(run_delta())
    removed = [e for e in by_type["ancestor_removed"]
               if e["seed"] == "model:my-org/serving-model"]
    assert len(removed) == 1
    assert removed[0]["evidence_level"] == "B"
    assert removed[0]["decision"] == "RISK_POTENTIAL"


def test_event_schema_conformance():
    """事件字段必须符合接口约定（path 初始为空数组）。"""
    for event in run_delta():
        assert {"event_id", "seed", "change_type", "before", "after",
                "path", "evidence_level", "decision"} <= set(event)
        assert event["path"] == []
        assert event["decision"] in {"RISK_CONFIRMED", "RISK_POTENTIAL", "UNDETERMINED"}
        assert event["event_id"].startswith("evt-")


def test_no_change_produces_no_events():
    """相同快照对比不产生任何事件。"""
    events = de.detect_delta(
        load("deep_t0_assets.json"),
        load("deep_t0_assets.json"),
        load("deep_t0_edges.json"),
        load("deep_t0_edges.json"),
    )
    assert events == []
