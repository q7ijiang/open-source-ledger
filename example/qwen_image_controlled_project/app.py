# -*- coding: utf-8 -*-
IMAGE_MODEL_ID = "unsloth/Qwen-Image-2.1-Turbo-FP8"
DOCUMENT_MODEL_ID = "OpenGVLab/InternVL3-8B-Instruct"


def load_image_pipeline():
    from diffusers import AutoPipelineForImage2Image

    # The production service loads the FP8 model locally.
    return AutoPipelineForImage2Image.from_pretrained(IMAGE_MODEL_ID)


def load_document_model():
    from transformers import AutoModelForVision2Seq

    return AutoModelForVision2Seq.from_pretrained(DOCUMENT_MODEL_ID)


def inspect_material(prompt: str) -> dict:
    image_pipe = load_image_pipeline()
    generated = image_pipe(prompt=prompt).images[0]
    return {"image": generated, "summary": "generated locally"}
