from vllm import LLM

CHAT_MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"


def build_chat_model():
    return LLM(model=CHAT_MODEL, quantization="awq")
