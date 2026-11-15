from __future__ import annotations

import json

from ai_layer.status import resolve_ai_status, write_ai_status


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
