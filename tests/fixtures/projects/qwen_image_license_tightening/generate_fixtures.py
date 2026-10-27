# -*- coding: utf-8 -*-
"""Generate reproducible Qwen-Image-2.1 license-change demo fixtures.

The fixture has two scenarios:

* ``direct`` reconstructs the real 2026-09-15/20 README metadata transition for
  a project that directly uses ``Qwen/Qwen-Image-2.1``.
* ``upstream`` uses the current, real ``unsloth/Qwen-Image-2.1-Turbo-FP8``
  lineage and replays the historical Apache-2.0 label on the common ancestor.
  The replay is counterfactual because the current descendants were published
  after the license tightening.

Network access is only needed with ``--refresh-evidence``. The committed
evidence files make normal regeneration and tests deterministic and offline.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import export_bom
import main as ledger_main
import modelscope_adapter
import modelscope_lineage
import risk_evaluator
from ai_layer.config import AIConfig
from ai_layer.provider import MockAIProvider
from ai_layer.schemas import (
    collect_project_evidence,
    normalize_model_analysis,
    normalize_project_context,
    semantic_diff,
    sha256_text,
)
from ai_layer.service import AIService, analysis_bundle

FIXTURE_ROOT = Path(__file__).resolve().parent
EVIDENCE_ROOT = FIXTURE_ROOT / "evidence"
TARGET_MODEL = "Qwen/Qwen-Image-2.1"
TURBO_MODEL = "Qwen/Qwen-Image-2.1-Turbo"
FP8_MODEL = "unsloth/Qwen-Image-2.1-Turbo-FP8"
DOCUMENT_MODEL = "OpenGVLab/InternVL3-8B-Instruct"

HISTORICAL_README_COMMIT = "72900d004951bd845d7a4a77d566562eadd37c3f"
LICENSE_COMMIT = "4b1751dd4e00f6c1a097c5a80d05e6521cea1c39"
README_LICENSE_COMMIT = "c64b6eace0507982fa3f4828461b201d836d625a"
EXPECTED_HISTORICAL_README_SHA256 = (
    "69219f4d55a4e13fe85ef680011993cda30523250da3cc2dc216445d0ecdd484"
)
EXPECTED_LICENSE_SHA256 = (
    "8dc973f024ff95966bea25866efa443fd16776dcb1001e681e3d467ea572b28d"
)

AI_CONFIG = AIConfig(
    enabled=True,
    provider="mock",
    model="frozen-qwen-image-license-fixture",
    base_url="offline://qwen-image-license-fixture",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _model_parts(model_id: str) -> tuple[str, str]:
    if "/" not in model_id:
        raise ValueError(f"invalid ModelScope model id: {model_id}")
    namespace, name = model_id.split("/", 1)
    return namespace, name


def _request_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    import requests

    response = requests.get(
        url,
        params=params,
        headers={
            "Accept": "application/json",
            "User-Agent": "open-source-ledger-qwen-license-fixture/1.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("Data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise ValueError(f"ModelScope returned no Data for {url}")
    return data


def _request_document(namespace: str, name: str, revision: str, path: str) -> str:
    import requests

    response = requests.get(
        f"{modelscope_adapter.API_BASE}/models/{namespace}/{name}/repo",
        params={"Revision": revision, "FilePath": path},
        headers={
            "Accept": "text/plain, text/markdown, application/octet-stream",
            "User-Agent": "open-source-ledger-qwen-license-fixture/1.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.content.decode("utf-8")


def _refresh_evidence() -> None:
    """Fetch official ModelScope metadata and freeze it under ``evidence/``."""

    namespace, name = _model_parts(TARGET_MODEL)
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)

    current = modelscope_adapter.fetch_source_bundle(namespace, name)
    license_doc = next(
        (item for item in current.get("documents", []) if item.get("path") == "LICENSE"),
        None,
    )
    if not license_doc:
        raise RuntimeError("current ModelScope source bundle has no LICENSE document")
    if license_doc.get("sha256") != EXPECTED_LICENSE_SHA256:
        raise RuntimeError(
            "Qwen-Image-2.1 LICENSE changed since this fixture was authored: "
            f"{license_doc.get('sha256')}"
        )

    historical_readme = _request_document(
        namespace,
        name,
        HISTORICAL_README_COMMIT,
        "README.md",
    )
    historical_digest = hashlib.sha256(historical_readme.encode("utf-8")).hexdigest()
    if historical_digest != EXPECTED_HISTORICAL_README_SHA256:
        raise RuntimeError(
            "historical README hash does not match the reviewed snapshot: "
            f"{historical_digest}"
        )

    commits = _request_json(
        f"{modelscope_adapter.API_BASE}/models/{namespace}/{name}/commits",
        {"Revision": "master", "PageNumber": 1, "PageSize": 100},
    )
    by_id = {
        str(item.get("Id") or ""): item
        for item in commits.get("Commit", [])
        if isinstance(item, dict)
    }
    required = {
        HISTORICAL_README_COMMIT,
        LICENSE_COMMIT,
        README_LICENSE_COMMIT,
    }
    missing = sorted(required - set(by_id))
    if missing:
        raise RuntimeError(f"required ModelScope commit metadata missing: {missing}")

    historical_bundle = {
        "schema_version": "modelscope-historical-source-bundle/v1",
        "source": "modelscope",
        "model_id": TARGET_MODEL,
        "revision": HISTORICAL_README_COMMIT,
        "retrieved_at": _utc_now(),
        "historical_reconstruction": True,
        "historical_boundary": (
            "This snapshot reconstructs only the README license metadata that "
            "ModelScope served before the Qwen Research License was added. It is "
            "not a retained copy of an Apache-2.0 LICENSE file."
        ),
        "facts": {
            "license": {
                "value": "Apache License 2.0",
                "source_field": "README.md:front_matter.license",
                "evidence_level": "A",
            },
            "detail": {
                "Name": name,
                "Path": namespace,
                "Revision": HISTORICAL_README_COMMIT,
            },
            "files": [
                {
                    "path": "README.md",
                    "sha256": historical_digest,
                    "size": len(historical_readme.encode("utf-8")),
                    "revision": HISTORICAL_README_COMMIT,
                }
            ],
            "lineage": None,
        },
        "documents": [
            {
                "path": "README.md",
                "content": historical_readme,
                "sha256": historical_digest,
                "size": len(historical_readme.encode("utf-8")),
                "source_url": (
                    f"https://www.modelscope.cn/models/{TARGET_MODEL}/"
                    f"file/view/{HISTORICAL_README_COMMIT}/README.md"
                ),
                "source_field": "README.md front matter",
                "evidence_level": "A",
            }
        ],
        "commits": {
            "historical_readme": by_id[HISTORICAL_README_COMMIT],
            "license_created": by_id[LICENSE_COMMIT],
            "readme_license_changed": by_id[README_LICENSE_COMMIT],
        },
        "warnings": [],
    }

    _write_json(EVIDENCE_ROOT / "qwen-image-2.1.current.json", current)
    _write_json(
        EVIDENCE_ROOT / "qwen-image-2.1.historical-apache.json",
        historical_bundle,
    )


def _load_or_refresh_evidence(refresh: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    current_path = EVIDENCE_ROOT / "qwen-image-2.1.current.json"
    historical_path = EVIDENCE_ROOT / "qwen-image-2.1.historical-apache.json"
    if refresh or not current_path.exists() or not historical_path.exists():
        _refresh_evidence()
    return _load_json(current_path), _load_json(historical_path)


def _document(bundle: dict[str, Any], path: str) -> dict[str, Any]:
    for item in bundle.get("documents", []) or []:
        if isinstance(item, dict) and item.get("path") == path:
            return item
    raise KeyError(f"document not found in source bundle: {path}")


def _line_containing(content: str, token: str) -> str:
    for line in content.splitlines():
        if token in line:
            return line.strip()
    raise ValueError(f"expected license text token not found: {token}")


def _current_ai_response(current_bundle: dict[str, Any]) -> dict[str, Any]:
    license_text = str(_document(current_bundle, "LICENSE").get("content") or "")
    commercial = _line_containing(license_text, "FOR NON-COMMERCIAL PURPOSES ONLY")
    commercial_request = _line_containing(
        license_text,
        "separate commercial license",
    )
    redistribution = _line_containing(
        license_text,
        "Subject to Section 2 (Grant of Rights)",
    )
    modification_notice = _line_containing(
        license_text,
        "prominent notices stating that you changed the files",
    )
    notice_file = _line_containing(
        license_text,
        'within a "Notice" text file',
    )
    model_training = _line_containing(
        license_text,
        "create, train, fine-tune, or improve an AI model",
    )
    derivative_terms = _line_containing(
        license_text,
        "additional or different license terms",
    )

    def claim(
        dimension: str,
        state: str,
        statement: str,
        quote: str,
    ) -> dict[str, Any]:
        return {
            "dimension": dimension,
            "state": state,
            "statement": statement,
            "evidences": [{"source_path": "LICENSE", "quote": quote}],
        }

    return {
        "summary": (
            "Qwen Research License 将材料用途限制为非商业目的；商用需要单独授权，"
            "再分发、修改、声明保留和模型训练相关发布还附带条件。"
        ),
        "claims": [
            claim(
                "commercial_use",
                "prohibited",
                "材料仅可用于非商业目的，未取得单独商业许可时不得商用。",
                commercial,
            ),
            claim(
                "commercial_license_request",
                "conditional",
                "商业使用需要向协议所列联系地址申请单独商业许可证。",
                commercial_request,
            ),
            claim(
                "redistribution",
                "conditional",
                "协议允许在满足第 2 条及后续条件时再分发材料或衍生作品。",
                redistribution,
            ),
            claim(
                "modification",
                "conditional",
                "修改文件必须带有醒目的修改声明。",
                modification_notice,
            ),
            claim(
                "notice",
                "conditional",
                "再分发副本需要保留 Notice 文件中的指定声明。",
                notice_file,
            ),
            claim(
                "training_other_models",
                "conditional",
                "使用材料或其输出训练、微调或改进其他 AI 模型并发布时，"
                "需要展示指定归属文案。",
                model_training,
            ),
            claim(
                "fine_tuned_redistribution",
                "conditional",
                "衍生作品可附带不同条款，但仍须遵守原协议。",
                derivative_terms,
            ),
        ],
        "gaps": [
            {
                "dimension": "patent",
                "reason": "证据不足：当前 LICENSE 未形成可独立验证的专利授权条款。",
            }
        ],
    }


def _historical_ai_response(historical_bundle: dict[str, Any]) -> dict[str, Any]:
    readme = str(_document(historical_bundle, "README.md").get("content") or "")
    quote = _line_containing(readme, "license: Apache License 2.0")
    return {
        "summary": (
            "该历史快照只能证明 README 元数据曾声明 Apache License 2.0；"
            "未保留当时的完整 Apache LICENSE 文件，不能据此补齐全部授权边界。"
        ),
        "claims": [
            {
                "dimension": "commercial_use",
                "state": "unknown",
                "statement": (
                    "README 元数据声明 Apache License 2.0，但仅凭该字段不能"
                    "替代对完整许可原文的核验。"
                ),
                "evidences": [{"source_path": "README.md", "quote": quote}],
            }
        ],
        "gaps": [
            {"dimension": "redistribution", "reason": "历史快照未保存完整许可文本"},
            {"dimension": "modification", "reason": "历史快照未保存完整许可文本"},
            {
                "dimension": "training_other_models",
                "reason": "证据不足：README 元数据无法说明训练其他模型的条件",
            },
        ],
    }


def _analysis(
    response: dict[str, Any],
    bundle: dict[str, Any],
    *,
    historical_reconstruction: bool,
    fact_source: str,
) -> dict[str, Any]:
    analysis = normalize_model_analysis(
        response,
        bundle,
        AI_CONFIG.public_dict(),
    )
    analysis["simulation"] = False
    analysis["historical_reconstruction"] = historical_reconstruction
    subject = analysis.setdefault("subject", {})
    subject["fact_source"] = fact_source
    return analysis


def _modelscope_assets(model_ids: Iterable[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    merged_assets: list[dict[str, Any]] = []
    merged_edges: list[dict[str, Any]] = []
    seen_assets: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()
    for model_id in model_ids:
        namespace, name = _model_parts(model_id)
        assets, edges = modelscope_lineage.extract(
            namespace,
            name,
            f"modelscope-{namespace}__{name}",
            f"{modelscope_adapter.API_BASE}/models/{namespace}/{name}",
            include_downstream=False,
            max_upstream_depth=4,
            max_upstream_nodes=128,
        )
        for asset in assets:
            canonical_id = str(asset.get("canonical_id") or "")
            if canonical_id and canonical_id not in seen_assets:
                seen_assets.add(canonical_id)
                merged_assets.append(asset)
        for edge in edges:
            signature = (
                str(edge.get("source") or ""),
                str(edge.get("target") or ""),
                str(edge.get("edge_type") or ""),
            )
            if signature not in seen_edges:
                seen_edges.add(signature)
                merged_edges.append(edge)
    return merged_assets, merged_edges


def _asset_by_name(assets: Iterable[dict[str, Any]], name: str) -> dict[str, Any]:
    for asset in assets:
        if asset.get("name") == name and not asset.get("aggregate"):
            return asset
    raise KeyError(f"model not found in fixture assets: {name}")


def _historical_license_evidence(
    historical_bundle: dict[str, Any],
) -> dict[str, Any]:
    readme = _document(historical_bundle, "README.md")
    commit = (
        historical_bundle.get("commits", {})
        .get("historical_readme", {})
        .get("Id")
    )
    return {
        "evidence_level": "A",
        "source_api": "modelscope",
        "source_url": readme.get("source_url"),
        "source_field": "README.md:front_matter.license",
        "retrieved_at": historical_bundle.get("retrieved_at"),
        "raw_value": "Apache License 2.0",
        "commit": commit,
        "historical_reconstruction": True,
    }


def _apply_historical_target(
    assets: list[dict[str, Any]],
    historical_bundle: dict[str, Any],
    historical_analysis: dict[str, Any],
    *,
    simulation: bool,
    simulation_reason: str,
) -> None:
    target = _asset_by_name(assets, TARGET_MODEL)
    target["license"] = "Apache License 2.0"
    target["historical_reconstruction"] = True
    target["historical_commit"] = HISTORICAL_README_COMMIT
    target["historical_source_url"] = _document(
        historical_bundle,
        "README.md",
    ).get("source_url")
    target["ai_analysis"] = historical_analysis
    if simulation:
        target["simulation"] = True
        target["simulation_reason"] = simulation_reason
        target["simulation_original_license"] = "qwen-research"
        target["simulation_target_license"] = "Apache License 2.0"

    evidence_chain = [
        item
        for item in target.get("evidence_chain", [])
        if isinstance(item, dict)
        and str(item.get("source_field") or "")
        not in {"Data.License", "Data.LicenseName"}
    ]
    evidence_chain.insert(0, _historical_license_evidence(historical_bundle))
    target["evidence_chain"] = evidence_chain


def _apply_current_target(
    assets: list[dict[str, Any]],
    current_analysis: dict[str, Any],
) -> None:
    target = _asset_by_name(assets, TARGET_MODEL)
    target["ai_analysis"] = current_analysis


def _project_context(
    project_path: Path,
    quote: str,
    use_type: str,
    statement: str,
    *,
    simulation: bool,
) -> dict[str, Any]:
    evidence = collect_project_evidence(project_path)
    response = {
        "uses": [
            {
                "use_type": use_type,
                "statement": statement,
                "evidence": {
                    "source_path": "app.py",
                    "quote": quote,
                },
            }
        ]
    }
    context = normalize_project_context(
        response,
        project_path,
        evidence,
        AI_CONFIG.public_dict(),
    )
    context["simulation"] = simulation
    context["historical_reconstruction"] = not simulation
    if simulation:
        context["simulation_note"] = (
            "项目文件是演示夹具；血缘来自当前 ModelScope，许可证时间点是反事实重放。"
        )
    else:
        context["historical_reconstruction_note"] = (
            "项目文件是演示夹具；许可证时间点来自 ModelScope 的真实提交历史。"
        )
    return context


def _attach_project_context(
    assets: list[dict[str, Any]],
    context: dict[str, Any],
) -> None:
    for asset in assets:
        if not asset.get("aggregate"):
            asset["ai_project_context"] = context


def _enrich_risk(assets: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    result = risk_evaluator.evaluate_model_risk(assets, edges)
    by_id = {
        item.get("canonical_id"): item
        for item in result.get("nodes", [])
        if isinstance(item, dict)
    }
    for asset in assets:
        detail = by_id.get(asset.get("canonical_id"))
        if not isinstance(detail, dict):
            continue
        for field in (
            "risk_level",
            "decision",
            "decision_zh",
            "license_recognized",
            "risk_note",
        ):
            asset[field] = detail.get(field)


def _portable_text(path: Path) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    prefixes = (str(ROOT) + "\\", ROOT.as_posix() + "/")
    for prefix in prefixes:
        text = text.replace(prefix, "")
    path.write_text(text, encoding="utf-8")


def _render_diff(
    scenario_dir: Path,
    title: str,
    ai_bundle: dict[str, Any],
) -> None:
    report_path = scenario_dir / "diff_report.md"
    ai_service = AIService(AI_CONFIG, MockAIProvider({}))
    ledger_main.run_diff(
        scenario_dir / "t0_bom.json",
        scenario_dir / "t1_bom.json",
        report_path,
        include_fixtures=False,
        ai_service=ai_service,
    )
    _portable_text(report_path)
    machine_diff = report_path.with_suffix(".ai.json")
    if machine_diff.exists():
        machine_diff.unlink()
    _write_json(scenario_dir / "ai_analysis.json", ai_bundle)

    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "render_diff.py"),
            "--before",
            str(scenario_dir / "t0_bom.json"),
            "--after",
            str(scenario_dir / "t1_bom.json"),
            "--output",
            str(scenario_dir / "diff_graph.html"),
            "--report",
            str(report_path),
            "--title",
            title,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(
            "render_diff.py failed: "
            + (process.stderr or process.stdout).strip()
        )


def _scenario_readme(
    *,
    direct: bool,
    t0_asset_count: int,
    t1_asset_count: int,
    t0_edge_count: int,
    t1_edge_count: int,
) -> str:
    if direct:
        return f"""# 场景一：项目直接使用 Qwen-Image-2.1

