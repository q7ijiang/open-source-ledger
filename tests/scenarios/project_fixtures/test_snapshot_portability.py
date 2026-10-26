from __future__ import annotations

from pathlib import Path


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "projects"
    / "real_modelscope"
)
SNAPSHOT_ROOT = FIXTURE_ROOT / "snapshots"


def test_committed_snapshot_text_has_no_machine_specific_paths() -> None:
    forbidden = ("C:\\Users\\", "/Users/", "/home/")

    for path in SNAPSHOT_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert not any(prefix in text for prefix in forbidden), path
