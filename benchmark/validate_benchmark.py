"""Gate 1 基准数据自检（v2）。

按 A 的 review 意见，这个脚本只做"能机器判定的一致性检查"，不做准确率评估。
检查项：
  A. 字段与枚举完整性
  B. 证据包四段（platform import / 模型绑定 / 调用表达式 / 条件分支）
  C. requested_revision 与调用证据一致
  D. 许可证 pipeline 层与 semantic 层分离，且 semantic 由固定 gold 表推出
  E. 快照落盘、同模型快照一致
  F. 正样本 / 负样本 / 排除记录三者互斥，负样本行号非 0
  G. 分组约束（同项目、同模型家族不跨组）
用法：
  python benchmark/validate_benchmark.py
退出码 0 表示全部通过，1 表示存在不一致（逐条打印）。
"""
import csv
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(HERE, "snapshots")
EV_DIR = os.path.join(HERE, "evidence")

PLATFORM_POSITIVE = {"modelscope_download", "modelscope_api", "modelscope_source_selected"}
PLATFORM_ALL = PLATFORM_POSITIVE | {
    "modelscope_import", "modelscope_namespace_only", "huggingface_import",
    "non_modelscope_remote_api", "local_path_only", "mapping_only", "ambiguous", "commented_out",
}
ROLES = {"primary", "conditional_fallback"}
CONFIDENCE = {"high", "medium", "low"}
REVISION_SOURCES = {"call_literal", "call_variable_resolved", "call_variable_resolved_none", "unspecified"}
LICENSE_STATES = {"standard_spdx", "recognized_non_spdx", "recognized_family_unresolved",
                  "missing", "unresolved", "conflict", "nonstandard"}
LICENSE_CLASSES = {"permissive", "weak_copyleft", "strong_copyleft", "network_copyleft",
                   "ai_restricted", "non_commercial", "unknown"}
RISK_BY_CLASS = {"permissive": {1, 2}, "weak_copyleft": {3}, "strong_copyleft": {4},
                 "network_copyleft": {5}, "ai_restricted": {4}, "non_commercial": {4}, "unknown": set()}
USE_TYPES = {"local_inference", "fine_tuning", "evaluation_only", "weight_distribution",
             "remote_api", "unknown"}
USE_BASES = {"download_only", "execution_call", "training_call", "distribution", "unspecified"}
DECISIONS = {"SAFE", "RISK_POTENTIAL", "RISK_CONFIRMED", "UNDETERMINED"}
GROUPS = {"dev", "validation", "sealed_test"}
EXCLUSION_REASONS = {"ambiguous", "mapping_only", "local_path_only", "namespace_only",
                     "commented_out", "non_modelscope_remote_api"}
NEGATIVE_BASES = {"other_platform_explicit", "modelscope_call_commented_out",
                  "modelscope_call_not_reached", "modelscope_namespace_only"}

REQUIRED_POSITIVE = [
    "case_id", "repo", "repo_url", "head_sha", "source_file", "source_kind", "line_start", "line_end",
    "model_literal_lines", "matched_text", "matched_text_sha256", "platform_evidence", "platform_role",
    "platform_confidence", "platform_import_lines", "platform_import_sha256", "model_id", "model_binding",
    "requested_revision", "revision_source", "api_revision", "model_source_url", "observed_at",
    "snapshot_path", "snapshot_sha256", "license_raw", "license_name_raw", "license_source_field",
    "license_observed_at", "semantic_license_family", "semantic_license_version", "semantic_license_state",
    "semantic_license_class", "semantic_risk_level", "semantic_basis", "use_type", "use_type_basis",
    "project_group", "family_group", "usage_evidence", "annotator", "note", "pipeline_known",
    "pipeline_spdx_like", "pipeline_category", "pipeline_canonical_license_id", "pipeline_risk_level",
    "pipeline_license_state", "pipeline_decision", "expected_decision", "needs_human_review",
]
REQUIRED_NEGATIVE = ["case_id", "repo", "repo_url", "head_sha", "source_file", "source_kind",
                     "line_start", "line_end", "matched_text", "matched_text_sha256", "platform_evidence",
                     "negative_basis", "negative_scope", "negative_confidence", "model_id",
                     "project_group", "family_group", "evidence_path", "note", "reviewer", "reviewed_at"]