本目录用于演示“项目直接使用的模型发生许可证变化”。

## 证据边界

- 2026-09-15 至 2026-09-17，ModelScope 的 `README.md` 元数据将许可证写作
  `license: Apache License 2.0`，对应提交 `{HISTORICAL_README_COMMIT}`。
- 2026-09-18 新增 `LICENSE`，内容为 Qwen Research License，对应提交
  `{LICENSE_COMMIT}`。
- 2026-09-20 `README.md` 改为 `license: other` 和
  `license_name: qwen-research`，对应提交 `{README_LICENSE_COMMIT}`。
- 历史快照只重建 README 元数据，没有保存或虚构 Apache-2.0 LICENSE 文件。
- 这不是“同一个 Apache LICENSE 文本被改写”的声明。

## 文件

- `project/`：演示项目的源码和配置。
- `evidence/`：历史 README、当前 ModelScope source bundle 和边界说明。
- `t0_bom.json`：Apache License 2.0 元数据时点的重建快照。
- `t1_bom.json`：读取当前 Qwen Research License 原文的快照。
- `diff_report.md`：Delta、路径证书和 AI 语义差异。
- `diff_graph.html`：可离线打开的交互验收页面。
- `ai_analysis.json`：冻结的 AI 条款画像和项目上下文。

