from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ACTION_FILES = (
    REPO_ROOT / "action.yml",
    REPO_ROOT / ".github" / "workflows" / "license-watch.yml",
)


def test_actions_use_explicit_outputs_and_runner_temp() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in ACTION_FILES)

    assert "find outputs" not in combined
    assert ".license-watch-cache" not in combined
    assert "--artifacts-dir" in combined
    assert "--cache-dir" in combined
    assert "--bom-output" in combined
    assert "--graph-output" in combined
    assert "runner.temp" in combined


def test_no_fixed_local_ai_endpoint_is_shipped() -> None:
    candidates = (
        REPO_ROOT / ".env.example",
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "AI能力说明.md",
        *sorted((REPO_ROOT / "ai_layer").glob("*.py")),
        *ACTION_FILES,
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in candidates)

    assert "127.0.0.1" not in combined
    assert "http://127.0.0.1" not in combined.lower()
    assert "http://localhost" not in combined.lower()


def test_runtime_files_do_not_embed_machine_specific_home_paths() -> None:
    candidates = [
        REPO_ROOT / "action.yml",
        REPO_ROOT / ".github" / "workflows" / "license-watch.yml",
        REPO_ROOT / "main.py",
        REPO_ROOT / "modelscope_lineage.py",
        REPO_ROOT / "ai_layer" / "config.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in candidates)

    assert "C:\\Users\\" not in combined
    assert "/Users/" not in combined
    assert "/home/" not in combined