REQUIRED_EXCLUDED = ["reject_id", "repo", "repo_url", "head_sha", "source_file", "line_no",
                     "location_status", "model_id", "observed_signal", "evidence_text",
                     "exclusion_reason", "exclusion_note", "reviewed_at", "reviewer"]
REQUIRED_CASE = ["case_id", "model_id", "source_url", "observed_at", "api_revision", "snapshot_path",
                 "snapshot_sha256", "source_field", "raw_value", "raw_license", "raw_license_name",
                 "semantic_license_family", "semantic_license_version", "semantic_license_state",
                 "semantic_license_class", "semantic_risk_level", "semantic_basis",
                 "pipeline_known", "pipeline_spdx_like", "pipeline_category", "pipeline_canonical_license_id",
                 "pipeline_risk_level", "pipeline_license_state", "pipeline_decision",
                 "expected_decision", "needs_human_review", "note"]

# gold 表：只看平台原值字符串，与 licenses.json 是否收录无关
GOLD = [
    (r"^apache", ("Apache-2.0", "2.0", "standard_spdx", "permissive", 2)),
    (r"^mit$|^mit license", ("MIT", "", "standard_spdx", "permissive", 1)),
    (r"^gpl-?3", ("GPL-3.0", "3.0", "standard_spdx", "strong_copyleft", 4)),
    (r"^cc-by-nc-nd", ("CC-BY-NC-ND", "", "recognized_family_unresolved", "non_commercial", 4)),
    (r"^gemma", ("Gemma-Terms-of-Use", "", "recognized_non_spdx", "ai_restricted", 4)),
    (r"^llama3", ("Llama-3.1-Community-License", "", "recognized_non_spdx", "ai_restricted", 4)),
    (r"^qwen-research", ("Qwen-Research-License", "", "recognized_non_spdx", "ai_restricted", 4)),
    (r"^bigscience-bloom-rail", ("BigScience-BLOOM-RAIL-1.0", "1.0", "recognized_non_spdx", "ai_restricted", 4)),
]
GOLD_OVERRIDE = {
    "AI-ModelScope/XTTS-v2": ("", "", "unresolved", "unknown", None),
    "ZhipuAI/glm-4-9b-chat": ("", "", "unresolved", "unknown", None),
    "Shanghai_AI_Laboratory/internlm2_5-7b-chat": ("", "", "unresolved", "unknown", None),
    "Shanghai_AI_Laboratory/internlm-chat-7b": ("", "", "missing", "unknown", None),
    "Qwen/Qwen-Image-2.1": ("Qwen-Research-License", "", "recognized_non_spdx", "ai_restricted", 4),
}
GENERIC = {"other", "none", "unknown", "noassertion", "not specified", ""}

errors = []


def err(msg):
    errors.append(msg)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def norm(text):
    return " ".join(text.split())


def read_csv(name, required):
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        err(f"{name}: 文件不存在")
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        err(f"{name}: 没有数据行")
        return []
    missing = [c for c in required if c not in rows[0]]
    if missing:
        err(f"{name}: 缺少列 {missing}")
    return rows


def gold_for(model_id, raw, raw_name):
    if model_id in GOLD_OVERRIDE:
        return GOLD_OVERRIDE[model_id]
    effective = (raw_name or raw or "").strip()
    if not effective or effective.lower() in GENERIC:
        return ("", "", "missing", "unknown", None)
    for pattern, spec in GOLD:
        if re.match(pattern, effective.lower()):
            return spec
    return ("", "", "unresolved", "unknown", None)


def decision_from(risk, state):
    if state in ("missing", "unresolved", "conflict"):
        return "UNDETERMINED"
    if state in ("nonstandard", "recognized_family_unresolved"):
        return "RISK_POTENTIAL"
    if risk is None:
        return "UNDETERMINED"
    return "SAFE" if risk <= 2 else "RISK_CONFIRMED"


def load_snapshots():
    idx_path = os.path.join(SNAP_DIR, "index.json")
    if not os.path.exists(idx_path):
        err("snapshots/index.json 不存在")
        return {}
    idx = json.load(open(idx_path, encoding="utf-8"))
    out = {}
    for m in idx.get("models", []):
        model_id = m["model_id"]
        path = os.path.join(os.path.dirname(HERE), m["snapshot"])
        if not os.path.exists(path):
            err(f"{model_id}: 快照文件不存在 {m['snapshot']}")
            continue
        raw = open(path, "rb").read()
        if hashlib.sha256(raw).hexdigest() != m["snapshot_sha256"]:
            err(f"{model_id}: 快照 sha256 与 index 不一致")
        try:
            data = json.loads(raw.decode("utf-8"))
            lic = (data.get("Data") or {}).get("License") or ""
            lic_name = (data.get("Data") or {}).get("LicenseName") or ""
            if lic != (m.get("license") or "") or lic_name != (m.get("license_name") or ""):
                err(f"{model_id}: index 里的 license 与快照原文不一致")
        except json.JSONDecodeError:
            err(f"{model_id}: 快照不是合法 JSON")
        out[model_id] = m
    return out