## 规模

- t0：{t0_asset_count} 个资产，{t0_edge_count} 条边。
- t1：{t1_asset_count} 个资产，{t1_edge_count} 条边。

直接模式没有下游项目节点可传播，风险落在项目直接依赖本身；预期看到许可证
名称变化和 AI 提取出的非商业限制。所有 AI 结论均为 C 级并处于人工复核状态。
"""
    return f"""# 场景二：真实上游血缘上的许可证变化传播

本目录用于演示“项目使用的模型不变，但其上游基座模型许可证变化”。

## 真实血缘

截至快照生成时，ModelScope 返回的真实关系为：

```text
{FP8_MODEL}
  -> {TURBO_MODEL}
  -> {TARGET_MODEL}
```

项目还直接使用 `{DOCUMENT_MODEL}` 作为无关的文档理解分支。许可证变化从
`{TARGET_MODEL}` 向图像生成分支传播，而文档理解分支不应被误标为受影响。

## 时间边界

- t0 的祖先许可证 `Apache License 2.0` 来自 ModelScope 真实历史 README 元数据。
- t1 的祖先许可证 `qwen-research` 和条款原文来自当前 ModelScope。
- 当前 Turbo 与 FP8 模型发布于许可证收紧之后，因此 t0 是
  `simulation=true` 的反事实重放：它复用当前真实血缘，但不声称这些下游
  模型在 Apache 阶段已经存在。
