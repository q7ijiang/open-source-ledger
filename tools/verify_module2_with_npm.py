#!/usr/bin/env python3
"""查询 npm 官方 registry，对模块 2 的 50 对抽样合并做独立核验。"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
SAMPLE_PATH = BASE_DIR / "work" / "module2_verification_sample_50.json"
RESOLVER_PATH = BASE_DIR / "entity_resolver.py"
EVIDENCE_PATH = BASE_DIR / "work" / "module2_npm_registry_evidence.json"
RESULT_PATH = BASE_DIR / "work" / "module2_verification_results_50.json"
USER_AGENT = "msu-sbom-module2-verification/1.0"


def load_module(module_name: str, module_path: Path) -> Any:
    """按文件路径加载实体对齐器中的 URL 和文本规范化函数。"""

    specification = importlib.util.spec_from_file_location(module_name, module_path)
    if specification is None or specification.loader is None:
        raise ImportError(f"无法加载模块：{module_path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def write_json(path: Path, value: Any) -> None:
    """以 UTF-8 写出可审计 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_npm_canonical(canonical_purl: str) -> tuple[str, str]:
    """从 npm 规范 purl 中提取包名和版本。"""

    prefix = "pkg:npm/"
    if not canonical_purl.startswith(prefix):
        raise ValueError(f"不是 npm purl：{canonical_purl}")
    body = canonical_purl[len(prefix) :]
    if "@" not in body:
        raise ValueError(f"purl 缺少版本：{canonical_purl}")
    name, version = body.rsplit("@", 1)
    return name, version


def registry_api_url(name: str, version: str) -> str:
    """构造 npm registry 的版本级官方 JSON URL。"""

    encoded_name = urllib.parse.quote(name, safe="")
    encoded_version = urllib.parse.quote(version, safe="")
    return f"https://registry.npmjs.org/{encoded_name}/{encoded_version}"


def registry_page_url(name: str, version: str) -> str:
    """构造 npm 官方网站的可读版本页面 URL。"""

    encoded_name = urllib.parse.quote(name, safe="@")
    encoded_version = urllib.parse.quote(version, safe="")
    return f"https://www.npmjs.com/package/{encoded_name}/v/{encoded_version}"


def fetch_json(url: str, timeout: int = 25) -> dict[str, Any]:
    """访问官方 JSON API，并清楚记录 HTTP 或网络错误。"""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    last_error: dict[str, Any] = {}
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                return {
                    "成功": True,
                    "HTTP状态": response.status,
                    "最终URL": response.geturl(),
                    "数据": json.loads(body.decode("utf-8")),
                    "错误": None,
                    "尝试次数": attempt,
                }
        except urllib.error.HTTPError as exc:
            last_error = {
                "HTTP状态": exc.code,
                "最终URL": exc.geturl(),
                "错误": f"HTTPError: {exc}",
            }
            # HTTP 4xx 通常不会因重试恢复，直接返回；5xx 和网络错误继续重试。
            if 400 <= exc.code < 500:
                break
        except Exception as exc:
            last_error = {
                "HTTP状态": None,
                "最终URL": url,
                "错误": f"{type(exc).__name__}: {exc}",
            }
        if attempt < 3:
            time.sleep(attempt * 2)
    return {
        "成功": False,
        "HTTP状态": last_error.get("HTTP状态"),
        "最终URL": last_error.get("最终URL", url),
        "数据": None,
        "错误": last_error.get("错误", "未知网络错误"),
        "尝试次数": 3,
    }


def trim_registry_record(data: dict[str, Any]) -> dict[str, Any]:
    """保留核验所需字段，避免把 npm 签名等大字段写入结果。"""

    dist = data.get("dist")
    if not isinstance(dist, dict):
        dist = {}
    return {
        "name": data.get("name"),
        "version": data.get("version"),
        "description": data.get("description"),
        "homepage": data.get("homepage"),
        "repository": data.get("repository"),
        "author": data.get("author"),
        "maintainers": data.get("maintainers"),
        "license": data.get("license"),
        "keywords": data.get("keywords"),
        "dist": {
            "shasum": dist.get("shasum"),
            "integrity": dist.get("integrity"),
            "tarball": dist.get("tarball"),
            "fileCount": dist.get("fileCount"),
            "unpackedSize": dist.get("unpackedSize"),
        },
        "_npmUser": data.get("_npmUser"),
    }


