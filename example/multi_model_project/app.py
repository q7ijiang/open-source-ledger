# -*- coding: utf-8 -*-
"""multi_model_project 演示应用：同时使用 3 个真实 ModelScope 模型。"""
from modelscope import pipeline, AutoModelForCausalLM

# 1) 对话模型（Qwen2.5-7B-Instruct）
chat_pipe = pipeline("chat", model="Qwen/Qwen2.5-7B-Instruct")

# 2) 新一代指令模型（Qwen3-8B）
qwen3 = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-8B")

# 3) 中英 OCR 识别模型（TeleOCR）
ocr_pipe = pipeline("ocr", model="XingChen-AGI/TeleOCR")

if __name__ == "__main__":
    print("multi_model_project ready")
