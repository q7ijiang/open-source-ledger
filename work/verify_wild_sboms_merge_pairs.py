#!/usr/bin/env python3
"""用官方包源独立核验 Wild SBOMs 中实际触发的跨生态合并对。"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import requests


BASE_DIR = Path(__file__).resolve().parents[1]
VALIDATION_PATH = BASE_DIR / "outputs" / "wild_sboms_merge_validation.json"
OUTPUT_PATH = BASE_DIR / "outputs" / "wild_sboms_independent_verification.json"
USER_AGENT = "open-source-ledger-wild-sboms-verifier/1.0"
REQUEST_TIMEOUT_SECONDS = 45
PURL_PATTERN = re.compile(r"^pkg:([^/]+)/(.+)$", re.IGNORECASE)


def clean_text(value: Any) -> str | None:
    """把值转成去首尾空白的非空文本。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_list(value: Any) -> list[Any]:
    """把单值、空值和数组统一成列表。"""

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def parse_purl(purl: str) -> dict[str, str | None]:
    """解析核验所需的 purl 类型、包名和版本。"""

    match = PURL_PATTERN.match(purl.strip())
    if match is None:
        raise ValueError(f"无法解析 purl：{purl}")

    purl_type = match.group(1).lower()
    coordinate = match.group(2).split("#", 1)[0].split("?", 1)[0]
    if "@" in coordinate:
        package_part, version = coordinate.rsplit("@", 1)
    else:
        package_part, version = coordinate, None

    package_part = unquote(package_part)
    if "/" in package_part:
        namespace, package_name = package_part.rsplit("/", 1)
    else:
        namespace, package_name = None, package_part

    full_name = f"{namespace}/{package_name}" if namespace else package_name
    return {
        "type": purl_type,
        "namespace": namespace,
        "name": unquote(package_name),
        "full_name": unquote(full_name),
        "version": unquote(version) if version else None,
        "purl": purl,
    }


def normalize_url(value: Any) -> str | None:
    """只保留 URL 字符串，并去掉 git+ 前缀和末尾斜线。"""

    text = clean_text(value)
    if not text:
        return None
    if text.startswith("git+"):
        text = text[4:]
    parsed = urlsplit(text)
    if not parsed.scheme or not parsed.netloc:
        return None
    path = parsed.path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def repository_identity(value: Any) -> str | None:
    """提取用于比较的代码仓库身份，特别处理 GitHub 大小写和别名。"""

    normalized = normalize_url(value)
    if not normalized:
        return None
    parsed = urlsplit(normalized)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")
    if host in {"github.com", "www.github.com"}:
        parts = path.split("/")
        if len(parts) >= 2:
            return f"github.com/{parts[0].lower()}/{parts[1].lower()}"
    return normalized.lower()


def extract_urls(value: Any) -> set[str]:
    """递归提取 metadata 中的 URL。"""

    urls: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            urls.update(extract_urls(item))
    elif isinstance(value, list):
        for item in value:
            urls.update(extract_urls(item))
    elif isinstance(value, str):
        candidate = clean_text(value)
        if candidate and "://" in candidate:
            urls.add(candidate)
    return urls


