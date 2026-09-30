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
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from bom_adapter import (
    PurlIdentity,
    build_asset_identifiers,
    parse_purl_identity,
)


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = BASE_DIR / "outputs" / "assets.json"
DEFAULT_OUTPUT_PATH = BASE_DIR / "outputs" / "assets_deduplicated.json"
DEFAULT_LOG_PATH = BASE_DIR / "outputs" / "merge_log.json"
RULE_VERSION = "merge-policy-v2"
# URL 类型覆盖 homepage 与 repository 等标准外部引用。
PAIR_STATUSES = {
    "AUTO_MERGE",
    "REVIEW",
    "KEEP_SEPARATE",
    "UNDETERMINED",
}
MERGE_STATUS_BY_DECISION = {
    "AUTO_MERGE": "MERGED",
    "REVIEW": "REVIEW",
    "KEEP_SEPARATE": "KEPT_SEPARATE",
    "UNDETERMINED": "UNDETERMINED",
}

URL_REFERENCE_TYPES = frozenset(
    {"website", "distribution", "homepage", "repository", "vcs"}
)
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


def compare_hashes(
    left_hashes: dict[str, set[str]], right_hashes: dict[str, set[str]]
) -> tuple[dict[str, set[str]], dict[str, dict[str, list[str]]]]:
    """同时返回共享摘要和冲突摘要，避免共享命中覆盖同算法冲突。"""

    shared: dict[str, set[str]] = {}
    conflicts: dict[str, dict[str, list[str]]] = {}
    for algorithm in left_hashes.keys() & right_hashes.keys():
        left_values = left_hashes[algorithm]
        right_values = right_hashes[algorithm]
        common_values = left_values & right_values
        if common_values:
            shared[algorithm] = common_values

        # 同一算法出现任一侧独有摘要，就保留为冲突证据。
        if left_values != right_values:
            conflicts[algorithm] = {
                "left_only": sorted(left_values - right_values),
                "right_only": sorted(right_values - left_values),
            }
    return shared, conflicts


def common_hashes(
    left_hashes: dict[str, set[str]], right_hashes: dict[str, set[str]]
) -> dict[str, set[str]]:
    """兼容旧日志调用，只返回双方同算法交集摘要。"""

    shared, _ = compare_hashes(left_hashes, right_hashes)
    return shared


def has_hash_conflict(
    left_hashes: dict[str, set[str]], right_hashes: dict[str, set[str]]
) -> bool:
    """兼容旧调用；同算法摘要集合不完全相同时视为冲突。"""

    _, conflicts = compare_hashes(left_hashes, right_hashes)
    return bool(conflicts)


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

    # purl 是统一身份层的坐标源，版本冲突时以 purl 版本为准。
    for purl in extract_purls(asset):
        version = purl_version(purl)
        if version:
            return version
    return clean_text(asset.get("version"))


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
    evidence_signals = {
        str(evidence.get("signal"))
        for evidence in decision.get("supporting_evidence", [])
        if isinstance(evidence, dict)
    }
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
        "auto_merge": decision["status"] in {"merged", "AUTO_MERGE"},
        "review_required": decision["status"] in {"needs_review", "REVIEW"},
        "status": decision["status"],
        "confidence": decision["confidence"],
        "basis": decision["basis"],
        "note": decision["note"],
        "merge_status": MERGE_STATUS_BY_DECISION[decision["status"]],
        "reason_code": decision["reason_code"],
        "rule_version": decision["rule_version"],
        "supporting_evidence": decision["supporting_evidence"],
        "conflicting_evidence": decision["conflicting_evidence"],
        "triggered_by_url_or_author": bool(
            evidence_signals & {"url", "author"}
        ),
        "veto_edge": bool(
            decision["status"] == "KEEP_SEPARATE"
            or decision["conflicting_evidence"]
        ),
    }


def candidate_group_keys(asset: dict[str, Any]) -> set[str]:
    """生成候选分组键；保留同名不同 namespace，供护栏判定。"""

    asset_type = clean_text(asset.get("asset_type")) or ""
    name = clean_text(asset.get("name"))
    keys: set[str] = set()
    if name:
        keys.add(f"name:{asset_type}:{name.casefold()}")
    for identity in purl_identities_for_asset(asset):
        keys.add(
            f"purl-name:{asset_type}:{identity.purl_type}:{identity.name.casefold()}"
        )
    return keys


