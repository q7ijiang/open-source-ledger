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

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import bom_adapter as ba


API_BASE = "https://www.modelscope.cn/api/v1"
REQUEST_TIMEOUT_SECONDS = 20.0
RULE_VERSION = "merge-policy-v2"

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
