# -*- coding: utf-8 -*-
"""enrich_lineage 补数据回归测试。

验证修复：components 为空的 BOM 补数据时，组件 type 由 "model" 改为
"machine-learning-model"，使 work/extract_hf_lineage.py 能识别该组件并提取血缘边。
"""

import json
import tempfile
from pathlib import Path

import enrich_lineage
import work.extract_hf_lineage as extract_hf


def test_enrich_empty_bom_writes_ml_model_type_and_extracts_edge():
    """空 BOM 补数据后 type 正确，且能被血缘提取器提取到至少 1 条边。"""
    with tempfile.TemporaryDirectory() as tmp:
        # 模型名命中 FAMILY_RULES 的 "llama-2" 关键词，才会推断出祖先。
        bom_path = Path(tmp) / "my-llama-2-7b.json"
        data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "version": 1,
            "metadata": {"component": {"name": "my-llama-2-7b"}},
            "components": [],
        }
        bom_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        status, message = enrich_lineage.enrich_bom(bom_path)
        assert status == "enriched", message

        enriched = json.loads(bom_path.read_text(encoding="utf-8"))
        assert enriched["components"][0]["type"] == "machine-learning-model"

        assets, edges = extract_hf.extract(bom_path)
        assert len(edges) >= 1