def candidate_pairs(assets: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """按名称和规范化 purl 名称生成去重候选对。"""

    indices_by_key: dict[str, list[int]] = {}
    for index, asset in enumerate(assets):
        for key in candidate_group_keys(asset):
            indices_by_key.setdefault(key, []).append(index)

    pairs: set[tuple[int, int]] = set()
    for indices in indices_by_key.values():
        if len(indices) < 2:
            continue
        for left_position, left_index in enumerate(indices):
            for right_index in indices[left_position + 1 :]:
                pairs.add((min(left_index, right_index), max(left_index, right_index)))
    return sorted(pairs)


def pair_decision_priority(entry: dict[str, Any]) -> tuple[int, str]:
    """为分量摘要选择最保守且最具体的代表边。"""

    reason_code = str(entry.get("reason_code") or "")
    if reason_code.startswith("HASH_") or reason_code == "PURL_COORDINATE_EXACT":
        priority = 0
    elif reason_code.startswith("COMMON_VALID_LOCATION"):
        priority = 1
    else:
        priority = 2
    return priority, str(entry.get("kept_asset_id"))


def canonical_id_suffix(asset: dict[str, Any]) -> str:
    """为极端冲突输出可解释且确定的 purl 坐标后缀。"""

    identities = purl_identities_for_asset(asset)
    if identities:
        return identities[0].coordinate_suffix
    asset_type = clean_text(asset.get("asset_type")) or "unknown"
    name = clean_text(asset.get("name")) or "unnamed"
    version = effective_version(asset)
    return f"{asset_type}/{name}" + (f"@{version}" if version else "")


def ensure_unique_canonical_ids(assets: list[dict[str, Any]]) -> None:
    """对未合并但 canonical_id 相同的极端情况追加确定后缀。"""

    used_ids: set[str] = set()
    for asset in assets:
        canonical_id = clean_text(asset.get("canonical_id"))
        if not canonical_id or canonical_id not in used_ids:
            if canonical_id:
                used_ids.add(canonical_id)
            continue

        suffix = quote(canonical_id_suffix(asset), safe="/:@._-")
        candidate = f"{canonical_id}#purl={suffix}"
        occurrence = 2
        while candidate in used_ids:
            candidate = f"{canonical_id}#purl={suffix}#{occurrence}"
            occurrence += 1
        asset["canonical_id"] = candidate
        asset["canonical_id_disambiguation"] = {
            "base_canonical_id": canonical_id,
            "suffix": suffix,
            "reason": "same canonical id without an auto-mergeable conflict resolution",
        }
        used_ids.add(candidate)


def deduplicate_assets(
    assets: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """执行受限传递对齐，并返回去重结果与逐对判定日志。"""

    candidate_index_pairs = candidate_pairs(assets)
    parent = list(range(len(assets)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left_index: int, right_index: int) -> None:
        left_root = find(left_index)
        right_root = find(right_index)
        if left_root != right_root:
            parent[right_root] = left_root

    pair_log: dict[tuple[int, int], dict[str, Any]] = {}
    for pair in candidate_index_pairs:
        left_index, right_index = pair
        decision = evaluate_pair(assets[left_index], assets[right_index])
        pair_log[pair] = build_pair_log_entry(
            assets[left_index], assets[right_index], decision
        )
        if decision["status"] == "AUTO_MERGE":
            union(left_index, right_index)

    positions_by_root: dict[int, list[int]] = {}
    for index in range(len(assets)):
        positions_by_root.setdefault(find(index), []).append(index)

    dropped_indices: set[int] = set()
    merged_by_main_index: dict[int, dict[str, Any]] = {}
    status_by_index: dict[int, str] = {
        index: "KEPT_SEPARATE" for index in range(len(assets))
    }
    reason_by_index: dict[int, str] = {}

    for component_index, positions in enumerate(
        sorted(positions_by_root.values(), key=lambda values: values[0]), start=1
    ):
        if len(positions) < 2:
            continue

        # 自动分量内补齐所有原始配对，确保 A-B、B-C 时仍检查 A-C 冲突。
        for left_position, left_index in enumerate(positions):
            for right_index in positions[left_position + 1 :]:
                pair = (min(left_index, right_index), max(left_index, right_index))
                if pair in pair_log:
                    continue
                decision = evaluate_pair(assets[pair[0]], assets[pair[1]])
                pair_log[pair] = build_pair_log_entry(
                    assets[pair[0]], assets[pair[1]], decision
                )

        component_pairs = [
            pair
            for pair in pair_log
            if pair[0] in positions and pair[1] in positions
        ]
        component_entries = [pair_log[pair] for pair in component_pairs]
        auto_entries = [
            entry for entry in component_entries if entry["status"] == "AUTO_MERGE"
        ]
        conflicting_entries = [
            entry for entry in component_entries if entry["veto_edge"]
        ]
        component_auto_folded = bool(auto_entries) and not conflicting_entries
        component_status = (
            "MERGED"
            if component_auto_folded
            else ("REVIEW" if conflicting_entries else "KEPT_SEPARATE")
        )
        minimum_support = min(auto_entries, key=pair_decision_priority) if auto_entries else None
        component_summary = {
            "component_id": f"component-{component_index}",
            "component_size": len(positions),
            "component_auto_folded": component_auto_folded,
            "component_status": component_status,
            "component_min_support_edge": (
                {
                    "left": minimum_support["kept_asset_id"],
                    "right": minimum_support["merged_asset_id"],
                    "reason_code": minimum_support["reason_code"],
                }
                if minimum_support
                else None
            ),
            "component_conflicting_edges": [
                {
                    "left": entry["kept_asset_id"],
                    "right": entry["merged_asset_id"],
                    "reason_code": entry["reason_code"],
                }
                for entry in conflicting_entries
            ],
            "component_review_triggered_by_url_or_author": any(
                entry["triggered_by_url_or_author"] for entry in component_entries
            ),
        }
        for entry in component_entries:
            entry.update(component_summary)

        if component_auto_folded:
            component_assets = [assets[index] for index in positions]
            main_position, main_asset = choose_main_asset(component_assets)
            main_asset_index = positions[main_position]
            result_asset = copy.deepcopy(main_asset)
            for index in positions:
                if index == main_asset_index:
                    continue
                result_asset = merge_assets(result_asset, assets[index])
                dropped_indices.add(index)
            result_asset["merge_status"] = "MERGED"
            result_asset["reason_code"] = (
                minimum_support["reason_code"] if minimum_support else "AUTO_MERGE"
            )
            result_asset["rule_version"] = RULE_VERSION
            result_asset["merge_component_id"] = component_summary["component_id"]
            merged_by_main_index[main_asset_index] = result_asset
            for index in positions:
                status_by_index[index] = "MERGED"
                reason_by_index[index] = result_asset["reason_code"]
        elif conflicting_entries:
            for index in positions:
                status_by_index[index] = "REVIEW"
                reason_by_index[index] = conflicting_entries[0]["reason_code"]

    for pair, entry in pair_log.items():
        for index in pair:
            if status_by_index[index] == "MERGED":
                continue
            if entry["status"] == "REVIEW":
                status_by_index[index] = "REVIEW"
                reason_by_index.setdefault(index, entry["reason_code"])
            elif entry["status"] == "UNDETERMINED" and status_by_index[index] == "KEPT_SEPARATE":
                status_by_index[index] = "UNDETERMINED"
                reason_by_index.setdefault(index, entry["reason_code"])
            elif entry["status"] == "KEEP_SEPARATE":
                if status_by_index[index] != "REVIEW":
                    status_by_index[index] = "KEPT_SEPARATE"
                reason_by_index.setdefault(index, entry["reason_code"])

    deduplicated: list[dict[str, Any]] = []
    for index, asset in enumerate(assets):
        if index in dropped_indices:
            continue
        if index in merged_by_main_index:
            deduplicated.append(merged_by_main_index[index])
            continue
        output_asset = copy.deepcopy(asset)
        output_asset["merge_status"] = status_by_index[index]
        output_asset["reason_code"] = reason_by_index.get(index, "NO_MERGE_CANDIDATE")
        output_asset["rule_version"] = RULE_VERSION
        deduplicated.append(output_asset)

    ensure_unique_canonical_ids(deduplicated)
    merge_log = [pair_log[pair] for pair in sorted(pair_log)]
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

    status_distribution = Counter(entry["status"] for entry in merge_log)
    reason_distribution = Counter(entry["reason_code"] for entry in merge_log)
    asset_status_distribution = Counter(
        str(asset.get("merge_status")) for asset in deduplicated
    )

    print(f"读取资产：{args.input}")
    print(f"资产数量：{len(assets)} -> {len(deduplicated)}")
    print(f"候选配对总数：{len(merge_log)}")
    for status in ("AUTO_MERGE", "REVIEW", "KEEP_SEPARATE", "UNDETERMINED"):
        print(f"{status}：{status_distribution.get(status, 0)}")
    print(
        "资产合并状态分布："
        + "，".join(
            f"{status}={asset_status_distribution.get(status, 0)}"
            for status in ("MERGED", "REVIEW", "KEPT_SEPARATE", "UNDETERMINED")
        )
    )
    print(
        "原因码分布："
        + (
            "，".join(
                f"{reason}={count}"
                for reason, count in sorted(reason_distribution.items())
            )
            or "无"
        )
    )
    print(f"去重结果：{args.output}")
    print(f"配对日志：{args.log}")


def make_decision(
    status: str,
    reason_code: str,
    note: str,
    *,
    supporting_evidence: list[dict[str, Any]] | None = None,
    conflicting_evidence: list[dict[str, Any]] | None = None,
    confidence: float | None = None,
    basis: str | None = None,
) -> dict[str, Any]:
    """构造统一决策对象；confidence 仅用于旧接口兼容。"""

    if status not in PAIR_STATUSES:
        raise ValueError(f"未知合并状态：{status}")
    return {
        "status": status,
        "reason_code": reason_code,
        "supporting_evidence": supporting_evidence or [],
        "conflicting_evidence": conflicting_evidence or [],
        "rule_version": RULE_VERSION,
        "confidence": confidence,
        "basis": basis or reason_code,
        "note": note,
    }


def purl_identities_for_asset(asset: dict[str, Any]) -> list[PurlIdentity]:
    """解析资产全部 purl，忽略无法解析的脏值。"""

    identities: list[PurlIdentity] = []
    for purl in extract_purls(asset):
        identity = parse_purl_identity(purl)
        if identity is not None:
            identities.append(identity)
    return identities


def purl_identity_evidence(identity: PurlIdentity) -> dict[str, Any]:
    """把 purl 四元组转成日志可序列化对象。"""

    return {
        "signal": "purl",
        "type": identity.purl_type,
        "namespace": identity.namespace,
        "name": identity.name,
        "version": identity.version,
    }


def identity_name_compatible(
    left: dict[str, Any],
    right: dict[str, Any],
    left_identities: list[PurlIdentity],
    right_identities: list[PurlIdentity],
    exact_identity_matches: list[tuple[PurlIdentity, PurlIdentity]],
    same_nonempty_version: bool,
) -> bool:
    """名称兼容时允许比较；purl 规范化名称相同可覆盖原始名称差异。"""

    left_name = clean_text(left.get("name"))
    right_name = clean_text(right.get("name"))
    if left_name and right_name and left_name.casefold() == right_name.casefold():
        return True
    if same_nonempty_version and exact_identity_matches:
        return True
    return any(
        left_identity.purl_type == right_identity.purl_type
        and left_identity.name == right_identity.name
        for left_identity in left_identities
        for right_identity in right_identities
    )


def evaluate_pair(
    left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    """按确定性决策表判断一对资产，不再使用硬编码分数控制结果。"""

    left_types = extract_purl_types(left)
    right_types = extract_purl_types(right)
    left_identities = purl_identities_for_asset(left)
    right_identities = purl_identities_for_asset(right)
    left_version = effective_version(left)
    right_version = effective_version(right)
    same_version = (
        left_version is not None
        and right_version is not None
        and left_version == right_version
    )
    version_mismatch = (
        left_version is not None
        and right_version is not None
        and left_version != right_version
    )

    exact_identity_matches = [
        (left_identity, right_identity)
        for left_identity in left_identities
        for right_identity in right_identities
        if left_identity.coordinate == right_identity.coordinate
    ]

    if not identity_name_compatible(
        left,
        right,
        left_identities,
        right_identities,
        exact_identity_matches,
        same_version,
    ):
        return make_decision(
            "KEEP_SEPARATE",
            "NAME_MISMATCH",
            "名称及规范化 purl 名称均不一致，确定为不同实体。",
            conflicting_evidence=[{"signal": "name"}],
            confidence=0.0,
        )

    if clean_text(left.get("asset_type")) != clean_text(right.get("asset_type")):
        return make_decision(
            "KEEP_SEPARATE",
            "ASSET_TYPE_MISMATCH",
            "资产类型不同，保持为不同节点。",
            conflicting_evidence=[{"signal": "asset_type"}],
            confidence=0.0,
        )

    left_locations = extract_evidence_locations(left)
    right_locations = extract_evidence_locations(right)
    common_locations = left_locations & right_locations
    left_hashes = extract_hashes(left)
    right_hashes = extract_hashes(right)
    shared_hashes, hash_conflicts = compare_hashes(left_hashes, right_hashes)
    shared_urls = extract_urls(left) & extract_urls(right)
    shared_authors = extract_authors(left) & extract_authors(right)

    hash_support = [
        {"signal": "hash", "algorithm": algorithm, "digests": sorted(digests)}
        for algorithm, digests in sorted(shared_hashes.items())
    ]
    hash_conflict_evidence = [
        {
            "signal": "hash_conflict",
            "algorithm": algorithm,
            "left_only": details["left_only"],
            "right_only": details["right_only"],
        }
        for algorithm, details in sorted(hash_conflicts.items())
    ]

    # Bug 1：冲突证据优先，绝不因另一算法命中而覆盖冲突。
    if hash_conflict_evidence:
        return make_decision(
            "REVIEW",
            "HASH_CONFLICT",
            "同算法同时存在共享摘要和不同摘要，进入人工复核。",
            supporting_evidence=hash_support,
            conflicting_evidence=hash_conflict_evidence,
            confidence=0.8,
        )

    if hash_support:
        if version_mismatch:
            return make_decision(
                "REVIEW",
                "HASH_MATCH_VERSION_MISMATCH",
                "哈希相同但版本不同，进入人工复核。",
                supporting_evidence=hash_support,
                conflicting_evidence=[
                    {
                        "signal": "version",
                        "left": left_version,
                        "right": right_version,
                    }
                ],
                confidence=0.8,
            )
        if not left_identities and not right_identities:
            return make_decision(
                "AUTO_MERGE",
                "HASH_MATCH_WITHOUT_PURL",
                "无 purl 时相同包哈希可确认同一实体。",
                supporting_evidence=hash_support,
                confidence=1.0,
            )
        if not same_version:
            return make_decision(
                "REVIEW",
                "HASH_MATCH_VERSION_UNKNOWN",
                "哈希相同但版本缺失，进入人工复核。",
                supporting_evidence=hash_support,
                conflicting_evidence=[{"signal": "version_missing"}],
                confidence=0.85,
            )
        return make_decision(
            "AUTO_MERGE",
            "HASH_MATCH_SAME_VERSION",
            "同算法哈希相同且版本相同，确认同一实体。",
            supporting_evidence=hash_support,
            confidence=1.0,
        )

    if exact_identity_matches:
        exact_evidence = [
            purl_identity_evidence(left_identity)
            for left_identity, _ in exact_identity_matches
        ]
        has_versioned_identity = any(
            left_identity.version is not None
            for left_identity, _ in exact_identity_matches
        )
        if has_versioned_identity and not version_mismatch:
            return make_decision(
                "AUTO_MERGE",
                "PURL_COORDINATE_EXACT",
                "purl 四元坐标完全相同，确认同一实体。",
                supporting_evidence=exact_evidence,
                confidence=1.0,
            )
        if common_locations:
            return make_decision(
                "AUTO_MERGE",
                "PURL_COORDINATE_UNVERSIONED_WITH_LOCATION",
                "purl 坐标相同且存在共同文件路径，确认同一实体。",
                supporting_evidence=exact_evidence + [
                    {"signal": "location", "paths": sorted(common_locations)}
                ],
                confidence=0.9,
            )
        return make_decision(
            "REVIEW",
            "PURL_COORDINATE_UNVERSIONED",
            "purl 坐标相同但缺少版本和共同路径，进入人工复核。",
            supporting_evidence=exact_evidence,
            conflicting_evidence=[{"signal": "version_missing"}],
            confidence=0.8,
        )

    if version_mismatch:
        return make_decision(
            "KEEP_SEPARATE",
            "VERSION_MISMATCH",
            "双方版本均为非空且不同，确定为不同版本节点。",
            conflicting_evidence=[
                {
                    "signal": "version",
                    "left": left_version,
                    "right": right_version,
                }
            ],
            confidence=0.0,
        )

    cross_ecosystem = bool(
        left_types and right_types and left_types.isdisjoint(right_types)
    )
    same_ecosystem = bool(left_types & right_types)

    if cross_ecosystem:
        if shared_urls:
            return make_decision(
                "REVIEW",
                "CROSS_ECOSYSTEM_URL_REVIEW",
                "跨生态组件仅共享 URL，只能进入人工复核。",
                supporting_evidence=[
                    {"signal": "url", "values": sorted(shared_urls)}
                ],
                conflicting_evidence=[
                    {
                        "signal": "ecosystem",
                        "left": sorted(left_types),
                        "right": sorted(right_types),
                    }
                ],
                confidence=0.85,
            )
        if shared_authors:
            return make_decision(
                "REVIEW",
                "CROSS_ECOSYSTEM_AUTHOR_REVIEW",
                "跨生态组件仅共享作者字段，只能进入人工复核。",
                supporting_evidence=[
                    {"signal": "author", "values": sorted(shared_authors)}
                ],
                conflicting_evidence=[
                    {
                        "signal": "ecosystem",
                        "left": sorted(left_types),
                        "right": sorted(right_types),
                    }
                ],
                confidence=0.8,
            )
        return make_decision(
            "KEEP_SEPARATE",
            "CROSS_ECOSYSTEM_DEFAULT",
            "跨生态默认不合并，且没有 URL 或 author 复核信号。",
            conflicting_evidence=[
                {
                    "signal": "ecosystem",
                    "left": sorted(left_types),
                    "right": sorted(right_types),
                }
            ],
            confidence=0.0,
        )

    if common_locations:
        if same_version and left_identities and right_identities and same_ecosystem:
            return make_decision(
                "AUTO_MERGE",
                "COMMON_VALID_LOCATION_SAME_VERSION",
                "同生态、同版本且存在共同有效文件路径，确认合并。",
                supporting_evidence=[
                    {"signal": "location", "paths": sorted(common_locations)},
                    {"signal": "version", "value": left_version},
                ],
                confidence=0.9,
            )
        return make_decision(
            "REVIEW",
            "COMMON_VALID_LOCATION_REVIEW",
            "存在共同文件路径，但版本或 purl 信息不足，进入人工复核。",
            supporting_evidence=[
                {"signal": "location", "paths": sorted(common_locations)}
            ],
            conflicting_evidence=[
                {"signal": "version_or_purl_missing"}
            ],
            confidence=0.85,
        )

    if shared_urls:
        url_evidence = [{"signal": "url", "values": sorted(shared_urls)}]
        if not left_identities and not right_identities and same_version:
            return make_decision(
                "AUTO_MERGE",
                "URL_SAME_VERSION_WITHOUT_PURL",
                "无 purl 且 URL、版本均相同，确认合并。",
                supporting_evidence=url_evidence
                + [{"signal": "version", "value": left_version}],
                confidence=0.95,
            )
        return make_decision(
            "REVIEW",
            "URL_SHARED_REVIEW",
            "URL 是中等信号，只能进入人工复核。",
            supporting_evidence=url_evidence,
            confidence=0.85,
        )

    if shared_authors:
        return make_decision(
            "REVIEW",
            "AUTHOR_SHARED_REVIEW",
            "author/maintainer 是中等信号，只能进入人工复核。",
            supporting_evidence=[
                {"signal": "author", "values": sorted(shared_authors)}
            ],
            confidence=0.8,
        )

    if not left_identities and not right_identities:
        if same_version:
            return make_decision(
                "UNDETERMINED",
                "NO_PURL_NAME_VERSION_ONLY",
                "只有 name 和 version 相同，缺少其他可验证信号。",
                supporting_evidence=[
                    {"signal": "name", "value": clean_text(left.get("name"))},
                    {"signal": "version", "value": left_version},
                ],
                confidence=None,
            )
        return make_decision(
            "UNDETERMINED",
            "NAME_ONLY_OR_VERSION_MISSING",
            "只有 name 相同或版本缺失，信息不足，不合并。",
            supporting_evidence=[
                {"signal": "name", "value": clean_text(left.get("name"))}
            ],
            conflicting_evidence=[{"signal": "version_or_purl_missing"}],
            confidence=None,
        )

    if same_version and same_ecosystem:
        return make_decision(
            "REVIEW",
            "SAME_ECOSYSTEM_VERSION_ONLY",
            "同生态且同名同版本，但没有共同路径、URL 或作者证据，进入人工复核。",
            supporting_evidence=[{"signal": "version", "value": left_version}],
            confidence=0.7,
        )

    return make_decision(
        "UNDETERMINED",
        "SAME_ECOSYSTEM_INSUFFICIENT_EVIDENCE",
        "生态相同但版本或其他身份信号不足，不自动合并。",
        conflicting_evidence=[{"signal": "version_missing"}],
        confidence=None,
    )


if __name__ == "__main__":
    # 在 Windows 终端中显式使用 UTF-8，避免中文提示乱码。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
