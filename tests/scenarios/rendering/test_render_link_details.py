from __future__ import annotations

import json
from pathlib import Path

import render_diff
import render_graph


REPO_ROOT = Path(__file__).resolve().parents[3]
ASSETS = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "projects"
    / "real_modelscope"
    / "snapshots"
    / "full"
    / "t0_assets.json"
)


def test_both_renderers_expose_model_page_and_api_evidence_links() -> None:
    for template in (render_graph.TPL, render_diff.TPL):
        assert "function modelscopeModelPageUrl" in template
        assert "ModelScope 模型主页" in template
        assert "原始 API 证据" in template
        assert "https://www.modelscope.cn/models/" in template
        assert "source_url" in template


def test_modelscope_fixture_contains_model_page_identity_and_api_evidence() -> None:
    assets = json.loads(ASSETS.read_text(encoding="utf-8"))
    gemma = next(asset for asset in assets if asset["name"] == "LLM-Research/gemma-3-4b-it")

    assert gemma["canonical_id"] == "model:modelscope/LLM-Research/gemma-3-4b-it@master"
    assert any(
        item.get("source_url")
        == "https://www.modelscope.cn/api/v1/models/LLM-Research/gemma-3-4b-it"
        for item in gemma["evidence_chain"]
    )
