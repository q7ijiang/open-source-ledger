# -*- coding: utf-8 -*-
"""BOM 导出适配层的回归测试。"""

from __future__ import annotations

import json
import types
from datetime import datetime
from pathlib import Path

import bom_adapter
import export_bom


def _asset(
    canonical_id: str,
    *,
    asset_type: str,
    name: str,
    version: str,
    purls: list[str] | None = None,
    license_value: str | None = None,
    evidence_level: str = "A",
) -> dict:
    evidence_chain = []
    if license_value:
        evidence_chain.append(
            {
                "evidence_level": evidence_level,
                "source_api": "modelscope",
                "source_url": "https://www.modelscope.cn/api/v1/models/acme/demo",
                "source_field": "Data.LicenseName",
                "retrieved_at": "2026-10-12T00:00:00Z",
                "status": "ok",
                "raw_value": license_value,
            }
        )
    return {
        "entity_key": canonical_id.split("@", 1)[0],
        "canonical_id": canonical_id,
        "asset_type": asset_type,
        "name": name,
        "version": version,
        "purls": purls or [],
        "license": license_value,
        "evidence_chain": evidence_chain,
        "snapshot_id": "modelscope-acme__demo",
        "source_file": "https://www.modelscope.cn/api/v1/models/acme/demo",
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_export_bom_has_standard_fields_and_timestamp(tmp_path: Path) -> None:
    assets_path = tmp_path / "assets.json"
    edges_path = tmp_path / "edges.json"
    output_path = tmp_path / "bom.json"
    _write_json(assets_path, [])
    _write_json(edges_path, [])

    export_bom.export_bom(assets_path, edges_path, output_path)

    bom = json.loads(output_path.read_text(encoding="utf-8"))
    assert bom["bomFormat"] == "CycloneDX"
    assert bom["specVersion"] == "1.7"
    assert bom["version"] == 1
    assert bom["components"] == []
    assert bom["dependencies"] == []
    assert datetime.fromisoformat(bom["metadata"]["timestamp"])


def test_export_bom_maps_ancestors_licenses_and_dependencies(
    tmp_path: Path,
) -> None:
    parent = _asset(
        "model:modelscope/acme/parent@v1",
        asset_type="model",
        name="acme/parent",
        version="v1",
        purls=["pkg:modelscope/acme/parent@v1"],
        license_value="Apache-2.0",
    )
    child = _asset(
        "model:modelscope/acme/child@v2",
        asset_type="model",
        name="acme/child",
        version="v2",
        purls=["pkg:modelscope/acme/child@v2"],
        license_value="MIT",
        evidence_level="A",
    )
    dependency = _asset(
        "package:pypi/demo@1.0",
        asset_type="package",
        name="demo",
        version="1.0",
        purls=["pkg:pypi/demo@1.0"],
    )
    edges = [
        {
            "source": child["canonical_id"],
            "target": parent["canonical_id"],
            "edge_type": "derived_from",
            "evidence_level": "B",
            "source_field": "lineage.ParentsModels",
        },
        {
            "source": child["canonical_id"],
            "target": dependency["canonical_id"],
            "edge_type": "depends_on",
            "evidence_level": "A",
            "source_field": "requirements.txt",
        },
    ]
    assets_path = tmp_path / "assets.json"
    edges_path = tmp_path / "edges.json"
    output_path = tmp_path / "bom.json"
    _write_json(assets_path, [parent, child, dependency])
    _write_json(edges_path, edges)

    export_bom.export_bom(assets_path, edges_path, output_path)
    bom = json.loads(output_path.read_text(encoding="utf-8"))
    components = {component["bom-ref"]: component for component in bom["components"]}

    child_component = components[child["canonical_id"]]
    assert child_component["pedigree"]["ancestors"] == [
        {
            "ref": parent["canonical_id"],
            "purl": parent["purls"][0],
            "evidence_level": "B",
            "source_field": "lineage.ParentsModels",
        }
    ]

    license_entry = child_component["licenses"][0]
    assert license_entry["license"] == {"id": "MIT"}
    assert license_entry["evidence_level"] == "A"
    assert license_entry["evidence_chain"][0]["raw_value"] == "MIT"

    parent_license = components[parent["canonical_id"]]["licenses"][0]
    assert parent_license["license"] == {"id": "Apache-2.0"}
    assert parent_license["evidence_level"] == "A"

    dependencies = {
        item["ref"]: item["dependsOn"] for item in bom["dependencies"]
    }
    assert set(dependencies) == set(components)
    assert dependencies[child["canonical_id"]] == [dependency["canonical_id"]]
    assert dependencies[parent["canonical_id"]] == []

    converted = bom_adapter.convert_bom(
        bom,
        source_file=str(output_path),
        snapshot_id="t0",
    )
    converted_child = next(
        asset
        for asset in converted
        if asset["canonical_id"] == child["canonical_id"]
    )
    assert converted_child["evidence_chain"][0]["evidence_level"] == "A"


def test_export_bom_adds_reversible_purl_for_internal_aggregate(
    tmp_path: Path,
) -> None:
    aggregate_id = (
        "model:modelscope/acme/demo:parent:ParentsModels@master"
    )
    aggregate = _asset(
        aggregate_id,
        asset_type="model",
        name="acme/demo · 基座 (Total: 1)",
        version="master",
    )
    child = _asset(
        "model:modelscope/acme/child@master",
        asset_type="model",
        name="acme/child",
        version="master",
        purls=["pkg:modelscope/acme/child@master"],
    )
    assets_path = tmp_path / "assets.json"
    edges_path = tmp_path / "edges.json"
    output_path = tmp_path / "bom.json"
    _write_json(assets_path, [aggregate, child])
    _write_json(
        edges_path,
        [
            {
                "source": child["canonical_id"],
                "target": aggregate_id,
                "edge_type": "derived_from",
                "evidence_level": "B",
                "source_field": "lineage.ParentsModels",
            }
        ],
    )

    export_bom.export_bom(assets_path, edges_path, output_path)
    bom = json.loads(output_path.read_text(encoding="utf-8"))
    components = {component["bom-ref"]: component for component in bom["components"]}

    ancestor = components[child["canonical_id"]]["pedigree"]["ancestors"][0]
    assert ancestor["ref"] == aggregate_id
    assert ancestor["purl"] == (
        "pkg:modelscope/acme/demo:parent:ParentsModels@master"
    )

    converted = bom_adapter.convert_bom(
        bom,
        source_file=str(output_path),
        snapshot_id="t0",
    )
    assert any(asset["canonical_id"] == aggregate_id for asset in converted)


def test_run_project_writes_bom_in_normal_path(monkeypatch, tmp_path: Path) -> None:
    import main
    import work.extract_modelscope_lineage as extractor

    project = tmp_path / "demo_project"
    project.mkdir()
    (project / "model_usage.py").write_text(
        'AutoModel.from_pretrained("acme/demo")\n',
        encoding="utf-8",
    )
    output_dir = tmp_path / "outputs"
    asset = _asset(
        "model:modelscope/acme/demo@master",
        asset_type="model",
        name="acme/demo",
        version="master",
        purls=["pkg:modelscope/acme/demo@master"],
        license_value="Apache-2.0",
    )
    edge = {
        "source": asset["canonical_id"],
        "target": asset["canonical_id"],
        "edge_type": "derived_from",
        "evidence_level": "B",
        "source_field": "lineage.ParentsModels",
    }

    monkeypatch.setattr(
        main,
        "_scan_project_models",
        lambda _path: [
            {
                "model": "acme/demo",
                "ns": "acme",
                "name": "demo",
                "sources": ["model_usage.py"],
            }
        ],
    )
    monkeypatch.setattr(
        main,
        "_validate_modelscope_models",
        lambda candidates: list(candidates),
    )
    monkeypatch.setattr(
        main,
        "_project_output_dir",
        lambda _root, _project_path: output_dir,
    )
    monkeypatch.setattr(
        extractor,
        "extract",
        lambda _ns, _name, _snapshot_id, _source_url: ([asset], [edge]),
    )

    args = types.SimpleNamespace(
        project=str(project),
        output=tmp_path / "report.md",
    )
    main.run_project(args)

    bom_path = output_dir / "bom.json"
    assert bom_path.exists()
    bom = json.loads(bom_path.read_text(encoding="utf-8"))
    assert bom["specVersion"] == "1.7"
    assert bom["components"][0]["bom-ref"] == asset["canonical_id"]
