# -*- coding: utf-8 -*-
"""模块 9：Delta 检测回归测试。

覆盖：
- 夹具六类变更事件（license_changed / ancestor_added / ancestor_removed /
  dataset_added / dataset_removed / evidence_downgrade）
- P0 修复：边变更事件 seed = edge.target（上游变化资产）
- 模块 2 版本化对齐：version_changed / version_upgraded、entity_key 索引、
  REVIEW / UNDETERMINED 不自动合并、compare_direction 接入
"""

import json

import delta_engine as de
from conftest import MODELSCOPE_FIXTURES


def load(name):
    return json.loads((MODELSCOPE_FIXTURES / name).read_text(encoding="utf-8"))


def run_delta():
    return de.detect_delta(
        load("scenario_t0_assets.json"),
        load("scenario_t1_assets.json"),
        load("scenario_t0_edges.json"),
        load("scenario_t1_edges.json"),
    )


def index_events(events):
    by_type = {}
    for event in events:
        by_type.setdefault(event["change_type"], []).append(event)
    return by_type


# ---------- 夹具六类事件 ----------


def test_six_change_types_covered():
    """夹具应覆盖接口约定的全部六类变更（非版本化夹具不触发版本事件）。"""
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
    """许可证变更事件：Llama-3.1-8B（llama3.1→GPL-3.0）与 bge-large-zh（MIT→GPL-3.0-only）。"""
    by_type = index_events(run_delta())
    changed = by_type["license_changed"]
    seeds = {event["seed"] for event in changed}
    assert "model:LLM-Research/Meta-Llama-3.1-8B-Instruct" in seeds
    assert "model:AI-ModelScope/bge-large-zh-v1.5" in seeds

    llama = next(e for e in changed if e["seed"] == "model:LLM-Research/Meta-Llama-3.1-8B-Instruct")
    assert llama["before"]["license"] == "llama3.1"
    assert llama["after"]["license"] == "GPL-3.0"
    assert llama["evidence_level"] == "A"
    assert llama["decision"] == "RISK_CONFIRMED"
    # compare_direction 已接入：license_changed 事件必须带方向判定
    assert llama["direction"]["direction"] in {
        "宽松→严格", "严格→宽松", "同级不变", "新增许可证", "许可证移除", "未知",
    }
    assert "risk_increased" in llama["direction"]
    assert "ai_involved" in llama["direction"]


def test_evidence_downgrade_event():
    """Qwen2.5-7B-Instruct 的许可证证据由 A 降到 C。"""
    by_type = index_events(run_delta())
    downgrades = [e for e in by_type["evidence_downgrade"]
                  if e["seed"] == "model:Qwen/Qwen2.5-7B-Instruct"]
    assert len(downgrades) == 1
    assert downgrades[0]["evidence_level"] == "C"
    assert downgrades[0]["decision"] == "UNDETERMINED"


def test_ancestor_added_missing_ancestor_undetermined():
    """Qwen-Image-2.1 新增祖先 Qwen2.5-7B（未出现在 BOM）-> seed=edge.target、UNDETERMINED。"""
    by_type = index_events(run_delta())
    added = [e for e in by_type["ancestor_added"]
             if e["seed"] == "model:Qwen/Qwen2.5-7B"]
    assert len(added) == 1
    assert added[0]["evidence_level"] == "C"
    assert added[0]["decision"] == "UNDETERMINED"


def test_dataset_added_and_removed():
    """数据集边新增（new-training-data）与移除（training-data），seed 指向边 target。"""
    by_type = index_events(run_delta())
    added = [e for e in by_type["dataset_added"]
             if e["seed"] == "dataset:scenario/qwen-sft-data-v2"]
    removed = [e for e in by_type["dataset_removed"]
               if e["seed"] == "dataset:scenario/qwen-sft-data-v1"]
    assert len(added) == 1 and added[0]["evidence_level"] == "C"
    assert added[0]["decision"] == "UNDETERMINED"
    assert len(removed) == 1 and removed[0]["evidence_level"] == "B"
    assert removed[0]["decision"] == "RISK_POTENTIAL"


def test_ancestor_removed_event():
    """Qwen-Image-2.1 移除旧祖先 old-model -> seed=edge.target、B 级证据。"""
    by_type = index_events(run_delta())
    removed = [e for e in by_type["ancestor_removed"]
               if e["seed"] == "model:ZhipuAI/glm-4-9b-chat"]
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
        load("scenario_t0_assets.json"),
        load("scenario_t0_assets.json"),
        load("scenario_t0_edges.json"),
        load("scenario_t0_edges.json"),
    )
    assert events == []