def normalize_person_name(value: Any) -> str | None:
    """归一化姓名或邮箱，用于比较 registry 和 SBOM 作者。"""

    if value is None:
        return None
    text = str(value).strip().casefold()
    text = re.sub(r"\s+", " ", text)
    return text or None


def registry_people(record: dict[str, Any]) -> list[dict[str, str]]:
    """提取所有官方 author/maintainer 姓名和邮箱。"""

    people: list[dict[str, str]] = []
    for key in ("author", "_npmUser"):
        value = record.get(key)
        if isinstance(value, dict):
            person = {
                "role": key,
                "name": normalize_person_name(value.get("name")) or "",
                "email": normalize_person_name(value.get("email")) or "",
            }
            if person["name"] or person["email"]:
                people.append(person)
    for raw_maintainer in record.get("maintainers") or []:
        if not isinstance(raw_maintainer, dict):
            continue
        person = {
            "role": "maintainer",
            "name": normalize_person_name(raw_maintainer.get("name")) or "",
            "email": normalize_person_name(raw_maintainer.get("email")) or "",
        }
        if person["name"] or person["email"]:
            people.append(person)
    return people


def registry_urls(record: dict[str, Any], resolver: Any) -> set[str]:
    """提取并归一化官方 homepage 和 repository URL。"""

    urls: set[str] = set()
    homepage = resolver.normalize_url(record.get("homepage"))
    if homepage:
        urls.add(homepage)
    repository = record.get("repository")
    if isinstance(repository, dict):
        repository_url = resolver.normalize_url(repository.get("url"))
    else:
        repository_url = resolver.normalize_url(repository)
    if repository_url:
        urls.add(repository_url)
    return urls


def evaluate_pair(
    pair: dict[str, Any],
    registry_by_purl: dict[str, dict[str, Any]],
    resolver: Any,
) -> dict[str, Any]:
    """按官方 registry 事实对一对合并给出独立结论。"""

    purl_a = pair["规范purlA"][0]
    purl_b = pair["规范purlB"][0]
    evidence_a = registry_by_purl[purl_a]
    evidence_b = registry_by_purl[purl_b]
    record_a = evidence_a.get("精简元数据") or {}
    record_b = evidence_b.get("精简元数据") or {}

    canonical_bodies_equal = purl_a.casefold() == purl_b.casefold()
    registry_records_equal = bool(record_a) and record_a == record_b
    both_registry_ok = bool(evidence_a.get("成功")) and bool(evidence_b.get("成功"))

    common_urls = {
        normalized
        for item in pair.get("共同URL", [])
        if (normalized := resolver.normalize_url(item))
    }
    official_urls = registry_urls(record_a, resolver) | registry_urls(record_b, resolver)
    url_supported = bool(common_urls & official_urls) if common_urls else None

    common_authors = [
        normalize_person_name(item) for item in pair.get("共同作者", [])
    ]
    common_authors = [item for item in common_authors if item]
    official_people = registry_people(record_a) + registry_people(record_b)
    author_supported = False
    if common_authors:
        for observed in common_authors:
            for person in official_people:
                if person["name"] and person["name"] in observed:
                    author_supported = True
                if person["email"] and person["email"] in observed:
                    author_supported = True

    basis = pair.get("合并依据")
    if (
        both_registry_ok
        and canonical_bodies_equal
        and registry_records_equal
        and record_a.get("name")
        and record_a.get("version")
    ):
        conclusion = "CONFIRMED"
        reason = "两个规范 purl 指向完全相同的 npm name@version，官方 registry 返回同一唯一版本记录。"
    elif both_registry_ok and not canonical_bodies_equal:
        conclusion = "WRONG"
        reason = "官方 registry 可访问，但两个规范 purl 指向不同 npm 包坐标。"
    else:
        conclusion = "SUSPECT"
        reason = "至少一个 purl 的官方 registry 查询失败，无法独立确认。"

    if basis == "homepage或repository URL相同" and url_supported is False:
        reason += " 日志 URL 未能与官方 homepage/repository 对齐，需人工复核。"
    if basis == "同名+同版本+同author或maintainer" and not author_supported:
        reason += " 日志 author 未能与官方 author/maintainer 对齐，需人工复核。"

    return {
        "核验编号": pair["核验编号"],
        "原始SBOM": pair["原始SBOM"],
        "name": pair["name"],
        "version": pair["version"],
        "purlA": pair["purlA"],
        "purlB": pair["purlB"],
        "规范purlA": purl_a,
        "规范purlB": purl_b,
        "合并依据": basis,
        "置信度": pair["置信度"],
        "官方源类型": "npm registry",
        "官方证据链接A": evidence_a.get("官方API URL"),
        "官方证据链接B": evidence_b.get("官方API URL"),
        "官方页面链接": registry_page_url(
            record_a.get("name") or pair["name"],
            record_a.get("version") or pair["version"],
        ),
        "官方repository": (
            record_a.get("repository", {}).get("url")
            if isinstance(record_a.get("repository"), dict)
            else record_a.get("repository")
        ),
        "官方homepage": record_a.get("homepage"),
        "官方author": record_a.get("author"),
        "官方maintainers": record_a.get("maintainers"),
        "官方dist": record_a.get("dist"),
        "日志共同URL": pair.get("共同URL"),
        "日志author": pair.get("共同作者"),
        "日志URL得到官方元数据支持": url_supported,
        "日志author得到官方元数据支持": author_supported if common_authors else None,
        "规范purl主体相同": canonical_bodies_equal,
        "官方记录相同": registry_records_equal,
        "结论": conclusion,
        "判断理由": reason,
    }


