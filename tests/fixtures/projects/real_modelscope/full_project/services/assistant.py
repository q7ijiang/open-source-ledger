from model_registry import CHAT_FAST, CHAT_PRIMARY, MULTILINGUAL_FALLBACK


def route_support_request(language: str, latency_sensitive: bool) -> str:
    if language not in {"zh", "en"}:
        return MULTILINGUAL_FALLBACK
    if latency_sensitive:
        return CHAT_FAST
    return CHAT_PRIMARY