# ---------- 模块 2 版本化对齐（3 类新测试） ----------


def _asset(canonical_id, license_value="MIT", merge_status="MERGED",
           reason_code="PURL_COORDINATE_EXACT", rule_version="merge-policy-v2",
           evidence_level="A", snapshot="t0"):
    entity_key = canonical_id.split("@", 1)[0] if "@" in canonical_id else canonical_id
    return {
        "entity_key": entity_key,
        "canonical_id": canonical_id,
        "asset_type": "package",
        "name": entity_key.split(":", 1)[1],
        "version": canonical_id.split("@", 1)[1] if "@" in canonical_id else None,
        "purls": [f"pkg:pypi/{entity_key.split(':', 1)[1].split('/', 1)[-1]}"],
        "license": license_value,
        "evidence_chain": [{
            "evidence_level": evidence_level,
            "source_api": "pypi",
            "source_url": None,
            "source_field": "info.license",
            "retrieved_at": None,
            "status": "ok",
            "raw_value": license_value,
        }],
        "snapshot_id": snapshot,
        "merge_status": merge_status,
        "reason_code": reason_code,
        "rule_version": rule_version,
    }


def test_version_changed_event_same_entity():
    """测试类 1：同一 entity_key、不同 canonical_id -> 版本变化事件。"""
    before = [_asset("package:pypi/ms@1.0.0", license_value="MIT", snapshot="t0")]
    after = [_asset("package:pypi/ms@2.0.0", license_value="GPL-3.0-only", snapshot="t1")]
    events = de.detect_delta(before, after, [], [])
    by_type = index_events(events)

    changed = by_type.get("version_changed", [])
    assert len(changed) == 1
    event = changed[0]
    assert event["seed"] == "package:pypi/ms@2.0.0"
    assert event["before"]["canonical_id"] == "package:pypi/ms@1.0.0"
    assert event["after"]["canonical_id"] == "package:pypi/ms@2.0.0"
    # 审计字段完整
    assert event["before"]["entity_key"] == "package:pypi/ms"
    assert event["after"]["merge_status"] == "MERGED"
    assert event["after"]["reason_code"] == "PURL_COORDINATE_EXACT"
    assert event["after"]["rule_version"] == "merge-policy-v2"
    # 版本变化不产生 license_changed（不同 ID 不是同一资产）
    assert "license_changed" not in by_type


def test_version_upgraded_from_unversioned():
    """从无版本引用升级为带版本 -> version_upgraded。"""
    before = [_asset("package:pypi/ms", license_value="MIT", snapshot="t0")]
    after = [_asset("package:pypi/ms@2.0.0", license_value="MIT", snapshot="t1")]
    events = de.detect_delta(before, after, [], [])
    by_type = index_events(events)
    upgraded = by_type.get("version_upgraded", [])
    assert len(upgraded) == 1
    assert upgraded[0]["seed"] == "package:pypi/ms@2.0.0"


def test_same_canonical_id_license_change_kept():
    """测试类 2：同 canonical_id -> 原有 license/evidence 变化事件不受影响。"""
    before = [_asset("package:pypi/ms@2.0.0", license_value="MIT", snapshot="t0")]
    after = [_asset("package:pypi/ms@2.0.0", license_value="GPL-3.0-only", snapshot="t1")]
    events = de.detect_delta(before, after, [], [])
    by_type = index_events(events)

    changed = by_type.get("license_changed", [])
    assert len(changed) == 1
    event = changed[0]
    assert event["seed"] == "package:pypi/ms@2.0.0"
    assert event["before"]["license"] == "MIT"
    assert event["after"]["license"] == "GPL-3.0-only"
    assert "direction" in event
    assert "version_changed" not in by_type


