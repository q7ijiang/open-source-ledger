"""演示夹具（is_fixture / display_only）语义与 demo 模式开关的回归测试。

组长评审的两个问题：
1. ``is_fixture`` / ``display_only`` 只在渲染端被检查，``bom_adapter`` 没有把字段
   带到资产对象上 —— 真实 BOM 输入时夹具过滤实际不生效。
2. 夹具到底算「验证资产」还是「演示夹具」——本仓库的结论是演示夹具，因此需要
   显式的 demo 开关：演示保留并参与差异，生产模式从 Delta / 传播 / 统计中排除。
"""

from __future__ import annotations

from pathlib import Path

import pytest

import bom_adapter
import main as main_module
import render_diff_operational

DATA = Path(__file__).resolve().parent.parent / "data" / "test_scenarios"
T0 = DATA / "project_t0_bom.json"
T1 = DATA / "project_t1_bom.json"


def _test_files_present() -> bool:
    return T0.exists() and T1.exists()


@pytest.mark.skipif(not _test_files_present(), reason="缺少 project_t0/t1 夹具")
class TestFixtureFlagPassThrough:
    """解析阶段必须把夹具标记带到资产对象上。"""

    def test_convert_bom_carries_is_fixture(self) -> None:
        bom = bom_adapter.load_json(T1)
        assets = bom_adapter.convert_bom(
            bom=bom,
            source_file=str(T1),
            snapshot_id="t1",
        )
        adapters = [a for a in assets if "Adapter-A" in str(a.get("name"))]
        assert adapters, "夹具里应当存在 Adapter-A 子节点"
        assert all(a.get("is_fixture") is True for a in adapters)

    def test_convert_bom_carries_expanded_from(self) -> None:
        bom = bom_adapter.load_json(T1)
        assets = bom_adapter.convert_bom(
            bom=bom,
            source_file=str(T1),
            snapshot_id="t1",
        )
        adapters = [a for a in assets if "Adapter-A" in str(a.get("name"))]
        assert all(a.get("expanded_from") for a in adapters)

    def test_aggregate_nodes_are_not_fixtures(self) -> None:
        """聚合域是平台级真实行，不能因为带 Adapters 字样被误当夹具。"""

        bom = bom_adapter.load_json(T1)
        assets = bom_adapter.convert_bom(
            bom=bom,
            source_file=str(T1),
            snapshot_id="t1",
        )
        aggregates = [a for a in assets if a.get("aggregate") is True]
        assert aggregates
        assert not any(a.get("is_fixture") for a in aggregates)


@pytest.mark.skipif(not _test_files_present(), reason="缺少 project_t0/t1 夹具")
class TestSnapshotFixtureMode:
    """生产模式默认排除夹具，demo 模式保留。"""

    def test_production_snapshot_excludes_fixtures(self) -> None:
        snapshot = main_module._build_snapshot(T1, "t1", include_fixtures=False)
        names = [str(a.get("name")) for a in snapshot["assets"]]
        assert snapshot["excluded_fixtures"] == 12
        assert not [n for n in names if "Adapter-A" in n]
        assert len(snapshot["assets"]) == 12
        assert len(snapshot["edges"]) == 9

    def test_demo_snapshot_keeps_fixtures(self) -> None:
        snapshot = main_module._build_snapshot(T1, "t1", include_fixtures=True)
        names = [str(a.get("name")) for a in snapshot["assets"]]
        assert snapshot["excluded_fixtures"] == 0
        assert [n for n in names if "Adapter-A" in n]
        assert len(snapshot["assets"]) == 24
        assert len(snapshot["edges"]) == 21

    def test_t0_has_no_fixtures_so_both_modes_match(self) -> None:
        prod = main_module._build_snapshot(T0, "t0", include_fixtures=False)
        demo = main_module._build_snapshot(T0, "t0", include_fixtures=True)
        assert prod["excluded_fixtures"] == 0
        assert len(prod["assets"]) == len(demo["assets"]) == 12


class TestOperationalFilter:
    """operational_snapshot 的开关语义。"""

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
        return {"source": "asset:real", "target": "asset:demo-fixture", "edge_type": "derived_from"}

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
        edge = {"source": "asset:real", "target": "asset:demo-fixture", "edge_type": "expanded_from"}
        _, edges = render_diff_operational.operational_snapshot(nodes, [edge], include_fixtures=True)
        assert edges == []


@pytest.mark.skipif(not _test_files_present(), reason="缺少 project_t0/t1 夹具")
def test_basic_report_can_exclude_fixtures() -> None:
    import report_basic

    _, prod_md = report_basic.generate(str(T1), include_fixtures=False)
    _, demo_md = report_basic.generate(str(T1), include_fixtures=True)
    assert "Adapter-A" not in prod_md
    assert "Adapter-A" in demo_md
