#!/usr/bin/env python3
"""按名称、版本、生态和有效文件位置对齐资产。"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = BASE_DIR / "outputs" / "assets.json"
DEFAULT_OUTPUT_PATH = BASE_DIR / "outputs" / "assets_deduplicated.json"
DEFAULT_LOG_PATH = BASE_DIR / "outputs" / "merge_log.json"

# 仅这些模型生态允许使用一个明确且狭窄的跨生态别名例外。
MODEL_ALIAS_PURL_TYPES = frozenset({"npm", "pypi", "huggingface"})
URL_REFERENCE_TYPES = frozenset({"website", "distribution", "homepage"})
HASH_ALGORITHM_ALIASES = {
    "sha1": "sha1",
    "sha224": "sha224",
    "sha256": "sha256",
    "sha384": "sha384",
    "sha512": "sha512",
    "md5": "md5",
}
DIGEST_PREFIXES = (
    "sha1:",
    "sha224:",
    "sha256:",
    "sha384:",
    "sha512:",
    "md5:",
    "blake2:",
    "blake3:",
)
NON_PATH_PREFIXES = (
    "http://",
    "https://",
    "urn:",
    "pkg:",
    "layer:",
    "layerid:",
    "layer-id:",
    "container:",
    "container-layer:",
    "docker:",
    "image:",
    "overlayfs:",
)
WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:/")
RELATIVE_FILE_NAME = re.compile(
    r"^[^/\\:*?\"<>|\x00-\x1f]+(?:\.[A-Za-z0-9._-]+){1,4}$"
)
PURL_TYPE = re.compile(r"^pkg:([^/]+)/", re.IGNORECASE)


def load_assets(path: Path) -> list[dict[str, Any]]:
    """读取资产 JSON，并校验顶层结构。"""

    try:
        with path.open("r", encoding="utf-8") as input_file:
            assets = json.load(input_file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"找不到资产文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"资产文件不是合法 JSON：{path}，位置：{exc.pos}"
        ) from exc

    if not isinstance(assets, list):
        raise ValueError(f"资产文件顶层必须是数组：{path}")
    if not all(isinstance(asset, dict) for asset in assets):
        raise ValueError(f"资产数组中的每一项都必须是对象：{path}")
    return assets


def clean_text(value: Any) -> str | None:
    """把字段转换为去除首尾空白的文本；空值返回 None。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_purls(asset: dict[str, Any]) -> list[str]:
    """提取资产的 purl，并保留首次出现顺序。"""

    purls: list[str] = []
    raw_purls = asset.get("purls", [])

    if isinstance(raw_purls, str):
        raw_purls = [raw_purls]
    if isinstance(raw_purls, list):
        for raw_purl in raw_purls:
            purl = clean_text(raw_purl)
            if purl and purl not in purls:
                purls.append(purl)

    fallback_purl = clean_text(asset.get("purl"))
    if fallback_purl and fallback_purl not in purls:
        purls.append(fallback_purl)

    return purls


def purl_type(purl: str) -> str | None:
    """从单个 purl 中提取生态类型。"""

    match = PURL_TYPE.match(purl.strip())
    if not match:
        return None
    return match.group(1).lower()


def extract_purl_types(asset: dict[str, Any]) -> set[str]:
    """提取资产中出现的全部 purl 生态类型。"""

    return {
        purl_type_value
        for purl in extract_purls(asset)
        if (purl_type_value := purl_type(purl)) is not None
    }


def normalize_hash_algorithm(value: Any) -> str | None:
    """统一哈希算法名称，支持 CycloneDX 的连字符写法。"""

    algorithm = clean_text(value)
    if not algorithm:
        return None
    normalized = algorithm.lower().replace("-", "").replace("_", "")
    return HASH_ALGORITHM_ALIASES.get(normalized)