- 历史快照没有保存 Apache LICENSE 文件，只保存 README 元数据与提交证据。

## 文件

- `project/`：使用 FP8 图像模型和 InternVL 文档模型的项目。
- `evidence/`：历史/当前 Qwen-Image-2.1 证据以及真实血缘说明。
- `t0_bom.json`：真实当前血缘 + 历史许可证的模拟基线。
- `t1_bom.json`：真实当前血缘 + 当前许可证。
- `diff_report.md`：Delta、传播事件、路径证书和 AI 语义差异。
- `diff_graph.html`：可离线打开的交互验收页面。
- `ai_analysis.json`：冻结的 AI 条款画像和项目上下文。

## 规模

- t0：{t0_asset_count} 个资产，{t0_edge_count} 条边。
- t1：{t1_asset_count} 个资产，{t1_edge_count} 条边。

预期传播路径至少覆盖 `Qwen-Image-2.1 -> Turbo -> FP8`。AI 不负责传播，
只解释新增条款、给出逐字原文、原文哈希和置信度分解；传播仍由确定性图算法
生成路径证书。
"""


def _write_project_files() -> None:
    direct_project = FIXTURE_ROOT / "direct" / "project"
    upstream_project = FIXTURE_ROOT / "upstream" / "project"

    _write_json(
        direct_project / "config.json",
        {
            "service": "image-generation",
            "model_id": TARGET_MODEL,
            "deployment": "internal",
        },
    )
    (direct_project / "app.py").parent.mkdir(parents=True, exist_ok=True)
    (direct_project / "app.py").write_text(
        """# -*- coding: utf-8 -*-
