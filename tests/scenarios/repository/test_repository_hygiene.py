from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ACTION_FILES = (
    REPO_ROOT / "action.yml",
    REPO_ROOT / ".github" / "workflows" / "license-watch.yml",
)


def test_checkout_paths_stay_inside_github_workspace() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "license-watch.yml").read_text(
        encoding="utf-8"
    )
    steps = re.findall(r"(?ms)^      - name:.*?(?=^      - |\Z)", workflow)
    checkout_steps = [step for step in steps if "uses: actions/checkout@v4" in step]

    assert checkout_steps
    for step in checkout_steps:
        path_lines = [
            line.strip()
            for line in step.splitlines()
            if line.strip().startswith("path:")
        ]
        for path_line in path_lines:
            checkout_path = path_line.removeprefix("path:").strip()
            assert "${{ runner.temp }}" not in checkout_path
            assert not checkout_path.startswith("/")
            assert not checkout_path.startswith("../")

    assert "path: .ci/open-source-ledger-tool" in workflow
    assert "Move tool checkout outside target workspace" in workflow


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


def test_workflow_scans_dedicated_demo_project() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "license-watch.yml").read_text(
        encoding="utf-8"
    )

    assert "WATCH_PROJECT_PATH" in workflow
    assert "example/qwen_image_controlled_project" in workflow
    assert '--project "$PROJECT_PATH"' in workflow
    assert '--project "$GITHUB_WORKSPACE"' not in workflow

    demo = REPO_ROOT / "example" / "qwen_image_controlled_project"
    assert (demo / "app.py").is_file()
    assert (demo / "config.json").is_file()


def test_snapshot_cache_prefix_is_stable_across_days() -> None:
    for path in ACTION_FILES:
        text = path.read_text(encoding="utf-8")
        assert "DATE_UTC" not in text, path
        assert "restore-keys" in text, path
        assert (
            "prefix=license-watch-${GITHUB_REPOSITORY_ID:-local}-${SAFE_REF}"
            in text
        ), path


def test_python_dependencies_are_exactly_pinned() -> None:
    raw = (REPO_ROOT / "requirements.txt").read_bytes()
    raw.decode("ascii")  # pip may read requirements.txt with the local ANSI codec.
    lines = [
        line.strip()
        for line in raw.decode("ascii").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert lines
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", line) for line in lines), lines