def extract_hashes(asset: dict[str, Any]) -> dict[str, set[str]]:
    """从 evidence_chain 和兼容字段中提取算法到摘要集合的映射。"""

    hashes: dict[str, set[str]] = {}

    def add_hash(raw_hash: Any) -> None:
        if not isinstance(raw_hash, dict):
            return
        algorithm = normalize_hash_algorithm(
            raw_hash.get("algorithm")
            or raw_hash.get("alg")
            or raw_hash.get("hashAlgorithm")
        )
        digest = clean_text(
            raw_hash.get("value")
            or raw_hash.get("content")
            or raw_hash.get("hash")
        )
        if not algorithm or not digest:
            return
        normalized_digest = digest.lower()
        for prefix in (f"{algorithm}:", f"{algorithm.replace('sha', 'sha-')}:"):
            if normalized_digest.startswith(prefix):
                normalized_digest = normalized_digest[len(prefix) :]
                break
        hashes.setdefault(algorithm, set()).add(normalized_digest)

    evidence_chain = asset.get("evidence_chain", [])
    if isinstance(evidence_chain, list):
        for evidence in evidence_chain:
            if not isinstance(evidence, dict):
                continue
            source_field = str(evidence.get("source_field", "")).lower()
            if "hash" in source_field:
                add_hash(evidence.get("raw_value"))

    raw_hashes = asset.get("hashes")
    if isinstance(raw_hashes, list):
        for raw_hash in raw_hashes:
            add_hash(raw_hash)
    return hashes


def common_hashes(
    left_hashes: dict[str, set[str]], right_hashes: dict[str, set[str]]
) -> dict[str, set[str]]:
    """返回双方同算法交集摘要；相同摘要可直接确认同一实体。"""

    return {
        algorithm: left_hashes[algorithm] & right_hashes[algorithm]
        for algorithm in left_hashes.keys() & right_hashes.keys()
        if left_hashes[algorithm] & right_hashes[algorithm]
    }


def has_hash_conflict(
    left_hashes: dict[str, set[str]], right_hashes: dict[str, set[str]]
) -> bool:
    """同算法摘要完全不同时视为冲突，禁止继续使用其他信号合并。"""

    return any(
        not (left_hashes[algorithm] & right_hashes[algorithm])
        for algorithm in left_hashes.keys() & right_hashes.keys()
    )


def normalize_url(value: Any) -> str | None:
    """归一化 homepage/repository URL，忽略 git+、片段和末尾斜线差异。"""

    raw_url = clean_text(value)
    if not raw_url:
        return None
    raw_url = raw_url.lower()
    if raw_url.startswith("git+"):
        raw_url = raw_url[4:]
    parsed = urlsplit(raw_url)
    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    normalized = urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, "")
    ).rstrip("/")
    return normalized or None


def extract_urls(asset: dict[str, Any]) -> set[str]:
    """提取 website、distribution 或 homepage 类型 URL。"""

    urls: set[str] = set()
    homepage = normalize_url(asset.get("homepage"))
    if homepage:
        urls.add(homepage)

    evidence_chain = asset.get("evidence_chain", [])
    if not isinstance(evidence_chain, list):
        return urls
    for evidence in evidence_chain:
        if not isinstance(evidence, dict):
            continue
        source_field = str(evidence.get("source_field", "")).lower()
        raw_value = evidence.get("raw_value")
        if "externalreferences" in source_field and isinstance(raw_value, dict):
            reference_type = clean_text(raw_value.get("type"))
            if reference_type and reference_type.lower() in URL_REFERENCE_TYPES:
                url = normalize_url(raw_value.get("url"))
                if url:
                    urls.add(url)
        elif "homepage" in source_field or "website" in source_field:
            url = normalize_url(raw_value)
            if url:
                urls.add(url)
    return urls


def normalize_person(value: Any) -> str | None:
    """归一化作者文本，仅消除大小写与连续空白差异。"""

    person = clean_text(value)
    if not person:
        return None
    return re.sub(r"\s+", " ", person).casefold()