MODEL_ID = "Qwen/Qwen-Image-2.1"


def load_pipeline():
    from diffusers import AutoPipelineForImage2Image

    return AutoPipelineForImage2Image.from_pretrained(MODEL_ID)


def generate(prompt: str) -> bytes:
    pipe = load_pipeline()
    result = pipe(prompt=prompt)
    return result.images[0]
""",
        encoding="utf-8",
    )
    (direct_project / "README.md").write_text(
        "# Direct dependency demo\n\n"
        "This project directly uses `Qwen/Qwen-Image-2.1` in an internal image "
        "generation service.\n",
        encoding="utf-8",
    )

    _write_json(
        upstream_project / "config" / "model_catalog.json",
        {
            "image_generation": {
                "model_id": FP8_MODEL,
                "purpose": "efficient image generation",
            },
            "document_understanding": {
                "model_id": DOCUMENT_MODEL,
                "purpose": "poster and document understanding",
            },
        },
    )
    (upstream_project / "app.py").parent.mkdir(parents=True, exist_ok=True)
    (upstream_project / "app.py").write_text(
        f"""# -*- coding: utf-8 -*-
IMAGE_MODEL_ID = "{FP8_MODEL}"
DOCUMENT_MODEL_ID = "{DOCUMENT_MODEL}"