def request_json(
    session: requests.Session,
    url: str,
    response_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """请求官方 JSON API；同一 URL 在一次运行内只访问一次。"""

    if url in response_cache:
        return response_cache[url]

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    record: dict[str, Any] = {
        "状态码": response.status_code,
        "最终URL": response.url,
        "内容类型": response.headers.get("content-type"),
    }
    if response.status_code == 200:
        try:
            record["数据"] = response.json()
        except ValueError:
            record["错误"] = "响应不是合法 JSON"
    else:
        record["错误"] = response.text[:500]
    response_cache[url] = record
    return record


def npm_evidence(
    session: requests.Session,
    parsed: dict[str, str | None],
    response_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """查询 npm 官方 registry。"""

    name = parsed["full_name"]
    version = parsed["version"]
    if not name or not version:
        return {"来源": "npm", "结论": "WRONG", "原因": "purl 缺少包名或版本"}

    url = f"https://registry.npmjs.org/{quote(name, safe='')}/{quote(version, safe='')}"
    response = request_json(session, url, response_cache)
    data = response.get("数据") or {}
    actual_name = clean_text(data.get("name"))
    actual_version = clean_text(data.get("version"))
    repository_urls = extract_urls(data.get("repository"))
    homepage_urls = extract_urls(data.get("homepage"))
    authors = extract_urls(data.get("author")) | extract_urls(data.get("maintainers"))
    author_names = set()
    for author_value in as_list(data.get("author")) + as_list(data.get("maintainers")):
        if isinstance(author_value, dict) and clean_text(author_value.get("name")):
            author_names.add(clean_text(author_value.get("name")))
        elif clean_text(author_value):
            author_names.add(clean_text(author_value))

    return {
        "来源": "npm官方registry",
        "API链接": url,
        "HTTP状态": response.get("状态码"),
        "预期包名": name,
        "实际包名": actual_name,
        "预期版本": version,
        "实际版本": actual_version,
        "名称匹配": actual_name == name,
        "版本匹配": actual_version == version,
        "仓库URL": sorted(repository_urls),
        "主页URL": sorted(homepage_urls),
        "作者": sorted(author_names),
    }


def composer_evidence(
    session: requests.Session,
    parsed: dict[str, str | None],
    response_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """查询 Packagist 官方 Composer 元数据源。"""

    name = parsed["full_name"]
    version = parsed["version"]
    if not name or "/" not in name or not version:
        return {"来源": "Packagist", "结论": "WRONG", "原因": "purl 缺少作者/包名或版本"}

    vendor, package_name = name.split("/", 1)
    url = f"https://repo.packagist.org/p2/{vendor}/{package_name}.json"
    response = request_json(session, url, response_cache)
    data = response.get("数据") or {}
    versions = data.get("packages", {}).get(name, [])
    selected = next(
        (item for item in versions if clean_text(item.get("version")) == version),
        None,
    )
    if selected is None:
        return {
            "来源": "Packagist官方元数据",
            "API链接": url,
            "HTTP状态": response.get("状态码"),
            "预期包名": name,
            "预期版本": version,
            "名称匹配": False,
            "版本匹配": False,
            "错误": "未找到指定版本",
        }

    repository_urls = extract_urls(selected.get("source")) | extract_urls(
        selected.get("support")
    )
    homepage_urls = extract_urls(selected.get("homepage"))
    authors = {
        clean_text(item.get("name"))
        for item in as_list(selected.get("authors"))
        if isinstance(item, dict) and clean_text(item.get("name"))
    }
    return {
        "来源": "Packagist官方元数据",
        "API链接": url,
        "HTTP状态": response.get("状态码"),
        "预期包名": name,
        "实际包名": clean_text(selected.get("name")),
        "预期版本": version,
        "实际版本": clean_text(selected.get("version")),
        "名称匹配": clean_text(selected.get("name")) == name,
        "版本匹配": clean_text(selected.get("version")) == version,
        "仓库URL": sorted(repository_urls),
        "主页URL": sorted(homepage_urls),
        "作者": sorted(author for author in authors if author),
        "是否废弃": selected.get("abandoned"),
    }


def pypi_evidence(
    session: requests.Session,
    parsed: dict[str, str | None],
    response_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """查询 PyPI 官方 JSON API，供未来含 pypi 的样本复用。"""

    name = parsed["full_name"]
    version = parsed["version"]
    if not name or not version:
        return {"来源": "PyPI", "结论": "WRONG", "原因": "purl 缺少包名或版本"}
    url = f"https://pypi.org/pypi/{quote(name, safe='')}/{quote(version, safe='')}/json"
    response = request_json(session, url, response_cache)
    data = response.get("数据") or {}
    info = data.get("info") or {}
    return {
        "来源": "PyPI官方API",
        "API链接": url,
        "HTTP状态": response.get("状态码"),
        "预期包名": name,
        "实际包名": clean_text(info.get("name")),
        "预期版本": version,
        "实际版本": clean_text(info.get("version")),
        "名称匹配": clean_text(info.get("name", "")).lower().replace("_", "-")
        == name.lower().replace("_", "-"),
        "版本匹配": clean_text(info.get("version")) == version,
        "仓库URL": sorted(extract_urls(info.get("project_urls"))),
        "主页URL": sorted(extract_urls(info.get("home_page"))),
        "作者": [
            author
            for author in (
                clean_text(info.get("author")),
                clean_text(info.get("maintainer")),
            )
            if author
        ],
    }


def debian_evidence(
    session: requests.Session,
    parsed: dict[str, str | None],
    response_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """查询 Debian sources 官方 API，供未来含 deb 的样本复用。"""

    name = parsed["full_name"]
    version = parsed["version"]
    if not name:
        return {"来源": "Debian sources", "结论": "WRONG", "原因": "purl 缺少包名"}
    url = f"https://sources.debian.org/api/src/{quote(name, safe='')}/"
    response = request_json(session, url, response_cache)
    data = response.get("数据") or {}
    versions = {
        clean_text(item.get("version"))
        for item in as_list(data.get("versions"))
        if isinstance(item, dict)
    }
    return {
        "来源": "Debian sources官方API",
        "API链接": url,
        "HTTP状态": response.get("状态码"),
        "预期包名": name,
        "预期版本": version,
        "版本匹配": version in versions if version else None,
        "可用版本": sorted(item for item in versions if item),
        "仓库URL": ["https://sources.debian.org/src/" + name + "/"],
        "主页URL": [],
        "作者": [],
    }


def verify_provider(
    session: requests.Session,
    parsed: dict[str, str | None],
    response_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """根据 purl 类型路由到对应官方数据源。"""

    purl_type = parsed["type"]
    if purl_type == "npm":
        evidence = npm_evidence(session, parsed, response_cache)
    elif purl_type == "composer":
        evidence = composer_evidence(session, parsed, response_cache)
    elif purl_type == "pypi":
        evidence = pypi_evidence(session, parsed, response_cache)
    elif purl_type in {"deb", "dpkg"}:
        evidence = debian_evidence(session, parsed, response_cache)
    else:
        evidence = {
            "来源": purl_type,
            "结论": "SUSPECT",
            "原因": "当前核验脚本未配置该生态的官方 API",
        }
    evidence["purl"] = parsed["purl"]
    evidence["purl类型"] = purl_type
    return evidence


def normalize_repo_set(evidence: dict[str, Any]) -> set[str]:
    """把证据中的仓库 URL 转成可比较的仓库身份集合。"""

    identities: set[str] = set()
    for url in evidence.get("仓库URL") or []:
        identity = repository_identity(url)
        if identity:
            identities.add(identity)
    return identities


def fetch_manifest(
    session: requests.Session,
    repository_url: str,
    version: str,
    file_name: str,
    response_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """读取指定 git tag 中的 package 清单，用于检查双生态是否同源。"""

    identity = (
        repository_url
        if repository_url.startswith("github.com/")
        else repository_identity(repository_url)
    )
    if not identity or not identity.startswith("github.com/"):
        return {"状态": "不适用", "原因": "共同仓库不是 GitHub"}

    owner_repo = identity.removeprefix("github.com/")
    url = f"https://raw.githubusercontent.com/{owner_repo}/{quote(version, safe='')}/{file_name}"
    response = request_json(session, url, response_cache)
    data = response.get("数据")
    return {
        "URL": url,
        "HTTP状态": response.get("状态码"),
        "是否JSON": isinstance(data, dict),
        "name": data.get("name") if isinstance(data, dict) else None,
        "version": data.get("version") if isinstance(data, dict) else None,
    }


def verify_unique_pair(
    session: requests.Session,
    pair: dict[str, Any],
    response_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """核验一个去重后的跨生态合并关系。"""

    components = [pair["组件A"], pair["组件B"]]
    parsed_components = [parse_purl(component["purl"][0]) for component in components]
    provider_evidence = [
        verify_provider(session, parsed, response_cache) for parsed in parsed_components
    ]

    name_matches = all(item.get("名称匹配") for item in provider_evidence)
    version_matches = all(item.get("版本匹配") for item in provider_evidence)
    repo_sets = [normalize_repo_set(item) for item in provider_evidence]
    common_repositories = set.intersection(*repo_sets) if all(repo_sets) else set()

    manifest_checks: list[dict[str, Any]] = []
    if common_repositories and version_matches:
        common_repo = sorted(common_repositories)[0]
        version = parsed_components[0].get("version") or ""
        manifest_checks = [
            fetch_manifest(session, common_repo, version, "package.json", response_cache),
            fetch_manifest(session, common_repo, version, "composer.json", response_cache),
        ]

    manifests_match = all(
        any(
            item.get("是否JSON")
            and clean_text(item.get("name")) == clean_text(provider.get("预期包名"))
            and (
                clean_text(item.get("version")) == clean_text(provider.get("预期版本"))
                or (
                    provider.get("purl类型") == "composer"
                    and item.get("version") is None
                )
            )
            for item in manifest_checks
        )
        for provider in provider_evidence
        if provider.get("预期包名")
    )

    if not name_matches or not version_matches:
        verdict = "WRONG"
        reason = "至少一个官方包源中的名称或版本与 purl 不匹配"
    elif not common_repositories:
        verdict = "WRONG"
        reason = "两个官方包源没有指向同一个代码仓库"
    elif manifests_match:
        verdict = "CONFIRMED"
        reason = "npm 与 Composer 官方元数据同版本、同仓库，且 git tag 同时包含双生态同源清单"
    else:
        verdict = "SUSPECT"
        reason = "官方包源同版本同仓库，但 git tag 双清单复核不完整"

    evidence_links = [
        item.get("API链接")
        for item in provider_evidence
        if item.get("API链接")
    ]
    evidence_links.extend(item.get("URL") for item in manifest_checks if item.get("URL"))
    for identity in sorted(common_repositories):
        if identity.startswith("github.com/"):
            owner_repo = identity.removeprefix("github.com/")
            evidence_links.append(f"https://api.github.com/repos/{owner_repo}")

    return {
        "name": pair.get("name"),
        "去重键": "|".join(
            sorted(str(component.get("purl")) for component in components)
        ),
        "出现文件数": pair.get("出现文件数"),
        "出现文件": pair.get("出现文件") or [],
        "组件A": components[0],
        "组件B": components[1],
        "官方源证据": provider_evidence,
        "共同仓库身份": sorted(common_repositories),
        "gitTag清单核验": manifest_checks,
        "结论": verdict,
        "判定原因": reason,
        "证据链接": evidence_links,
    }


def pair_signature(pair: dict[str, Any]) -> tuple[str, ...]:
    """生成跨文件重复合并关系的去重键。"""

    values = [str(pair["组件A"]["purl"]), str(pair["组件B"]["purl"])]
    return tuple(sorted(values))


def main() -> int:
    """读取验证抽样，执行官方源核验并输出中文 JSON 结果。"""

    started_at = time.perf_counter()
    validation = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
    sampled_pairs = validation.get("随机抽样核验对") or []

    unique_pairs: dict[tuple[str, ...], dict[str, Any]] = {}
    record_to_signature: list[tuple[dict[str, Any], tuple[str, ...]]] = []
    for pair in sampled_pairs:
        signature = pair_signature(pair)
        record_to_signature.append((pair, signature))
        unique_pairs.setdefault(
            signature,
            {
                "name": pair.get("name"),
                "组件A": pair.get("组件A"),
                "组件B": pair.get("组件B"),
                "出现文件数": 0,
                "出现文件": [],
            },
        )
        unique_pairs[signature]["出现文件数"] += 1
        unique_pairs[signature]["出现文件"].append(pair.get("文件"))

    session = requests.Session()
    response_cache: dict[str, dict[str, Any]] = {}
    verified_unique_pairs = [
        verify_unique_pair(session, pair, response_cache)
        for pair in unique_pairs.values()
    ]
    verdict_by_signature = {
        item["去重键"]: item["结论"] for item in verified_unique_pairs
    }

    record_verdicts: list[dict[str, Any]] = []
    for pair, signature in record_to_signature:
        record_verdicts.append(
            {
                "文件": pair.get("文件"),
                "组件A": pair.get("组件A"),
                "组件B": pair.get("组件B"),
                "去重键": "|".join(signature),
                "结论": verdict_by_signature.get("|".join(signature)),
            }
        )

    unique_counts = Counter(item["结论"] for item in verified_unique_pairs)
    record_counts = Counter(item["结论"] for item in record_verdicts)
    requested_source_coverage = {
        "npm官方registry": "已使用" if any(
            item.get("purl类型") == "npm"
            for pair in verified_unique_pairs
            for item in pair["官方源证据"]
        )
        else "本样本不适用",
        "PyPI官方API": "已使用" if any(
            item.get("purl类型") == "pypi"
            for pair in verified_unique_pairs
            for item in pair["官方源证据"]
        )
        else "本样本不适用",
        "Debian sources官方API": "已使用" if any(
            item.get("purl类型") in {"deb", "dpkg"}
            for pair in verified_unique_pairs
            for item in pair["官方源证据"]
        )
        else "本样本不适用",
        "Packagist官方元数据": "已使用" if any(
            item.get("purl类型") == "composer"
            for pair in verified_unique_pairs
            for item in pair["官方源证据"]
        )
        else "本样本不适用",
    }

    result = {
        "验证输入": str(VALIDATION_PATH.resolve()),
        "抽样来源": validation.get("第三方核验候选池"),
        "原始抽样记录数": len(sampled_pairs),
        "去重后独立跨生态关系数": len(verified_unique_pairs),
        "说明": (
            f"原始抽样中的 {len(sampled_pairs)} 条记录去重后为 "
            f"{len(verified_unique_pairs)} 个独立关系，因此独立证据只核验一次；"
            "记录级计数会因文件重复而放大。"
        ),
        "用户指定官方源覆盖": requested_source_coverage,
        "去重关系判定计数": {
            "CONFIRMED": unique_counts["CONFIRMED"],
            "SUSPECT": unique_counts["SUSPECT"],
            "WRONG": unique_counts["WRONG"],
        },
        "记录级判定计数": {
            "CONFIRMED": record_counts["CONFIRMED"],
            "SUSPECT": record_counts["SUSPECT"],
            "WRONG": record_counts["WRONG"],
        },
        "去重关系核验": verified_unique_pairs,
        "原始记录判定": record_verdicts,
        "网络请求数": len(response_cache),
        "核验耗时秒": round(time.perf_counter() - started_at, 3),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"原始抽样记录：{len(sampled_pairs)}")
    print(f"去重独立关系：{len(verified_unique_pairs)}")
    print(f"去重关系判定：{result['去重关系判定计数']}")
    print(f"记录级判定：{result['记录级判定计数']}")
    print(f"输出：{OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
