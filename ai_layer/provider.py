# -*- coding: utf-8 -*-
"""OpenAI-compatible 与可离线复现的 Mock Provider。"""

from __future__ import annotations

import json
from typing import Any, Protocol

import requests

from .config import AIConfig


class AIProviderError(RuntimeError):
    """Provider 调用或响应解析失败。"""


class CompletionProvider(Protocol):
    def complete(self, system_prompt: str, user_prompt: str, config: AIConfig) -> str:
        ...


class OpenAICompatibleProvider:
    """通过 /chat/completions 调用本地 vLLM、Ollama 或兼容服务。"""

    def complete(self, system_prompt: str, user_prompt: str, config: AIConfig) -> str:
        if not config.base_url.strip():
            raise AIProviderError("未配置 AI_BASE_URL，AI 语义证据不可用")
        url = f"{config.base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        payload = {
            "model": config.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=config.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise AIProviderError(f"AI 服务请求失败：{exc}") from exc
        except ValueError as exc:
            raise AIProviderError("AI 服务返回的不是合法 JSON") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("AI 服务响应缺少 choices[0].message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("AI 服务返回了空内容")
        return content


class MockAIProvider:
    """固定响应 Provider，只用于测试和完全离线验收。"""

    def __init__(self, responses: Any) -> None:
        if isinstance(responses, list):
            self._responses = list(responses)
        else:
            self._responses = [responses]
        self.calls: list[dict[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str, config: AIConfig) -> str:
        self.calls.append({"system": system_prompt, "user": user_prompt})
        if not self._responses:
            raise AIProviderError("Mock Provider 没有剩余响应")
        value = self._responses.pop(0)
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)


def build_provider(config: AIConfig, provider: CompletionProvider | None = None) -> CompletionProvider:
    if provider is not None:
        return provider
    if config.provider == "mock":
        raise ValueError("AI_PROVIDER=mock 时必须显式传入 MockAIProvider")
    return OpenAICompatibleProvider()