def load_image_pipeline():
    from diffusers import AutoPipelineForImage2Image

    # The production service loads the FP8 model locally.
    return AutoPipelineForImage2Image.from_pretrained(IMAGE_MODEL_ID)


def load_document_model():
    from transformers import AutoModelForVision2Seq

    return AutoModelForVision2Seq.from_pretrained(DOCUMENT_MODEL_ID)


def inspect_material(prompt: str) -> dict:
    image_pipe = load_image_pipeline()
    generated = image_pipe(prompt=prompt).images[0]
    return {{"image": generated, "summary": "generated locally"}}
""",
        encoding="utf-8",
    )
    (upstream_project / "README.md").write_text(
        "# Upstream propagation demo\n\n"
        f"- Image branch: `{FP8_MODEL}` with real ancestors "
        f"`{TURBO_MODEL}` and `{TARGET_MODEL}`.\n"
        f"- Unrelated document branch: `{DOCUMENT_MODEL}`.\n"
        "- The license replay is demonstrated in the frozen t0/t1 BOM files.\n",
        encoding="utf-8",
    )


def _write_evidence_note(
    path: Path,
    *,
    direct: bool,
    current_bundle: dict[str, Any],
    historical_bundle: dict[str, Any],
) -> None:
    current_license = _document(current_bundle, "LICENSE")
    historical_readme = _document(historical_bundle, "README.md")
    scope = (
        "项目直接依赖 Qwen-Image-2.1。"
        if direct
        else "项目直接依赖 FP8 下游模型，并通过真实血缘追溯到共同祖先。"
    )
    text = f"""# ModelScope 证据边界

{scope}

## 已核实事实

- 历史 README 提交：`{HISTORICAL_README_COMMIT}`。
- 历史 README SHA256：`{historical_readme.get("sha256")}`。
- 历史 README 原文包含：`license: Apache License 2.0`。
- LICENSE 创建提交：`{LICENSE_COMMIT}`，提交说明为 `Create LICENSE`。
- README 许可证字段变更提交：`{README_LICENSE_COMMIT}`。
- 当前 LICENSE SHA256：`{current_license.get("sha256")}`。
- 当前 ModelScope 字段：`Data.License = other`，
  `Data.LicenseName = qwen-research`。
- 当前许可证协议标题：`Qwen RESEARCH LICENSE AGREEMENT`，标注日期
  `September 20, 2026`。

## 不得扩大解释

- 历史 README 的 Apache 标注是元数据事实，不等于本仓库保存了当时的完整
  Apache-2.0 LICENSE 文件。
- 没有证据支持“同一个 Apache LICENSE 文件后来被替换成 Qwen Research
  License”。