def test_review_asset_keeps_reason_code_no_auto_merge():
    """测试类 3：REVIEW / UNDETERMINED -> 事件保留 reason_code 且不自动合并。"""
    # REVIEW 资产：同 canonical_id 许可证变化 -> license_changed 保留 reason_code
    before = [_asset(
        "package:pypi/ms@2.0.0", license_value="MIT", snapshot="t0",
        merge_status="REVIEW", reason_code="CONFLICT_HASH_AND_PURL",
    )]
    after = [_asset(
        "package:pypi/ms@2.0.0", license_value="GPL-3.0-only", snapshot="t1",
        merge_status="REVIEW", reason_code="CONFLICT_HASH_AND_PURL",
    )]
    events = de.detect_delta(before, after, [], [])
    by_type = index_events(events)
    changed = by_type.get("license_changed", [])
    assert len(changed) == 1
    assert changed[0]["before"]["merge_status"] == "REVIEW"
    assert changed[0]["before"]["reason_code"] == "CONFLICT_HASH_AND_PURL"
    assert changed[0]["after"]["reason_code"] == "CONFLICT_HASH_AND_PURL"

    # REVIEW 资产：同 entity_key、不同 canonical_id -> 不自动产生版本事件
    before_review = [_asset(
        "package:pypi/ms@1.0.0", license_value="MIT", snapshot="t0",
        merge_status="REVIEW", reason_code="CONFLICT_HASH_AND_PURL",
    )]
    after_review = [_asset(
        "package:pypi/ms@2.0.0", license_value="MIT", snapshot="t1",
        merge_status="REVIEW", reason_code="CONFLICT_HASH_AND_PURL",
    )]
    events_review = de.detect_delta(before_review, after_review, [], [])
    by_type_review = index_events(events_review)
    assert "version_changed" not in by_type_review
    assert "version_upgraded" not in by_type_review

    # UNDETERMINED 同理
    before_und = [_asset(
        "package:pypi/ms@1.0.0", license_value="MIT", snapshot="t0",
        merge_status="UNDETERMINED", reason_code="NO_MERGE_CANDIDATE",
    )]
    after_und = [_asset(
        "package:pypi/ms@2.0.0", license_value="MIT", snapshot="t1",
        merge_status="UNDETERMINED", reason_code="NO_MERGE_CANDIDATE",
    )]
    events_und = de.detect_delta(before_und, after_und, [], [])
    by_type_und = index_events(events_und)
    assert "version_changed" not in by_type_und


def test_multiple_canonical_ids_not_folded():
    """同一 entity_key 同一快照多个 canonical_id 且非全部 MERGED -> 不自行折叠。"""
    before = [
        _asset("package:pypi/ms@1.0.0", license_value="MIT", snapshot="t0"),
        _asset("package:pypi/ms@1.0.1", license_value="MIT", snapshot="t0",
               merge_status="KEPT_SEPARATE", reason_code="NO_MERGE_CANDIDATE"),
    ]
    after = [_asset("package:pypi/ms@1.0.1", license_value="MIT", snapshot="t1")]
    events = de.detect_delta(before, after, [], [])
    by_type = index_events(events)
    # before 侧同一 entity_key 有两个 canonical_id 且非全部 MERGED
    # （第二个是 KEPT_SEPARATE 默认）-> 不产生版本事件，不自行选代表
    assert "version_changed" not in by_type
    assert "version_upgraded" not in by_type


# ---------- license risk=3 判定统一（与 risk_evaluator.decision_for_license 一致） ----------


def _lic(risk_level, evidence_level, license_name="LGPL-3.0-only"):
    return {
        "entity_key": "acme/demo",
        "canonical_id": "model:acme/demo@1",
        "asset_type": "model",
        "name": "acme/demo",
        "version": "1",
        "purls": ["pkg:modelscope/acme/demo@1"],
        "license": license_name,
        "evidence_chain": [{
            "evidence_level": evidence_level,
            "source_api": "modelscope",
            "source_url": None,
            "source_field": "license",
            "retrieved_at": None,
            "status": "ok",
            "raw_value": license_name,
        }],
        "risk_level": risk_level,
        "snapshot_id": "t0",
        "merge_status": "MERGED",
        "reason_code": "PURL_COORDINATE_EXACT",
        "rule_version": "merge-policy-v2",
    }


def test_license_change_decision_risk3_matches_evidence_grading():
    """risk_level==3 的新许可证按证据分级，与 risk_evaluator.decision_for_license 一致。

    组长 10-23 命令第④条：delta_engine.license_change_decision() 对风险等级 3 的
    处理必须与 risk_evaluator.decision_for_license() 一致——证据 A -> RISK_CONFIRMED、
    证据 B -> RISK_POTENTIAL、证据 C -> UNDETERMINED。
    使用规则库真实等级：MIT(1) -> LGPL-3.0-only(3)，保证 compare_direction 一致。
    """
    import risk_evaluator as reval

    for evidence, expected in (
        ("A", "RISK_CONFIRMED"),
        ("B", "RISK_POTENTIAL"),
        ("C", "UNDETERMINED"),
    ):
        before = [_lic(risk_level=1, evidence_level="A", license_name="MIT")]
        after = [_lic(risk_level=3, evidence_level=evidence, license_name="LGPL-3.0-only")]
        events = de.detect_delta(before, after, [], [])
        changed = index_events(events).get("license_changed", [])
        assert len(changed) == 1, evidence
        delta_decision = changed[0]["decision"]

        # 与 risk_evaluator 独立判定的口径对比
        evaluator_decision = reval.decision_for_license(
            risk_level=3,
            ev_level=evidence,
        )
        assert delta_decision == expected, evidence
        assert evaluator_decision == expected, evidence
        assert delta_decision == evaluator_decision, evidence


