# -*- coding: utf-8 -*-
MODEL_ID = "Qwen/Qwen-Image-2.1"


def load_pipeline():
    from diffusers import AutoPipelineForImage2Image

    return AutoPipelineForImage2Image.from_pretrained(MODEL_ID)


def generate(prompt: str) -> bytes:
    pipe = load_pipeline()
    result = pipe(prompt=prompt)
    return result.images[0]
