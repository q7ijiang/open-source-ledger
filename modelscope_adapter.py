# -*- coding: utf-8 -*-
"""ModelScope 数据入口适配器。

把 ModelScope 官方 API 的详情/血缘响应映射为项目统一的资产节点与证据，
不触碰算法层（entity_resolver / build_graph / delta_engine / propagation_engine）。

命名空间字段实测为 ``Data.Path``（如 "Qwen" / "iic"），故按
``Path -> Namespace -> Organization.Name`` 优先提取，确保 PURL
（``pkg:modelscope/{ns}/{name}@{revision}``）能正确生成。

用法：
    import modelscope_adapter as msa

    detail = msa.fetch_model_detail("Qwen", "Qwen-Image-2.1")
    asset = msa.map_to_asset(detail, "snapshot-1", "https://...")
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import bom_adapter as ba


API_BASE = "https://www.modelscope.cn/api/v1"
REQUEST_TIMEOUT_SECONDS = 20.0
RULE_VERSION = "merge-policy-v2"
_TEXT_DOCUMENT_NAMES = ("license", "copying", "notice", "readme", "use_policy", "acceptable_use_policy")
_TEXT_DOCUMENT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".toml"}
_MAX_DOCUMENT_BYTES = 200_000

# 证据等级（2026-10-12 A 最终口径）：
#   A = "搬运"：ModelScope 官方 API 直接返回的字段值（如 Data.LicenseName）原样保留，不是推断也不是重构；
#   B = "推导"：工具基于 API 数据计算/聚合/重组出来的东西（如 derived_from 血缘边、聚合计数节点）；
#   C = "推断"：API 没给、由模型卡文本正则匹配猜出来的。
# 因此许可证字段值 = A，血缘边 / 聚合节点 = B。
LICENSE_EVIDENCE_LEVEL = "A"
LINEAGE_EVIDENCE_LEVEL = "B"

# 常见许可证别名 -> SPDX id；不在表内的按非标文本用 name 承载（如 qwen-research）。
_LICENSE_ALIASES = {
    "apache license 2.0": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "mit license": "MIT",
    "mit": "MIT",
    "bsd 3-clause license": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "gpl-3.0": "GPL-3.0-only",
    "gpl-2.0": "GPL-2.0-only",
    "lgpl-2.1": "LGPL-2.1-only",
    "mpl-2.0": "MPL-2.0",
    "cc-by-4.0": "CC-BY-4.0",
}

# License 兜底字段中这些通用类别不视为具体许可证。
_GENERIC_LICENSE_VALUES = {"", "other", "none", "unknown", "noassertion", "not found"}


def _load_env() -> None:
    """从项目根目录 .env 读取配置（显式指定路径，避免受工作目录影响）。"""
    env_path = Path(__file__).resolve().parent / ".env"
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=env_path, override=False)
    except ImportError:
        # 未安装 python-dotenv 时退化为仅读取进程环境变量。
        pass


_load_env()


def api_key() -> str:
    return os.getenv("MODELSCOPE_API_KEY", "").strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_api(url: str) -> dict[str, Any] | None:
    """请求 ModelScope API，剥离 {Code, Data} 信封，返回 Data；Data 为 null 时返回 None。"""
    headers = {
        "Accept": "application/json",
        "User-Agent": "KaiYuanLedger-modelscope-adapter/0.1",
    }
    key = api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return None

    # ModelScope 信封：{"Code": 200, "Data": {...}, "Message": "success", ...}
    if "Data" in payload and "Code" in payload:
        data = payload.get("Data")
        return data if isinstance(data, dict) else None
    return payload


def fetch_model_detail(ns: str, name: str) -> dict[str, Any] | None:
    """请求详情 API；404（模型不在 ModelScope）返回 None，网络异常向上抛。"""
    try:
        return request_api(f"{API_BASE}/models/{ns}/{name}")
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 404:
            return None
        raise


def fetch_lineage(ns: str, name: str) -> dict[str, Any] | None:
    """请求血缘 API；Data 为 null（无血缘）返回 None。"""
    try:
        return request_api(f"{API_BASE}/models/{ns}/{name}/lineage")
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in (404, 405):
            return None
        raise


def namespace_of(data: dict[str, Any]) -> str:
    """按 Path -> Namespace -> Organization.Name 提取命名空间（实测字段为 Data.Path）。"""
    for key in ("Path", "Namespace"):
        value = ba.clean_text(data.get(key))
        if value:
            return value
    organization = data.get("Organization")
    if isinstance(organization, dict):
        value = ba.clean_text(organization.get("Name"))
        if value:
            return value
    return ""


def model_purl(data: dict[str, Any]) -> str | None:
    """由详情生成 pkg:modelscope/{ns}/{name}@{revision}。"""
    ns = namespace_of(data)
    name = ba.clean_text(data.get("Name"))
    if not name:
        return None
    revision = ba.clean_text(data.get("Revision")) or ""
    purl = f"pkg:modelscope/{ns}/{name}"
    if revision:
        purl = f"{purl}@{revision}"
    return purl


def license_name_of(data: dict[str, Any]) -> tuple[str | None, str | None]:
    """返回 (许可证文本, 实际字段名)；优先 LicenseName，其次 License。"""
    name_value = ba.clean_text(data.get("LicenseName"))
    if name_value:
        return name_value, "Data.LicenseName"

    license_value = ba.clean_text(data.get("License"))
    if license_value and license_value.strip().lower() not in _GENERIC_LICENSE_VALUES:
        return license_value, "Data.License"

    return None, None


def map_license(
    data: dict[str, Any],
    source_url: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """把 ModelScope 详情映射为 CycloneDX 许可证对象 + A 级证据链，返回展示名。"""
    license_value, field = license_name_of(data)
    if not license_value:
        return [], [], None

    normalized = license_value.strip().lower()
    spdx_id = _LICENSE_ALIASES.get(normalized)
    if spdx_id:
        license_obj = {"license": {"id": spdx_id}}
        display = spdx_id
    else:
        license_obj = {"license": {"name": license_value}}
        display = license_value

    evidence = {
        "evidence_level": LICENSE_EVIDENCE_LEVEL,
        "source_api": "modelscope",
        "source_url": source_url,
        "source_field": field,
        "retrieved_at": utc_now(),
        "status": "ok",
        "raw_value": license_value,
    }
    return [license_obj], [evidence], display


def map_to_asset(
    data: dict[str, Any],
    snapshot_id: str,
    source_file: str,
) -> dict[str, Any]:
    """把 ModelScope 详情映射为符合接口约定 v0.2 的资产节点（复用标识生成）。"""
    ns = namespace_of(data)
    name = ba.clean_text(data.get("Name")) or ""
    revision = ba.clean_text(data.get("Revision")) or ""
    purl = model_purl(data)
    purls = [purl] if purl else []

    display_name = "/".join(part for part in (ns, name) if part)
    source_url = f"{API_BASE}/models/{ns}/{name}" if name else None

    license_entries, license_evidence, license_display = map_license(data, source_url)

    entity_key, canonical_id, _ = ba.build_asset_identifiers(
        asset_type="model",
        name=display_name or name or "(未命名模型)",
        version=revision or None,
        purls=purls,
    )

    return {
        "entity_key": entity_key,
        "canonical_id": canonical_id,
        "asset_type": "model",
        "name": display_name or name,
        "version": revision or "",
        "purls": purls,
        "license": license_display,
        "evidence_chain": list(license_evidence),
        "snapshot_id": snapshot_id,
        "merge_status": "KEPT_SEPARATE",
        "reason_code": "NO_MERGE_CANDIDATE",
        "rule_version": RULE_VERSION,
        "hashes": [],
        "source_file": source_file,
    }


def _decode_document(content: bytes) -> str | None:
    """只接受可审计文本；权重、图片和无法解码内容不进入 source_bundle。"""
    if not content or b"\x00" in content[:4096] or len(content) > _MAX_DOCUMENT_BYTES:
        return None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _safe_repo_path(raw_path: str) -> str | None:
    """只接受仓库内相对路径，避免把输入拼成任意路径。"""
    normalized = raw_path.strip().replace("\\", "/").lstrip("/")
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def _document_path(item: Any) -> str | None:
    if isinstance(item, str):
        return _safe_repo_path(ba.clean_text(item))
    if not isinstance(item, dict):
        return None
    raw_path = ba.clean_text(
        item.get("Path")
        or item.get("path")
        or item.get("FilePath")
        or item.get("Name")
        or item.get("name")
    )
    return _safe_repo_path(raw_path)


def _is_auditable_document(path: str) -> bool:
    lower = path.lower().strip("/")
    name = lower.rsplit("/", 1)[-1]
    return name.startswith(_TEXT_DOCUMENT_NAMES) or Path(name).suffix in _TEXT_DOCUMENT_SUFFIXES


def _document_priority(path: str) -> tuple[int, str]:
    """让许可证与说明文件先于大量结构化元数据进入上下文预算。"""
    lower = path.lower().strip("/")
    name = lower.rsplit("/", 1)[-1]
    if name.startswith(("license", "copying")):
        rank = 0
    elif name.startswith("readme"):
        rank = 1
    elif name.startswith(("notice", "use_policy", "acceptable_use_policy")):
        rank = 2
    elif Path(name).suffix in {".md", ".txt"}:
        rank = 3
    else:
        rank = 4
    return rank, lower


def _repo_headers(accept: str) -> dict[str, str]:
    headers = {
        "Accept": accept,
        "User-Agent": "KaiYuanLedger-modelscope-adapter/0.1",
    }
    key = api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _request_repo_json(
    url: str,
    params: dict[str, str],
) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    try:
        response = requests.get(
            url,
            headers=_repo_headers("application/json"),
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        return None, str(exc)
    except ValueError as exc:
        return None, f"响应不是 JSON：{exc}"
    if isinstance(payload, dict) and "Data" in payload:
        data = payload.get("Data")
        if isinstance(data, (dict, list)):
            return data, None
        return None, ba.clean_text(payload.get("Message")) or "Data 为空"
    if isinstance(payload, (dict, list)):
        return payload, None
    return None, "响应结构无法识别"


def _file_candidates(data: dict[str, Any] | list[Any] | None) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("Files", "files", "FileList", "file_list", "Items", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _fetch_repo_document(
    ns: str,
    name: str,
    revision: str,
    file_path: str,
) -> str | None:
    try:
        response = requests.get(
            f"{API_BASE}/models/{ns}/{name}/repo",
            headers=_repo_headers("text/plain, text/markdown, application/octet-stream"),
            params={"Revision": revision, "FilePath": file_path},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None
    content = _decode_document(response.content)
    if content and content.lstrip().startswith("{") and '"Data"' in content[:200]:
        try:
            envelope = json.loads(content)
        except ValueError:
            return content
        if isinstance(envelope, dict) and isinstance(envelope.get("Data"), str):
            return envelope["Data"]
    return content


def fetch_source_bundle(
    ns: str,
    name: str,
    revision: str | None = None,
) -> dict[str, Any]:
    """收集 ModelScope 官方详情与文本文件，形成可审计 source_bundle。"""
    detail = fetch_model_detail(ns, name)
    if detail is None:
        raise ValueError(f"ModelScope 未返回模型详情：{ns}/{name}")
    effective_revision = ba.clean_text(revision) or ba.clean_text(detail.get("Revision")) or "master"
    license_value, license_field = license_name_of(detail)
    warnings: list[str] = []
    files_data, warning = _request_repo_json(
        f"{API_BASE}/models/{ns}/{name}/repo/files",
        {"Revision": effective_revision, "Recursive": "true"},
    )
    if warning:
        warnings.append(f"文件清单读取失败：{warning}")
    file_entries = _file_candidates(files_data)
    metadata_by_path = {
        path: item
        for item in file_entries
        if (path := _document_path(item))
    }
    candidates = [
        path
        for item in file_entries
        if (path := _document_path(item)) and _is_auditable_document(path)
    ]
    candidates.sort(key=_document_priority)
    if not candidates:
        candidates = ["LICENSE", "README.md"]
    deduplicated: list[str] = []
    for path in candidates:
        if path not in deduplicated:
            deduplicated.append(path)

    documents: list[dict[str, Any]] = []
    file_facts: list[dict[str, Any]] = []
    for path in deduplicated[:12]:
        content = _fetch_repo_document(ns, name, effective_revision, path)
        if not content:
            warnings.append(f"文件未读取或不是文本：{path}")
            continue
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        metadata = metadata_by_path.get(path)
        metadata = metadata if isinstance(metadata, dict) else {}
        declared_digest = ba.clean_text(metadata.get("Sha256") or metadata.get("sha256"))
        if declared_digest and declared_digest.lower() != digest:
            warnings.append(f"文件 SHA256 与仓库清单不一致：{path}")
        source_url = f"https://www.modelscope.cn/models/{ns}/{name}/file/view/{effective_revision}/{path}"
        documents.append(
            {
                "path": path,
                "content": content,
                "sha256": digest,
                "size": len(content.encode("utf-8")),
                "source_url": source_url,
                "evidence_level": "A",
            }
        )
        file_facts.append(
            {
                "path": path,
                "sha256": digest,
                "size": len(content.encode("utf-8")),
                "declared_sha256": declared_digest or None,
                "sha256_match": (declared_digest.lower() == digest) if declared_digest else None,
            }
        )

    if not any(item.get("path") == "README.md" for item in documents):
        readme = ba.clean_text(detail.get("ReadMeContent"))
        if readme:
            digest = hashlib.sha256(readme.encode("utf-8")).hexdigest()
            documents.append(
                {
                    "path": "README.md",
                    "content": readme,
                    "sha256": digest,
                    "size": len(readme.encode("utf-8")),
                    "source_url": f"https://www.modelscope.cn/models/{ns}/{name}",
                    "source_field": "Data.ReadMeContent",
                    "evidence_level": "A",
                }
            )
            file_facts.append(
                {
                    "path": "README.md",
                    "sha256": digest,
                    "size": len(readme.encode("utf-8")),
                    "source_field": "Data.ReadMeContent",
                }
            )

    try:
        lineage = fetch_lineage(ns, name)
    except Exception as exc:  # noqa: BLE001
        lineage = None
        warnings.append(f"血缘读取失败：{exc}")

    return {
        "schema_version": "modelscope-source-bundle/v1",
        "source": "modelscope",
        "model_id": f"{ns}/{name}",
        "revision": effective_revision,
        "retrieved_at": utc_now(),
        "facts": {
            "license": {
                "value": license_value,
                "source_field": license_field,
                "evidence_level": LICENSE_EVIDENCE_LEVEL if license_value else None,
            },
            "detail": detail,
            "files": file_facts,
            "lineage": lineage,
        },
        "documents": documents,
        "warnings": warnings,
    }
