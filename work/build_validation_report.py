#!/usr/bin/env python3
"""汇总模块 2 真实重复样本验证结果，并生成中文报告。"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "outputs"

SCAN_PATH = OUTPUT_DIR / "duplicate_candidates.json"
MAIN_ASSETS_PATH = OUTPUT_DIR / "assets_real_dup.json"
MAIN_DEDUPLICATED_PATH = OUTPUT_DIR / "assets_real_dup_deduplicated.json"
MAIN_LOG_PATH = OUTPUT_DIR / "merge_log_real_dup.json"
LITERAL_ASSETS_PATH = OUTPUT_DIR / "assets_real_dup_literal_max_trivy_lts.json"
LITERAL_DEDUPLICATED_PATH = (
    OUTPUT_DIR / "assets_real_dup_literal_max_trivy_lts_deduplicated.json"
)
LITERAL_LOG_PATH = OUTPUT_DIR / "merge_log_real_dup_literal_max_trivy_lts.json"

CROSS_VALIDATION = [
    {
        "名称": "Syft Node Jod",
        "原始SBOM": "sbom_syft_node_jod_cdx.json",
        "资产文件": "work/assets_cross_syft_jod.json",
        "去重文件": "work/assets_cross_syft_jod_deduplicated.json",
        "日志文件": "outputs/cross_validation_merge_log_syft_jod.json",
        "路径": (
            r"D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms"
            r"\benchmark-alpine-busybox-ngnix-node-ubuntu\sbom_syft_node_jod_cdx.json"
        ),
    },
    {
        "名称": "Syft Node Current Bookworm",
        "原始SBOM": "sbom_syft_node_current-bookworm_cdx.json",
        "资产文件": "work/assets_cross_syft_current_bookworm.json",
        "去重文件": "work/assets_cross_syft_current_bookworm_deduplicated.json",
        "日志文件": (
            "outputs/cross_validation_merge_log_syft_current_bookworm.json"
        ),
        "路径": (
            r"D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms"
            r"\benchmark-alpine-busybox-ngnix-node-ubuntu"
            r"\sbom_syft_node_current-bookworm_cdx.json"
        ),
    },
    {
        "名称": "Trivy Node Jod",
        "原始SBOM": "sbom_trivy_node_jod_cdx.json",
        "资产文件": "work/assets_cross_trivy_jod.json",
        "去重文件": "work/assets_cross_trivy_jod_deduplicated.json",
        "日志文件": "outputs/cross_validation_merge_log_trivy_jod.json",
        "路径": (
            r"D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms"
            r"\benchmark-alpine-busybox-ngnix-node-ubuntu\sbom_trivy_node_jod_cdx.json"
        ),
    },
]

SUMMARY_PATH = OUTPUT_DIR / "cross_validation_real_dup_summary.json"
REPORT_PATH = OUTPUT_DIR / "module2_real_duplicate_validation_report.md"


def load_json(path: Path) -> Any:
    """读取 UTF-8 JSON。"""

    return json.loads(path.read_text(encoding="utf-8"))


def purl_value(value: Any) -> str:
    """取日志里的主 purl；模块 2 可能输出字符串或 purl 数组。"""

    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def base_purl(value: Any) -> str:
    """去掉 package-id、架构和发行版查询参数，保留包坐标主体。"""

    return purl_value(value).split("?", 1)[0]


def purl_parts(value: Any) -> tuple[str, str, str]:
    """拆出生态、包路径和版本，用于识别跨生态或跨版本合并。"""

    base = base_purl(value)
    match = re.match(r"pkg:([^/]+)/(.+?)(?:@([^/?#]+))?$", base)
    if not match:
        return "?", base, ""
    return match.group(1), match.group(2), match.group(3) or ""


def classify_merges(log_entries: list[dict[str, Any]]) -> dict[str, int]:
    """统计合并属于相同坐标、同名跨版本或跨生态。"""

    counts = Counter()
    for entry in log_entries:
        left_base = base_purl(entry.get("kept_purl"))
        right_base = base_purl(entry.get("merged_purl"))
        left_parts = purl_parts(entry.get("kept_purl"))
        right_parts = purl_parts(entry.get("merged_purl"))

        if left_base == right_base:
            counts["相同包坐标"] += 1
        elif left_parts[:2] == right_parts[:2]:
            counts["同名同生态不同版本"] += 1
        else:
            counts["不同生态或命名空间"] += 1
    return dict(counts)


def count_location_intersection_types(
    log_entries: list[dict[str, Any]],
) -> dict[str, int]:
    """统计每条合并日志的位置交集类型，不重复计算同一条内的多个值。"""

    counts = Counter()
    for entry in log_entries:
        kept_locations = set(entry.get("kept_locations") or [])
        merged_locations = set(entry.get("merged_locations") or [])
        intersection = kept_locations & merged_locations
        if not intersection:
            counts["无交集"] += 1
            continue
        if all(value.startswith("sha256:") for value in intersection):
            counts["仅层ID"] += 1
        elif any(value.startswith("sha256:") for value in intersection):
            counts["层ID与路径混合"] += 1
        else:
            counts["仅路径或其他"] += 1
    return dict(counts)


def build_name_summary(
    log_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """按包名汇总日志中的合并对数和所有涉及的包坐标。"""

    entries_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in log_entries:
        entries_by_name[str(entry.get("name") or "(未命名)")].append(entry)

    result: list[dict[str, Any]] = []
    for name, entries in sorted(
        entries_by_name.items(),
        key=lambda item: (-len(item[1]), item[0]),
    ):
        coordinates = {
            base_purl(entry.get("kept_purl"))
            for entry in entries
        } | {
            base_purl(entry.get("merged_purl"))
            for entry in entries
        }
        result.append(
            {
                "name": name,
                "合并对数": len(entries),
                "涉及包坐标": sorted(coordinates),
            }
        )
    return result


def main_result() -> dict[str, Any]:
    """读取主样本并生成验证统计。"""

    assets = load_json(MAIN_ASSETS_PATH)
    deduplicated = load_json(MAIN_DEDUPLICATED_PATH)
    log_entries = load_json(MAIN_LOG_PATH)
    return {
        "原始SBOM": (
            r"D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms"
            r"\benchmark-alpine-busybox-ngnix-node-ubuntu\sbom_syft_node_lts_cdx.json"
        ),
        "资产数量": len(assets),
        "去重后数量": len(deduplicated),
        "减少数量": len(assets) - len(deduplicated),
        "合并日志数": len(log_entries),
        "置信度分布": dict(
            Counter(str(entry.get("confidence")) for entry in log_entries)
        ),
        "合并依据分布": dict(
            Counter(str(entry.get("basis")) for entry in log_entries)
        ),
        "合并分类": classify_merges(log_entries),
        "位置交集类型": count_location_intersection_types(log_entries),
        "按名称汇总": build_name_summary(log_entries),
    }


def literal_max_result() -> dict[str, Any]:
    """读取同名不同 purl 对数最高的字面主候选结果。"""

    assets = load_json(LITERAL_ASSETS_PATH)
    deduplicated = load_json(LITERAL_DEDUPLICATED_PATH)
    log_entries = load_json(LITERAL_LOG_PATH)
    return {
        "原始SBOM": (
            r"D:\datasets\msu-sbom-benchmark\zenodo\docker\_sboms"
            r"\benchmark-alpine-busybox-ngnix-node-ubuntu\sbom_trivy_node_lts_cdx.json"
        ),
        "同名不同purl对数": 79,
        "同名同purl对数": 50,
        "资产数量": len(assets),
        "去重后数量": len(deduplicated),
        "合并日志数": len(log_entries),
        "置信度分布": dict(
            Counter(str(entry.get("confidence")) for entry in log_entries)
        ),
        "合并依据分布": dict(
            Counter(str(entry.get("basis")) for entry in log_entries)
        ),
    }


def cross_results() -> list[dict[str, Any]]:
    """汇总三个交叉验证样本。"""

    results: list[dict[str, Any]] = []
    for sample in CROSS_VALIDATION:
        assets = load_json(BASE_DIR / sample["资产文件"])
        deduplicated = load_json(BASE_DIR / sample["去重文件"])
        log_entries = load_json(BASE_DIR / sample["日志文件"])
        results.append(
            {
                "名称": sample["名称"],
                "原始SBOM": sample["原始SBOM"],
                "路径": sample["路径"],
                "资产数量": len(assets),
                "去重后数量": len(deduplicated),
                "减少数量": len(assets) - len(deduplicated),
                "合并日志数": len(log_entries),
                "置信度分布": dict(
                    Counter(str(entry.get("confidence")) for entry in log_entries)
                ),
                "合并依据分布": dict(
                    Counter(str(entry.get("basis")) for entry in log_entries)
                ),
                "合并分类": classify_merges(log_entries),
                "位置交集类型": count_location_intersection_types(log_entries),
                "日志文件": sample["日志文件"],
            }
        )
    return results


def markdown_table(
    headers: list[str], rows: list[list[Any]]
) -> str:
    """生成 Markdown 表格。"""

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def build_report(
    scan: dict[str, Any],
    literal: dict[str, Any],
    main: dict[str, Any],
    cross: list[dict[str, Any]],
) -> str:
    """生成中文 Markdown 验证报告。"""

    candidates = scan["候选文件"]
    candidate_projects = Counter(candidate["项目"] for candidate in candidates)
    candidate_tools = Counter(candidate["文件名"].split("_")[1] for candidate in candidates)
    name_rows = [
        [
            item["name"],
            item["合并对数"],
            "<br>".join(item["涉及包坐标"]),
        ]
        for item in main["按名称汇总"]
    ]
    cross_rows = [
        [
            item["名称"],
            item["原始SBOM"],
            f"{item['资产数量']} -> {item['去重后数量']}",
            item["合并日志数"],
            item["置信度分布"] or "无",
            item["位置交集类型"] or "无",
        ]
        for item in cross
    ]
    output_rows = [
        [
            "主验证样本",
            "sbom_syft_node_lts_cdx.json",
            "assets_real_dup.json",
            "assets_real_dup_deduplicated.json",
            "merge_log_real_dup.json",
        ],
        [
            "字面最高重复候选",
            "sbom_trivy_node_lts_cdx.json",
            "assets_real_dup_literal_max_trivy_lts.json",
            "assets_real_dup_literal_max_trivy_lts_deduplicated.json",
            "merge_log_real_dup_literal_max_trivy_lts.json",
        ],
        [
            "交叉验证 1",
            "sbom_syft_node_jod_cdx.json",
            "work/assets_cross_syft_jod.json",
            "work/assets_cross_syft_jod_deduplicated.json",
            "cross_validation_merge_log_syft_jod.json",
        ],
        [
            "交叉验证 2",
            "sbom_syft_node_current-bookworm_cdx.json",
            "work/assets_cross_syft_current_bookworm.json",
            "work/assets_cross_syft_current_bookworm_deduplicated.json",
            "cross_validation_merge_log_syft_current_bookworm.json",
        ],
        [
            "交叉验证 3",
            "sbom_trivy_node_jod_cdx.json",
            "work/assets_cross_trivy_jod.json",
            "work/assets_cross_trivy_jod_deduplicated.json",
            "cross_validation_merge_log_trivy_jod.json",
        ],
    ]

    return f"""# 模块 2 真实重复样本验证报告

