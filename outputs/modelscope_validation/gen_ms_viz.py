# -*- coding: utf-8 -*-
"""MS 版 t0/t1 → 可视化数据（C 模块）：产出 ms_viz/graph.json + events.json + certificates.json。
基于 bom_adapter + build_graph + delta_engine + propagation_engine，输出供 ECharts HTML 渲染。"""
import json
import sys
import traceback
from pathlib import Path

LOG_PATH = Path(__file__).resolve().with_name("gen_ms_viz.log")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    import bom_adapter
    import build_graph
    import delta_engine
    import propagation_engine
except Exception:
    LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
    raise

T0 = ROOT / "data" / "test_scenarios" / "ms_t0_bom.json"
T1 = ROOT / "data" / "test_scenarios" / "ms_t1_bom.json"
OUT = ROOT / "outputs" / "modelscope_validation" / "ms_viz"


def load_snapshot(path: Path, sid: str):
    bom = bom_adapter.load_json(path)
    assets = bom_adapter.convert_bom(bom, source_file=str(path), snapshot_id=sid)
    purl2cid = {}
    for a in assets:
        for p in (a.get("purls") or []):
            purl2cid[str(p)] = a.get("canonical_id")
    edges = []
    for comp in bom.get("components", []):
        comp_purls = bom_adapter.extract_purls(comp)
        src = next((purl2cid[p] for p in comp_purls if p in purl2cid), None)
        if not src:
            continue
        for anc in (comp.get("pedigree", {}) or {}).get("ancestors", []):
            apurl = anc.get("purl")
            if not apurl:
                continue
            target = purl2cid.get(apurl)
            if not target:
                ident = bom_adapter.parse_purl_identity(apurl)
                if ident is None:
                    continue
                target = bom_adapter.build_asset_identifiers(
                    "model", ident.name, ident.version, [apurl]
                )[1]
            edges.append({
                "source": src,
                "target": target,
                "edge_type": "derived_from",
                "evidence_level": anc.get("evidence_level", "B"),
                "source_field": "pedigree.ancestors",
                "snapshot_id": sid,
            })
    # 数据集训练边：modelCard.modelParameters.datasets -> trained_on（t1 快照）
    if sid == "ms-t1":
        for comp in bom.get("components", []):
            comp_purls = bom_adapter.extract_purls(comp)
            src = next((purl2cid[p] for p in comp_purls if p in purl2cid), None)
            if not src:
                continue
            datasets = ((comp.get("modelCard") or {}).get("modelParameters") or {}).get("datasets") or []
            for ds in datasets:
                dpurl = ds.get("ref") or ds.get("purl")
                if not dpurl:
                    continue
                target = purl2cid.get(dpurl)
                if not target:
                    ident = bom_adapter.parse_purl_identity(dpurl)
                    if ident is None:
                        continue
                    target = bom_adapter.build_asset_identifiers(
                        "dataset", ident.name, ident.version, [dpurl]
                    )[1]
                edges.append({
                    "source": src,
                    "target": target,
                    "edge_type": "trained_on",
                    "evidence_level": "B",
                    "source_field": "modelCard.modelParameters.datasets",
                    "snapshot_id": sid,
                })
    return assets, edges


def main():
    log = open(LOG_PATH, "w", encoding="utf-8")
    sys.stdout, sys.stderr = log, log
    try:
        assets0, edges0 = load_snapshot(T0, "ms-t0")
        assets1, edges1 = load_snapshot(T1, "ms-t1")

        g0 = build_graph.build_graph(assets0, edges0)
        g1 = build_graph.build_graph(assets1, edges1)
        c0, comp0 = build_graph.compress_scc(g0)
        c1, comp1 = build_graph.compress_scc(g1)
        g0_dict = build_graph.graph_to_dict(g0, c0, comp0)
        g1_dict = build_graph.graph_to_dict(g1, c1, comp1)
        events = delta_engine.detect_delta(assets0, assets1, edges0, edges1)
        prop = propagation_engine.propagate(events, g0, g1)
        certs = prop["path_certificates"]

        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "graph_t1.json").write_text(
            json.dumps(g1_dict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (OUT / "events.json").write_text(
            json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (OUT / "certificates.json").write_text(
            json.dumps(certs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # 给 HTML 用的精简数据（节点着色依据 + 证据 + 事件 + 路径）
        nodes = []
        for n in g1_dict["nodes"]:
            nodes.append({
                "id": n["canonical_id"],
                "name": n.get("name"),
                "version": n.get("version"),
                "type": n.get("asset_type"),
                "license": n.get("license"),
                "evidence": n.get("evidence_chain", []),
                "merge_status": n.get("merge_status"),
                "reason_code": n.get("reason_code"),
            })
        edges = []
        for e in g1_dict.get("edges", []):
            edges.append({
                "source": e["source"], "target": e["target"],
                "edge_type": e.get("edge_type"), "evidence_level": e.get("evidence_level"),
            })
        viz = {"nodes": nodes, "edges": edges, "events": events, "certificates": certs}
        (OUT / "viz_data.json").write_text(
            json.dumps(viz, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        print("=== MS 可视化数据生成完成 ===")
        print("t1 图：%d 节点 / %d 边" % (g1_dict["node_count"], g1_dict["edge_count"]))
        print("变更事件：%d；路径证书：%d" % (len(events), len(certs)))
        print("输出目录：%s" % OUT)
    finally:
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__
        log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
