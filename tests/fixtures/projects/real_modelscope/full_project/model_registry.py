CHAT_PRIMARY = "Qwen/Qwen2.5-14B-Instruct-AWQ"
CHAT_FAST = "Qwen/Qwen2.5-7B-Instruct-AWQ"
CODE_SUPPORT = "Qwen/Qwen2.5-Coder-7B-Instruct-AWQ"
VISION_SUPPORT = "OpenGVLab/InternVL3-8B-Instruct"
BILLING_SUPPORT = "Qwen/Qwen2.5-Math-7B-Instruct"
MULTILINGUAL_FALLBACK = "LLM-Research/gemma-3-4b-it"
EMBEDDING_MODEL = "BAAI/bge-m3"

MODEL_ROUTES = {
    "chat_primary": CHAT_PRIMARY,
    "chat_fast": CHAT_FAST,
    "code_support": CODE_SUPPORT,
    "vision_support": VISION_SUPPORT,
    "billing_support": BILLING_SUPPORT,
    "multilingual_fallback": MULTILINGUAL_FALLBACK,
    "retrieval": EMBEDDING_MODEL,
}
