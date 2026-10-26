# -*- coding: utf-8 -*-
"""AI 语义证据服务与三种模式的统一入口。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import AIConfig
from .provider import AIProviderError, CompletionProvider, build_provider
from .schemas import (
    PROMPT_VERSION,
    collect_project_evidence,
    normalize_model_analysis,
    normalize_project_context,
    semantic_diff,
    unavailable_analysis,
    utc_now,
)

MODEL_SYSTEM_PROMPT = """你是开源 AI 模型的许可证证据抽取器。
只依据用户提供的 ModelScope 官方文档作结论。每个结论必须给出 source_path 和逐字 quote。
不得猜测文档中没有的条款，不得改写许可证名称，不得输出法律意见。
同一维度可给出多条证据；证据优先来自 LICENSE/COPYING，其次 README/使用政策。
仅输出 JSON：{"summary":"...","claims":[{"dimension":"commercial_use","state":"allowed|conditional|restricted|prohibited|unknown|not_found","statement":"...","conditions":[{"text":"...","source_path":"LICENSE","quote":"逐字原文"}],"exceptions":[],"evidences":[{"source_path":"LICENSE","quote":"逐字原文"}]}],"gaps":[{"dimension":"training_other_models","reason":"证据不足"}]}。
"""

PROJECT_SYSTEM_PROMPT = """你是 AI 模型使用上下文审计器。
只依据用户提供的项目文件片段判断模型如何被使用。每条判断必须给出 source_path 和逐字 quote。
不得根据项目名猜测，不得输出密钥。仅输出 JSON：{"uses":[{"use_type":"remote_api|local_inference|weight_distribution|fine_tuning|derivative_release|evaluation_only|unknown","statement":"...","evidence":{"source_path":"app.py","quote":"逐字原文"}}]}。
"""


def parse_json_response(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end <= start:
            raise AIProviderError("AI 输出不是 JSON") from exc
        try:
            parsed = json.loads(value[start : end + 1])
        except json.JSONDecodeError as nested:
            raise AIProviderError("AI 输出不是合法 JSON") from nested
    if not isinstance(parsed, dict):
        raise AIProviderError("AI 输出根节点必须是 JSON 对象")
    return parsed


class AIService:
    def __init__(
        self,
        config: AIConfig,
        provider: CompletionProvider | None = None,
    ) -> None:
        self.config = config
        self.provider = build_provider(config, provider) if config.enabled else provider

    def analyze_model_source(self, source_bundle: dict[str, Any]) -> dict[str, Any]:
        subject = {
            "model_id": source_bundle.get("model_id"),
            "revision": source_bundle.get("revision"),
            "license_fact": ((source_bundle.get("facts") or {}).get("license") or {}).get("value"),
        }
        if not self.config.enabled:
            return unavailable_analysis("model_profile", subject, "AI 未启用", self.config.public_dict())
        documents = []
        remaining = self.config.max_context_chars
        for item in source_bundle.get("documents", []) or []:
            if not isinstance(item, dict) or remaining <= 0:
                continue
            content = str(item.get("content") or "")[:remaining]
            documents.append(
                {
                    "path": item.get("path"),
                    "sha256": item.get("sha256"),
                    "content": content,
                }
            )
            remaining -= len(content)
        user_payload = {
            "model_id": source_bundle.get("model_id"),
            "revision": source_bundle.get("revision"),
            "license_fact": subject["license_fact"],
            "documents": documents,
        }
        try:
            assert self.provider is not None
            raw = parse_json_response(
                self.provider.complete(
                    MODEL_SYSTEM_PROMPT,
                    json.dumps(user_payload, ensure_ascii=False),
                    self.config,
                )
            )
            return normalize_model_analysis(raw, source_bundle, self.config.public_dict())
        except Exception as exc:  # noqa: BLE001
            return unavailable_analysis(
                "model_profile",
                subject,
                f"{type(exc).__name__}: {exc}",
                self.config.public_dict(),
            )

    def analyze_project_context(
        self,
        project_path: Path,
        model_analyses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        evidence_files = collect_project_evidence(project_path)
        subject = {"project_path": str(project_path), "model_count": len(model_analyses)}
        if not self.config.enabled:
            return unavailable_analysis("project_context", subject, "AI 未启用", self.config.public_dict())
        payload = {
            "project_path": str(project_path),
            "models": [analysis.get("subject") for analysis in model_analyses],
            "files": evidence_files,
        }
        try:
            assert self.provider is not None
            raw = parse_json_response(
                self.provider.complete(
                    PROJECT_SYSTEM_PROMPT,
                    json.dumps(payload, ensure_ascii=False),
                    self.config,
                )
            )
            return normalize_project_context(raw, project_path, evidence_files, self.config.public_dict())
        except Exception as exc:  # noqa: BLE001
            return unavailable_analysis(
                "project_context",
                subject,
                f"{type(exc).__name__}: {exc}",
                self.config.public_dict(),
            )

    def compare_models(
        self,
        before: list[dict[str, Any]],
        after: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return semantic_diff(before, after)


def analysis_bundle(
    config: AIConfig,
    model_analyses: list[dict[str, Any]] | None = None,
    project_context: dict[str, Any] | None = None,
    diff_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "ai-analysis-bundle/v1",
        "prompt_version": PROMPT_VERSION,
        "generated_at": utc_now(),
        "provider": config.public_dict(),
        "model_analyses": model_analyses or [],
        "project_context": project_context,
        "semantic_diff": diff_analysis,
    }


def attach_model_analysis(assets: list[dict[str, Any]], analysis: dict[str, Any]) -> int:
    subject = analysis.get("subject") if isinstance(analysis.get("subject"), dict) else {}
    target = str(subject.get("model_id") or "")
    attached = 0
    for asset in assets:
        if target and str(asset.get("name") or "") == target:
            asset["ai_analysis"] = analysis
            attached += 1
    return attached


def attach_project_context(assets: list[dict[str, Any]], context: dict[str, Any]) -> None:
    for asset in assets:
        if not asset.get("aggregate"):
            asset["ai_project_context"] = context