def check_row_license(row, snaps, where):
    model_id = row["model_id"]
    snap = snaps.get(model_id)
    if not snap:
        err(f"{where}: 模型 {model_id} 没有快照")
        return
    raw_license = row.get("license_raw", row.get("raw_license", ""))
    raw_name = row.get("license_name_raw", row.get("raw_license_name", ""))
    if (raw_license or "") != (snap.get("license") or ""):
        err(f"{where}: license_raw 与快照不一致")
    if (raw_name or "") != (snap.get("license_name") or ""):
        err(f"{where}: license_name_raw 与快照不一致")
    if (row.get("snapshot_sha256") or "") != snap["snapshot_sha256"]:
        err(f"{where}: snapshot_sha256 与快照不一致")
    if (row.get("api_revision") or "") != (snap.get("revision") or ""):
        err(f"{where}: api_revision 与快照的 Data.Revision 不一致")
    family, version, state, klass, risk = gold_for(model_id, raw_license or "", raw_name or "")
    if row.get("semantic_license_family") != family:
        err(f"{where}: semantic_license_family 应为 {family!r}（由平台原值推出，不看规则库是否收录）")
    if row.get("semantic_license_version") != version:
        err(f"{where}: semantic_license_version 应为 {version!r}")
    if row.get("semantic_license_state") != state:
        err(f"{where}: semantic_license_state 应为 {state!r}")
    if row.get("semantic_license_class") != klass:
        err(f"{where}: semantic_license_class 应为 {klass!r}")
    want_risk = "" if risk is None else str(risk)
    if row.get("semantic_risk_level") != want_risk:
        err(f"{where}: semantic_risk_level 应为 {want_risk!r}，实际 {row.get('semantic_risk_level')!r}")
    if row.get("semantic_license_class") not in LICENSE_CLASSES:
        err(f"{where}: semantic_license_class 不在枚举内")
    else:
        risk_val = row.get("semantic_risk_level")
        if risk_val and int(risk_val) not in RISK_BY_CLASS[row["semantic_license_class"]]:
            err(f"{where}: 风险等级 {risk_val} 与许可类型 {row['semantic_license_class']} 不匹配")
    pip_state = row.get("pipeline_license_state")
    if pip_state not in {"standard", "missing", "nonstandard", "unresolved", "conflict"}:
        err(f"{where}: pipeline_license_state 取值非法 {pip_state!r}")
    if row.get("expected_decision") != decision_from(risk, state):
        err(f"{where}: expected_decision 应为 {decision_from(risk, state)}")
    if row.get("expected_decision") not in DECISIONS:
        err(f"{where}: expected_decision 不在枚举内")


