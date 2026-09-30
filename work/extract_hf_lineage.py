# -*- coding: utf-8 -*-
"""B 交付补充：从真实 HF 模型 BOM 提取血缘边并验证模块 8（血缘图构建）。

背景：
A 的 data/hf_models_bom/ 下 9 份真实 Hugging Face 模型 BOM（CycloneDX 1.7）中，
7 份带 pedigree.ancestors、4 份带 modelCard.modelParameters.datasets，
但仓库内尚无将其转换为接口约定血缘边格式的工具。本脚本补齐该输入链路，
证明模块 8 可消费 A 的真实数据建图。

用法：
    python work/extract_hf_lineage.py \
        --bom-dir data/hf_models_bom --output-dir out/hf_lineage

输出（均符合 docs/接口约定.md）：
    out/hf_lineage/assets.json   资产节点（model / dataset）
    out/hf_lineage/edges.json    血缘边（derived_from / trained_on，证据 A 级）
    out/hf_lineage/graph.json    模块 8 构建的血缘图（含 SCC 与统计）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_graph as bg

ASSET_TYPE_BY_PURL = {"model": "model", "dataset": "dataset"}


def purl_to_canonical(purl: str | None, fallback_type: str) -> str | None:
    """把 pkg:huggingface/... purl 转为接口约定的 canonical_id（asset_type:name）。

    例：pkg:huggingface/meta-llama/Llama-2-7b-chat-hf
        -> model:meta-llama/Llama-2-7b-chat-hf
        pkg:huggingface/datasets/wikipedia?repository_url=...
        -> dataset:wikipedia
    """
    if not purl:
        return None
    if not purl.startswith("pkg:huggingface/"):
        return None
    rest = purl[len("pkg:huggingface/"):]
    # 去掉 URL 查询参数（数据集 ref 常带 repository_url 等）
    name = rest.split("?", 1)[0].strip("/")
    if not name:
        return None
    if name.startswith("datasets/"):
        return f"dataset:{name[len('datasets/'):]}"
    return f"{fallback_type}:{name}"


def component_license(component: dict) -> str:
    """从 CycloneDX licenses 提取许可证名（多个以 ';' 连接）。

    HF BOM 的 license 对象可能用 id（SPDX，如 Apache-2.0）或 name
    （原始名，如 LLAMA2）标识，两者都取。
    """
    parts = []
    for entry in component.get("licenses", []) or []:
        license_info = entry.get("license", {}) if isinstance(entry, dict) else {}
        name = license_info.get("name") or license_info.get("id") or entry.get("name")
        if name:
            parts.append(str(name))
    return "; ".join(parts)


def extract(bom_path: Path) -> tuple[list[dict], list[dict]]:
    """从单个 BOM 提取资产节点与血缘边。"""
    data = json.loads(bom_path.read_text(encoding="utf-8"))
    snapshot_id = (
        data.get("serialNumber", "").removeprefix("urn:uuid:")
        or f"snapshot-{bom_path.stem}"
    )
    assets: list[dict] = []
    edges: list[dict] = []

    components = data.get("components", []) or []
    if not components:
        return assets, edges

    # 主模型 = 第一个组件（cdxgen 生成的 HF BOM 惯例）
    model = components[0]
    model_name = f"{model.get('group', '')}/{model.get('name', '')}".strip("/")
    model_canonical = f"model:{model_name}"
    assets.append({
        "canonical_id": model_canonical,
        "asset_type": "model",
        "name": model_name,
        "version": model.get("version"),
        "purls": [model.get("purl")] if model.get("purl") else [],
        "license": component_license(model),
        "evidence_chain": [],
        "snapshot_id": snapshot_id,
    })

    # derived_from：pedigree.ancestors（含嵌套展开）
    def ancestors_of(component: dict) -> list[dict]:
        out = []
        for anc in component.get("pedigree", {}).get("ancestors", []) or []:
            if not isinstance(anc, dict):
                continue
            out.append(anc)
            out.extend(ancestors_of(anc))
        return out

    for anc in ancestors_of(model):
        anc_canonical = purl_to_canonical(anc.get("purl") or anc.get("bom-ref"), "model")
        if not anc_canonical:
            continue
        edges.append({
            "source": model_canonical,
            "target": anc_canonical,
            "edge_type": "derived_from",
            "evidence_level": "A",
            "source_field": "pedigree.ancestors",
            "snapshot_id": snapshot_id,
        })
        assets.append({
            "canonical_id": anc_canonical,
            "asset_type": "model",
            "name": anc_canonical.split(":", 1)[1],
            "version": anc.get("version"),
            "purls": [anc.get("purl")] if anc.get("purl") else [],
            "license": "",
            "evidence_chain": [],
            "snapshot_id": snapshot_id,
        })

    # trained_on：modelCard.modelParameters.datasets
    datasets = (
        model.get("modelCard", {})
        .get("modelParameters", {})
        .get("datasets", []) or []
    )
    for entry in datasets:
        if not isinstance(entry, dict):
            entry = {"ref": None, "name": str(entry)}
        ref = entry.get("ref") or ""
        ds_canonical = purl_to_canonical(str(ref), "dataset")
        if ds_canonical is None:
            # 数据集 ref 可能不是 huggingface purl：退化为 name
            ds_name = entry.get("name")
            if not ds_name:
                continue
            ds_canonical = f"dataset:{ds_name}"
        edges.append({
            "source": model_canonical,
            "target": ds_canonical,
            "edge_type": "trained_on",
            "evidence_level": "A",
            "source_field": "modelCard.modelParameters.datasets",
            "snapshot_id": snapshot_id,
        })
        assets.append({
            "canonical_id": ds_canonical,
            "asset_type": "dataset",
            "name": ds_canonical.split(":", 1)[1],
            "version": None,
            "purls": [ref] if ref else [],
            "license": "",
            "evidence_chain": [],
            "snapshot_id": snapshot_id,
        })

    return assets, edges


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="从真实 HF BOM 提取血缘边并建图")
    parser.add_argument("--bom-dir", default="data/hf_models_bom", help="BOM 目录")
    parser.add_argument("--output-dir", default="out/hf_lineage", help="输出目录")
    args = parser.parse_args(argv)

    bom_dir = Path(args.bom_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_assets: dict[str, dict] = {}
    all_edges: list[dict] = []
    for bom_path in sorted(bom_dir.glob("*.json")):
        assets, edges = extract(bom_path)
        for asset in assets:
            all_assets.setdefault(asset["canonical_id"], asset)
        all_edges.extend(edges)

    assets = list(all_assets.values())
    assets_path = output_dir / "assets.json"
    edges_path = output_dir / "edges.json"
    assets_path.write_text(
        json.dumps(assets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    edges_path.write_text(
        json.dumps(all_edges, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    graph = bg.build_graph(assets, all_edges)
    canonical_to_scc, compressed = bg.compress_scc(graph)
    graph_dict = bg.graph_to_dict(graph, canonical_to_scc, compressed)
    graph_path = output_dir / "graph.json"
    graph_path.write_text(
        json.dumps(graph_dict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    stats = graph_dict
    print(f"真实 BOM 数：{len(list(bom_dir.glob('*.json')))}")
    print(f"资产节点：{stats['node_count']}（含缺失祖先自动补建）")
    print(f"血缘边：{stats['edge_count']}（derived_from + trained_on）")
    print(f"SCC 分量：{stats['scc_count']}")
    by_type: dict[str, int] = {}
    for edge in all_edges:
        by_type[edge["edge_type"]] = by_type.get(edge["edge_type"], 0) + 1
    print(f"边类型分布：{by_type}")
    print(f"已写入 {assets_path} / {edges_path} / {graph_path}")


if __name__ == "__main__":
    main()