def main() -> None:
    """抓取官方 registry 并生成 50 对逐对核验结果。"""

    resolver = load_module("module2_verification_resolver", RESOLVER_PATH)
    sample = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    pairs = sample["合并对"]

    unique_purls: list[str] = []
    for pair in pairs:
        for purl in pair["规范purlA"] + pair["规范purlB"]:
            if purl not in unique_purls:
                unique_purls.append(purl)

    registry_by_purl: dict[str, dict[str, Any]] = {}
    started_at = time.perf_counter()
    for position, purl in enumerate(unique_purls, start=1):
        if not purl.startswith("pkg:npm/"):
            registry_by_purl[purl] = {
                "成功": False,
                "官方API URL": None,
                "错误": f"本核验脚本仅支持 npm，当前为：{purl}",
                "精简元数据": None,
            }
            continue
        name, version = parse_npm_canonical(purl)
        api_url = registry_api_url(name, version)
        response = fetch_json(api_url)
        record = (
            trim_registry_record(response["数据"])
            if response.get("成功") and isinstance(response.get("数据"), dict)
            else None
        )
        registry_by_purl[purl] = {
            "成功": response["成功"],
            "HTTP状态": response["HTTP状态"],
            "尝试次数": response.get("尝试次数"),
            "官方API URL": api_url,
            "最终URL": response["最终URL"],
            "错误": response["错误"],
            "精简元数据": record,
        }
        print(
            f"已查询 {position}/{len(unique_purls)}：{name}@{version} "
            f"{'成功' if response['成功'] else '失败'}"
        )

    results = [
        evaluate_pair(pair, registry_by_purl, resolver)
        for pair in pairs
    ]
    counts = Counter(item["结论"] for item in results)
    evidence_document = {
        "核验时间": datetime.now(timezone.utc).isoformat(),
        "官方来源": "https://registry.npmjs.org/",
        "查询唯一purl数": len(unique_purls),
        "查询耗时秒": round(time.perf_counter() - started_at, 6),
        "查询记录": registry_by_purl,
    }
    result_document = {
        "抽样来源": str(SAMPLE_PATH),
        "抽样方式": sample["抽样方式"],
        "抽样数量": len(results),
        "结论分布": dict(sorted(counts.items())),
        "核验结果": results,
    }
    write_json(EVIDENCE_PATH, evidence_document)
    write_json(RESULT_PATH, result_document)

    print(json.dumps(result_document["结论分布"], ensure_ascii=False, indent=2))
    print(f"官方证据：{EVIDENCE_PATH}")
    print(f"逐对结果：{RESULT_PATH}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