def extract_authors(asset: dict[str, Any]) -> set[str]:
    """提取 author/maintainer 证据；故意排除 publisher 和 supplier。"""

    authors: set[str] = set()
    evidence_chain = asset.get("evidence_chain", [])
    if not isinstance(evidence_chain, list):
        return authors
    for evidence in evidence_chain:
        if not isinstance(evidence, dict):
            continue
        source_field = str(evidence.get("source_field", "")).lower()
        if not any(token in source_field for token in ("author", "maintainer")):
            continue
        raw_value = evidence.get("raw_value")
        if isinstance(raw_value, dict):
            raw_value = raw_value.get("name")
        author = normalize_person(raw_value)
        if author:
            authors.add(author)
    return authors


def extract_layer_locations(asset: dict[str, Any]) -> set[str]:
    """提取 B 级 layerID，仅用于日志和跳过原因说明。"""

    locations: set[str] = set()
    evidence_chain = asset.get("evidence_chain", [])
    if not isinstance(evidence_chain, list):
        return locations
    for evidence in evidence_chain:
        if not isinstance(evidence, dict):
            continue
        source_field = str(evidence.get("source_field", "")).lower()
        if not any(
            token in source_field
            for token in ("location", "path", "filepath", "layer")
        ):
            continue
        location = normalize_location(evidence.get("raw_value"))
        if location and location.lower().startswith(DIGEST_PREFIXES):
            locations.add(location)
    return locations


def canonical_purl(purl: str) -> str:
    """移除 purl 的限定参数和子路径，得到用于坐标比较的主体。"""

    base = purl.strip().split("#", 1)[0].split("?", 1)[0]
    return unquote(base)


def purl_version(purl: str) -> str | None:
    """在资产 version 缺失时，从 purl 主体中读取版本。"""

    base = canonical_purl(purl)
    last_segment = base.rsplit("/", 1)[-1]
    if "@" not in last_segment:
        return None
    version = last_segment.rsplit("@", 1)[-1].strip()
    return version or None


def effective_version(asset: dict[str, Any]) -> str | None:
    """优先读取 version 字段，缺省时再从 purl 读取版本。"""

    version = clean_text(asset.get("version"))
    if version:
        return version
    for purl in extract_purls(asset):
        version = purl_version(purl)
        if version:
            return version
    return None


def normalize_location(raw_value: Any) -> str | None:
    """归一化文件位置，便于跨记录比较。"""

    location = clean_text(raw_value)
    if not location:
        return None

    location = location.replace("\\", "/")
    lower_location = location.lower()
    if lower_location.startswith("file://"):
        location = location[7:]
        if re.match(r"^/[A-Za-z]:/", location):
            location = location[1:]

    while location.startswith("./"):
        location = location[2:]

    return location.strip() or None


def is_valid_location(location: Any) -> bool:
    """判断位置是否为具体文件路径，而不是 layerID 或摘要标识。"""

    normalized = normalize_location(location)
    if not normalized or len(normalized) > 4096:
        return False

    # 控制字符、换行和常见 URL/URN/层标识都不是文件路径。
    if any(ord(character) < 32 for character in normalized):
        return False
    lower_location = normalized.lower()
    if lower_location.startswith(NON_PATH_PREFIXES):
        return False
    if lower_location.startswith(DIGEST_PREFIXES):
        return False
    if re.match(r"^(sha|md5|blake)[a-z0-9]*[-_:]", lower_location):
        return False

    # 去掉行号锚点后再判断文件部分。
    file_part = normalized.split("#", 1)[0].rstrip()
    if not file_part or file_part in {"/", "\\", "."}:
        return False

    # 裸十六进制摘要通常是镜像层或内容标识，不是路径。
    compact_hex = re.sub(r"[-_:]", "", file_part.lower())
    if re.fullmatch(r"[0-9a-f]{32,}", compact_hex):
        return False

    if file_part.startswith("/") or file_part.startswith("~/"):
        return True
    if WINDOWS_DRIVE_PATH.match(file_part):
        return True

    # 含目录分隔符的字符串按相对路径处理；纯摘要已在前面排除。
    if "/" in file_part:
        file_name = file_part.rstrip("/").rsplit("/", 1)[-1]
        if not file_name:
            return False
        if re.fullmatch(r"[0-9a-f]{32,}", file_name.lower()):
            return False
        return True

    # 接受 model_usage.py#L3、package.json 这类具体文件名。
    return RELATIVE_FILE_NAME.fullmatch(file_part) is not None


