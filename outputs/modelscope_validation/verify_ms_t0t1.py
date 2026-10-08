# -*- coding: utf-8 -*-
"""MS 版 t0/t1 数据有效性验证（C 模块）：绕过缺失的 extract_modelscope_lineage，
直接验证 bom_adapter → 血缘边构建 → delta_engine → propagation_engine 全链路。
不动 main.py / 引擎代码，仅验证 C 造的数据能驱动引擎正确判定。"""
import json
import sys
import traceback
from pathlib import Path

# 输出写日志文件，避免 Windows PowerShell 吞 stdout
LOG_PATH = Path(__file__).resolve().with_name("verify_ms_t0t1.log")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    import bom_adapter
    import build_graph
    import delta_engine
    import propagation_engine
    import license_db
except Exception:
    LOG_PATH.write_text(traceback.format_exc(), encoding="utf-8")
    raise

T0 = ROOT / "data" / "test_scenarios" / "ms_t0_bom.json"
T1 = ROOT / "data" / "test_scenarios" / "ms_t1_bom.json"


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
        # 边方向：source=下游衍生模型，target=上游祖先（canonical_id 版本化，接口约定 v0.3）
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
    return assets, edges, bom


def main():
    _log = open(LOG_PATH, "w", encoding="utf-8")
    _stdout, _stderr = sys.stdout, sys.stderr
    sys.stdout = _log
    sys.stderr = _log
    try:
        _run()
    except Exception:
        _log.write("\n" + traceback.format_exc())
    finally:
        sys.stdout, sys.stderr = _stdout, _stderr
        _log.close()
    print("日志已写入：%s" % LOG_PATH)
    return 0


def _run():
    assets0, edges0, bom0 = load_snapshot(T0, "ms-t0")
    assets1, edges1, bom1 = load_snapshot(T1, "ms-t1")

    print("=== 一、资产解析（qwen-research 非标协议容错） ===")
    for a in assets0:
        print("  %s | lic=%s | 未识别项=%s" % (
            a.get("canonical_id"), a.get("license"),
            delta_engine.best_evidence(a) if a.get("license") == "qwen-research" else "-"))
    # 评估 qwen-research
    expr = license_db.evaluate_expression("qwen-research")
    print("  license_db 对 qwen-research 评估：max_risk=%s worst=%s unknown=%s" % (
        expr.get("max_risk_level"), expr.get("worst_category"),
        list(expr.get("unknown_items", []))))

    print("\n=== 二、血缘边 ===")
    print("  t0 边数：%d；t1 边数：%d" % (len(edges0), len(edges1)))
    for e in edges0:
        print("  %s --%s--> %s (证据%s)" % (e["source"], e["edge_type"], e["target"], e["evidence_level"]))

    print("\n=== 三、delta_engine.detect_delta ===")
    events = delta_engine.detect_delta(assets0, assets1, edges0, edges1)
    print("  变更事件数：%d" % len(events))
    for ev in events:
        print("  [%s] %s %s -> %s (decision=%s, seed=%s, reason=%s)" % (
            ev.get("event_type"), ev.get("entity_key") or ev.get("asset_id"),
            ev.get("before"), ev.get("after"), ev.get("decision"),
            ev.get("seed"), ev.get("reason_code") or ev.get("reason")))

    print("\n=== 四、propagation_engine.propagate ===")
    g0 = build_graph.build_graph(assets0, edges0)
    g1 = build_graph.build_graph(assets1, edges1)
    prop = propagation_engine.propagate(events, g0, g1)
    certs = prop["path_certificates"]
    print("  传播后事件数：%d" % len(prop["events"]))
    print("  路径证书数：%d  (要求 > 0)" % len(certs))
    for c in certs[:10]:
        print("   证书: %s | 判定=%s | 种子=%s" % (
            c.get("path_fingerprint") or c.get("fingerprint"), c.get("decision"),
            c.get("seed") or c.get("source")))

    # 判定分布
    from collections import Counter
    dist = Counter(e.get("decision") for e in prop["events"])
    print("  三级判定分布：%s" % dict(dist))

    ok = len(certs) > 0
    print("\n验证结论：%s (path_certificates=%d)" % ("通过" if ok else "不通过", len(certs)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