## 1. 扫描结果

- 实际扫描 JSON 文件数：{scan['实际扫描文件数']}。
- 候选文件数：{scan['候选文件数']}。
- 含同名不同 purl 的文件数：{scan['同名不同purl文件数']}。
- 含同名同 purl 的文件数：{scan['同名同purl文件数']}。
- 同时含两类重复的文件数：{scan['两种重复类型均存在的文件数']}。
- 跳过文件数：{scan['跳过文件数']}。
- 扫描耗时：{scan['扫描耗时秒']} 秒。
- 候选项目分布：{dict(candidate_projects)}。
- 候选来源工具分布：{dict(candidate_tools)}。
- 候选中的同名不同 purl 对数合计：{sum(item['同名不同purl对数'] for item in candidates)}。
- 候选中的同名同 purl 对数合计：{sum(item['同名同purl对数'] for item in candidates)}。

数据集中的 {scan['JSON文件总数']} 个 JSON 文件全部完成扫描，没有超时或解析失败。所有候选均来自 Node 项目，分别由 Trivy 和 Syft 生成，因此无法按“不同项目”选择交叉验证样本；改用三个不同的 Node 镜像变体，其中两个来自 Syft，一个来自 Trivy。

## 2. 样本选择与输出映射

字面规则下，同名不同 purl 对数最高的文件是 `sbom_trivy_node_lts_cdx.json`，共 79 对。实际运行模块 2 后，该文件合并数为 0，因为其同名同 purl 副本位于不同文件路径，而同名不同 purl 副本的版本不同，不满足模块 2 当前判定条件。

