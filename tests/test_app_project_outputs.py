# -*- coding: utf-8 -*-
"""回归测试：Streamlit 项目模式的产物目录必须与 main.py 的 artifacts 根一致。

历史问题：app.py 曾用 ``_project_output_dir(ROOT, proj)`` 计算产物目录，
而 ``main.py --project`` 的产物落在 ``.open-source-ledger/artifacts/projects/<name>``，
于是 ``render_graph.py --input <ROOT>/projects/<name>/graph.json`` 必报
``FileNotFoundError``。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app  # noqa: E402  （模块级会调用 st.*，bare 模式下只是告警）
import main as ledger_main  # noqa: E402

PROJECT = Path("tests/fixtures/projects/qwen_image_license_tightening/upstream/project")


def test_artifacts_root_matches_main_default(monkeypatch):
    monkeypatch.delenv("OPEN_SOURCE_LEDGER_ARTIFACTS_DIR", raising=False)
    expected = (app.ROOT / ".open-source-ledger" / "artifacts").resolve()
    assert app._artifacts_root() == expected


def test_artifacts_root_honours_env(monkeypatch, tmp_path):
    monkeypatch.setenv("OPEN_SOURCE_LEDGER_ARTIFACTS_DIR", str(tmp_path))
    assert app._artifacts_root() == tmp_path


def test_run_project_uses_same_output_dir_as_main(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(app, "_run", lambda args: calls.append([str(a) for a in args]))
    monkeypatch.setattr(app.st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(app, "_embed_html", lambda *a, **k: None)
    monkeypatch.setattr(app, "_show_report", lambda *a, **k: None)
    monkeypatch.delenv("OPEN_SOURCE_LEDGER_ARTIFACTS_DIR", raising=False)

    app.run_project(PROJECT)

    assert len(calls) == 2, calls
    main_call, graph_call = calls

    # 1) main.py 必须显式收到 artifacts 根，避免再和 Streamlit 的 cwd 产生歧义。
    assert "--artifacts-dir" in main_call
    artifacts_dir = Path(main_call[main_call.index("--artifacts-dir") + 1])

    # 2) render_graph.py 读的 graph.json 必须正好在 main.py 写的那份目录下。
    graph_input = Path(graph_call[graph_call.index("--input") + 1])
    resolved_project = (app.ROOT / PROJECT).resolve()
    expected_graph = ledger_main._project_output_dir(artifacts_dir, resolved_project) / "graph.json"
    assert graph_input == expected_graph
    # 3) 产物目录本身要落在 artifacts 根下，而不是仓库根下的 projects/。
    assert expected_graph.name == "graph.json"
    assert expected_graph.parent.parent.name == "projects"
    assert expected_graph.parent.parent.parent == artifacts_dir
