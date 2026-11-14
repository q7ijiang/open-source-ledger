from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from portable_paths import sanitize_text, sanitize_value

REPO_ROOT = Path(__file__).resolve().parents[3]
FULL_GRAPH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "projects"
    / "real_modelscope"
    / "snapshots"
    / "full"
    / "t0_graph.json"
)


def test_sanitize_text_removes_repository_and_home_prefixes() -> None:
    repository_path = str(REPO_ROOT / "tests" / "fixtures" / "t0_bom.json")
    cleaned = sanitize_text(repository_path)

    assert "Qijiang" not in cleaned
    assert repository_path not in cleaned
    assert cleaned.endswith("t0_bom.json")

    assert "C:\\Users\\alice" not in sanitize_text("C:\\Users\\alice\\project\\bom.json")
    assert "/home/alice" not in sanitize_text("/home/alice/project/bom.json")
    assert "/Users/alice" not in sanitize_text("/Users/alice/project/bom.json")


def test_sanitize_value_is_recursive_and_keeps_unrelated_text() -> None:
    cleaned = sanitize_value(
        {
            "source_file": str(REPO_ROOT / "tests" / "fixtures" / "t0_bom.json"),
            "items": [{"project_path": "/home/alice/demo"}],
            "url": "https://www.modelscope.cn/models/Qwen/Qwen-Image-2.1",
        }
    )

    assert cleaned["source_file"].endswith("t0_bom.json")
    assert "alice" not in cleaned["items"][0]["project_path"]
    assert cleaned["url"] == "https://www.modelscope.cn/models/Qwen/Qwen-Image-2.1"


def test_rendered_graph_html_does_not_embed_machine_paths(tmp_path: Path) -> None:
    output = tmp_path / "lineage.html"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "render_graph.py"),
            "--input",
            str(FULL_GRAPH),
            "--output",
            str(output),
            "--title",
            "portable test",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    html = output.read_text(encoding="utf-8")
    assert "C:\\Users\\" not in html
    assert "C:\\\\Users\\\\" not in html
    assert "/Users/" not in html
    assert "/home/" not in html