为了让模块 2 真正触发实体对齐规则，主验证样本改用 `sbom_syft_node_lts_cdx.json`。该文件有 76 对同名不同 purl，实际产生 124 条合并日志。字面最高候选仍单独保留，便于核对。

{markdown_table(['用途', '原始 SBOM', '资产文件', '去重文件', '合并日志'], output_rows)}

## 3. 主样本运行结果

- 原始 SBOM：`{main['原始SBOM']}`。
- 资产数量：{main['资产数量']}。
- 去重后数量：{main['去重后数量']}。
- 减少数量：{main['减少数量']}。
- 合并日志数：{main['合并日志数']}。
- 置信度分布：{main['置信度分布']}。
- 合并依据分布：{main['合并依据分布']}。
- 位置交集类型：{main['位置交集类型']}。
- 合并分类：{main['合并分类']}。

124 条日志全部标记为 0.9，依据文本均为“同名+同 evidence 位置”。进一步检查发现，位置交集全部来自 `sha256:` 开头的 Syft 层 ID，没有任何一条来自相同文件路径。因此这些结果不能证明两个组件出现在同一文件位置，更不能说明它们应合并为同一实体。

### 被合并的组件

{markdown_table(['包名', '合并日志数', '涉及的包坐标'], name_rows)}

## 4. 交叉验证结果

