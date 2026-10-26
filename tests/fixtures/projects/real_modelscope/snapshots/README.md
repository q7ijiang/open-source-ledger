# Generated Snapshots

Run `python tests/fixtures/projects/real_modelscope/generate_live_fixtures.py --stage smoke` for the one-model smoke snapshot.

Run the same command with `--stage full` to scan the complete multi-model project. The full validation currently covers 7 direct models, 18 nodes, 22 edges and a maximum upstream depth of 3.

The live scan creates:

- `t0_bom.json`
- `t0_assets.json`
- `t0_edges.json`
- `t0_graph.json`
- `project_report.md`
- `scan_manifest.json`
- `validation_report.md`

`scan_manifest.json` records model IDs, upstream depth, license values, source URLs, timestamps, live API status and direct-model precision/recall checks. `validation_report.md` records the required ancestry paths.

To create controlled Diff inputs from the frozen full snapshot, run:

```powershell
python tests/fixtures/projects/real_modelscope/generate_diff_scenarios.py
```

The generated scenarios are under `full/scenarios/`. Every `t1` BOM is explicitly marked with `simulation=true`; its original A-level ModelScope evidence remains present and must not be presented as a live license change.
