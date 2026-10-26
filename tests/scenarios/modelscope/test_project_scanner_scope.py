from __future__ import annotations

from pathlib import Path

import main


def test_project_scanner_excludes_documentation_only_models(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        'MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"\n',
        encoding="utf-8",
    )
    (tmp_path / "config.json").write_text(
        '{"model_id": "LLM-Research/gemma-3-4b-it"}\n',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "Upstream chain includes Qwen/Qwen2.5-7B and Qwen/Qwen2.5-7B-Instruct.\n",
        encoding="utf-8",
    )

    models = main._scan_project_models(tmp_path)
    names = {item["model"] for item in models}

    assert names == {
        "Qwen/Qwen2.5-7B-Instruct-AWQ",
        "LLM-Research/gemma-3-4b-it",
    }
    assert all(item["direct_usage"] is True for item in models)


def test_project_scanner_keeps_source_reference_for_direct_model(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text(
        'MODEL = "BAAI/bge-m3"\n',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "The service uses BAAI/bge-m3 for embeddings.\n",
        encoding="utf-8",
    )

    models = main._scan_project_models(tmp_path)
    model = next(item for item in models if item["model"] == "BAAI/bge-m3")

    assert set(model["sources"]) == {"service.py", "README.md"}