{markdown_table(['样本', '原始 SBOM', '组件数变化', '合并日志数', '置信度分布', '位置交集类型'], cross_rows)}

两个 Syft 样本均稳定复现相同结果：662 个资产减为 596 个，产生 124 条 0.9 合并，全部由层 ID 交集触发。Trivy 样本的 660 个资产没有合并，日志为空。这说明触发差异主要来自不同扫描器写出的位置属性，而不是来自真实的同路径实体重复。

## 5. 误合并判断

- 不同版本误合并：73 条。
- 跨生态或跨命名空间误合并：1 条。
- 包坐标相同的合并：50 条；这些记录虽然 purl 主体或版本一致，但触发依据仍是共享层 ID，而不是相同文件路径，因此不能视为通过了位置规则验证。
- 同名同 purl 但实际属于不同包的案例：未发现。
- 明确误合并总数：至少 74 条。

典型误合并包括：

- `minipass`：`3.3.6`、`5.0.0`、`7.1.2` 被连通合并。
- `ansi-styles`：`4.3.0` 与 `6.2.1` 被合并。
- `tar`：npm 的 `6.2.1` 与 `7.4.3` 被合并。
- `mercurial`：PyPI `6.3.2` 与 Debian `6.3.2-1` 被合并，属于跨生态误合并。
- `@npmcli/agent`：`2.2.2` 与 `3.0.0` 被合并。

## 6. 结论

模块 2 已在真实 MSU SBOM 数据集上成功触发，并能稳定产生输出；但当前 0.9 位置规则存在明确缺陷。Syft 的 `syft:location:*:layerID` 是整层内容摘要，不是文件位置。只要两个组件位于同一镜像层，规则就会把层 ID 当作共同证据，导致不同版本、不同安装路径，甚至不同生态的同名包被合并。

在修复规则前，不应把本报告的 124 条合并视为正确去重结果。建议至少将 `layerID` 从文件位置证据中排除，只保留具体路径字段；同时增加版本冲突保护，禁止不同版本的同名包仅凭层内位置自动合并。现有手工合成数据仍适合作为规则单元测试，但需要新增“共享 layerID、路径不同、版本不同”的负例，防止该缺陷回归。

## 7. 输出文件

- 扫描脚本：`scan_duplicates.py`。
- 候选结果：`outputs/duplicate_candidates.json`。
- 主样本资产：`outputs/assets_real_dup.json`。
- 主样本去重结果：`outputs/assets_real_dup_deduplicated.json`。
- 主样本合并日志：`outputs/merge_log_real_dup.json`。
- 字面最高候选日志：`outputs/merge_log_real_dup_literal_max_trivy_lts.json`。
- 交叉验证汇总：`outputs/cross_validation_real_dup_summary.json`。
"""


def main() -> None:
    """写出机器可读汇总和 Markdown 报告。"""

    scan = load_json(SCAN_PATH)
    literal = literal_max_result()
    main = main_result()
    cross = cross_results()

    summary = {
        "扫描结果": {
            "JSON文件总数": scan["JSON文件总数"],
            "实际扫描文件数": scan["实际扫描文件数"],
            "候选文件数": scan["候选文件数"],
            "同名不同purl文件数": scan["同名不同purl文件数"],
            "同名同purl文件数": scan["同名同purl文件数"],
            "两种重复类型均存在的文件数": scan["两种重复类型均存在的文件数"],
            "跳过文件数": scan["跳过文件数"],
        },
        "字面最高候选": literal,
        "主验证样本": main,
        "交叉验证": cross,
        "误合并判断": {
            "明确误合并最少条数": 74,
            "不同版本误合并": main["合并分类"].get("同名同生态不同版本", 0),
            "跨生态或跨命名空间误合并": main["合并分类"].get(
                "不同生态或命名空间", 0
            ),
            "审计结论": "0.9 位置规则误把整层 layerID 当作相同文件位置证据",
        },
    }

    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        build_report(scan, literal, main, cross),
        encoding="utf-8",
    )
    print(f"汇总输出：{SUMMARY_PATH}")
    print(f"报告输出：{REPORT_PATH}")


if __name__ == "__main__":
    main()
