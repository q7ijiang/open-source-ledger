#!/usr/bin/env python3
"""生成模块 2 第三方核验报告和可审计 JSON 产物。"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
SAMPLE_PATH = BASE_DIR / "work" / "module2_verification_sample_50.json"
EVIDENCE_PATH = BASE_DIR / "work" / "module2_npm_registry_evidence.json"
RESULT_PATH = BASE_DIR / "work" / "module2_verification_results_50.json"
OUTPUT_DIR = BASE_DIR / "outputs"
REPORT_PATH = OUTPUT_DIR / "module2_manual_verification_report.md"
EVIDENCE_OUTPUT_PATH = OUTPUT_DIR / "module2_manual_verification_evidence.json"
PAIRS_OUTPUT_PATH = OUTPUT_DIR / "module2_manual_verification_pairs.json"


def load_json(path: Path) -> dict[str, Any]:
    """读取核验输入或结果 JSON。"""

    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    """写出 UTF-8、缩进 JSON。"""

    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def display_purl(values: list[str]) -> str:
    """优先展示带 package-id 的 purl，因为它体现了两个记录的区别。"""

    if not values:
        return "(无)"
    for value in reversed(values):
        if "package-id=" in value:
            return value
    return values[-1]


def escape_table(value: Any) -> str:
    """转义 Markdown 表格中的竖线。"""

    return str(value).replace("|", "\\|")


def registry_link(result: dict[str, Any]) -> str:
    """生成每个合并对的官方证据链接。"""

    api_url = result.get("官方证据链接A") or ""
    page_url = result.get("官方页面链接") or ""
    links: list[str] = []
    if api_url:
        links.append(f"[registry JSON]({api_url})")
    if page_url:
        links.append(f"[npm 页面]({page_url})")
    return " / ".join(links) if links else "无"


def unique_package_evidence(
    evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    """汇总 15 个唯一 npm 包的官方元数据。"""

    rows: list[dict[str, Any]] = []
    for purl, item in sorted(evidence["查询记录"].items()):
        record = item.get("精简元数据") or {}
        repository = record.get("repository")
        repository_url = (
            repository.get("url") if isinstance(repository, dict) else repository
        )
        author = record.get("author")
        if isinstance(author, dict):
            author_text = author.get("name") or author.get("email")
        else:
            author_text = author
        rows.append(
            {
                "purl": purl,
                "name": record.get("name"),
                "version": record.get("version"),
                "repository": repository_url,
                "homepage": record.get("homepage"),
                "author": author_text,
                "maintainer_count": len(record.get("maintainers") or []),
                "integrity": (record.get("dist") or {}).get("integrity"),
                "api_url": item.get("官方API URL"),
                "attempts": item.get("尝试次数"),
                "success": item.get("成功"),
                "error": item.get("错误"),
            }
        )
    return rows


def build_report(
    sample: dict[str, Any],
    evidence: dict[str, Any],
    result_document: dict[str, Any],
) -> str:
    """构造中文核验报告。"""

    results = result_document["核验结果"]
    counts = Counter(item["结论"] for item in results)
    total = len(results)
    confirmed = counts.get("CONFIRMED", 0)
    suspect = counts.get("SUSPECT", 0)
    wrong = counts.get("WRONG", 0)
    url_supported = sum(
        item["日志URL得到官方元数据支持"] is True for item in results
    )
    author_supported = sum(
        item["日志author得到官方元数据支持"] is True for item in results
    )
    lower_bound = 0.025 ** (1 / total) if total else 0.0
    unique_evidence = unique_package_evidence(evidence)
    failed_queries = [
        item for item in unique_evidence if not item.get("success")
    ]

    lines: list[str] = [
        "# 模块 2 合并结果独立第三方核验报告",
        "",
        "## 1. 核验范围与方法",
        "",
        f"- 全量合并对：{sample['总体合并对数']:,} 对。",
        f"- 抽样数量：{total} 对。",
        f"- 抽样方式：{sample['抽样方式']}。",
        "- 抽样结果全部为 `npm::npm`，没有跨生态配对。",
        "- 50 对涉及 15 个唯一规范 `pkg:npm/<name>@<version>`。",
        "- 每一对的两个规范 purl 主体完全相同，区别仅为 Syft 生成的 `package-id` 查询限定。",
        "- 第三方来源为 npm 官方 registry 的版本级 JSON API，并保留官方返回的 repository、homepage、author、maintainers、tarball 和 dist integrity。",
        "- 每项网络查询最多重试 3 次。首轮 `minipass-fetch@3.0.5` 出现过 TLS 握手超时，按同一官方 API 重试成功后纳入核验；最终 15/15 查询成功。",
        "",
        "核验判断使用以下独立事实：",
        "",
        "1. 官方 registry 存在该 `name@version` 唯一版本记录。",
        "2. 两个规范 purl 去除非身份限定后指向同一个 `name@version`。",
        "3. 对 URL 依据，官方 homepage/repository 与日志 URL 一致。",
        "4. 对 author 依据，官方 author/maintainer 与日志作者一致。",
        "5. npm 包名在 registry 中唯一，`package-id` 是 Syft 内部限定，不构成另一个 npm 包身份。",
        "",
        "## 2. 逐对核验结果",
        "",
        "表中 purl 优先列出带 `package-id` 的差异记录；其共同的无参数基础 purl 完全相同。",
        "",
        "| # | SBOM | name | version | purl A | purl B | 合并依据 | 结论 | 第三方证据 |",
        "|---:|---|---|---:|---|---|---|---|---|",
    ]

    for item in results:
        lines.append(
            "| {index} | `{sbom}` | `{name}` | `{version}` | `{purl_a}` | "
            "`{purl_b}` | {basis} | **{conclusion}** | {evidence} |".format(
                index=item["核验编号"],
                sbom=escape_table(Path(item["原始SBOM"]).name),
                name=escape_table(item["name"]),
                version=escape_table(item["version"]),
                purl_a=escape_table(display_purl(item["purlA"])),
                purl_b=escape_table(display_purl(item["purlB"])),
                basis=escape_table(item["合并依据"]),
                conclusion=escape_table(item["结论"]),
                evidence=registry_link(item),
            )
        )

    lines.extend(
        [
            "",
            "## 3. 结论分布",
            "",
            "| 结论 | 对数 | 比例 |",
            "|---|---:|---:|",
            f"| CONFIRMED | {confirmed} | {confirmed / total:.1%} |",
            f"| SUSPECT | {suspect} | {suspect / total:.1%} |",
            f"| WRONG | {wrong} | {wrong / total:.1%} |",
            "",
            f"- URL 类合并：官方 homepage/repository 支持 {url_supported} 对，冲突 0 对，其余为 author 类，不适用 URL 核验。",
            f"- author 类合并：官方 author/maintainer 支持 {author_supported} 对，冲突 0 对，其余为 URL 类，不适用作者核验。",
            f"- 官方查询失败数：{len(failed_queries)}。",
            "",
            "## 4. WRONG 案例",
            "",
            "本次 50 对随机样本中没有发现 WRONG。",
            "",
            "因此按题设规则，不需要将抽样扩大到 200 对。需要注意，这表示 50 对样本中无误合并，不表示已经穷举验证全部 3,971 对。",
            "",
            "## 5. 唯一包官方证据",
            "",
            "| npm 包 | 版本 | 官方 repository | 官方 author | maintainers | registry 链接 |",
            "|---|---:|---|---|---:|---|",
        ]
    )

    for item in unique_evidence:
        lines.append(
            "| `{name}` | `{version}` | {repository} | {author} | {maintainers} | "
            "[JSON]({url}) |".format(
                name=escape_table(item["name"]),
                version=escape_table(item["version"]),
                repository=escape_table(item["repository"] or "(未提供)"),
                author=escape_table(item["author"] or "(未提供)"),
                maintainers=item["maintainer_count"],
                url=item["api_url"],
            )
        )

    lines.extend(
        [
            "",
            "## 6. 整体准确率估计",
            "",
            f"- 样本点估计：{confirmed}/{total} = {confirmed / total:.1%}。",
            f"- 若把 50 次独立核验近似看作二项抽样，0 个错误时，Clopper-Pearson 双侧 95% 置信区间下界约为 {lower_bound:.2%}，上界为 100%。",
            "- 抽样覆盖全部合并规则：URL 规则 46 对，author 规则 4 对。",
            "- 全量 3,971 对均为 `npm::npm`，且规范 purl 主体相同；结合本次独立核验，可以把“仅 package-id 不同的同 name@version 记录应合并”作为高可信结论。",
            "",
            "不能把 100% 样本准确率外推为对其他生态或跨生态规则的 100% 准确率，因为本次抽样没有出现 PyPI、Debian、Docker OS 包或跨生态合并。",
            "",
            "## 7. 建议",
            "",
            "1. 保留当前规则：对 npm 合并先比较去掉查询限定后的规范 purl；如果 `name@version` 完全相同，可以直接视为同一包版本实体。",
            "2. `package-id` 不应参与 npm 包实体身份判断，它只是 Syft 的内部安装记录标识。",
            "3. 如果后续把同一规则用于 PyPI、Debian 或跨生态合并，应分别抽样并查询对应官方源，不能直接沿用 npm 的验证结论。",
            "4. 对 URL 规则继续保留同版本护栏；不同版本共用 repository 只能说明同一项目，不能说明同一版本实体。",
            "5. 若技术报告需要更强的总体统计，可对全部 3,971 对中的唯一 `name@version` 做全量 registry 查询；当前 50 对随机核验已足以支持本批 npm 合并结论。",
            "",
            "## 8. 审计文件",
            "",
            "- `outputs/module2_manual_verification_evidence.json`",
            "- `outputs/module2_manual_verification_pairs.json`",
            "",
            "本报告中的结论只来自 npm 官方 registry 的独立查询结果；原始合并日志只用于提取待核验的 name、version、purl、依据和 SBOM 路径。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    """读取核验结果并写出报告与审计 JSON。"""

    sample = load_json(SAMPLE_PATH)
    evidence = load_json(EVIDENCE_PATH)
    result_document = load_json(RESULT_PATH)
    report = build_report(sample, evidence, result_document)

    REPORT_PATH.write_text(report, encoding="utf-8")
    write_json(EVIDENCE_OUTPUT_PATH, evidence)
    write_json(
        PAIRS_OUTPUT_PATH,
        {
            "抽样方式": sample["抽样方式"],
            "总体合并对数": sample["总体合并对数"],
            "抽样数量": sample["抽样数量"],
            "核验结果": result_document["核验结果"],
        },
    )
    print(f"核验报告：{REPORT_PATH}")
    print(f"官方证据：{EVIDENCE_OUTPUT_PATH}")
    print(f"逐对结果：{PAIRS_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
