# -*- coding: utf-8 -*-
"""AI 输出的原文校验、置信度与统一 schema。"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "ai-analysis/v2"
PROMPT_VERSION = "modelscope-license-audit-v2"

DIMENSION_ZH = {
    "commercial_use": "商业使用",
    "redistribution": "再分发",
    "modification": "修改与衍生",
    "fine_tuned_redistribution": "微调版本再分发",
    "training_other_models": "训练其他模型",
    "notice": "许可证与版权声明保留",
    "commercial_license_request": "商用授权申请方式",
    "patent": "专利条款",
    "liability": "责任限制",
}

STATE_ZH = {
    "allowed": "允许",
    "conditional": "有条件允许",
    "restricted": "受限",
    "prohibited": "禁止",
    "unknown": "证据不足",
    "not_found": "未找到明确条款",
}

ALLOWED_STATES = set(STATE_ZH)
DEFAULT_GAP_DIMENSIONS = (
    "training_other_models",
    "fine_tuned_redistribution",
    "commercial_license_request",
)

PROJECT_USE_TYPES = {
    "remote_api": "远程 API 调用",
    "local_inference": "本地推理",
    "weight_distribution": "模型权重分发",
    "fine_tuning": "微调训练",
    "derivative_release": "衍生模型发布",
    "evaluation_only": "仅评测",
    "unknown": "未分类使用",
}

_RESTRICTION_WORDS = (
    "不得",
    "仅限",
    "禁止",
    "需要另行",
    "需另行",
    "未经许可",
    "may not",
    "must not",
    "prohibited",
    "non-commercial",
    "research only",
)
_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[^\s'\"]+"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_text(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _documents(source_bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in source_bundle.get("documents", []) or []:
        if not isinstance(item, dict):
            continue
        path = _safe_text(item.get("path"))
        content = _safe_text(item.get("content"))
        if path and content:
            result[path] = item
    return result


def confidence_for_claim(
    source_path: str,
    quote: str,
    content: str,
    state: str,
    file_sha256: str | None,
) -> tuple[float, dict[str, float]]:
    """计算可复核置信度；它不是模型自报概率，也不是法律结论概率。"""

    normalized_path = source_path.lower()
    score = 0.48
    factors = {"base": 0.48}
    if Path(normalized_path).name.startswith(("license", "copying")):
        score += 0.15
        factors["license_file"] = 0.15
    elif Path(normalized_path).name.startswith("readme"):
        score += 0.08
        factors["readme"] = 0.08
    else:
        score += 0.03
        factors["structured_file"] = 0.03
    if quote and quote in content:
        score += 0.10
        factors["exact_quote"] = 0.10
    if any(word in quote.lower() for word in _RESTRICTION_WORDS):
        score += 0.08
        factors["restriction_wording"] = 0.08
    if file_sha256:
        score += 0.03
        factors["source_sha256"] = 0.03
    if len(quote) >= 8:
        score += 0.02
        factors["quote_context"] = 0.02
    if state in {"conditional", "unknown", "not_found"}:
        score -= 0.12
        factors["uncertain_state"] = -0.12
    score = max(0.05, min(0.89, score))
    return round(score, 2), factors


def _normalize_model_analysis_v1(
    raw: dict[str, Any],
    source_bundle: dict[str, Any],
    config_public: dict[str, Any],
) -> dict[str, Any]:
    documents = _documents(source_bundle)
    facts = source_bundle.get("facts") if isinstance(source_bundle.get("facts"), dict) else {}
    license_fact = None
    if isinstance(facts.get("license"), dict):
        license_fact = facts["license"].get("value")
    claims: list[dict[str, Any]] = []
    seen_dimensions: set[str] = set()
    rejected: list[dict[str, str]] = []
    for item in raw.get("claims", []) if isinstance(raw.get("claims"), list) else []:
        if not isinstance(item, dict):
            continue
        dimension = _safe_text(item.get("dimension"))
        state = _safe_text(item.get("state")).lower()
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        source_path = _safe_text(evidence.get("source_path"))
        quote = _safe_text(evidence.get("quote"))
        doc = documents.get(source_path)
        if not dimension or dimension in seen_dimensions or state not in ALLOWED_STATES:
            continue
        if doc is None or not quote or quote not in _safe_text(doc.get("content")):
            rejected.append({"dimension": dimension, "reason": "引文未在指定原文中精确命中"})
            continue
        confidence, factors = confidence_for_claim(
            source_path,
            quote,
            _safe_text(doc.get("content")),
            state,
            _safe_text(doc.get("sha256")) or None,
        )
        claims.append(
            {
                "dimension": dimension,
                "dimension_zh": DIMENSION_ZH.get(dimension, dimension),
                "state": state,
                "state_zh": STATE_ZH[state],
                "statement": _safe_text(item.get("statement")) or quote,
                "condition": _safe_text(item.get("condition")),
                "evidence_level": "C",
                "confidence": confidence,
                "confidence_factors": factors,
                "evidence": {
                    "source_path": source_path,
                    "source_url": _safe_text(doc.get("source_url")),
                    "quote": quote,
                    "quote_sha256": sha256_text(quote),
                    "file_sha256": _safe_text(doc.get("sha256")),
                },
                "human_review": "pending",
            }
        )
        seen_dimensions.add(dimension)

    gaps: list[dict[str, str]] = []
    seen_gaps: set[str] = set()
    for source_gaps in (raw.get("gaps", []), rejected):
        if not isinstance(source_gaps, list):
            continue
        for item in source_gaps:
            if not isinstance(item, dict):
                continue
            dimension = _safe_text(item.get("dimension"))
            if not dimension or dimension in seen_dimensions or dimension in seen_gaps:
                continue
            gaps.append(
                {
                    "dimension": dimension,
                    "dimension_zh": DIMENSION_ZH.get(dimension, dimension),
                    "reason": _safe_text(item.get("reason")) or "证据不足",
                }
            )
            seen_gaps.add(dimension)
    for dimension in DEFAULT_GAP_DIMENSIONS:
        if dimension not in seen_dimensions and dimension not in seen_gaps:
            gaps.append(
                {
                    "dimension": dimension,
                    "dimension_zh": DIMENSION_ZH[dimension],
                    "reason": "证据不足",
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_type": "model_profile",
        "status": "ok" if claims and not rejected else ("partial" if claims else "no_evidence"),
        "subject": {
            "model_id": _safe_text(source_bundle.get("model_id")),
            "revision": _safe_text(source_bundle.get("revision")),
            "license_fact": license_fact,
            "fact_source": "ModelScope",
            "source_bundle_sha256": sha256_text(
                __import__("json").dumps(source_bundle, ensure_ascii=False, sort_keys=True)
            ),
        },
        "provider": config_public,
        "prompt_version": PROMPT_VERSION,
        "generated_at": utc_now(),
        "summary": _safe_text(raw.get("summary")),
        "claims": claims,
        "gaps": gaps,
        "fact_policy": {
            "ai_may_change_license": False,
            "ai_may_change_decision": False,
            "ai_evidence_level": "C",
            "human_review_required": True,
        },
    }


def _structured_notes(value: Any) -> list[dict[str, str]]:
    entries = value if isinstance(value, list) else [value]
    notes: list[dict[str, str]] = []
    for entry in entries:
        if isinstance(entry, dict):
            text = _safe_text(
                entry.get("text")
                or entry.get("statement")
                or entry.get("condition")
                or entry.get("exception")
            )
            if not text:
                continue
            note = {"text": text}
            for field_name in ("source_path", "quote"):
                field_value = _safe_text(entry.get(field_name))
                if field_value:
                    note[field_name] = field_value
            notes.append(note)
        else:
            text = _safe_text(entry)
            if text:
                notes.append({"text": text})
    return notes


def _validated_evidences(
    item: dict[str, Any],
    state: str,
    documents: dict[str, dict[str, Any]],
    rejected: list[dict[str, str]],
) -> list[dict[str, Any]]:
    raw_evidences = item.get("evidences")
    if not isinstance(raw_evidences, list):
        raw_evidences = [item.get("evidence")]
    evidences: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw_evidence in raw_evidences:
        if not isinstance(raw_evidence, dict):
            continue
        source_path = _safe_text(raw_evidence.get("source_path"))
        quote = _safe_text(raw_evidence.get("quote"))
        doc = documents.get(source_path)
        if doc is None or not quote or quote not in _safe_text(doc.get("content")):
            rejected.append(
                {
                    "dimension": _safe_text(item.get("dimension")),
                    "source_path": source_path,
                    "reason": "引文未在指定原文中精确命中",
                }
            )
            continue
        signature = (source_path, quote)
        if signature in seen:
            continue
        seen.add(signature)
        confidence, factors = confidence_for_claim(
            source_path,
            quote,
            _safe_text(doc.get("content")),
            state,
            _safe_text(doc.get("sha256")) or None,
        )
        evidences.append(
            {
                "source_path": source_path,
                "source_url": _safe_text(doc.get("source_url")),
                "quote": quote,
                "quote_sha256": sha256_text(quote),
                "file_sha256": _safe_text(doc.get("sha256")),
                "confidence": confidence,
                "confidence_factors": factors,
            }
        )
    return evidences


def normalize_model_analysis(
    raw: dict[str, Any],
    source_bundle: dict[str, Any],
    config_public: dict[str, Any],
) -> dict[str, Any]:
    """归一化多证据条款输出；同一维度允许保留多条逐字依据。"""
    documents = _documents(source_bundle)
    facts = source_bundle.get("facts") if isinstance(source_bundle.get("facts"), dict) else {}
    license_fact = None
    if isinstance(facts.get("license"), dict):
        license_fact = facts["license"].get("value")

    rejected: list[dict[str, str]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    raw_claims = raw.get("claims") if isinstance(raw.get("claims"), list) else []
    for item in raw_claims:
        if not isinstance(item, dict):
            continue
        dimension = _safe_text(item.get("dimension"))
        state = _safe_text(item.get("state")).lower()
        if not dimension or state not in ALLOWED_STATES:
            continue
        evidences = _validated_evidences(item, state, documents, rejected)
        if not evidences:
            continue
        grouped.setdefault(dimension, []).append(
            {
                "state": state,
                "statement": _safe_text(item.get("statement")) or evidences[0]["quote"],
                "conditions": _structured_notes(item.get("conditions") or item.get("condition")),
                "exceptions": _structured_notes(item.get("exceptions")),
                "evidences": evidences,
            }
        )

    claims: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for dimension in sorted(grouped):
        candidates = grouped[dimension]
        primary = candidates[0]
        all_evidences: list[dict[str, Any]] = []
        seen_evidence: set[tuple[str, str]] = set()
        for candidate in candidates:
            for entry in candidate["evidences"]:
                key = (entry["source_path"], entry["quote"])
                if key not in seen_evidence:
                    seen_evidence.add(key)
                    all_evidences.append(entry)
        primary_evidence = all_evidences[0]
        confidence = float(primary_evidence["confidence"])
        factors = dict(primary_evidence.get("confidence_factors") or {})
        document_count = len({entry["source_path"] for entry in all_evidences})
        if document_count > 1:
            bonus = min(0.02 * (document_count - 1), 0.06)
            factors["cross_document_support"] = round(bonus, 2)
            confidence = min(0.89, round(confidence + bonus, 2))
        states = sorted({candidate["state"] for candidate in candidates})
        conditions = [
            note for candidate in candidates for note in candidate["conditions"]
        ]
        exceptions = [
            note for candidate in candidates for note in candidate["exceptions"]
        ]
        claim_id = "claim-" + sha256_text(
            f"{dimension}|{primary_evidence['source_path']}|{primary_evidence['quote']}"
        )[:12]
        conflicting = len(states) > 1
        if conflicting:
            conflicts.append(
                {
                    "dimension": dimension,
                    "dimension_zh": DIMENSION_ZH.get(dimension, dimension),
                    "states": states,
                    "reason": "同一维度存在状态不一致的证据，需人工复核",
                    "human_review": "pending",
                }
            )
        claims.append(
            {
                "claim_id": claim_id,
                "dimension": dimension,
                "dimension_zh": DIMENSION_ZH.get(dimension, dimension),
                "state": primary["state"],
                "state_zh": STATE_ZH[primary["state"]],
                "statement": primary["statement"],
                "condition": conditions[0]["text"] if conditions else "",
                "conditions": conditions,
                "exceptions": exceptions,
                "evidence_level": "C",
                "confidence": confidence,
                "confidence_factors": factors,
                "evidence": primary_evidence,
                "evidences": all_evidences,
                "evidence_count": len(all_evidences),
                "cross_document_support": document_count > 1,
                "conflict": conflicting,
                "human_review": "pending",
            }
        )

    seen_dimensions = set(grouped)
    gaps: list[dict[str, str]] = []
    seen_gaps: set[str] = set()
    source_gaps = raw.get("gaps") if isinstance(raw.get("gaps"), list) else []
    for item in [*source_gaps, *rejected]:
        if not isinstance(item, dict):
            continue
        dimension = _safe_text(item.get("dimension"))
        if not dimension or dimension in seen_dimensions or dimension in seen_gaps:
            continue
        gaps.append(
            {
                "dimension": dimension,
                "dimension_zh": DIMENSION_ZH.get(dimension, dimension),
                "reason": _safe_text(item.get("reason")) or "证据不足",
            }
        )
        seen_gaps.add(dimension)
    for dimension in DEFAULT_GAP_DIMENSIONS:
        if dimension not in seen_dimensions and dimension not in seen_gaps:
            gaps.append(
                {
                    "dimension": dimension,
                    "dimension_zh": DIMENSION_ZH[dimension],
                    "reason": "证据不足",
                }
            )

    if conflicts:
        status = "conflict" if claims else "no_evidence"
    elif claims and not rejected:
        status = "ok"
    elif claims:
        status = "partial"
    else:
        status = "no_evidence"

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_type": "model_profile",
        "status": status,
        "subject": {
            "model_id": _safe_text(source_bundle.get("model_id")),
            "revision": _safe_text(source_bundle.get("revision")),
            "license_fact": license_fact,
            "fact_source": "ModelScope",
            "source_bundle_sha256": sha256_text(
                __import__("json").dumps(source_bundle, ensure_ascii=False, sort_keys=True)
            ),
        },
        "provider": config_public,
        "prompt_version": PROMPT_VERSION,
        "generated_at": utc_now(),
        "summary": _safe_text(raw.get("summary")),
        "claims": claims,
        "conflicts": conflicts,
        "gaps": gaps,
        "simulation": bool(source_bundle.get("simulation")),
        "simulation_note": _safe_text(source_bundle.get("simulation_note")),
        "fact_policy": {
            "ai_may_change_license": False,
            "ai_may_change_decision": False,
            "ai_evidence_level": "C",
            "human_review_required": True,
        },
    }


def unavailable_analysis(
    analysis_type: str,
    subject: dict[str, Any],
    reason: str,
    config_public: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_type": analysis_type,
        "status": "unavailable",
        "subject": subject,
        "provider": config_public or {},
        "prompt_version": PROMPT_VERSION,
        "generated_at": utc_now(),
        "reason": _safe_text(reason),
        "claims": [],
        "gaps": [],
        "fact_policy": {
            "ai_may_change_license": False,
            "ai_may_change_decision": False,
            "ai_evidence_level": "C",
            "human_review_required": True,
        },
    }


def collect_project_evidence(
    project_path: Path,
    max_files: int = 40,
    max_file_chars: int = 6000,
) -> list[dict[str, str]]:
    suffixes = {".py", ".yaml", ".yml", ".json", ".toml", ".md"}
    skip = {".git", "node_modules", "vendor", "dist", "build", "__pycache__", ".venv"}
    results: list[dict[str, str]] = []
    for path in sorted(project_path.rglob("*")):
        if len(results) >= max_files:
            break
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in skip for part in path.relative_to(project_path).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        text = _SECRET_RE.sub(lambda m: f"{m.group(1)}=<redacted>", text)
        results.append(
            {
                "path": path.relative_to(project_path).as_posix(),
                "content": text[:max_file_chars],
                "sha256": sha256_text(text),
            }
        )
    return results


def normalize_project_context(
    raw: dict[str, Any],
    project_path: Path,
    evidence_files: list[dict[str, str]],
    config_public: dict[str, Any],
) -> dict[str, Any]:
    by_path = {item["path"]: item for item in evidence_files}
    uses: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for item in raw.get("uses", []) if isinstance(raw.get("uses"), list) else []:
        if not isinstance(item, dict):
            continue
        use_type = _safe_text(item.get("use_type"))
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        source_path = _safe_text(evidence.get("source_path"))
        quote = _safe_text(evidence.get("quote"))
        doc = by_path.get(source_path)
        if use_type not in PROJECT_USE_TYPES or doc is None or not quote or quote not in doc["content"]:
            rejected.append({"source_path": source_path, "reason": "项目原文未精确命中"})
            continue
        confidence = min(
            0.89,
            round(0.45 + 0.25 + 0.10 + (0.03 if doc.get("sha256") else 0), 2),
        )
        uses.append(
            {
                "use_type": use_type,
                "use_type_zh": PROJECT_USE_TYPES[use_type],
                "statement": _safe_text(item.get("statement")) or quote,
                "evidence_level": "C",
                "confidence": confidence,
                "evidence": {
                    "source_path": source_path,
                    "quote": quote,
                    "quote_sha256": sha256_text(quote),
                    "file_sha256": doc.get("sha256"),
                },
                "human_review": "pending",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_type": "project_context",
        "status": "ok" if uses else "no_evidence",
        "subject": {"project_path": str(project_path), "model_count": len(raw.get("models", []) or [])},
        "provider": config_public,
        "prompt_version": PROMPT_VERSION,
        "generated_at": utc_now(),
        "uses": uses,
        "rejected": rejected,
        "fact_policy": {
            "ai_may_change_license": False,
            "ai_may_change_decision": False,
            "ai_evidence_level": "C",
            "human_review_required": True,
        },
    }


def _analysis_index(analyses: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for analysis in analyses:
        if analysis.get("analysis_type") != "model_profile":
            continue
        if analysis.get("status") == "unavailable":
            continue
        subject = analysis.get("subject") if isinstance(analysis.get("subject"), dict) else {}
        model_id = _safe_text(subject.get("model_id"))
        if model_id:
            result[model_id] = analysis
    return result


def _semantic_change_audit(claim: dict[str, Any] | None, prefix: str) -> dict[str, Any]:
    """Expose frozen claim confidence and evidence provenance in Diff outputs."""
    if not isinstance(claim, dict):
        return {}
    evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
    return {
        f"{prefix}_confidence": claim.get("confidence"),
        f"{prefix}_confidence_factors": dict(claim.get("confidence_factors") or {}),
        f"{prefix}_evidence_level": _safe_text(claim.get("evidence_level")) or "C",
        f"{prefix}_source_path": _safe_text(evidence.get("source_path")),
        f"{prefix}_source_url": _safe_text(evidence.get("source_url")),
        f"{prefix}_quote_sha256": _safe_text(evidence.get("quote_sha256")),
        f"{prefix}_file_sha256": _safe_text(evidence.get("file_sha256")),
    }


def semantic_diff(before: Iterable[dict[str, Any]], after: Iterable[dict[str, Any]]) -> dict[str, Any]:
    before_by_model = _analysis_index(before)
    after_by_model = _analysis_index(after)
    simulation = any(
        analysis.get("simulation")
        for analysis in [*before_by_model.values(), *after_by_model.values()]
    )
    ai_available = bool(before_by_model or after_by_model)
    ranks = {"allowed": 0, "conditional": 1, "restricted": 2, "prohibited": 3, "not_found": 1, "unknown": 1}
    changes: list[dict[str, Any]] = []
    for model_id in sorted(set(before_by_model) | set(after_by_model)):
        before_claims = {
            claim.get("dimension"): claim
            for claim in before_by_model.get(model_id, {}).get("claims", [])
            if isinstance(claim, dict)
        }
        after_claims = {
            claim.get("dimension"): claim
            for claim in after_by_model.get(model_id, {}).get("claims", [])
            if isinstance(claim, dict)
        }
        for dimension in sorted(set(before_claims) | set(after_claims)):
            left = before_claims.get(dimension)
            right = after_claims.get(dimension)
            before_state = _safe_text(left.get("state")) if left else "not_found"
            after_state = _safe_text(right.get("state")) if right else "not_found"
            before_quote = _safe_text((left.get("evidence") or {}).get("quote")) if left else ""
            after_quote = _safe_text((right.get("evidence") or {}).get("quote")) if right else ""
            before_audit = _semantic_change_audit(left, "before")
            after_audit = _semantic_change_audit(right, "after")
            if before_state == after_state:
                if left and right and before_quote and after_quote and before_quote != after_quote:
                    changes.append(
                        {
                            "model_id": model_id,
                            "dimension": dimension,
                            "dimension_zh": DIMENSION_ZH.get(dimension, dimension),
                            "before_state": before_state,
                            "before_state_zh": STATE_ZH.get(before_state, before_state),
                            "after_state": after_state,
                            "after_state_zh": STATE_ZH.get(after_state, after_state),
                            "change_type": "evidence_changed",
                            "review_priority": "medium",
                            "reason": f"{dimension}状态未变，但原文依据发生变化",
                            "before_quote": before_quote,
                            "after_quote": after_quote,
                            **before_audit,
                            **after_audit,
                        }
                    )
                continue
            direction = ranks.get(after_state, 1) - ranks.get(before_state, 1)
            if left is None:
                change_type = "evidence_added"
            elif right is None:
                change_type = "evidence_removed"
            else:
                change_type = "tightened" if direction > 0 else ("loosened" if direction < 0 else "state_changed")
            priority = "high" if (
                change_type == "evidence_removed" or (direction > 0 and dimension == "commercial_use")
            ) else ("medium" if direction != 0 else "low")
            reason = f"许可证名称未变，但{dimension}语义由{before_state}变为{after_state}"
            if change_type == "evidence_added":
                reason = f"t1 新增可验证的{dimension}条款证据"
            elif change_type == "evidence_removed":
                reason = f"t1 未再形成可验证的{dimension}条款证据，需复核是否丢失上下文"
            changes.append(
                {
                    "model_id": model_id,
                    "dimension": dimension,
                    "dimension_zh": DIMENSION_ZH.get(dimension, dimension),
                    "before_state": before_state,
                    "before_state_zh": STATE_ZH.get(before_state, before_state),
                    "after_state": after_state,
                    "after_state_zh": STATE_ZH.get(after_state, after_state),
                    "change_type": change_type,
                    "review_priority": priority,
                    "reason": reason,
                    "before_quote": before_quote,
                    "after_quote": after_quote,
                    **before_audit,
                    **after_audit,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_type": "semantic_diff",
        "status": "no_profile" if not ai_available else ("ok" if changes else "no_change"),
        "ai_available": ai_available,
        "before_profile_count": len(before_by_model),
        "after_profile_count": len(after_by_model),
        "simulation": simulation,
        "generated_at": utc_now(),
        "changes": changes,
        "fact_policy": {
            "ai_may_change_decision": False,
            "ai_may_change_delta": False,
            "ai_evidence_level": "C",
            "human_review_required": True,
        },
    }
