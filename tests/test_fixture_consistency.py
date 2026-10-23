# -*- coding: utf-8 -*-
"""场景夹具与真实许可证快照的一致性（防止"看似真实、实际无法溯源"）。

背景：PR #15 review 指出 `ZhipuAI/glm-4-9b-chat` 在场景夹具里被记成 A 级
`Data.LicenseName = "Apache-2.0"`，而同 PR 的真实快照是 `null`，ModelScope API 当天只返回
`Data.License = "other"` / `Data.LicenseName = ""`。夹具声称的"A 级 API 原值"无法溯源。

这里锁两条规则：
1. 场景夹具 **t0** 的许可证必须与 `real_model_licenses.json` 完全一致（t0 声称是 API 原值）；
2. **t1** 允许偏离 t0，但只允许偏离 README 登记的那两处构造变更点。
"""

import json

from conftest import MODELSCOPE_FIXTURES

# README「真实性边界」登记的构造变更点：t1 只在这两个模型上改许可证
CONSTRUCTED_T1_LICENSE_CHANGES = {
    "LLM-Research/Meta-Llama-3.1-8B-Instruct",  # llama3.1 -> GPL-3.0
    "AI-ModelScope/bge-large-zh-v1.5",          # MIT -> GPL-3.0-only
}


def load(name):
    return json.loads((MODELSCOPE_FIXTURES / name).read_text(encoding="utf-8"))


def model_licenses(filename):
    return {a["name"]: a.get("license") for a in load(filename) if a.get("asset_type") == "model"}


def test_t0_licenses_match_real_snapshot():
    """t0 声称是 ModelScope API 原值，就必须与实抓快照逐条一致。"""
    real = {r["name"]: r.get("license") for r in load("real_model_licenses.json")}
    t0 = model_licenses("scenario_t0_assets.json")

    for name, license_value in t0.items():
        assert name in real, f"t0 夹具里的 {name} 不在真实快照中，无法溯源"
        assert license_value == real[name], (
            f"{name}: 夹具记 {license_value!r}，真实快照记 {real[name]!r}；"
            "真实身份的 t0 许可证必须与 real_model_licenses.json 一致"
        )


def test_unknown_license_model_keeps_null_and_no_evidence():
    """glm-4-9b-chat 的 API 只返回 other，夹具必须记 null 且不得伪造 A 级证据。"""
    real = {r["name"]: r.get("license") for r in load("real_model_licenses.json")}
    assert real["ZhipuAI/glm-4-9b-chat"] is None

    for filename in ("scenario_t0_assets.json", "scenario_t1_assets.json"):
        asset = next(a for a in load(filename) if a.get("name") == "ZhipuAI/glm-4-9b-chat")
        assert asset["license"] is None
        assert asset["evidence_chain"] == []


def test_t1_license_changes_are_only_the_documented_ones():
    """t1 只允许在 README 登记的两处构造变更点上偏离 t0。"""
    t0 = model_licenses("scenario_t0_assets.json")
    t1 = model_licenses("scenario_t1_assets.json")

    assert set(t0) == set(t1)
    changed = {name for name in t0 if t0[name] != t1[name]}
    assert changed == CONSTRUCTED_T1_LICENSE_CHANGES, (
        f"t1 实际改动的模型是 {sorted(changed)}，与 README 登记的构造变更点不一致"
    )