def extract_evidence_locations(asset: dict[str, Any]) -> set[str]:
    """提取并通过有效性校验的 evidence 文件位置。"""

    locations: set[str] = set()
    evidence_chain = asset.get("evidence_chain", [])
    if not isinstance(evidence_chain, list):
        return locations

    for evidence in evidence_chain:
        if not isinstance(evidence, dict):
            continue

        source_field = str(evidence.get("source_field", "")).lower()
        if not any(
            token in source_field
            for token in ("occurrence", "location", "path", "filepath")
        ):
            continue

        location = normalize_location(evidence.get("raw_value"))
        if location and is_valid_location(location):
            locations.add(location)

    return locations


def has_license(asset: dict[str, Any]) -> bool:
    """判断资产是否包含非空许可证信息。"""

    return bool(clean_text(asset.get("license")))


def choose_main_asset(assets: list[dict[str, Any]]) -> tuple[int, dict[str, Any]]:
    """选择信息更完整的记录；信息量相同时保留输入顺序。"""

    def score(indexed_asset: tuple[int, dict[str, Any]]) -> tuple[int, int, int, int]:
        index, asset = indexed_asset
        return (
            1 if has_license(asset) else 0,
            len(asset.get("evidence_chain", []))
            if isinstance(asset.get("evidence_chain"), list)
            else 0,
            len(extract_purls(asset)),
            -index,
        )

    return max(enumerate(assets), key=score)


def is_model_alias_bridge(
    left: dict[str, Any],
    right: dict[str, Any],
    left_types: set[str],
    right_types: set[str],
    left_version: str | None,
    right_version: str | None,
    common_locations: set[str],
) -> bool:
    """判断是否命中同模型跨生态别名的窄例外。"""

    if not common_locations or left_version != right_version:
        return False
    if clean_text(left.get("asset_type")) != "model":
        return False
    if clean_text(right.get("asset_type")) != "model":
        return False
    combined_types = left_types | right_types
    return bool(combined_types) and combined_types <= MODEL_ALIAS_PURL_TYPES


