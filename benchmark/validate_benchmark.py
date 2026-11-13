# -*- coding: utf-8 -*-
"""校验 benchmark/ 数据自洽性（对应 annotation_spec.md §11）。

用法：
    python benchmark/validate_benchmark.py

退出码 0 表示全部通过；非 0 表示存在不一致，输出会逐条列出。
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

import license_db  # noqa: E402

DECISIONS = {"SAFE", "RISK_POTENTIAL", "RISK_CONFIRMED", "UNDETERMINED"}
PIPELINE_STATES = {"standard", "nonstandard", "missing", "unresolved"}
SEMANTIC_STATES = {"standard_spdx", "recognized_non_spdx", "nonstandard", "missing", "unresolved", "conflict"}
LICENSE_CLASSES = {"spdx", "recognized_non_spdx", "nonstandard", "missing", "unresolved"}
PLATFORM_EVIDENCE = {
    "modelscope_download", "modelscope_api", "modelscope_source_selected", "modelscope_import",
    "modelscope_namespace_only", "huggingface_import", "non_modelscope_remote_api",
    "local_path_only", "mapping_only", "ambiguous", "commented_out",
}
POSITIVE_PLATFORM = {"modelscope_download", "modelscope_api", "modelscope_source_selected"}
REJECT_REASONS = {
    "huggingface_only", "local_path_only", "mapping_only", "non_modelscope_remote_api",
    "ambiguous_platform", "commented_out", "namespace_only",
}
USE_TYPES = {
    "remote_api", "local_inference", "weight_distribution", "fine_tuning",
    "derivative_release", "evaluation_only", "unknown",
}
SOURCE_KINDS = {"code", "script", "config", "docs", "other"}
GROUPS = {"dev", "validation", "sealed_test"}
GENERIC = {"", "other", "none", "unknown", "noassertion", "not found"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

CANDIDATE_COLUMNS = [
    "case_id", "repo", "repo_url", "head_sha", "source_file", "source_kind",
    "line_start", "line_end", "matched_text", "matched_text_sha256",
    "platform_evidence", "platform_confidence", "model_id", "model_revision",
    "model_source_url", "model_observed_at", "license_raw", "license_name_raw",
    "license_source_field", "license_observed_at", "raw_response_sha256",
    "license_known", "license_spdx_like", "license_category", "canonical_license_id",
    "risk_level", "pipeline_license_state", "semantic_license_state", "license_class",
    "needs_human_review", "use_type", "expected_decision", "candidate_status",
    "candidate_role", "project_group", "family_group", "usage_evidence", "annotator", "note",
]


def norm(text: str) -> str:
    return " ".join((text or "").split())


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def expected_decision(semantic: str, risk) -> str:
    """与 annotation_spec.md §4 的规则表一一对应（本批证据等级均为 A）。"""
    if semantic in ("missing", "unresolved", "conflict"):
        return "UNDETERMINED"
    if semantic == "nonstandard":
        return "RISK_POTENTIAL"
    if risk is None:
        return "UNDETERMINED"
    if risk <= 2:
        return "SAFE"
    if risk >= 4:
        return "RISK_CONFIRMED"
    return "RISK_CONFIRMED"  # risk == 3，证据等级 A


def needs_review(semantic: str, license_class: str, use_type: str, conf: str = "high") -> bool:
    """§7 的触发条件（证据等级本批恒为 A）。"""
    return (
        semantic in ("conflict", "unresolved", "missing")
        or license_class in ("nonstandard", "recognized_non_spdx")
        or use_type == "unknown"
        or conf == "low"
    )


def check_license_block(prefix: str, row: dict, errors: list[str], has_use_type: bool = True) -> None:
    """校验 raw / pipeline / semantic / class 四段许可证字段自洽。"""
    known = row.get("license_known") in (True, "true")
    spdx_like = row.get("license_spdx_like") in (True, "true")
    pipeline = row.get("pipeline_license_state")
    semantic = row.get("semantic_license_state")
    klass = row.get("license_class")
    canonical = row.get("canonical_license_id") or None
    risk = row.get("risk_level")
    if isinstance(risk, str):
        risk = int(risk) if risk.strip().isdigit() else None
    if risk in ("", 0):
        risk = None
    raw = row.get("license_raw") or ""
    name = row.get("license_name_raw") or ""

    if pipeline not in PIPELINE_STATES:
        errors.append(f"{prefix}: pipeline_license_state 非法 {pipeline!r}")
    if semantic not in SEMANTIC_STATES:
        errors.append(f"{prefix}: semantic_license_state 非法 {semantic!r}")
    if klass not in LICENSE_CLASSES:
        errors.append(f"{prefix}: license_class 非法 {klass!r}")

    if known:
        if not canonical:
            errors.append(f"{prefix}: known=true 必须有 canonical_license_id")
        rule = license_db.get_rule(canonical) if canonical else None
        if rule is None:
            errors.append(f"{prefix}: canonical_license_id {canonical!r} 不在规则库")
        else:
            if risk != rule.risk_level:
                errors.append(f"{prefix}: risk_level {risk} 与规则库 {rule.risk_level} 不符")
            if row.get("license_category") != rule.category:
                errors.append(f"{prefix}: license_category {row.get('license_category')!r} 与规则库 {rule.category!r} 不符")
    else:
        if canonical:
            errors.append(f"{prefix}: known=false 不得有 canonical_license_id")
        if risk not in (None, "", 0):
            errors.append(f"{prefix}: known=false 不得有 risk_level")

    # pipeline / semantic / class 三者的一致性
    if pipeline == "standard":
        if not known:
            errors.append(f"{prefix}: pipeline=standard 必须 known=true")
        if semantic not in ("standard_spdx", "recognized_non_spdx"):
            errors.append(f"{prefix}: pipeline=standard 时 semantic 必须为 standard_spdx/recognized_non_spdx")
        if semantic == "standard_spdx" and not spdx_like:
            errors.append(f"{prefix}: semantic=standard_spdx 必须 spdx_like=true")
        if semantic == "recognized_non_spdx" and spdx_like:
            errors.append(f"{prefix}: semantic=recognized_non_spdx 必须 spdx_like=false")
    if pipeline == "missing":
        if known or canonical:
            errors.append(f"{prefix}: pipeline=missing 不得有 canonical_id / known=true")
        if semantic not in ("missing", "unresolved"):
            errors.append(f"{prefix}: pipeline=missing 时 semantic 必须为 missing 或 unresolved")
    if pipeline == "nonstandard":
        if semantic != "nonstandard":
            errors.append(f"{prefix}: pipeline=nonstandard 时 semantic 必须为 nonstandard")
    if pipeline == "unresolved" and semantic != "unresolved":
        errors.append(f"{prefix}: pipeline=unresolved 时 semantic 必须为 unresolved")

    expect_class = {"standard_spdx": "spdx", "recognized_non_spdx": "recognized_non_spdx",
                    "nonstandard": "nonstandard", "missing": "missing", "unresolved": "unresolved",
                    "conflict": "unresolved"}.get(semantic)
    if expect_class and klass != expect_class:
        errors.append(f"{prefix}: semantic={semantic} 时 license_class 应为 {expect_class}，实为 {klass}")

    # semantic=unresolved 只能来自占位符或接口失败
    if semantic == "unresolved" and raw.strip().lower() not in GENERIC and name.strip().lower() not in GENERIC:
        errors.append(f"{prefix}: semantic=unresolved 但 raw_license 不是占位符（{raw!r}）")

    if klass == "recognized_non_spdx" and not (known and not spdx_like):
        errors.append(f"{prefix}: recognized_non_spdx 必须 known=true 且 spdx_like=false")

    want = expected_decision(semantic, risk)
    if row.get("expected_decision") != want:
        errors.append(f"{prefix}: expected_decision={row.get('expected_decision')} 应为 {want}")

    conf = row.get("platform_confidence", "high")
    trig = needs_review(semantic, klass, row.get("use_type", "unknown"), conf)
    flag = row.get("needs_human_review") in (True, "true")
    if flag != trig:
        errors.append(f"{prefix}: needs_human_review={flag} 与 §7 触发条件（应为 {trig}）不一致")


def check_candidates(errors: list[str]) -> tuple[list[dict], set[str]]:
    rows = list(csv.DictReader((HERE / "candidates.csv").open(encoding="utf-8-sig")))
    if not rows:
        errors.append("candidates.csv 为空")
        return [], set()

    missing_cols = [c for c in CANDIDATE_COLUMNS if c not in rows[0]]
    if missing_cols:
        errors.append(f"candidates.csv 缺少列：{missing_cols}")

    seen_ids: set[str] = set()
    families: dict[str, str] = {}
    for row in rows:
        cid = row["case_id"]
        if cid in seen_ids:
            errors.append(f"{cid}: case_id 重复")
        seen_ids.add(cid)
        if not re.match(r"^pc-\d{4}$", cid):
            errors.append(f"{cid}: case_id 格式应为 pc-NNNN")
        if not SHA40_RE.match(row["head_sha"]):
            errors.append(f"{cid}: head_sha 不是 40 位小写 SHA")
        if row.get("source_kind") not in SOURCE_KINDS:
            errors.append(f"{cid}: source_kind 非法 {row.get('source_kind')!r}")
        ev = row.get("platform_evidence")
        if ev not in PLATFORM_EVIDENCE:
            errors.append(f"{cid}: platform_evidence 非法 {ev!r}")
        if row.get("candidate_status") == "positive" and ev not in POSITIVE_PLATFORM:
            errors.append(f"{cid}: 正样本 platform_evidence={ev} 不构成 ModelScope 使用证据")
        if row.get("platform_confidence") not in ("high", "low"):
            errors.append(f"{cid}: platform_confidence 非法 {row.get('platform_confidence')!r}")
        if row.get("use_type") not in USE_TYPES:
            errors.append(f"{cid}: use_type 非法 {row.get('use_type')!r}")
        if row.get("use_type") == "weight_distribution":
            errors.append(f"{cid}: 本批不存在对外分发权重的项目，use_type 不应为 weight_distribution")
        if not row.get("model_id") or "/" not in row["model_id"]:
            errors.append(f"{cid}: model_id 必须为 namespace/name")
        if not row.get("model_revision"):
            errors.append(f"{cid}: model_revision 不能为空")
        if not row.get("model_source_url", "").startswith("https://www.modelscope.cn/models/"):
            errors.append(f"{cid}: model_source_url 不是 ModelScope 模型页")
        for col in ("model_observed_at", "license_observed_at"):
            if not DATE_RE.match(row.get(col, "")):
                errors.append(f"{cid}: {col} 不是 YYYY-MM-DD")
        if not SHA256_RE.match(row.get("raw_response_sha256", "")):
            errors.append(f"{cid}: raw_response_sha256 不是 64 位十六进制")
        if row.get("license_source_field") not in ("Data.License", "Data.LicenseName"):
            errors.append(f"{cid}: license_source_field 非法 {row.get('license_source_field')!r}")
        try:
            start, end = int(row["line_start"]), int(row["line_end"])
        except (TypeError, ValueError):
            errors.append(f"{cid}: line_start / line_end 不是整数")
        else:
            if not (1 <= start <= end):
                errors.append(f"{cid}: 行号区间非法 {start}..{end}")
        matched = row.get("matched_text", "")
        if not matched.strip():
            errors.append(f"{cid}: matched_text 为空")
        elif sha256(norm(matched)) != row.get("matched_text_sha256"):
            errors.append(f"{cid}: matched_text_sha256 与 matched_text 不匹配")
        if row.get("project_group") not in GROUPS:
            errors.append(f"{cid}: project_group 非法 {row.get('project_group')!r}")
        fam = row.get("family_group", "")
        if not fam:
            errors.append(f"{cid}: family_group 不能为空")
        elif fam in families and families[fam] != row["project_group"]:
            errors.append(f"{cid}: 家族 {fam} 跨组（{families[fam]} vs {row['project_group']}）")
        else:
            families[fam] = row["project_group"]

        check_license_block(cid, row, errors)

    if len(rows) < 20:
        errors.append(f"候选项目不足 20 条（当前 {len(rows)}）")
    return rows, {r["repo"] for r in rows}


def check_rejected(selected: set[str], errors: list[str]) -> list[dict]:
    rows = list(csv.DictReader((HERE / "rejected_candidates.csv").open(encoding="utf-8-sig")))
    if not rows:
        errors.append("rejected_candidates.csv 为空")
        return []
    seen: set[str] = set()
    for row in rows:
        rid = row["reject_id"]
        if rid in seen:
            errors.append(f"{rid}: reject_id 重复")
        seen.add(rid)
        if row["repo"] in selected:
            errors.append(f"{rid}: {row['repo']} 同时在正样本中")
        if row.get("reject_reason") not in REJECT_REASONS:
            errors.append(f"{rid}: reject_reason 非法 {row.get('reject_reason')!r}")
        if row.get("platform_evidence") not in PLATFORM_EVIDENCE:
            errors.append(f"{rid}: platform_evidence 非法 {row.get('platform_evidence')!r}")
        if not row.get("evidence_text", "").strip():
            errors.append(f"{rid}: evidence_text 为空")
        if not str(row.get("line_no", "")).isdigit():
            errors.append(f"{rid}: line_no 不是数字")
        if row["reject_reason"] in ("huggingface_only", "local_path_only", "mapping_only",
                                    "non_modelscope_remote_api") and not row.get("note"):
            errors.append(f"{rid}: 被排除条目必须写 note 说明原因")
    if len(rows) < 20:
        errors.append(f"排除记录不足 20 条（当前 {len(rows)}）")
    return rows


def check_model_cases(errors: list[str]) -> list[dict]:
    cases = json.loads((HERE / "model_cases.json").read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        errors.append("model_cases.json 顶层必须是数组")
        return []
    if len(cases) < 10:
        errors.append(f"模型案例不足 10 个（当前 {len(cases)}）")
    seen: set[str] = set()
    for case in cases:
        cid = case.get("case_id", "?")
        if cid in seen:
            errors.append(f"{cid}: case_id 重复")
        seen.add(cid)
        for key in ("source_url", "observed_at", "model_revision", "source_field", "raw_value",
                    "raw_license", "raw_license_name", "license_class", "pipeline_license_state",
                    "semantic_license_state", "expected_decision", "note"):
            if key not in case:
                errors.append(f"{cid}: 缺少字段 {key}")
        if not case.get("model_id") or "/" not in case.get("model_id", ""):
            errors.append(f"{cid}: model_id 必须为 namespace/name")
        if not DATE_RE.match(case.get("observed_at", "")):
            errors.append(f"{cid}: observed_at 不是 YYYY-MM-DD")
        if case.get("source_field") not in ("Data.License", "Data.LicenseName"):
            errors.append(f"{cid}: source_field 非法 {case.get('source_field')!r}")
        raw_sha = case.get("raw_response_sha256", "")
        if raw_sha and not SHA256_RE.match(raw_sha):
            errors.append(f"{cid}: raw_response_sha256 不是 64 位十六进制")
        if not raw_sha and case.get("semantic_license_state") != "unresolved":
            errors.append(f"{cid}: 只有接口失败（unresolved）的案例允许缺 raw_response_sha256")
        raw_value = case.get("raw_value", "")
        effective = case.get("raw_license_name") or case.get("raw_license")
        if raw_value != effective:
            errors.append(f"{cid}: raw_value 必须等于生效原值（LicenseName 优先）")
        if case.get("source_field") == "Data.License" and case.get("raw_license_name"):
            errors.append(f"{cid}: LicenseName 非空时 source_field 应为 Data.LicenseName")
        # 模型案例用的是 known / spdx_like / category，这里映射成校验器的统一键名
        flat = dict(case)
        flat["license_known"] = case.get("known")
        flat["license_spdx_like"] = case.get("spdx_like")
        flat["license_category"] = case.get("category")
        flat["license_raw"] = case.get("raw_license", "")
        flat["license_name_raw"] = case.get("raw_license_name", "")
        flat["platform_confidence"] = "high"
        flat["use_type"] = "model_case"  # 模型级案例不判 use_type，避免误触发 §7 第 5 条
        check_license_block(cid, flat, errors)
        if case.get("canonical_license_id") == "Gemma-Terms-of-Use":
            if case.get("spdx_like") is not False or case.get("category") != "ai_restricted":
                errors.append(f"{cid}: Gemma 必须 spdx_like=false 且 category=ai_restricted")
    return cases


def main() -> int:
    errors: list[str] = []
    rows, selected = check_candidates(errors)
    rejected = check_rejected(selected, errors)
    cases = check_model_cases(errors)

    # 同一模型在两张表里出现时，状态必须一致
    cand_by_model = {r["model_id"]: r for r in rows}
    for case in cases:
        row = cand_by_model.get(case.get("model_id"))
        if not row:
            continue
        for field in ("pipeline_license_state", "semantic_license_state", "license_class", "canonical_license_id"):
            a = (row.get(field) or None) if field != "canonical_license_id" else (row.get(field) or None)
            b = case.get(field) or None
            if a != b:
                errors.append(f"{case.get('case_id')}: 与 candidates.csv 中 {row['model_id']} 的 {field} 不一致（{a!r} vs {b!r}）")

    total_rows = len(rows) + len(rejected)
    if errors:
        print(f"FAILED: {len(errors)} 项不一致")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(
        f"OK: {len(rows)} 个正样本、{len(rejected)} 条排除记录、{len(cases)} 个模型案例，"
        f"共 {total_rows} 条候选全部通过"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
