# Real ModelScope full validation

- Overall: **PASS**
- Direct model precision: **1.000**
- Direct model recall: **1.000**
- Maximum upstream depth observed: **3**
- Downstream model nodes included: **0**

## Required lineage paths

| From | To (ancestor) | Result |
| --- | --- | --- |
| `Qwen/Qwen2.5-Coder-7B-Instruct-AWQ` | `Qwen/Qwen2.5-7B` | PASS |
| `OpenGVLab/InternVL3-8B-Instruct` | `OpenGVLab/InternViT-300M-448px` | PASS |
| `OpenGVLab/InternVL3-8B-Instruct` | `Qwen/Qwen2.5-7B` | PASS |
| `Qwen/Qwen2.5-Math-7B-Instruct` | `Qwen/Qwen2.5-7B` | PASS |
| `LLM-Research/gemma-3-4b-it` | `google/gemma-3-4b-pt` | PASS |

This report validates the frozen live snapshot. It does not claim that any license changed.