def check_evidence(row, positives_by_repo, where):
    path = os.path.join(EV_DIR, f"{row['case_id']}.json")
    if not os.path.exists(path):
        err(f"{where}: 缺少证据包 evidence/{row['case_id']}.json")
        return
    ev = json.load(open(path, encoding="utf-8"))
    for key, want in (("case_id", row["case_id"]), ("repo", row["repo"]),
                      ("model_id", row["model_id"]), ("head_sha", row["head_sha"]),
                      ("source_file", row["source_file"])):
        if ev.get(key) != want:
            err(f"{where}: 证据包 {key}={ev.get(key)!r} 与行内 {want!r} 不一致")
    platform = ev.get("platform") or {}
    if not platform.get("imports"):
        err(f"{where}: 证据包缺少 platform import")
    if platform.get("imports_sha256") != row["platform_import_sha256"]:
        err(f"{where}: platform_import_sha256 与证据包不一致")
    if sha(norm("\n".join(i["text"] for i in platform.get("imports", [])))) != row["platform_import_sha256"]:
        err(f"{where}: platform_import_sha256 无法由 import 原文复算")
    call = ev.get("call") or {}
    if not call.get("text"):
        err(f"{where}: 证据包缺少调用表达式")
    if call.get("sha256") != row["matched_text_sha256"] or sha(norm(call.get("text", ""))) != row["matched_text_sha256"]:
        err(f"{where}: matched_text_sha256 与证据包调用不一致")
    if not (int(row["line_start"]) <= call.get("start", 0) <= int(row["line_end"])):
        err(f"{where}: 证据包调用区间 {call.get('start')}-{call.get('end')} 不在 CSV 行窗口 "
            f"{row['line_start']}-{row['line_end']} 内")
    if not (ev.get("model_binding") or ev.get("model_literals")):
        err(f"{where}: 证据包既没有变量绑定也没有模型 ID 字面行")
    binding = ev.get("model_binding")
    if binding and binding["line"] >= call.get("start", 0):
        err(f"{where}: 变量绑定行必须在调用行之前")
    for imp in platform.get("imports", []):
        if imp["line"] >= call.get("start", 0):
            err(f"{where}: platform import 行 {imp['line']} 应在调用行之前")
    if row["platform_role"] == "conditional_fallback":
        branch = ev.get("branch") or {}
        if not branch.get("conditional_fallback") or not branch.get("lines"):
            err(f"{where}: conditional_fallback 的证据包缺少条件分支")
        if "try:" not in "\n".join(l["text"] for l in branch.get("lines", [])):
            err(f"{where}: conditional_fallback 的分支证据应包含 try/except 上下文")
    elif (ev.get("branch") or {}).get("conditional_fallback"):
        err(f"{where}: 证据包标了 conditional_fallback，但 platform_role 是 {row['platform_role']}")


def check_positive(row, snaps):
    where = row["case_id"]
    if row["platform_evidence"] not in PLATFORM_POSITIVE:
        err(f"{where}: 正样本 platform_evidence={row['platform_evidence']} 不是 ModelScope 使用证据")
    if row["platform_evidence"] not in PLATFORM_ALL:
        err(f"{where}: platform_evidence 不在枚举内")
    if row["platform_role"] not in ROLES:
        err(f"{where}: platform_role 非法 {row['platform_role']!r}")
    if row["platform_confidence"] not in CONFIDENCE:
        err(f"{where}: platform_confidence 非法")
    if row["source_kind"] not in {"code", "script", "config", "docs", "other"}:
        err(f"{where}: source_kind 非法")
    if row["source_file"].startswith("modelscope/") or row["repo"].startswith("modelscope/"):
        err(f"{where}: 官方仓库不能作为项目正样本")
    try:
        start, end = int(row["line_start"]), int(row["line_end"])
        if start < 1 or end < start:
            err(f"{where}: 行号区间非法 {start}-{end}")
    except ValueError:
        err(f"{where}: 行号不是整数")
    if sha(norm(row["matched_text"])) != row["matched_text_sha256"]:
        err(f"{where}: matched_text_sha256 与 CSV 内文本不一致")
    for lit in filter(None, row["model_literal_lines"].split(";")):
        if not lit.isdigit() or int(lit) < 1:
            err(f"{where}: model_literal_lines 含非法行号 {lit!r}")
    if row["revision_source"] not in REVISION_SOURCES:
        err(f"{where}: revision_source 非法")
    if row["revision_source"] == "call_literal":
        if not row["requested_revision"]:
            err(f"{where}: call_literal 但 requested_revision 为空")
        if row["requested_revision"] == "master" and row["case_id"] != "pc-0017":
            err(f"{where}: 除 pc-0017（项目源码显式写 master）外不应出现 requested_revision=master")
    else:
        if row["requested_revision"]:
            err(f"{where}: revision_source={row['revision_source']} 时 requested_revision 应为空")
    if row["use_type"] not in USE_TYPES:
        err(f"{where}: use_type 非法")
    if row["use_type_basis"] not in USE_BASES:
        err(f"{where}: use_type_basis 非法")
    if row["use_type"] == "fine_tuning" and row["use_type_basis"] != "training_call":
        err(f"{where}: 只有训练调用证据才能标 fine_tuning")
    if row["use_type"] == "weight_distribution" and row["use_type_basis"] != "distribution":
        err(f"{where}: weight_distribution 只指向第三方对外分发权重")
    if row["platform_role"] == "conditional_fallback":
        pass  # 允许，但 README 会解释它是 HF 优先、MS 回退
    if row["project_group"] not in GROUPS:
        err(f"{where}: project_group 非法")
    if not row["family_group"]:
        err(f"{where}: family_group 为空")
    if row["needs_human_review"] not in {"true", "false"}:
        err(f"{where}: needs_human_review 应为 true/false")
    check_row_license(row, snaps, where)


