from transformers import AutoModel, AutoTokenizer

# 演示项目：引用了 4 个有代表性的 Hugging Face 模型

# 1. 基座模型
bert = AutoModel.from_pretrained("bert-base-uncased")

# 2. 长血缘链模型（4 层：Llama-3.1-8B → SFT → DPO → Tulu-3-8B）
tulu = AutoModel.from_pretrained("allenai/Llama-3.1-Tulu-3-8B")

# 3. 量化模型（3 层）
qwen_gguf = AutoModel.from_pretrained("TheBloke/Qwen2.5-0.5B-Instruct-GGUF")

# 4. 跨架构微调模型（3 层）
deberta = AutoModel.from_pretrained("cross-encoder/nli-deberta-v3-base")