- 上游传播场景中的 t0 是反事实重放，`scenario.json` 必须保持
  `simulation=true`。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_scenario(
    name: str,
    model_ids: list[str],
    *,
    direct: bool,
    current_bundle: dict[str, Any],
    historical_bundle: dict[str, Any],
    current_analysis: dict[str, Any],
    historical_analysis: dict[str, Any],
    refresh: bool,
) -> dict[str, Any]:
    scenario_dir = FIXTURE_ROOT / name
    project_dir = scenario_dir / "project"
    _write_project_files()

    t1_assets, t1_edges = _modelscope_assets(model_ids)
    t0_assets = copy.deepcopy(t1_assets)
    t0_edges = copy.deepcopy(t1_edges)
    simulation = not direct
    reason = (
        "当前真实血缘与 Qwen-Image-2.1 历史 README 许可证元数据的反事实重放；"
        "Turbo/FP8 在 Apache 标注阶段尚未发布。"
    )
    scenario_historical_analysis = copy.deepcopy(historical_analysis)
    scenario_current_analysis = copy.deepcopy(current_analysis)
    if simulation:
        scenario_historical_analysis["simulation"] = True
        scenario_historical_analysis["simulation_note"] = reason
    _apply_historical_target(
        t0_assets,
        historical_bundle,
        scenario_historical_analysis,
        simulation=simulation,
        simulation_reason=reason,
    )
    _apply_current_target(t1_assets, scenario_current_analysis)

    quote = (
        f'pip = AutoPipelineForImage2Image.from_pretrained("{TARGET_MODEL}")\n'
    )
    direct_app = scenario_dir / "project" / "app.py"
    if direct:
        direct_app.write_text(
            f"""# -*- coding: utf-8 -*-
MODEL_ID = "{TARGET_MODEL}"


def load_pipeline():
    from diffusers import AutoPipelineForImage2Image

    pipeline = AutoPipelineForImage2Image.from_pretrained(MODEL_ID)
    return pipeline
""",
            encoding="utf-8",
        )
        quote = f'pipeline = AutoPipelineForImage2Image.from_pretrained(MODEL_ID)\n'
    else:
        quote = "return AutoPipelineForImage2Image.from_pretrained(IMAGE_MODEL_ID)\n"

    context = _project_context(
        project_dir,
        quote.strip(),
        "local_inference",
        (
            "项目源码在本地加载模型并执行推理。"
            if not direct
            else "项目源码直接加载 Qwen-Image-2.1 并在本地执行推理。"
        ),
        simulation=simulation,
    )
    _attach_project_context(t0_assets, context)
    _attach_project_context(t1_assets, context)

    _enrich_risk(t0_assets, t0_edges)
    _enrich_risk(t1_assets, t1_edges)
    _write_json(scenario_dir / "t0_assets.json", t0_assets)
    _write_json(scenario_dir / "t0_edges.json", t0_edges)
    _write_json(scenario_dir / "t1_assets.json", t1_assets)
    _write_json(scenario_dir / "t1_edges.json", t1_edges)
    export_bom.export_bom(
        scenario_dir / "t0_assets.json",
        scenario_dir / "t0_edges.json",
        scenario_dir / "t0_bom.json",
    )
    export_bom.export_bom(
        scenario_dir / "t1_assets.json",
        scenario_dir / "t1_edges.json",
        scenario_dir / "t1_bom.json",
    )

    semantic = semantic_diff(
        ledger_main._ai_model_analyses_from_assets(t0_assets),
        ledger_main._ai_model_analyses_from_assets(t1_assets),
    )
    semantic["simulation"] = simulation
    bundle = analysis_bundle(
        AI_CONFIG,
        model_analyses=[scenario_historical_analysis, scenario_current_analysis],
        project_context=context,
        diff_analysis=semantic,
    )
    bundle["simulation"] = simulation
    bundle["historical_reconstruction"] = True
    bundle["simulation_note"] = (
        "上游 t0 复用当前真实血缘并重放历史许可证元数据，属于反事实模拟。"
        if simulation
        else "t0/t1 分别重建 ModelScope 历史 README 元数据和当前许可原文。"
    )

    _write_evidence_note(
        scenario_dir / "evidence" / "README.md",
        direct=direct,
        current_bundle=current_bundle,
        historical_bundle=historical_bundle,
    )
    _write_json(
        scenario_dir / "evidence" / "qwen-image-2.1.current.json",
        current_bundle,
    )
    _write_json(
        scenario_dir / "evidence" / "qwen-image-2.1.historical-apache.json",
        historical_bundle,
    )

    scenario = {
        "schema_version": "modelscope-license-tightening-demo/v1",
        "name": name,
        "generated_at": _utc_now(),
        "fixture_project": True,
        "historical_reconstruction": True,
        "simulation": simulation,
        "simulation_reason": reason if simulation else None,
        "project_path": "project",
        "direct_models": model_ids,
        "target_model": TARGET_MODEL,
        "historical_commit": HISTORICAL_README_COMMIT,
        "license_commit": LICENSE_COMMIT,
        "readme_license_commit": README_LICENSE_COMMIT,
        "historical_license_label": "Apache License 2.0",
        "current_license": "qwen-research",
        "t0": "t0_bom.json",
        "t1": "t1_bom.json",
        "diff_report": "diff_report.md",
        "diff_graph": "diff_graph.html",
        "ai_bundle": "ai_analysis.json",
        "historical_boundary": (
            "README metadata only; no retained Apache-2.0 LICENSE file is claimed."
        ),
    }
    _write_json(scenario_dir / "scenario.json", scenario)
    (scenario_dir / "README.md").write_text(
        _scenario_readme(
            direct=direct,
            t0_asset_count=len(t0_assets),
            t1_asset_count=len(t1_assets),
            t0_edge_count=len(t0_edges),
            t1_edge_count=len(t1_edges),
        ),
        encoding="utf-8",
    )
    _render_diff(
        scenario_dir,
        "Qwen-Image-2.1 许可证收紧 - " + ("直接依赖" if direct else "真实上游传播"),
        bundle,
    )
    return scenario


