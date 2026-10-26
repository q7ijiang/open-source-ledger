# Full Fixture Acceptance

This directory contains a frozen Project snapshot generated from the official
ModelScope API and two controlled what-if Diff scenarios. It separates live
ModelScope facts from acceptance-only AI simulations.

## Live Project Snapshot

- Direct models: **7**
- Total lineage nodes: **18**
- Lineage edges: **22**
- Maximum upstream depth: **3**
- Downstream model nodes included: **0**
- Direct-model precision: **1.000**
- Direct-model recall: **1.000**

Validation evidence:

- [validation_report.md](validation_report.md)
- [scan_manifest.json](scan_manifest.json)
- [project_report.md](project_report.md)
- [project_graph.html](project_graph.html)

The graph is a fixed-height DAG view: deeper ancestors are above project
models, and arrows point from a downstream model to its upstream source.
Cards use short display labels while the full model identity remains in the
detail panel, path tree, report and downloaded data. Aggregate membership is
not a lineage edge; the aggregate legend is hidden when no aggregate node is
present.

## Controlled Diff Scenarios

- [direct_license_change](scenarios/direct_license_change/scenario.json): one
  direct model changes from `Apache-2.0` to `qwen-research`; one model is
  affected and no multi-hop path certificate is required.
- [upstream_license_change](scenarios/upstream_license_change/scenario.json):
  shared ancestor `Qwen/Qwen2.5-7B` changes from `Apache-2.0` to
  `qwen-research`; 10 change events include the seed and 9 propagated models,
  and 9 path certificates describe the concrete affected models.

Open the what-if graphs:

- [direct_license_change/diff_graph.html](scenarios/direct_license_change/diff_graph.html)
- [upstream_license_change/diff_graph.html](scenarios/upstream_license_change/diff_graph.html)

The Diff renderer lays out the union of t0 and t1 once, then reuses the same
coordinates on both tabs. Switching snapshots does not move shared models, so
positional differences cannot be mistaken for project changes. The default
view is t1; t0 is available as the baseline tab.

## AI Acceptance Evidence

The AI overlay is deliberately frozen and marked `simulation=true`. It
demonstrates the evidence path, not the current ModelScope license of Qwen:

- Two model profiles and four exact clauses are attached to the live model
  identities; one project context cites the OpenAI-compatible call in
  `full_project/inference_client.py`.
- The t0 profile allows commercial use. The controlled t1 profile contains
  the exact simulated clause `仅限研究用途，不得用于商业目的`, and the
  semantic Diff reports `commercial_use: allowed -> prohibited`.
- The prohibited profile is evidence level C with confidence **0.86**.
  The score is factorized as base `+0.48`, LICENSE evidence `+0.15`,
  exact quote `+0.10`, restriction wording `+0.08`, verified source SHA256
  `+0.03`, and quote context `+0.02`.
- The project-context claim is also C-level and pending; its **0.83** score
  is tied to an exact source line and a file SHA256.
- AI never changes license facts, rule risk colors, Delta, decisions or CI.
  Human confirmation remains mandatory for every C-level conclusion.

Both HTML views include an AI status strip, evidence details and a
`下载 Markdown 报告` button. The report is downloaded from the accompanying
`project_report.md` or `diff_report.md`; HTML is a presentation layer, not a
replacement for the report artifact.

## Truth Boundary

The `t0` BOM is a frozen live ModelScope observation. Each `t1` BOM is a
controlled mutation with `simulation=true`; the original A-level evidence is
retained and the mutated value is accompanied by a C-level simulation entry.
The AI source bundles and semantic Diff are also acceptance simulations.
Do not cite this fixture as evidence that Qwen's real-world license changed.

## Reproduce

From the repository root, reuse the frozen live t0 snapshot while refreshing
the AI acceptance overlay and HTML:

```powershell
python tests\fixtures\projects\real_modelscope\generate_live_fixtures.py --stage full --reuse-existing
python tests\fixtures\projects\real_modelscope\generate_diff_scenarios.py
```

To repeat the live ModelScope collection, omit `--reuse-existing`. The latter
requires network access and a current ModelScope response.
