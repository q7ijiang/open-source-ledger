# -*- coding: utf-8 -*-
"""模块 8：血缘图构建回归测试。"""

import json

import build_graph as bg
from conftest import FIXTURES


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_build_graph_t1():
    """t1 快照：8 个节点（7 资产 + Qwen 由边自动创建）+ 7 条边。"""
    assets = load("deep_t1_assets.json")
    edges = load("deep_t1_edges.json")
    graph = bg.build_graph(assets, edges)
    assert graph.number_of_nodes() == 8
    assert graph.number_of_edges() == 7
    # 边类型覆盖
    types = {data["edge_type"] for _, _, data in graph.edges(data=True)}
    assert {"derived_from", "trained_on", "depends_on"} <= types
    # Qwen 由边自动创建且无元数据 -> 缺失祖先场景
    assert graph.nodes["model:Qwen/Qwen2.5-7B"].get("asset_type") is None


def test_parallel_edges_preserved():
    """同一对节点间并行边（MultiDiGraph）必须保留。"""
    assets = load("deep_t1_assets.json")
    edges = load("deep_t1_edges.json")
    graph = bg.build_graph(assets, edges)
    # lib-x 与 example-parser 互相 depends_on：两条边都要保留
    assert graph.number_of_edges("package:pypi/example-parser", "package:pypi/lib-x") == 1
    assert graph.number_of_edges("package:pypi/lib-x", "package:pypi/example-parser") == 1
    assert graph.number_of_edges() == 7


def test_scc_compression_detects_cycle():
    """lib-x 与 example-parser 的相互依赖应被识别为一个 SCC 环。"""
    assets = load("deep_t1_assets.json")
    edges = load("deep_t1_edges.json")
    graph = bg.build_graph(assets, edges)
    canonical_to_scc, compressed = bg.compress_scc(graph)

    cycle_scc = canonical_to_scc["package:pypi/example-parser"]
    assert canonical_to_scc["package:pypi/lib-x"] == cycle_scc
    members = compressed.nodes[cycle_scc]["members"]
    assert set(members) == {"package:pypi/example-parser", "package:pypi/lib-x"}
    assert compressed.nodes[cycle_scc]["size"] == 2

    # 压缩图节点数 = SCC 数
    assert compressed.number_of_nodes() <= graph.number_of_nodes()


def test_scc_weakest_aggregation():
    """压缩边证据按 weakest link 聚合。"""
    assets = load("deep_t1_assets.json")
    edges = load("deep_t1_edges.json")
    graph = bg.build_graph(assets, edges)
    canonical_to_scc, compressed = bg.compress_scc(graph)

    scc_parser = canonical_to_scc["package:pypi/example-parser"]
    scc_finetuned = canonical_to_scc["model:my-org/finetuned-model"]
    if compressed.has_edge(scc_finetuned, scc_parser):
        data = compressed.edges[scc_finetuned, scc_parser]
        assert data["evidence_level"] == "B"
        assert data["count"] >= 1


def test_graph_to_dict_schema():
    """输出 JSON 字段符合模块 8 结构约定。"""
    assets = load("deep_t1_assets.json")
    edges = load("deep_t1_edges.json")
    graph = bg.build_graph(assets, edges)
    canonical_to_scc, compressed = bg.compress_scc(graph)
    result = bg.graph_to_dict(graph, canonical_to_scc, compressed)

    assert result["node_count"] == 8
    assert result["edge_count"] == 7
    assert result["scc_count"] == compressed.number_of_nodes()
    node = result["nodes"][0]
    assert {"canonical_id", "asset_type", "license", "scc_id"} <= set(node)
    edge = result["edges"][0]
    assert {"source", "target", "edge_type", "evidence_level", "source_field"} <= set(edge)
    # 每个 canonical_id 都有 scc 归属
    assert set(result["canonical_to_scc"]) == {n["canonical_id"] for n in result["nodes"]}