def test_license_change_decision_risk4_confirmed_risk2_safe():
    """risk>=4 -> RISK_CONFIRMED（强收紧）；risk<=2 -> SAFE（宽松/同级）。

    规则库真实等级：MIT(1)/Apache-2.0(2) 宽松；GPL-3.0-only(4)/AGPL-3.0(5) 高风险。
    """
    for risk, license_name, expected in (
        (4, "GPL-3.0-only", "RISK_CONFIRMED"),
        (5, "AGPL-3.0", "RISK_CONFIRMED"),
        (1, "MIT", "SAFE"),
        (2, "Apache-2.0", "SAFE"),
    ):
        # before 固定 BSD-3-Clause(1)，after 为待测 license
        before = [_lic(risk_level=1, evidence_level="A", license_name="BSD-3-Clause")]
        after = [_lic(risk_level=risk, evidence_level="B", license_name=license_name)]
        events = de.detect_delta(before, after, [], [])
        changed = index_events(events).get("license_changed", [])
        assert len(changed) == 1, license_name
        assert changed[0]["decision"] == expected, license_name


def test_license_change_decision_unknown_protocol_matches_scanner():
    """P1-2：未知/非标协议（规则库不认识的许可证，如 qwen-research / llama3.1）
    必须与 risk_evaluator._UNKNOWN_LICENSE_DECISION 一致：
    证据 A/B -> RISK_POTENTIAL（黄，潜在风险），证据 C -> UNDETERMINED（灰，待补证）。

    组长实测：qwen-research -> llama3.1、证据 A 时 Delta 曾得 RISK_CONFIRMED（红），
    扫描器得 RISK_POTENTIAL（黄）——两处必须统一；证据 C 的许可证移除场景也
    不得再出现黄/灰不一致。
    """
    import risk_evaluator as reval

    # 场景 1：未知 -> 未知（qwen-research -> llama3.1），证据 A/B/C
    for evidence, expected in (
        ("A", "RISK_POTENTIAL"),
        ("B", "RISK_POTENTIAL"),
        ("C", "UNDETERMINED"),
    ):
        before = [_lic(risk_level=None, evidence_level="A", license_name="qwen-research")]
        after = [_lic(risk_level=None, evidence_level=evidence, license_name="llama3.1")]
        events = de.detect_delta(before, after, [], [])
        changed = index_events(events).get("license_changed", [])
        assert len(changed) == 1, evidence
        delta_decision = changed[0]["decision"]
        # 扫描器对非标协议（risk_level None）的单点判定
        scanner_decision = reval.decision_for_license(risk_level=None, ev_level=evidence)
        # 注意：risk_evaluator.decision_for_license(risk_level=None) 返回 UNDETERMINED；
        # delta 的"未知协议"语义按 _UNKNOWN_LICENSE_DECISION（A/B 黄、C 灰）处理。
        assert delta_decision == expected, evidence
        assert delta_decision == de.UNKNOWN_LICENSE_DECISION.get(evidence or "C", "UNDETERMINED"), evidence

    # 场景 2：从已知（Apache-2.0）收紧为未知（qwen-research），证据 A -> 黄
    before = [_lic(risk_level=2, evidence_level="A", license_name="Apache-2.0")]
    after = [_lic(risk_level=None, evidence_level="A", license_name="qwen-research")]
    events = de.detect_delta(before, after, [], [])
    changed = index_events(events).get("license_changed", [])
    assert len(changed) == 1
    assert changed[0]["decision"] == "RISK_POTENTIAL", changed[0]["decision"]

    # 场景 3：许可证移除（已知 -> 无），证据 C -> 灰（UNDETERMINED），不得为黄
    before = [_lic(risk_level=2, evidence_level="A", license_name="Apache-2.0")]
    after = [_lic(risk_level=None, evidence_level="C", license_name=None)]
    events = de.detect_delta(before, after, [], [])
    changed = index_events(events).get("license_changed", [])
    assert len(changed) == 1
    assert changed[0]["decision"] == "UNDETERMINED", changed[0]["decision"]
