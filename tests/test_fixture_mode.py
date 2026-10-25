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


REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not _test_files_present(), reason="缺少 project_t0/t1 夹具")
class TestAggregateFixtureStats:
    """P1：生产模式不能残留夹具贡献的聚合域统计。"""

    def _aggregates(self, snapshot: dict) -> list[dict]:
        return [a for a in snapshot["assets"] if main_module._is_aggregate_asset(a)]

    def test_production_snapshot_resets_aggregate_stats(self) -> None:
        snapshot = main_module._build_snapshot(T1, "t1", include_fixtures=False)
        aggregates = self._aggregates(snapshot)
        assert len(aggregates) == 9
        for aggregate in aggregates:
            assert aggregate.get("expanded_count") == 0, aggregate.get("name")
            assert aggregate.get("known_risk_counts") == {
                "red": 0,
                "yellow": 0,
                "gray": 0,
            }, aggregate.get("name")
            # 下游总量来自平台，是真实数据，必须保留
            assert aggregate.get("remaining_count") == aggregate.get("count")

    def test_demo_snapshot_keeps_aggregate_stats(self) -> None:
        snapshot = main_module._build_snapshot(T1, "t1", include_fixtures=True)
        target = [
            a
            for a in self._aggregates(snapshot)
            if "Qwen3-8B" in str(a.get("name")) and "适配" in str(a.get("name"))
        ]
        assert target, "夹具里应当有 Qwen3-8B 适配聚合域"
        aggregate = target[0]
        assert aggregate.get("expanded_count") == 3
        assert aggregate.get("known_risk_counts") == {"red": 1, "yellow": 1, "gray": 1}
        assert aggregate.get("remaining_count") == 20 - 3

    def test_real_children_are_recounted_not_zeroed(self) -> None:
        """夹具移除后若还剩真实子节点，统计要按真实子节点重算。"""

        assets = [
            {
                "id": "agg",
                "name": "Qwen/Qwen3-8B · 适配 (Total: 20)",
                "aggregate": True,
                "coverage_status": "AGGREGATE_ONLY",
                "count": 20,
                "expanded_count": 3,
                "remaining_count": 17,
                "known_risk_counts": {"red": 1, "yellow": 1, "gray": 1},
            },
            {"id": "real-child", "name": "真实下游", "decision": "RISK_POTENTIAL"},
            {"id": "fx-child", "name": "构造夹具", "is_fixture": True, "decision": "RISK_CONFIRMED"},
        ]
        edges = [
            {"source": "agg", "target": "real-child", "edge_type": "expanded_from"},
            {"source": "agg", "target": "fx-child", "edge_type": "expanded_from"},
        ]
        kept_assets, kept_edges, removed = main_module.exclude_fixture_assets(assets, edges)
        assert removed == 1
        assert [e["target"] for e in kept_edges] == ["real-child"]
        aggregate = kept_assets[0]
        assert aggregate["expanded_count"] == 1
        assert aggregate["remaining_count"] == 19
        assert aggregate["known_risk_counts"] == {"red": 0, "yellow": 1, "gray": 0}

    def test_aggregate_without_expansion_edges_is_untouched(self) -> None:
        """计数直接来自 BOM、没有展开边的聚合域，不因本次过滤被清零。"""

        assets = [
            {
                "id": "agg-only-count",
                "name": "Qwen/Qwen2.5-7B-Instruct · 微调 (Total: 1744)",
                "aggregate": True,
                "count": 1744,
                "expanded_count": 0,
                "remaining_count": 1744,
                "known_risk_counts": {"red": 0, "yellow": 0, "gray": 0},
            },
            {"id": "fx", "name": "构造夹具", "is_fixture": True},
        ]
        kept_assets, _, removed = main_module.exclude_fixture_assets(assets, [])
        assert removed == 1
        assert kept_assets[0]["known_risk_counts"] == {"red": 0, "yellow": 0, "gray": 0}
        assert kept_assets[0]["count"] == 1744


@pytest.mark.skipif(not _test_files_present(), reason="缺少 project_t0/t1 夹具")
class TestProductionHtmlEndToEnd:
    """P1 端到端：生产 HTML 里不能再出现夹具统计，demo 里必须还在。"""

    def _render(self, tmp_path: Path, include_fixtures: bool) -> str:
        import subprocess
        import sys

        output = tmp_path / ("demo.html" if include_fixtures else "prod.html")
        command = [
            sys.executable,
            str(REPO_ROOT / "render_diff.py"),
            "--before",
            str(T0),
            "--after",
            str(T1),
            "--output",
            str(output),
        ]
        if include_fixtures:
            command.append("--include-fixtures")
        subprocess.run(command, cwd=str(REPO_ROOT), check=True, capture_output=True)
        return output.read_text(encoding="utf-8")

    def test_production_html_has_no_fixture_stats(self, tmp_path: Path) -> None:
        html = self._render(tmp_path, include_fixtures=False)
        assert "Adapter-A" not in html, "生产 HTML 不应出现夹具节点"
        assert '"expanded_count": 3' not in html, "聚合域不应残留「展开 3 个」"
        assert '"red": 1' not in html, "聚合域不应残留「红 1」"
        assert '"known_risk_counts": {"red": 1' not in html

    def test_demo_html_keeps_fixture_stats(self, tmp_path: Path) -> None:
        html = self._render(tmp_path, include_fixtures=True)
        assert "Adapter-A" in html
        assert '"expanded_count": 3' in html
        assert '"red": 1' in html
        assert '"is_fixture": true' in html


class TestFixtureBadgeUsesExplicitFlag:
    """P2：来源标注只看显式字段，不再按名称正则猜。"""

    def test_no_name_based_fixture_regex(self) -> None:
        for name in ("render_diff.py", "render_graph.py"):
            source = (REPO_ROOT / name).read_text(encoding="utf-8")
            assert "/Adapter-[ABC]/" not in source, f"{name} 仍按名称判夹具"
            assert "isFixtureNode(" in source
            assert "n.is_fixture === true || n.display_only === true" in source
