# Customer Support Model Router

A realistic multi-model application fixture for Project and Diff verification.

The application routes requests by capability:

- `Qwen/Qwen2.5-14B-Instruct-AWQ`: main support assistant
- `Qwen/Qwen2.5-7B-Instruct-AWQ`: low-latency chat route
- `Qwen/Qwen2.5-Coder-7B-Instruct-AWQ`: code-aware support route
- `OpenGVLab/InternVL3-8B-Instruct`: image and document triage route
- `Qwen/Qwen2.5-Math-7B-Instruct`: refund and billing calculation route
- `LLM-Research/gemma-3-4b-it`: multilingual fallback
- `BAAI/bge-m3`: knowledge-base embeddings

No model weights are downloaded by this fixture.
