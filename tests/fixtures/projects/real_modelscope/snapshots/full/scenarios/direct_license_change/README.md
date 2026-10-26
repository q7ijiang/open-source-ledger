# direct_license_change

This is a controlled what-if scenario. It is not a ModelScope claim that the
license changed in the real world.

- Base snapshot: `tests/fixtures/projects/real_modelscope/snapshots/full/t0_bom.json`
- Mutated model: `Qwen/Qwen2.5-7B-Instruct-AWQ`
- Canonical ID: `model:modelscope/Qwen/Qwen2.5-7B-Instruct-AWQ@master`
- Original license: `Apache-2.0`
- Simulated license: `qwen-research`
- Simulation metadata: `simulation=true`
- AI overlay: `tests/fixtures/projects/real_modelscope/ai_acceptance/`

Expected downstream set in the frozen project subgraph:

- `Qwen/Qwen2.5-7B-Instruct-AWQ`

The t1 assets retain the original lineage edges. The mutation is represented by
a C-level simulation evidence entry and never overwrites the original A-level
ModelScope evidence.

The AI section is also simulated. It demonstrates quote validation, confidence
factors and semantic tightening, but it is not a claim about the real model's
current ModelScope license.
