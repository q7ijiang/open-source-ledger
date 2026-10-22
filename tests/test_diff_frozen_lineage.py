# -*- coding: utf-8 -*-
"""--diff 时间化对比语义回归测试。

固化血缘必须只来自 BOM，不允许回退到在线 API，否则 Action 里存的
"上周 t0" 会被今天的最新血缘替换，时间对比失去意义。
"""

import json

import main as m
from conftest import REPO_ROOT

MS_T0 = REPO_ROOT / "data" / "test_scenarios" / "ms_t0_bom.json"
MS_T1 = REPO_ROOT / "data" / "test_scenarios" / "ms_t1_bom.json"


def test_snapshot_uses_frozen_bom_edges():
    """ms_t0_bom 的 2 条 pedigree.ancestors 必须原样成为快照的 derived_from 边。"""
    snapshot = m._build_snapshot(MS_T0, "t0")
    edges = snapshot["edges"]
    assert len(edges) == 2
    assert all(e["edge_type"] == "derived_from" for e in edges)
    assert all(e["source_field"] == "pedigree.ancestors" for e in edges)
    assert all(e["snapshot_id"] == "t0" for e in edges)


def test_snapshot_does_not_pull_online_lineage():
    """在线提取器会产出 :son:/:parent: 聚合节点；快照里必须一个都没有。"""
    snapshot = m._build_snapshot(MS_T0, "t0")
    canonical_ids = [a.get("canonical_id") or "" for a in snapshot["assets"]]
    assert not [cid for cid in canonical_ids if ":son:" in cid or ":parent:" in cid]
    # 节点数应与 BOM 组件数一致，不因在线拉取而膨胀
    bom = json.loads(MS_T0.read_text(encoding="utf-8"))
    assert len(snapshot["assets"]) == len(bom["components"])


def test_snapshot_edges_are_deterministic():
    """同一份 BOM 两次快照，边必须完全一致（判定结果可复现）。"""
    first = m._build_snapshot(MS_T0, "t0")
    second = m._build_snapshot(MS_T0, "t0")
    assert first["edges"] == second["edges"]


def test_missing_ancestor_becomes_placeholder_node():
    """只在 pedigree.ancestors 出现、BOM 未单列的祖先要补占位节点并保留该边。"""
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "components": [
            {
                "bom-ref": "cdxgen:ai:model/pkg:modelscope/acme/child@v1",
                "type": "machine-learning-model",
                "name": "child",
                "version": "v1",
                "purl": "pkg:modelscope/acme/child@v1",
                "pedigree": {
                    "ancestors": [
                        {"purl": "pkg:modelscope/acme/absent-parent@v2", "evidence_level": "A"}
                    ]
                },
            }
        ],
    }
    path = REPO_ROOT / "outputs" / "_pytest_missing_ancestor_bom.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bom, ensure_ascii=False), encoding="utf-8")
    try:
        snapshot = m._build_snapshot(path, "t0")
        assert len(snapshot["edges"]) == 1
        edge = snapshot["edges"][0]
        assert edge["target"] == "model:modelscope/acme/absent-parent@v2"
        assert edge["evidence_level"] == "A"
        placeholder = [
            a for a in snapshot["assets"] if a.get("canonical_id") == edge["target"]
        ]
        assert len(placeholder) == 1
        assert placeholder[0]["reason_code"] == "MISSING_ANCESTOR"
    finally:
        path.unlink(missing_ok=True)


def test_t0_and_t1_share_same_graph_shape():
    """t0/t1 血缘结构一致时才谈得上"只有许可证变了"。"""
    before = m._build_snapshot(MS_T0, "t0")
    after = m._build_snapshot(MS_T1, "t1")
    assert len(before["assets"]) == len(after["assets"])
    assert len(before["edges"]) == len(after["edges"])


def test_legacy_fallback_fails_loudly():
    """旧平台回退已移除：必须抛错，不能静默返回 0 退出码（否则 Action 假绿）。"""
    import pytest

    with pytest.raises(RuntimeError):
        m._run_legacy_fallback(object(), "legacy/unknown-model", REPO_ROOT)


def test_unknown_model_exits_nonzero(monkeypatch):
    """非 ModelScope 模型走真实入口时以退出码 2 失败，而不是静默成功（Action 假绿）。

    注意：RuntimeError → SystemExit(2) 的转换在 main.py 的 __main__ 块里，
    所以要跑模块级入口（runpy），而不是直接调 m.main()。
    """
    import pytest
    import runpy

    monkeypatch.setattr(m, "_probe_modelscope", lambda model: False)
    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "--model", "TheBloke/Qwen2.5-0.5B-Instruct-GGUF",
         "--output", str(REPO_ROOT / "outputs" / "_pytest_should_not_exist.md")],
    )
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(REPO_ROOT / "main.py"), run_name="__main__")
    assert excinfo.value.code == 2
    assert not (REPO_ROOT / "outputs" / "_pytest_should_not_exist.md").exists()
