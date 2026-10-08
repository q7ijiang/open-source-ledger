# -*- coding: utf-8 -*-
"""为资产补充 PyPI、npm 和 Hugging Face 远程证据。

输入为 entity_resolver.py 的 assets_deduplicated.json，也兼容 bom_adapter.py
直接生成的 assets.json。脚本遵循以下降级策略：

* 官方 API 返回许可证时追加 A 级证据；
* API 返回成功但没有许可证字段时追加 A 级 missing 证据；
* 请求失败时追加 C 级 network_error 证据；
* 原有 evidence_chain 始终保留；
* 没有任何 purl 且原证据为空时，追加 C 级 missing 证据，保证证据链非空。

所有请求超时固定为 3 秒，断网时不会中断整个流程。

用法：
    python evidence_enricher.py --input outputs/assets_deduplicated.json \
                                --output outputs/assets_enriched.json
"""

from __future__ import annotations

import argparse
import copy
import json
import socket
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = BASE_DIR / "outputs" / "assets_deduplicated.json"
DEFAULT_OUTPUT_PATH = BASE_DIR / "outputs" / "assets_enriched.json"
REQUEST_TIMEOUT_SECONDS = 3.0
SUPPORTED_PURL_TYPES = {"pypi", "npm", "huggingface"}


def load_assets(path: Path) -> list[dict[str, Any]]:
    """读取资产数组，并兼容 assets / nodes 包装。"""

    try:
        with path.open("r", encoding="utf-8") as input_file:
            data = json.load(input_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"找不到资产文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"资产文件不是合法 JSON：{path}，位置：{exc.pos}") from exc

    if isinstance(data, dict):
        data = data.get("assets", data.get("nodes"))
    if not isinstance(data, list):
        raise ValueError(f"资产文件顶层必须是数组，或包含 assets/nodes 数组：{path}")
    if not all(isinstance(asset, dict) for asset in data):
        raise ValueError(f"资产数组中的每一项都必须是对象：{path}")
    return data


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 和两空格缩进写出 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(value, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def clean_text(value: Any) -> str | None:
    """把值转换为去除首尾空白后的文本；空值返回 None。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_list(value: Any) -> list[Any]:
    """把单个值或列表统一为列表。"""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def utc_now() -> str:
    """返回符合接口约定的 ISO 8601 UTC 时间。"""

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_purl(purl: str) -> dict[str, str] | None:
    """解析项目支持的 purl，返回类型、包名、版本和请求 URL。"""

    value = clean_text(purl)
    if not value or not value.lower().startswith("pkg:"):
        return None

    value = value.split("#", 1)[0].split("?", 1)[0]
    remainder = value[4:]
    if "/" not in remainder:
        return None

    purl_type, package_part = remainder.split("/", 1)
    purl_type = purl_type.lower()
    if purl_type not in SUPPORTED_PURL_TYPES:
        return None

    version = ""
    if "@" in package_part:
        package_part, version = package_part.rsplit("@", 1)
    package_name = unquote(package_part).strip("/")
    if not package_name:
        return None

    if purl_type == "pypi":
        source_url = f"https://pypi.org/pypi/{quote(package_name, safe='.-_')}/json"
    elif purl_type == "npm":
        encoded_name = quote(package_name, safe="@")
        source_url = f"https://registry.npmjs.org/{encoded_name}"
    else:
        encoded_name = quote(package_name, safe="/")
        source_url = f"https://huggingface.co/api/models/{encoded_name}"

    return {
        "source_api": purl_type,
        "package_name": package_name,
        "version": version,
        "source_url": source_url,
    }


def is_meaningful_value(value: Any) -> bool:
    """判断许可证值是否包含有效内容。"""

    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().upper()
        return bool(normalized) and normalized not in {
            "UNKNOWN",
            "NONE",
            "NOASSERTION",
            "NOT FOUND",
        }
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def license_from_classifiers(classifiers: Any) -> str | None:
    """从 PyPI classifiers 中提取许可证名称。"""

    for classifier in as_list(classifiers):
        text = clean_text(classifier)
        if text and text.startswith("License :: OSI Approved ::"):
            return text.rsplit("::", 1)[-1].strip()
    return None


def extract_pypi_license(
    payload: dict[str, Any],
) -> tuple[str, Any, str]:
    """提取 PyPI 许可证字段。"""

    info = payload.get("info")
    if not isinstance(info, dict):
        return "info.license", None, "missing"

    expression = info.get("license_expression")
    if is_meaningful_value(expression):
        return "info.license_expression", expression, "ok"

    license_value = info.get("license")
    if is_meaningful_value(license_value):
        return "info.license", license_value, "ok"

    classifier_license = license_from_classifiers(info.get("classifiers"))
    if classifier_license:
        return "info.classifiers", classifier_license, "ok"

    return "info.license", license_value, "missing"


def extract_npm_license(
    payload: dict[str, Any], version: str
) -> tuple[str, Any, str]:
    """提取 npm 元数据中的许可证字段。"""

    license_value = payload.get("license")
    if is_meaningful_value(license_value):
        return "license", license_value, "ok"

    licenses = payload.get("licenses")
    if is_meaningful_value(licenses):
        return "licenses", licenses, "ok"

    versions = payload.get("versions")
    if isinstance(versions, dict):
        selected_version = version or payload.get("dist-tags", {}).get("latest")
        version_payload = versions.get(str(selected_version))
        if isinstance(version_payload, dict):
            version_license = version_payload.get("license")
            if is_meaningful_value(version_license):
                return f"versions.{selected_version}.license", version_license, "ok"
            version_licenses = version_payload.get("licenses")
            if is_meaningful_value(version_licenses):
                return f"versions.{selected_version}.licenses", version_licenses, "ok"

    return "license", license_value, "missing"


def extract_huggingface_license(
    payload: dict[str, Any],
) -> tuple[str, Any, str]:
    """提取 Hugging Face cardData.license 或 tags 中的许可证。"""

    card_data = payload.get("cardData")
    if isinstance(card_data, dict):
        license_value = card_data.get("license")
        if is_meaningful_value(license_value):
            return "cardData.license", license_value, "ok"

    for tag in as_list(payload.get("tags")):
        text = clean_text(tag)
        if text and text.lower().startswith("license:"):
            return "tags", text.split(":", 1)[1], "ok"

    license_value = payload.get("license")
    if is_meaningful_value(license_value):
        return "license", license_value, "ok"
    return "cardData.license", license_value, "missing"


def extract_license(
    source_api: str,
    payload: dict[str, Any],
    version: str,
) -> tuple[str, Any, str]:
    """按 API 类型提取许可证。"""

    if source_api == "pypi":
        return extract_pypi_license(payload)
    if source_api == "npm":
        return extract_npm_license(payload, version)
    return extract_huggingface_license(payload)


def request_json(url: str, timeout: float) -> dict[str, Any]:
    """请求 JSON，并校验响应顶层是否为对象。"""

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "KaiYuanLedger-evidence-enricher/0.1",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("API 响应顶层不是 JSON 对象")
    return payload


def network_error_message(exc: BaseException) -> str:
    """把网络异常转换为便于写入证据链的简短信息。"""

    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "请求超时（3 秒）"
    if isinstance(exc, URLError):
        return f"网络错误：{exc.reason}"
    return f"{type(exc).__name__}: {exc}"


def fetch_remote_evidence(
    target: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    """调用单个远程 API，失败时返回 C 级网络错误证据。"""

    source_api = target["source_api"]
    source_url = target["source_url"]
    retrieved_at = utc_now()
    try:
        payload = request_json(source_url, timeout)
        source_field, raw_value, status = extract_license(
            source_api,
            payload,
            target.get("version", ""),
        )
        return {
            "evidence_level": "A",
            "source_api": source_api,
            "source_url": source_url,
            "source_field": source_field,
            "retrieved_at": retrieved_at,
            "status": status,
            "raw_value": raw_value,
        }
    except Exception as exc:  # 单个请求失败不能中断整批任务
        return {
            "evidence_level": "C",
            "source_api": source_api,
            "source_url": source_url,
            "source_field": "网络请求",
            "retrieved_at": retrieved_at,
            "status": "network_error",
            "raw_value": network_error_message(exc),
        }


def evidence_fingerprint(evidence: dict[str, Any]) -> str:
    """生成忽略抓取时间的证据去重指纹。"""

    stable_fields = {
        "evidence_level": evidence.get("evidence_level"),
        "source_api": evidence.get("source_api"),
        "source_url": evidence.get("source_url"),
        "source_field": evidence.get("source_field"),
        "status": evidence.get("status"),
        "raw_value": evidence.get("raw_value"),
    }
    return json.dumps(stable_fields, ensure_ascii=False, sort_keys=True)


def local_fallback_evidence() -> dict[str, Any]:
    """为没有 purl 且没有证据的资产生成 C 级本地降级证据。"""

    return {
        "evidence_level": "C",
        "source_api": "cyclonedx",
        "source_url": None,
        "source_field": "purls",
        "retrieved_at": utc_now(),
        "status": "missing",
        "raw_value": "资产没有受支持的 purl，无法执行远程证据补全",
    }


def enrich_asset(
    asset: dict[str, Any],
    timeout: float,
) -> tuple[dict[str, Any], dict[str, int]]:
    """补全单个资产，并返回本次新增证据的统计。"""

    result = copy.deepcopy(asset)
    evidence_chain = result.get("evidence_chain")
    if not isinstance(evidence_chain, list):
        evidence_chain = []
    else:
        evidence_chain = list(evidence_chain)

    existing_fingerprints = {
        evidence_fingerprint(entry)
        for entry in evidence_chain
        if isinstance(entry, dict)
    }
    stats = Counter(
        {
            "supported_purls": 0,
            "requests": 0,
            "remote_ok": 0,
            "remote_missing": 0,
            "network_error": 0,
            "fallback_added": 0,
        }
    )

    seen_purls: set[str] = set()
    for raw_purl in as_list(result.get("purls")):
        purl = clean_text(raw_purl)
        if not purl or purl in seen_purls:
            continue
        seen_purls.add(purl)

        target = parse_purl(purl)
        if not target:
            continue

        stats["supported_purls"] += 1
        stats["requests"] += 1
        evidence = fetch_remote_evidence(target, timeout)
        if evidence["status"] == "ok":
            stats["remote_ok"] += 1
        elif evidence["status"] == "network_error":
            stats["network_error"] += 1
        else:
            stats["remote_missing"] += 1

        fingerprint = evidence_fingerprint(evidence)
        if fingerprint not in existing_fingerprints:
            evidence_chain.append(evidence)
            existing_fingerprints.add(fingerprint)

    if not evidence_chain:
        evidence_chain.append(local_fallback_evidence())
        stats["fallback_added"] = 1

    result["evidence_chain"] = evidence_chain
    return result, dict(stats)


def enrich_assets(
    assets: list[dict[str, Any]],
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """补全全部资产，并汇总统计。"""

    enriched_assets: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()
    by_api: Counter[str] = Counter()
    assets_without_evidence_before = 0
    assets_with_new_remote = 0

    for asset in assets:
        before_chain = asset.get("evidence_chain")
        if not isinstance(before_chain, list) or not before_chain:
            assets_without_evidence_before += 1

        enriched, stats = enrich_asset(asset, timeout)
        enriched_assets.append(enriched)
        totals.update(stats)

        remote_added = stats["remote_ok"] + stats["remote_missing"] + stats["network_error"]
        if remote_added:
            assets_with_new_remote += 1
            for purl in asset.get("purls", []):
                target = parse_purl(clean_text(purl) or "")
                if target:
                    by_api[target["source_api"]] += 1

    assets_without_evidence_after = sum(
        1
        for asset in enriched_assets
        if not isinstance(asset.get("evidence_chain"), list)
        or not asset.get("evidence_chain")
    )
    summary = {
        "assets": len(assets),
        "supported_purls": totals["supported_purls"],
        "requests": totals["requests"],
        "remote_ok": totals["remote_ok"],
        "remote_missing": totals["remote_missing"],
        "network_error": totals["network_error"],
        "fallback_added": totals["fallback_added"],
        "assets_without_evidence_before": assets_without_evidence_before,
        "assets_with_new_remote": assets_with_new_remote,
        "assets_without_evidence_after": assets_without_evidence_after,
        "by_api": dict(sorted(by_api.items())),
    }
    return enriched_assets, summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="补全资产远程证据链")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """执行远程证据补全并输出统计。"""

    args = parse_args(argv)
    assets = load_assets(args.input)
    enriched, summary = enrich_assets(assets, REQUEST_TIMEOUT_SECONDS)
    write_json(args.output, enriched)

    print(f"读取资产：{args.input}（{summary['assets']} 个）")
    print(f"受支持的 purl：{summary['supported_purls']} 个")
    print(f"远程请求：{summary['requests']} 次")
    print(f"补全 A 级许可证证据：{summary['remote_ok']} 条")
    print(f"官方 API 成功但许可证缺失：{summary['remote_missing']} 条")
    print(f"网络失败降级为 C 级：{summary['network_error']} 条")
    print(f"无 purl 的本地降级证据：{summary['fallback_added']} 条")
    print(f"按 API 请求分布：{summary['by_api']}")
    print(f"处理前无证据资产：{summary['assets_without_evidence_before']} 个")
    print(f"处理后无证据资产：{summary['assets_without_evidence_after']} 个")
    print(f"证据输出：{args.output}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
