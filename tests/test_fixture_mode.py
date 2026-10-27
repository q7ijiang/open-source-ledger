"""显式演示夹具标记与生产过滤语义的回归测试。"""

from __future__ import annotations

import json
from pathlib import Path

import bom_adapter
import main as main_module
import render_diff_operational

REPO_ROOT = Path(__file__).resolve().parent.parent


def _fixture_bom(tmp_path: Path) -> Path:
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "version": 1,
        "components": [
            {
                "bom-ref": "model:modelscope/acme/base@v1",
                "type": "machine-learning-model",
                "name": "acme/base",
                "version": "v1",
                "purl": "pkg:modelscope/acme/base@v1",
                "licenses": [{"license": {"id": "Apache-2.0"}, "evidence_level": "A"}],
            },
            {
                "bom-ref": "model:modelscope/acme/fixture@v1",
                "type": "machine-learning-model",
                "name": "acme/fixture",
                "version": "v1",
                "purl": "pkg:modelscope/acme/fixture@v1",
                "licenses": [{"license": {"id": "MIT"}, "evidence_level": "A"}],
                "properties": [
                    {"name": "open-source-ledger:is_fixture", "value": "true"},
                    {
                        "name": "open-source-ledger:expanded_from",
                        "value": "model:modelscope/acme/base@v1",
                    },
                ],
            },
        ],
    }
    path = tmp_path / "fixture-bom.json"
    path.write_text(json.dumps(bom, ensure_ascii=False), encoding="utf-8")
    return path


def test_convert_bom_carries_explicit_fixture_fields(tmp_path):
    path = _fixture_bom(tmp_path)
    assets = bom_adapter.convert_bom(
        bom=bom_adapter.load_json(path),
        source_file=str(path),
        snapshot_id="t1",
    )
    fixture = next(a for a in assets if a.get("name") == "acme/fixture")
    assert fixture.get("is_fixture") is True
    assert fixture.get("expanded_from") == "model:modelscope/acme/base@v1"


def test_snapshot_excludes_or_keeps_explicit_fixture(tmp_path):
    path = _fixture_bom(tmp_path)
    production = main_module._build_snapshot(path, "t1", include_fixtures=False)
    demo = main_module._build_snapshot(path, "t1", include_fixtures=True)

    assert production["excluded_fixtures"] == 1
    assert [a["name"] for a in production["assets"]] == ["acme/base"]
    assert demo["excluded_fixtures"] == 0
    assert {a["name"] for a in demo["assets"]} == {"acme/base", "acme/fixture"}


class TestOperationalFilter:
    """operational_snapshot 的显式开关语义。"""

    def _flagged_node(self) -> dict:
        return {
            "id": "asset:demo-fixture",
            "name": "demo fixture",
            "license": "MIT",
            "is_fixture": True,
        }

    def _real_node(self) -> dict:
        return {"id": "asset:real", "name": "real", "license": "MIT"}

    def _lineage_edge(self) -> dict:
        return {
            "source": "asset:real",
            "target": "asset:demo-fixture",
            "edge_type": "derived_from",
        }

    def test_flagged_node_without_lineage_is_dropped_by_default(self) -> None:
        nodes = [self._real_node(), self._flagged_node()]
        kept, _ = render_diff_operational.operational_snapshot(nodes, [])
        assert [n["id"] for n in kept] == ["asset:real"]

    def test_flagged_node_is_kept_in_demo_mode(self) -> None:
        nodes = [self._real_node(), self._flagged_node()]
        kept, _ = render_diff_operational.operational_snapshot(
            nodes, [], include_fixtures=True
        )
        assert {n["id"] for n in kept} == {"asset:real", "asset:demo-fixture"}

    def test_flagged_node_with_lineage_survives_default_mode(self) -> None:
        """带真实血缘的节点即使被标记也保留，否则血缘边会断。"""
        nodes = [self._real_node(), self._flagged_node()]
        kept, edges = render_diff_operational.operational_snapshot(
            nodes, [self._lineage_edge()]
        )
        assert {n["id"] for n in kept} == {"asset:real", "asset:demo-fixture"}
        assert edges == [self._lineage_edge()]

    def test_expanded_from_edge_is_always_filtered(self) -> None:
        nodes = [self._real_node(), self._flagged_node()]
        edge = {
            "source": "asset:real",
            "target": "asset:demo-fixture",
            "edge_type": "expanded_from",
        }
        _, edges = render_diff_operational.operational_snapshot(
            nodes, [edge], include_fixtures=True
        )
        assert edges == []


def test_fixture_badge_uses_explicit_flag() -> None:
    for name in ("render_diff.py", "render_graph.py"):
        source = (REPO_ROOT / name).read_text(encoding="utf-8")
        assert "/Adapter-[ABC]/" not in source, f"{name} 仍按名称判夹具"
        assert "isFixtureNode(" in source
        assert "n.is_fixture === true || n.display_only === true" in source
