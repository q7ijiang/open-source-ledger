from __future__ import annotations

import json

from ai_layer.config import AIConfig
from ai_layer.provider import MockAIProvider
from ai_layer.service import AIService, has_special_token, is_ai_document
from ai_layer.status import resolve_ai_status, write_ai_status


def test_ai_input_only_includes_license_and_readme_documents() -> None:
    assert is_ai_document("LICENSE")
    assert is_ai_document("README.md")
    assert is_ai_document("docs/USE_POLICY.md")
    assert not is_ai_document("tokenizer_config.json")
    assert not is_ai_document("model_index.json")
    assert not is_ai_document("processor/preprocessor_config.json")

    assert has_special_token("token: <|image_pad|>")
    assert not has_special_token("Apache License Version 2.0")


def test_ai_service_filters_special_token_documents() -> None:
    provider = MockAIProvider(
        {
            "summary": "",
            "claims": [],
            "gaps": [{"dimension": "commercial_use", "reason": "证据不足"}],
        }
    )
    service = AIService(
        AIConfig(
            enabled=True,
            base_url="https://example.invalid/v1",
            model="test-model",
            api_key="test-key",
        ),
        provider=provider,
    )
    bundle = {
        "model_id": "acme/demo",
        "revision": "master",
        "facts": {"license": {"value": "apache-2.0"}},
        "documents": [
            {"path": "LICENSE", "content": "Apache License Version 2.0"},
            {
                "path": "tokenizer_config.json",
                "content": '{"token": "<|image_pad|>"}',
            },
            {"path": "README.md", "content": "license: apache-2.0"},
        ],
    }

    service.analyze_model_source(bundle)

    user_prompt = provider.calls[0]["user"]
    assert "Apache License Version 2.0" in user_prompt
    assert "tokenizer_config" not in user_prompt
    assert "<|image_pad|>" not in user_prompt


def test_ai_status_ready_when_all_config_present() -> None:
    status = resolve_ai_status(
        {
            "AI_ENABLED": "",
            "AI_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "Qwen/Qwen3.5-27B",
            "AI_API_KEY": "test-key",
            "GITHUB_SHA": "abc123",
        }
    )

    assert status["status"] == "ready"
    assert status["ready"] is True
    assert status["reasons"] == []
    assert status["api_key_present"] is True


def test_ai_status_degrades_when_config_missing() -> None:
    status = resolve_ai_status({"AI_ENABLED": "", "AI_MODEL": "Qwen/Qwen3.5-27B"})

    assert status["status"] == "unavailable"
    assert status["ready"] is False
    assert "missing AI_BASE_URL" in status["reasons"]
    assert "missing AI_API_KEY" in status["reasons"]


def test_ai_status_can_be_explicitly_disabled() -> None:
    status = resolve_ai_status(
        {
            "AI_ENABLED": "false",
            "AI_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "Qwen/Qwen3.5-27B",
            "AI_API_KEY": "test-key",
        }
    )

    assert status["status"] == "disabled"
    assert status["ready"] is False
    assert status["reasons"] == ["AI_ENABLED=false"]


def test_write_ai_status_does_not_include_api_key(tmp_path) -> None:
    output = tmp_path / "ai_status.json"
    write_ai_status(
        output,
        {
            "AI_BASE_URL": "https://example.invalid/v1",
            "AI_MODEL": "Qwen/Qwen3.5-27B",
            "AI_API_KEY": "secret-value",
        },
    )

    data = json.loads(output.read_text(encoding="utf-8"))
    assert "secret-value" not in output.read_text(encoding="utf-8")
    assert data["api_key_present"] is True
