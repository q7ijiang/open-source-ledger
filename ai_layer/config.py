# -*- coding: utf-8 -*-
"""AI 旁路分析配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_AI_MODEL = "Qwen/Qwen3-4B-Instruct-2507"


def _load_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=env_path, override=False)
    except ImportError:
        pass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AIConfig:
    """运行期 AI 配置；不包含任何需要写入产物的密钥。"""

    enabled: bool = False
    provider: str = "openai-compatible"
    model: str = DEFAULT_AI_MODEL
    base_url: str = ""
    api_key: str = ""
    timeout: float = 60.0
    max_context_chars: int = 24000

    @classmethod
    def from_env(cls, enabled: bool | None = None) -> "AIConfig":
        _load_env()
        effective_enabled = _env_bool("AI_ENABLED", False) if enabled is None else enabled
        try:
            timeout = max(1.0, float(os.getenv("AI_TIMEOUT", "60")))
        except ValueError:
            timeout = 60.0
        try:
            max_context_chars = max(4000, int(os.getenv("AI_MAX_CONTEXT_CHARS", "24000")))
        except ValueError:
            max_context_chars = 24000
        return cls(
            enabled=effective_enabled,
            provider=os.getenv("AI_PROVIDER", "openai-compatible").strip(),
            model=os.getenv("AI_MODEL", DEFAULT_AI_MODEL).strip() or DEFAULT_AI_MODEL,
            base_url=os.getenv("AI_BASE_URL", "").strip(),
            api_key=os.getenv("AI_API_KEY", "").strip(),
            timeout=timeout,
            max_context_chars=max_context_chars,
        )

    def validate(self) -> None:
        if not self.enabled:
            return
        if self.provider not in {"mock", "openai-compatible"}:
            raise ValueError(f"不支持的 AI Provider：{self.provider}")

    def public_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "timeout": self.timeout,
        }