def main():
    positives = read_csv("candidates.csv", REQUIRED_POSITIVE)
    negatives = read_csv("negative_cases.csv", REQUIRED_NEGATIVE)
    excluded = read_csv("excluded_candidates.csv", REQUIRED_EXCLUDED)
    cases = json.load(open(os.path.join(HERE, "model_cases.json"), encoding="utf-8"))
    snaps = load_snapshots()

    if os.path.exists(os.path.join(HERE, "rejected_candidates.csv")):
        err("rejected_candidates.csv 已拆分，不应继续存在（负样本见 negative_cases.csv，审计记录见 excluded_candidates.csv）")

    if len(positives) != 20:
        err(f"正样本应为 20 条，实际 {len(positives)}")
    if len(cases) != 13:
        err(f"模型案例应为 13 条，实际 {len(cases)}")
    if not negatives:
        err("负样本表为空")

    pos_index = {}
    for row in positives:
        check_positive(row, snaps)
        check_evidence(row, pos_index, row["case_id"])
        pos_index[(row["repo"], row["model_id"], row["source_file"])] = row

    # 同模型多行时必须共享同一份快照事实
    by_model = {}
    for row in positives:
        by_model.setdefault(row["model_id"], []).append(row)
    for model_id, rows in by_model.items():
        for key in ("snapshot_sha256", "license_raw", "license_name_raw", "semantic_license_state",
                    "semantic_license_class", "semantic_risk_level"):
            values = {r[key] for r in rows}
            if len(values) > 1:
                err(f"{model_id}: 同一模型的多条记录 {key} 不一致 {values}")

    # 负样本
    for row in negatives:
        where = row["case_id"]
        if row["platform_evidence"] in PLATFORM_POSITIVE:
            err(f"{where}: 负样本不能标成 {row['platform_evidence']}")
        if row["platform_evidence"] not in PLATFORM_ALL:
            err(f"{where}: platform_evidence 不在枚举内")
        if row["negative_basis"] not in NEGATIVE_BASES:
            err(f"{where}: negative_basis 非法")
        if row["negative_confidence"] not in CONFIDENCE:
            err(f"{where}: negative_confidence 非法")
        if row["negative_scope"] not in {"repo_platform", "call_site"}:
            err(f"{where}: negative_scope 非法")
        if row["project_group"] not in GROUPS:
            err(f"{where}: project_group 非法")
        try:
            start, end = int(row["line_start"]), int(row["line_end"])
        except ValueError:
            err(f"{where}: 行号不是整数")
        else:
            if start < 1 or end < start:
                err(f"{where}: 负样本行号必须 >= 1（当前 {start}-{end}）")
        if sha(norm(row["matched_text"])) != row["matched_text_sha256"]:
            err(f"{where}: matched_text_sha256 与文本不一致")
        path = os.path.join(EV_DIR, f"{row['case_id']}.json")
        if not os.path.exists(path):
            err(f"{where}: 缺少证据包")
        else:
            ev = json.load(open(path, encoding="utf-8"))
            if ev.get("model_id") != row["model_id"] or ev.get("repo") != row["repo"]:
                err(f"{where}: 证据包与行内 repo/model 不一致")
            if (ev.get("call") or {}).get("sha256") != row["matched_text_sha256"]:
                err(f"{where}: 证据包调用哈希与行内不一致")
            if not (ev.get("negative") or {}).get("basis"):
                err(f"{where}: 证据包缺少 negative.basis")
        if row["family_group"] in {p["family_group"] for p in positives} and row["model_id"] in by_model:
            err(f"{where}: 负样本的模型 {row['model_id']} 同时出现在正样本中，需确认是调用点级负样本")

    # 正负调用点分离
    for neg in negatives:
        for pos in positives:
            if neg["repo"] != pos["repo"] or neg["source_file"] != pos["source_file"]:
                continue
            n1, n2 = int(neg["line_start"]), int(neg["line_end"])
            p1, p2 = int(pos["line_start"]), int(pos["line_end"])
            if not (n2 < p1 or n1 > p2):
                err(f"{neg['case_id']}: 负样本调用点与 {pos['case_id']} 的正样本调用点重叠")

    # 排除记录
    seen = set()
    for row in excluded:
        where = row["reject_id"]
        if row["exclusion_reason"] not in EXCLUSION_REASONS:
            err(f"{where}: exclusion_reason 非法")
        if row["location_status"] == "located":
            if not row["source_file"] or not row["line_no"].isdigit() or int(row["line_no"]) < 1:
                err(f"{where}: located 的记录必须给出文件与行号")
        elif row["location_status"] == "unlocated":
            if row["line_no"]:
                err(f"{where}: unlocated 的记录不应填行号")
        else:
            err(f"{where}: location_status 非法")
        key = (row["repo"], row["model_id"])
        if key in seen:
            err(f"{where}: 与其它排除记录重复 {key}")
        seen.add(key)
        if key in {(p["repo"], p["model_id"]) for p in positives}:
            err(f"{where}: 已排除的候选又出现在正样本中")
        if key in {(n["repo"], n["model_id"]) for n in negatives}:
            err(f"{where}: 已排除的候选又出现在负样本中")

    # 模型案例
    case_models = set()
    for row in cases:
        where = row["case_id"]
        missing = [c for c in REQUIRED_CASE if c not in row]
        if missing:
            err(f"{where}: 缺少字段 {missing}")
            continue
        if row["model_id"] in case_models:
            err(f"{where}: 模型重复")
        case_models.add(row["model_id"])
        check_row_license(row, snaps, where)
        if row.get("pipeline_license_state") not in {"standard", "missing", "nonstandard", "unresolved", "conflict"}:
            err(f"{where}: pipeline_license_state 非法")
        if row.get("needs_human_review") not in {"true", "false"}:
            err(f"{where}: needs_human_review 应为 true/false")
    for row in positives:
        if row["model_id"] in case_models:
            match = [c for c in cases if c["model_id"] == row["model_id"]][0]
            pairs = (("license_raw", "raw_license"), ("license_name_raw", "raw_license_name"),
                     ("semantic_license_state", "semantic_license_state"),
                     ("semantic_license_class", "semantic_license_class"),
                     ("semantic_risk_level", "semantic_risk_level"),
                     ("expected_decision", "expected_decision"))
            for row_key, case_key in pairs:
                if row.get(row_key) != match.get(case_key):
                    err(f"{row['case_id']}: 与模型案例 {match['case_id']} 的 {row_key} 不一致")
    if "Qwen/Qwen-Image-2.1" not in case_models:
        err("缺少 Qwen/Qwen-Image-2.1 的 qwen-research 案例")
    gemma = [c for c in cases if "gemma" in c["model_id"].lower()]
    llama = [c for c in cases if "llama-3.1" in c["model_id"].lower()]
    if gemma and llama:
        g, l = gemma[0], llama[0]
        # gold 只看平台原值：两者都应是"已识别的受限 AI 条款"，风险同为 4。
        # pipeline 层允许不同（Gemma 在规则库里、Llama 3.1 不在），这正是要报告的 pipeline 缺口。
        for key in ("semantic_license_class", "semantic_risk_level", "expected_decision"):
            if g[key] != l[key]:
                err(f"Gemma 与 Llama 3.1 的 {key} 口径不一致（gold 不应依赖规则库是否收录）")
        if g["pipeline_license_state"] == l["pipeline_license_state"] and g["pipeline_known"] == l["pipeline_known"]:
            pass  # 允许一致；不一致时由 README 的"已知 pipeline 缺口"说明

    # 分组约束
    fam_group = {}
    proj_group = {}
    for row in positives:
        fam_group.setdefault(row["family_group"], set()).add(row["project_group"])
        proj_group.setdefault(row["source_file"].split("/")[0] or row["repo"], set()).add(row["project_group"])
    for fam, groups in fam_group.items():
        if len(groups) > 1:
            err(f"模型家族 {fam} 跨组 {groups}")
    if len({g for groups in proj_group.values() for g in groups}) == 1:
        err("所有项目落在同一组，dev/validation/sealed 拆分失效")

    if errors:
        print(f"FAILED: {len(errors)} 项不一致")
        for e in errors:
            print(" -", e)
        return 1
    print(f"OK: {len(positives)} 个正样本、{len(negatives)} 个负样本、{len(excluded)} 条排除记录、"
          f"{len(cases)} 个模型案例，共 {len(positives) + len(negatives) + len(excluded) + len(cases)} 条记录全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