def _write_root_readme(scenarios: list[dict[str, Any]]) -> None:
    lines = [
        "# Qwen-Image-2.1 许可证收紧演示数据",
        "",
        "本目录只包含用于演示和回归测试的夹具。事实证据、模拟边界与演示项目",
        "分别保存在每个场景的 `evidence/`、`scenario.json` 和 `project/`。",
        "",
        "| 场景 | 项目直接模型 | t0 口径 | t1 口径 |",
        "| --- | --- | --- | --- |",
    ]
    for scenario in scenarios:
        model_text = "<br>".join(f"`{item}`" for item in scenario["direct_models"])
        t0_text = "历史 README 元数据重建"
        if scenario["simulation"]:
            t0_text = "当前真实血缘 + 历史许可证反事实重放"
        lines.append(
            f"| [{scenario['name']}]({scenario['name']}/README.md) | "
            f"{model_text} | {t0_text} | 当前 ModelScope 许可证 |"
        )
    lines.extend(
        [
            "",
            "## 重新生成",
            "",
            "在仓库根目录运行：",
            "",
            "```powershell",
            "python tests/fixtures/projects/qwen_image_license_tightening/generate_fixtures.py",
            "```",
            "",
            "普通生成优先读取已冻结的网络证据，不要求联网。若需要从 ModelScope",
            "重新抓取，显式增加 `--refresh-evidence`。脚本会对关键提交和 LICENSE",
            "哈希做硬性校验，证据漂移时停止生成。",
            "",
            "## 事实边界",
            "",
            "- 历史 Apache 口径来自 ModelScope README 元数据和提交历史。",
            "- 没有证据声称当时的 Apache LICENSE 文件被原地修改。",
            "- `upstream` 的 t0 必须保持 `simulation=true`，不得用于宣称 Turbo/FP8",
            "  在 Apache 阶段已经发布。",
        ]
    )
    (FIXTURE_ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _assert_portable(paths: Iterable[Path]) -> None:
    forbidden = [
        re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE),
        re.compile(r"/Users/[^/\s]+/"),
        re.compile(r"file://", re.IGNORECASE),
    ]
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".py"}:
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            if pattern.search(text):
                raise RuntimeError(f"machine-specific path leaked into {path}")


def generate(refresh: bool = False) -> list[dict[str, Any]]:
    current_bundle, historical_bundle = _load_or_refresh_evidence(refresh)
    current_analysis = _analysis(
        _current_ai_response(current_bundle),
        current_bundle,
        historical_reconstruction=False,
        fact_source="ModelScope current source bundle",
    )
    historical_analysis = _analysis(
        _historical_ai_response(historical_bundle),
        historical_bundle,
        historical_reconstruction=True,
        fact_source="ModelScope historical README reconstruction",
    )

    direct = _build_scenario(
        "direct",
        [TARGET_MODEL],
        direct=True,
        current_bundle=current_bundle,
        historical_bundle=historical_bundle,
        current_analysis=current_analysis,
        historical_analysis=historical_analysis,
        refresh=refresh,
    )
    upstream = _build_scenario(
        "upstream",
        [FP8_MODEL, DOCUMENT_MODEL],
        direct=False,
        current_bundle=current_bundle,
        historical_bundle=historical_bundle,
        current_analysis=current_analysis,
        historical_analysis=historical_analysis,
        refresh=refresh,
    )
    scenarios = [direct, upstream]
    _write_root_readme(scenarios)
    _assert_portable(FIXTURE_ROOT.rglob("*"))
    return scenarios


def main_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the Qwen-Image-2.1 license-change demo fixtures"
    )
    parser.add_argument(
        "--refresh-evidence",
        action="store_true",
        help="Fetch and freeze current/historical ModelScope evidence before generation",
    )
    args = parser.parse_args(argv)
    scenarios = generate(refresh=args.refresh_evidence)
    for scenario in scenarios:
        print(
            f"{scenario['name']}: simulation={scenario['simulation']} "
            f"models={len(scenario['direct_models'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
