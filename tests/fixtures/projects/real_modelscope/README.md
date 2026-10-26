# Real ModelScope Project Fixtures

This directory contains input projects that use real ModelScope model identifiers.

The fixtures are split into two stages:

- `smoke_project/`: a one-model project used to verify the Project -> BOM -> Diff chain.
- `full_project/`: a realistic support application with 7 direct models covering chat, code, image triage, billing calculations, multilingual fallback and retrieval.

`full_project/config/config.json` contains the machine-readable model registry. The Python files contain the same identifiers in realistic call sites so that the scanner's config and source-code paths are both exercised.

The full project deliberately includes multi-level and shared ancestry:

- `OpenGVLab/InternVL3-8B-Instruct` has a three-level branch through `InternVL3-8B-Pretrained` and the two InternViT generations, plus a shared `Qwen/Qwen2.5-7B` parent.
- The Qwen chat, code and math routes converge on the shared `Qwen/Qwen2.5-7B` ancestor.
- The Gemma route carries a non-Apache license through two generations.
- `BAAI/bge-m3` is retained as a direct model with no upstream parent.

The generated full snapshot currently validates 7 direct models, 18 total nodes, 22 edges and a maximum upstream depth of 3. See `snapshots/full/validation_report.md` and `snapshots/full/scenarios/README.md`.

All model identifiers in these fixtures exist on ModelScope. The files in this directory do not contain downloaded weights or API keys.

Generated snapshots belong in `snapshots/` and must record the retrieval time, ModelScope source URLs and the live/injected boundary. A snapshot is evidence, not a claim that the simulated t1 change happened on ModelScope.
