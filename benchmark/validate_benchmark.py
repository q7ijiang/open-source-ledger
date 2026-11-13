# -*- coding: utf-8 -*-
"""校验 benchmark/ 数据自洽性（对应 annotation_spec.md §11）。

用法：
    python benchmark/validate_benchmark.py
退出码 0 表示全部通过；非 0 表示存在不一致，输出会逐条列出。
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

import license_db  # noqa: E402

LICENSE_STATUS = {"standard", "nonstandard", "missing", "conflict", "unresolved"}
DECISIONS = {"SAFE", "RISK_POTENTIAL", "RISK_CONFIRMED", "UNDETERMINED"}
USE_TYPES = {
    "remote_api", "local_inference", "weight_distribution", "fine_tuning",
    "derivative_release", "evaluation_only", "unknown",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def expected_decision(status, risk_level, evidence_level):
    """与 annotation_spec.md §4 的规则表一一对应。"""
    if status in ("missing", "unresolved"):
        return "UNDETERMINED"
    if status == "nonstandard":
        return "RISK_POTENTIAL" if evidence_level in ("A", "B") else "UNDETERMINED"
    if status == "standard":
        if risk_level is None:
            return "UNDETERMINED"
        if risk_level <= 2:
            return "SAFE"
        if risk_level >= 4:
            return "RISK_CONFIRMED"
        return {"A": "RISK_CONFIRMED", "B": "RISK_POTENTIAL", "C": "UNDETERMINED"}.get(
            evidence_level, "UNDETERMINED"
        )
    return "UNDETERMINED"


def check_model_case(case, errors):
    cid = case.get("case_id")
    fact = case.get("fact") or {}
    status = fact.get("license_status")
    risk = fact.get("risk_level")
    ev = fact.get("evidence_level")

    if status not in LICENSE_STATUS:
        errors.append(f"{cid}: license_status 非法 {status!r}")
    if case.get("expected_decision") not in DECISIONS:
        errors.append(f"{cid}: expected_decision 非法 {case.get('expected_decision')!r}")

    if status == "standard":
        if not fact.get("canonical_id"):
            errors.append(f"{cid}: standard 必须有 canonical_id")
        if not isinstance(risk, int) or not 1 <= risk <= 5:
            errors.append(f"{cid}: standard 的 risk_level 必须在 1..5")
    if status in ("missing", "unresolved") and fact.get("canonical_id"):
        errors.append(f"{cid}: {status} 不得有 canonical_id")
    if status == "nonstandard" and fact.get("canonical_id"):
        errors.append(f"{cid}: nonstandard 不应被归一化")

    # 规则库必须真的认识 canonical_id
    if status == "standard" and fact.get("canonical_id"):
        rule = license_db.get_rule(fact["canonical_id"])
        if rule is None:
            errors.append(f"{cid}: canonical_id {fact['canonical_id']!r} 不在规则库中")
        elif rule.risk_level != risk:
            errors.append(f"{cid}: risk_level {risk} 与规则库 {rule.risk_level} 不符")

    want = expected_decision(status, risk, ev)
    if case.get("expected_decision") != want:
        errors.append(f"{cid}: expected_decision={case.get('expected_decision')} 应为 {want}")

    triggers = (
        ev == "C"
        or case.get("expected_decision") == "UNDETERMINED"
        or status in ("conflict", "unresolved", "nonstandard")
    )
    if bool(case.get("needs_human_review")) != triggers:
        errors.append(f"{cid}: needs_human_review 与 §7 触发条件不一致")


def check_candidates(errors):
    path = HERE / "candidates.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    if not rows:
        errors.append("candidates.csv 为空")
        return
    seen = set()
    for row in rows:
        cid = row["case_id"]
        if cid in seen:
            errors.append(f"{cid}: case_id 重复")
        seen.add(cid)
        if not SHA_RE.match(row["head_sha"]):
            errors.append(f"{cid}: head_sha 不是 40 位小写 SHA")
        if row["use_type"] not in USE_TYPES:
            errors.append(f"{cid}: use_type 非法 {row['use_type']!r}")
        if row["license_status"] not in LICENSE_STATUS:
            errors.append(f"{cid}: license_status 非法 {row['license_status']!r}")
        if row["expected_decision"] not in DECISIONS:
            errors.append(f"{cid}: expected_decision 非法")
        if row["license_status"] in ("missing", "unresolved") and row["expected_decision"] != "UNDETERMINED":
            errors.append(f"{cid}: 缺失/未解析必须判 UNDETERMINED")
        if not row["source_file"] or not row["model_id"]:
            errors.append(f"{cid}: source_file / model_id 不能为空")
        if not row["line_no"].isdigit():
            errors.append(f"{cid}: line_no 不是数字")


def main() -> int:
    errors: list[str] = []

    cases_path = HERE / "model_cases.json"
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    if len(cases) < 10:
        errors.append(f"模型案例不足 10 个（当前 {len(cases)}）")
    for case in cases:
        check_model_case(case, errors)

    check_candidates(errors)

    if errors:
        print(f"FAILED: {len(errors)} 项不一致")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"OK: {len(cases)} 个模型案例、{len(list(csv.DictReader((HERE / 'candidates.csv').open(encoding='utf-8-sig'))))} 个候选项目全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