def evaluate_pair(
    left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    """判断一对同名资产是否可合并，并返回完整判定结果。"""

    if clean_text(left.get("name")) != clean_text(right.get("name")):
        return {
            "status": "skipped: name_mismatch",
            "confidence": None,
            "basis": None,
            "note": "名称不同，不进入实体对齐。",
        }

    left_purls = set(extract_purls(left))
    right_purls = set(extract_purls(right))
    if not left_purls or not right_purls:
        return {
            "status": "skipped: missing_purl",
            "confidence": None,
            "basis": None,
            "note": "任一方缺少 purl，无法确认生态和包坐标。",
        }

    left_types = extract_purl_types(left)
    right_types = extract_purl_types(right)
    if not left_types or not right_types:
        return {
            "status": "skipped: missing_purl_type",
            "confidence": None,
            "basis": None,
            "note": "任一方 purl 缺少可解析的生态类型。",
        }

    left_version = effective_version(left)
    right_version = effective_version(right)
    left_locations = extract_evidence_locations(left)
    right_locations = extract_evidence_locations(right)
    common_locations = left_locations & right_locations
    left_hashes = extract_hashes(left)
    right_hashes = extract_hashes(right)
    shared_hashes = common_hashes(left_hashes, right_hashes)
    hash_conflict = has_hash_conflict(left_hashes, right_hashes)
    shared_urls = extract_urls(left) & extract_urls(right)
    shared_authors = extract_authors(left) & extract_authors(right)

    # 新信号 1：相同文件哈希可直接确认同一实体；同算法不同摘要必须阻断合并。
    if shared_hashes:
        return {
            "status": "merged",
            "confidence": 1.0,
            "basis": "包哈希相同",
            "note": "双方至少一个哈希算法与摘要完全一致。",
        }
    if hash_conflict:
        return {
            "status": "skipped: hash_conflict",
            "confidence": None,
            "basis": None,
            "note": "同一哈希算法下摘要不同，禁止使用其他信号覆盖冲突。",
        }

    # 新信号 2：website/distribution URL 相同，置信度为 0.95。
    if left_version == right_version and shared_urls:
        return {
            "status": "merged",
            "confidence": 0.95,
            "basis": "homepage或repository URL相同",
            "note": "同版本下存在相同的 website/distribution URL。",
        }

    # 新信号 3：同名、同版本且 author/maintainer 相同，置信度为 0.85。
    if (
        left_version is not None
        and left_version == right_version
        and shared_authors
    ):
        return {
            "status": "merged",
            "confidence": 0.85,
            "basis": "同名+同版本+同author或maintainer",
            "note": "作者字段一致，且名称和版本均相同。",
        }


    # 规则 3：不同 purl type 默认禁止自动合并。
    if left_types.isdisjoint(right_types):
        if is_model_alias_bridge(
            left,
            right,
            left_types,
            right_types,
            left_version,
            right_version,
            common_locations,
        ):
            return {
                "status": "merged",
                "confidence": 0.9,
                "basis": "模型别名跨生态+同名+同版本+相同有效文件位置",
                "note": (
                    "规则 3 的显式窄例外：仅用于同一模型在包生态中的别名，"
                    "且必须存在相同有效文件路径。"
                ),
            }
        return {
            "status": "skipped: cross_ecosystem",
            "confidence": None,
            "basis": None,
            "note": "purl type 不同，按保守规则禁止自动合并。",
        }

    # 版本是 Delta 检测的实体边界；不同版本只允许由完全相同哈希覆盖。
    if left_version != right_version:
        return {
            "status": "skipped: version_mismatch",
            "confidence": None,
            "basis": None,
            "note": "名称相同但版本不同，禁止基于 URL、作者或位置证据合并。",
        }


    # 规则 1：只有通过 is_valid_location 校验的具体文件路径才可用作位置证据。
    if common_locations:
        return {
            "status": "merged",
            "confidence": 0.9,
            "basis": "相同有效文件位置",
            "note": "同名、同版本、同生态且共享具体文件路径。",
        }

    # 相同 purl 主体但位置不同，说明更可能是同一包在不同目录中的多份安装。
    left_canonical = {canonical_purl(purl) for purl in left_purls}
    right_canonical = {canonical_purl(purl) for purl in right_purls}
    if left_canonical & right_canonical:
        return {
            "status": "skipped: no_valid_location_match",
            "confidence": None,
            "basis": None,
            "note": "包坐标相同，但没有共同的具体文件路径证据。",
        }

    # 同名、同版本、同生态但不是同一 purl 时，保留原有的保守名称+版本规则。
    if left_version is not None and right_version is not None:
        return {
            "status": "needs_review",
            "confidence": 0.7,
            "basis": "同名+同版本+同 purl 类型",
            "note": "证据不足，仅进入 0.7-0.85 人工复核区，不自动合并。",
        }

    return {
        "status": "skipped: missing_version",
        "confidence": None,
        "basis": None,
        "note": "双方均无有效版本，且没有共同具体文件路径。",
    }


def merge_assets(
    main_asset: dict[str, Any], merged_asset: dict[str, Any]
) -> dict[str, Any]:
    """把被合并资产的信息并入主记录副本。"""

    result = copy.deepcopy(main_asset)

    combined_purls = extract_purls(main_asset)
    for purl in extract_purls(merged_asset):
        if purl not in combined_purls:
            combined_purls.append(purl)
    result["purls"] = combined_purls

    combined_evidence: list[dict[str, Any]] = []
    seen_evidence: set[str] = set()
    for asset in (main_asset, merged_asset):
        evidence_chain = asset.get("evidence_chain", [])
        if not isinstance(evidence_chain, list):
            continue
        for evidence in evidence_chain:
            if not isinstance(evidence, dict):
                continue
            fingerprint = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
            if fingerprint in seen_evidence:
                continue
            seen_evidence.add(fingerprint)
            combined_evidence.append(copy.deepcopy(evidence))
    result["evidence_chain"] = combined_evidence

    licenses: list[str] = []
    for asset in (main_asset, merged_asset):
        license_text = clean_text(asset.get("license"))
        if not license_text:
            continue
        for item in license_text.split(";"):
            name = item.strip()
            if name and name not in licenses:
                licenses.append(name)
    result["license"] = "; ".join(licenses)

    if not clean_text(result.get("version")):
        result["version"] = merged_asset.get("version", "")

    return result


def purl_log_value(purls: list[str]) -> str | list[str] | None:
    """把 purl 数组转换为日志中易读的值。"""

    if not purls:
        return None
    if len(purls) == 1:
        return purls[0]
    return purls


def build_pair_log_entry(
    left: dict[str, Any],
    right: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    """构造包含合并或跳过原因的完整配对日志。"""

    left_purls = extract_purls(left)
    right_purls = extract_purls(right)
    left_locations = extract_evidence_locations(left)
    right_locations = extract_evidence_locations(right)
    left_hashes = extract_hashes(left)
    right_hashes = extract_hashes(right)
    shared_hashes = common_hashes(left_hashes, right_hashes)
    left_urls = extract_urls(left)
    right_urls = extract_urls(right)
    left_authors = extract_authors(left)
    right_authors = extract_authors(right)
    left_layer_locations = extract_layer_locations(left)
    right_layer_locations = extract_layer_locations(right)
    return {
        "name": clean_text(left.get("name")),
        "kept_asset_id": clean_text(left.get("canonical_id")),
        "merged_asset_id": clean_text(right.get("canonical_id")),
        "kept_source_file": clean_text(left.get("source_file")),
        "merged_source_file": clean_text(right.get("source_file")),
        "asset_type": clean_text(left.get("asset_type")),
        "asset_type_left": clean_text(left.get("asset_type")),
        "asset_type_right": clean_text(right.get("asset_type")),
        "kept_purl": purl_log_value(left_purls),
        "merged_purl": purl_log_value(right_purls),
        "kept_purl_types": sorted(extract_purl_types(left)),
        "merged_purl_types": sorted(extract_purl_types(right)),
        "kept_version": effective_version(left),
        "merged_version": effective_version(right),
        "kept_hashes": {
            algorithm: sorted(values)
            for algorithm, values in sorted(left_hashes.items())
        },
        "merged_hashes": {
            algorithm: sorted(values)
            for algorithm, values in sorted(right_hashes.items())
        },
        "common_hashes": {
            algorithm: sorted(values)
            for algorithm, values in sorted(shared_hashes.items())
        },
        "kept_urls": sorted(left_urls),
        "merged_urls": sorted(right_urls),
        "common_urls": sorted(left_urls & right_urls),
        "kept_authors": sorted(left_authors),
        "merged_authors": sorted(right_authors),
        "common_authors": sorted(left_authors & right_authors),
        "kept_locations": sorted(left_locations),
        "merged_locations": sorted(right_locations),
        "common_valid_locations": sorted(left_locations & right_locations),
        "kept_layer_locations": sorted(left_layer_locations),
        "merged_layer_locations": sorted(right_layer_locations),
        "kept_location_level": (
            "A" if left_locations else ("B" if left_layer_locations else "C")
        ),
        "merged_location_level": (
            "A" if right_locations else ("B" if right_layer_locations else "C")
        ),
        "auto_merge": decision["status"] == "merged",
        "review_required": decision["status"] == "needs_review",
        "status": decision["status"],
        "confidence": decision["confidence"],
        "basis": decision["basis"],
        "note": decision["note"],
    }


def deduplicate_assets(
    assets: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """执行资产对齐，并返回去重结果与逐对判定日志。"""

    indices_by_name: dict[str, list[int]] = {}
    for index, asset in enumerate(assets):
        name = clean_text(asset.get("name")) or ""
        indices_by_name.setdefault(name, []).append(index)

    dropped_indices: set[int] = set()
    merged_by_main_index: dict[int, dict[str, Any]] = {}
    merge_log: list[dict[str, Any]] = []

    for name, indices in indices_by_name.items():
        if len(indices) < 2:
            continue

        # 先对本组所有原始记录两两判定，再用并查集处理传递关系。
        parent = list(range(len(indices)))

        def find(position: int) -> int:
            while parent[position] != position:
                parent[position] = parent[parent[position]]
                position = parent[position]
            return position

        def union(left_position: int, right_position: int) -> None:
            left_root = find(left_position)
            right_root = find(right_position)
            if left_root != right_root:
                parent[right_root] = left_root

        pair_decisions: list[tuple[int, int, dict[str, Any]]] = []
        for left_position in range(len(indices)):
            for right_position in range(left_position + 1, len(indices)):
                left_index = indices[left_position]
                right_index = indices[right_position]
                left_asset = assets[left_index]
                right_asset = assets[right_index]
                decision = evaluate_pair(left_asset, right_asset)
                pair_decisions.append((left_position, right_position, decision))
                merge_log.append(
                    build_pair_log_entry(left_asset, right_asset, decision)
                )
                if decision["status"] == "merged":
                    union(left_position, right_position)

        positions_by_root: dict[int, list[int]] = {}
        for position in range(len(indices)):
            positions_by_root.setdefault(find(position), []).append(position)

        for positions in positions_by_root.values():
            if len(positions) < 2:
                continue

            component_assets = [assets[indices[position]] for position in positions]
            main_position, main_asset = choose_main_asset(component_assets)
            main_asset_index = indices[positions[main_position]]
            result_asset = copy.deepcopy(main_asset)

            for position in positions:
                index = indices[position]
                if index == main_asset_index:
                    continue
                result_asset = merge_assets(result_asset, assets[index])
                dropped_indices.add(index)

            merged_by_main_index[main_asset_index] = result_asset

    deduplicated: list[dict[str, Any]] = []
    for index, asset in enumerate(assets):
        if index in merged_by_main_index:
            deduplicated.append(merged_by_main_index[index])
        elif index not in dropped_indices:
            deduplicated.append(asset)

    return deduplicated, merge_log


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 和两个空格缩进写出 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(value, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="合并跨生态同名资产")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    return parser.parse_args()


def main() -> None:
    """执行实体对齐并输出结果。"""

    args = parse_args()
    assets = load_assets(args.input)
    deduplicated, merge_log = deduplicate_assets(assets)

    write_json(args.output, deduplicated)
    write_json(args.log, merge_log)

    merged_entries = [
        entry for entry in merge_log if entry["status"] == "merged"
    ]
    review_entries = [
        entry for entry in merge_log if entry["status"] == "needs_review"
    ]
    skipped_entries = [
        entry for entry in merge_log
        if entry["status"] not in {"merged", "needs_review"}
    ]
    confidence_distribution = Counter(
        str(entry["confidence"]) for entry in merged_entries
    )
    skip_distribution = Counter(
        str(entry["status"]) for entry in skipped_entries
    )

    print(f"读取资产：{args.input}")
    print(f"资产数量：{len(assets)} -> {len(deduplicated)}")
    print(f"同名配对总数：{len(merge_log)}")
    print(f"合并对数：{len(merged_entries)}")
    print(f"需人工复核对数：{len(review_entries)}")
    print(f"跳过对数：{len(skipped_entries)}")
    print(
        "置信度分布："
        + (
            "，".join(
                f"{confidence}={count}"
                for confidence, count in sorted(
                    confidence_distribution.items(),
                    reverse=True,
                )
            )
            or "无"
        )
    )
    print(
        "跳过原因分布："
        + (
            "，".join(
                f"{reason}={count}"
                for reason, count in sorted(skip_distribution.items())
            )
            or "无"
        )
    )
    print(f"去重结果：{args.output}")
    print(f"配对日志：{args.log}")


if __name__ == "__main__":
    # 在 Windows 终端中显式使用 UTF-8，避免中文提示乱码。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
