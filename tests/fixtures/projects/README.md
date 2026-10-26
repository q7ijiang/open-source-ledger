# Project Fixtures

Project fixtures exercise the BOM-driven ModelScope scanner without vendoring model weights.

- `real_modelscope/`: real ModelScope model identifiers, live API snapshots, controlled what-if Diff inputs, and per-directory README files.

Regenerate and validate the real fixtures from the repository root:

```powershell
python tests\fixtures\projects\real_modelscope\generate_live_fixtures.py --stage smoke
python tests\fixtures\projects\real_modelscope\generate_live_fixtures.py --stage full
python tests\fixtures\projects\real_modelscope\generate_diff_scenarios.py
python -m pytest tests\test_real_modelscope_project_fixtures.py -q
```

A live `t0` snapshot is observed ModelScope data. A scenario `t1` snapshot is a controlled simulation and must retain `simulation=true` plus the original A-level evidence.
