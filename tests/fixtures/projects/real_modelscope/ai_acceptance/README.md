# AI Acceptance Overlay

This directory contains the frozen C-level AI evidence used only by the
repository acceptance snapshot.

- `before_source_bundle.json` and `before_response.json` describe an explicitly
  simulated permissive policy.
- `after_source_bundle.json` and `after_response.json` describe an explicitly
  simulated research-only tightening.
- `project_context_response.json` identifies the fixture's OpenAI-compatible
  call using a quote that exists verbatim in `full_project/inference_client.py`.
- `__TARGET_MODEL__` is replaced with a model identity that already exists in
  the real Project lineage snapshot. It is not a hard-coded filesystem path.
- Every generated AI profile carries `simulation=true` and a note saying that
  the quoted acceptance text is not the model's current ModelScope license.

The fixture exists to make the AI evidence, quote hashes, confidence factors,
semantic Diff and pending human review visible during offline acceptance. It
must not be used as evidence about the real Qwen license.
