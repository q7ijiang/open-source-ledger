from __future__ import annotations

from pathlib import Path


FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures"


def test_committed_fixture_text_has_no_machine_specific_paths() -> None:
    # JSON/HTML 中的反斜杠会被二次转义，必须同时检查单层和双层形式。
    forbidden = (
        "C:\\Users\\",
        "C:\\\\Users\\\\",
        "C:/Users/",
        "/Users/",
        "/home/",
    )

    for path in FIXTURE_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert not any(prefix in text for prefix in forbidden), path
