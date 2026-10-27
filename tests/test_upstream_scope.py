"""当前作品边界：项目直接模型与其上游闭包。"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE_ROOT = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "projects"
    / "qwen_image_license_tightening"
    / "upstream"
)
T0 = FIXTURE_ROOT / "t0_bom.json"
T1 = FIXTURE_ROOT / "t1_bom.json"
SCENARIO = FIXTURE_ROOT / "scenario.json"

DIRECT_MODELS = {
    "unsloth/Qwen-Image-2.1-Turbo-FP8",
    "OpenGVLab/InternVL3-8B-Instruct",
}


def _bom(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _properties(component: dict) -> dict[str, str]:
    return {
        item["name"]: item["value"]
        for item in component.get("properties", [])
        if "name" in item and "value" in item
    }


def test_current_fixture_contains_only_concrete_upstream_models() -> None:
    for path in (T0, T1):
        bom = _bom(path)
        names = {component.get("name") for component in bom["components"]}
        assert DIRECT_MODELS <= names
        assert not [
            name
            for name in names
            if name and (":son:" in name or " · " in name or "Adapter-" in name)
        ]

        for component in bom["components"]:
            props = _properties(component)
            assert props.get("open-source-ledger:aggregate") is None
            assert props.get("open-source-ledger:coverage_status") != "AGGREGATE_ONLY"
            assert props.get("open-source-ledger:expanded_from") is None
            for ancestor in component.get("pedigree", {}).get("ancestors", []):
                assert ancestor.get("source_field") != "lineage.SonModels"


def test_current_fixture_has_expected_upstream_closure() -> None:
    bom = _bom(T1)
    edges = {
        (
            component["name"],
            ancestor.get("ref") or ancestor.get("purl"),
        )
        for component in bom["components"]
        for ancestor in component.get("pedigree", {}).get("ancestors", [])
    }
    assert len(edges) == 9
    assert (
        "unsloth/Qwen-Image-2.1-Turbo-FP8",
        "model:modelscope/Qwen/Qwen-Image-2.1-Turbo@master",
    ) in edges
    assert (
        "Qwen/Qwen-Image-2.1-Turbo",
        "model:modelscope/Qwen/Qwen-Image-2.1@master",
    ) in edges
    assert (
        "OpenGVLab/InternViT-300M-448px-V2_5",
        "model:modelscope/OpenGVLab/InternViT-300M-448px@master",
    ) in edges


def test_current_fixture_declares_historical_reconstruction() -> None:
    scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
    assert scenario["fixture_project"] is True
    assert scenario["historical_reconstruction"] is True
    assert scenario["simulation"] is True
    assert scenario["direct_models"] == [
        "unsloth/Qwen-Image-2.1-Turbo-FP8",
        "OpenGVLab/InternVL3-8B-Instruct",
    ]
    assert scenario["historical_boundary"] == (
        "README metadata only; no retained Apache-2.0 LICENSE file is claimed."
    )
