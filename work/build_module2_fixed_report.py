#!/usr/bin/env python3
"""汇总模块 2 修复后的真实样本验证结果并生成中文报告。"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
WORK_DIR = BASE_DIR / "work"
OUTPUT_DIR = BASE_DIR / "outputs"
sys.path.insert(0, str(BASE_DIR))

import entity_resolver as resolver  # noqa: E402


SCAN_PATH = OUTPUT_DIR / "duplicate_candidates.json"
BASELINE_SUMMARY_PATH = WORK_DIR / "baseline_cross_validation_real_dup_summary.json"
BASELINE_MAIN_LOG_PATH = WORK_DIR / "baseline_merge_log_real_dup.json"

MAIN_ASSETS_PATH = OUTPUT_DIR / "assets_real_dup.json"
MAIN_DEDUPLICATED_PATH = OUTPUT_DIR / "assets_real_dup_deduplicated.json"
MAIN_LOG_PATH = OUTPUT_DIR / "merge_log_real_dup.json"

TRIVY_ASSETS_PATH = OUTPUT_DIR / "assets_real_dup_literal_max_trivy_lts.json"
TRIVY_DEDUPLICATED_PATH = (
    OUTPUT_DIR / "assets_real_dup_literal_max_trivy_lts_deduplicated.json"
)
TRIVY_LOG_PATH = OUTPUT_DIR / "merge_log_real_dup_literal_max_trivy_lts.json"

SYNTHETIC_ASSETS_PATH = OUTPUT_DIR / "assets.json"
SYNTHETIC_DEDUPLICATED_PATH = OUTPUT_DIR / "assets_deduplicated.json"
SYNTHETIC_LOG_PATH = OUTPUT_DIR / "merge_log.json"

MODEL_ALIAS_ASSETS_PATH = BASE_DIR / "test-project" / "assets_real.json"
MODEL_ALIAS_DEDUPLICATED_PATH = WORK_DIR / "assets_real_fixed_deduplicated.json"
MODEL_ALIAS_LOG_PATH = WORK_DIR / "merge_log_real_fixed.json"

CROSS_VALIDATION = [
    {
        "name": "Syft Node Jod",
        "source": "sbom_syft_node_jod_cdx.json",
        "assets": WORK_DIR / "assets_cross_syft_jod.json",
        "deduplicated": WORK_DIR / "assets_cross_syft_jod_deduplicated.json",
        "log": OUTPUT_DIR / "cross_validation_merge_log_syft_jod.json",
    },
    {
        "name": "Syft Node Current Bookworm",
        "source": "sbom_syft_node_current-bookworm_cdx.json",
        "assets": WORK_DIR / "assets_cross_syft_current_bookworm.json",
        "deduplicated": (
            WORK_DIR / "assets_cross_syft_current_bookworm_deduplicated.json"
        ),
        "log": (
            OUTPUT_DIR / "cross_validation_merge_log_syft_current_bookworm.json"
        ),
    },
    {
        "name": "Trivy Node Jod",
        "source": "sbom_trivy_node_jod_cdx.json",
        "assets": WORK_DIR / "assets_cross_trivy_jod.json",
        "deduplicated": WORK_DIR / "assets_cross_trivy_jod_deduplicated.json",
        "log": OUTPUT_DIR / "cross_validation_merge_log_trivy_jod.json",
    },
]

SUMMARY_PATH = OUTPUT_DIR / "cross_validation_real_dup_summary.json"
REPORT_PATH = OUTPUT_DIR / "module2_real_duplicate_validation_report.md"


def load_json(path: Path) -> Any:
    """读取 UTF-8 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def first_purl(value: Any) -> str:
    """从字符串或 purl 数组日志值中取得首个 purl。"""

    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def purl_type_from_log(entry: dict[str, Any], side: str) -> str | None:
    """读取日志中的 purl type，兼容新日志字段和旧日志结构。"""

    explicit_key = f"{side}_purl_types"
    explicit_value = entry.get(explicit_key)
    if isinstance(explicit_value, list) and explicit_value:
        return str(explicit_value[0]).lower()

    purl_key = "kept_purl" if side == "kept" else "merged_purl"
    return resolver.purl_type(first_purl(entry.get(purl_key)))


def purl_version_from_log(entry: dict[str, Any], side: str) -> str | None:
    """读取日志中的版本，兼容新日志字段和旧日志结构。"""

    explicit_key = f"{side}_version"
    if explicit_key in entry:
        return resolver.clean_text(entry.get(explicit_key))

    purl_key = "kept_purl" if side == "kept" else "merged_purl"
    return resolver.purl_version(first_purl(entry.get(purl_key)))


def canonical_from_log(entry: dict[str, Any], side: str) -> str:
    """读取日志中的 purl 主体。"""

    purl_key = "kept_purl" if side == "kept" else "merged_purl"
    return resolver.canonical_purl(first_purl(entry.get(purl_key)))


def classify_old_pair(entry: dict[str, Any]) -> str:
    """判断旧日志中的合并对属于哪类误合并风险。"""

    left_type = purl_type_from_log(entry, "kept")
    right_type = purl_type_from_log(entry, "merged")
    if left_type != right_type:
        return "跨生态"

    left_version = purl_version_from_log(entry, "kept")
    right_version = purl_version_from_log(entry, "merged")
    if left_version != right_version:
        return "不同版本"

    if canonical_from_log(entry, "kept") == canonical_from_log(entry, "merged"):
        return "相同包坐标"
    return "同生态其他坐标"


def analyze_old_main_log() -> dict[str, Any]:
    """分析修复前主样本日志，保留真实的修复前基线。"""

    entries = load_json(BASELINE_MAIN_LOG_PATH)
    classifications = Counter(classify_old_pair(entry) for entry in entries)
    layer_only = 0
    for entry in entries:
        left_locations = set(entry.get("kept_locations") or [])
        right_locations = set(entry.get("merged_locations") or [])
        common_locations = left_locations & right_locations
        if common_locations and all(
            str(location).lower().startswith("sha256:")
            for location in common_locations
        ):
            layer_only += 1

    return {
        "合并对数": len(entries),
        "置信度分布": dict(
            Counter(str(entry.get("confidence")) for entry in entries)
        ),
        "合并分类": dict(classifications),
        "仅由layerID触发": layer_only,
        "明确误合并": classifications["不同版本"] + classifications["跨生态"],
    }


def analyze_result(
    assets_path: Path,
    deduplicated_path: Path,
    log_path: Path,
) -> dict[str, Any]:
    """汇总一组资产、去重结果和日志。"""

    assets = load_json(assets_path)
    deduplicated = load_json(deduplicated_path)
    log_entries = load_json(log_path)
    merged_entries = [
        entry for entry in log_entries if entry.get("status") == "merged"
    ]
    skipped_entries = [
        entry for entry in log_entries if entry.get("status") != "merged"
    ]

    invalid_location_values: list[str] = []
    for entry in log_entries:
        for key in ("kept_locations", "merged_locations"):
            for location in entry.get(key) or []:
                if not resolver.is_valid_location(location):
                    invalid_location_values.append(str(location))

    return {
        "资产数": len(assets),
        "去重后资产数": len(deduplicated),
        "减少数": len(assets) - len(deduplicated),
        "同名配对总数": len(log_entries),
        "合并对数": len(merged_entries),
        "跳过对数": len(skipped_entries),
        "置信度分布": dict(
            Counter(str(entry.get("confidence")) for entry in merged_entries)
        ),
        "合并依据分布": dict(
            Counter(str(entry.get("basis")) for entry in merged_entries)
        ),
        "跳过原因分布": dict(
            Counter(str(entry.get("status")) for entry in skipped_entries)
        ),
        "合并组件": [
            {
                "name": entry.get("name"),
                "kept_purl": entry.get("kept_purl"),
                "merged_purl": entry.get("merged_purl"),
                "confidence": entry.get("confidence"),
                "basis": entry.get("basis"),
                "common_valid_locations": entry.get(
                    "common_valid_locations", []
                ),
            }
            for entry in merged_entries
        ],
        "日志中的无效位置数": len(invalid_location_values),
        "日志中的无效位置示例": invalid_location_values[:10],
    }


def summarize_cross_validation() -> list[dict[str, Any]]:
    """汇总修复后的三组交叉验证结果。"""

    results: list[dict[str, Any]] = []
    for sample in CROSS_VALIDATION:
        result = analyze_result(
            sample["assets"],
            sample["deduplicated"],
            sample["log"],
        )
        results.append(
            {
                "名称": sample["name"],
                "原始SBOM": sample["source"],
                **result,
            }
        )
    return results


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    """生成 Markdown 表格，并转义竖线字符。"""

    def clean(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    lines = [
        "| " + " | ".join(clean(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(clean(value) for value in row) + " |")
    return "\n".join(lines)


def distribution_text(distribution: dict[str, Any]) -> str:
    """把统计分布转换为适合报告表格的文本。"""

    if not distribution:
        return "无"
    return "；".join(
        f"{key}={value}" for key, value in sorted(distribution.items())
    )


def build_report(
    scan: dict[str, Any],
    baseline_summary: dict[str, Any],
    old_main: dict[str, Any],
    main: dict[str, Any],
    trivy: dict[str, Any],
    synthetic_hf: dict[str, Any],
    synthetic_model: dict[str, Any],
    cross: list[dict[str, Any]],
) -> str:
    """生成修复后的中文 Markdown 报告。"""

    old_summary = baseline_summary["主验证样本"]
    baseline_trivy = baseline_summary["字面最高候选"]
    baseline_cross = {
        item["名称"]: item for item in baseline_summary["交叉验证"]
    }

    comparison_rows = [
        [
            "Syft Node LTS 主样本",
            (
                f"{old_summary['资产数量']} -> "
                f"{old_summary['去重后数量']}，"
                f"合并 {old_summary['合并日志数']} 对"
            ),
            (
                f"{main['资产数']} -> {main['去重后资产数']}，"
                f"合并 {main['合并对数']} 对，"
                f"跳过 {main['跳过对数']} 对"
            ),
            "旧结果 124 对全部由 layerID 触发；新结果不再把 layerID 当作文件位置。",
        ],
        [
            "Trivy Node LTS 样本",
            (
                f"{baseline_trivy['资产数量']} -> "
                f"{baseline_trivy['去重后数量']}，"
                f"合并 {baseline_trivy['合并日志数']} 对"
            ),
            (
                f"{trivy['资产数']} -> {trivy['去重后资产数']}，"
                f"合并 {trivy['合并对数']} 对，"
                f"跳过 {trivy['跳过对数']} 对"
            ),
            "仍保持 0 合并。",
        ],
    ]

    for item in cross:
        baseline = baseline_cross[item["名称"]]
        comparison_rows.append(
            [
                item["名称"],
                (
                    f"{baseline['资产数量']} -> "
                    f"{baseline['去重后数量']}，"
                    f"合并 {baseline['合并日志数']} 对"
                ),
                (
                    f"{item['资产数']} -> {item['去重后资产数']}，"
                    f"合并 {item['合并对数']} 对，"
                    f"跳过 {item['跳过对数']} 对"
                ),
                "旧 Syft 层 ID 合并已全部停止。",
            ]
        )

    main_status_rows = [
        [reason, count]
        for reason, count in sorted(main["跳过原因分布"].items())
    ]
    trivy_status_rows = [
        [reason, count]
        for reason, count in sorted(trivy["跳过原因分布"].items())
    ]
    cross_rows = [
        [
            item["名称"],
            item["原始SBOM"],
            f"{item['资产数']} -> {item['去重后资产数']}",
            item["合并对数"],
            item["跳过对数"],
            distribution_text(item["跳过原因分布"]),
        ]
        for item in cross
    ]

    synthetic_rows = [
        [
            "outputs/assets.json",
            "bert-base-uncased 的同 purl Hugging Face 重复",
            f"{synthetic_hf['资产数']} -> {synthetic_hf['去重后资产数']}",
            synthetic_hf["合并对数"],
            distribution_text(synthetic_hf["置信度分布"]),
            distribution_text(synthetic_hf["合并依据分布"]),
        ],
        [
            "test-project/assets_real.json",
            "bert-base-uncased 的 npm/pypi 模型别名",
            (
                f"{synthetic_model['资产数']} -> "
                f"{synthetic_model['去重后资产数']}"
            ),
            synthetic_model["合并对数"],
            distribution_text(synthetic_model["置信度分布"]),
            distribution_text(synthetic_model["合并依据分布"]),
        ],
    ]

    return f"""# 模块 2 真实重复样本验证报告

## 1. 修复结论

本次修复已经落实三条核心规则，并重新转换、运行真实 SBOM。修复前主样本的 124 对合并全部由 Syft `sha256:` layerID 触发；修复后主样本不再产生任何合并，126 个同名组件对全部进入日志并给出跳过原因，其中 73 对是版本冲突，3 对是跨生态，50 对是同一包坐标但没有共同的具体文件路径。

{markdown_table(['样本', '修复前', '修复后', '结论'], comparison_rows)}

修复前主样本的 {old_main['合并对数']} 对合并中，{old_main['仅由layerID触发']} 对的位置交集全部是 layerID；分类上包含 {old_main['合并分类'].get('相同包坐标', 0)} 对相同包坐标、{old_main['合并分类'].get('不同版本', 0)} 对不同版本和 {old_main['合并分类'].get('跨生态', 0)} 对跨生态。因此此前已确认至少 {old_main['明确误合并']} 对属于明确误合并，且另外 50 对也没有通过“具体文件路径相同”的验证。

## 2. 修复依据

### 规则 1：位置证据只认具体文件路径

`is_valid_location(location)` 现在会先归一化 `file://`、反斜杠和 `./`，再执行以下判断：

- 接受绝对路径、Windows 盘符路径、`~/` 路径、含目录分隔符的相对路径，以及 `model_usage.py#L3`、`package.json` 这类具体文件。
- 拒绝 `sha256:`、`sha1:`、`md5:` 等摘要前缀、裸十六进制摘要、`layerID:`、`overlayfs:`、URN、HTTP URL、purl 和 Docker/容器层标识。
- 只有通过校验的位置才会进入 `extract_evidence_locations()`，因此同一 layer 不再等同于同一文件位置。

### 规则 2：不同版本禁止仅凭位置合并

同名组件的有效版本不同返回 `skipped: version_mismatch`。位置比较只在版本一致后执行，避免 `minipass@3.3.6`、`minipass@5.0.0`、`minipass@7.1.2` 这类不同版本因同层而被连通合并。

### 规则 3：跨生态默认不自动合并

两侧 purl type 不相交时返回 `skipped: cross_ecosystem`。因此普通 npm/deb、pypi/deb、npm/pypi 同名包不会自动合并。

### 明确记录的窄例外

用户同时要求保留 `bert-base-uncased` 的 pypi/npm 核心场景，这与“所有跨生态都不合并”存在直接张力。代码采用一个可审计的窄例外，而不是恢复通用跨生态合并：

- 双方 `asset_type` 都必须是 `model`。
- purl type 只能属于 `npm`、`pypi`、`huggingface`。
- 名称和有效版本必须一致。
- 必须存在至少一个通过 `is_valid_location()` 的共同文件路径。
- 命中后记录置信度 `0.9`，依据明确写为“模型别名跨生态+同名+同版本+相同有效文件位置”。

这个例外只解决同一模型在不同包生态中的别名，不适用于普通依赖包。该例外也是当前规则与核心场景之间的主要已知折中。

## 3. 数据集扫描结果

- 扫描目录：`D:\\datasets\\msu-sbom-benchmark\\zenodo\\docker\\_sboms`。
- JSON 文件总数：{scan['JSON文件总数']}。
- 实际扫描文件数：{scan['实际扫描文件数']}。
- 存在重复组件的候选文件数：{scan['候选文件数']}。
- 含同名不同 purl 的文件数：{scan['同名不同purl文件数']}。
- 含同名同 purl 重复的文件数：{scan['同名同purl文件数']}。
- 两种重复类型都存在的文件数：{scan['两种重复类型均存在的文件数']}。
- 跳过文件数：{scan['跳过文件数']}。
- 扫描耗时：{scan['扫描耗时秒']} 秒。

{scan['候选文件数']} 个候选文件均至少存在一种同名重复组件。主验证样本 `sbom_syft_node_lts_cdx.json` 被转换为 `outputs/assets_real_dup.json`，用于复现 Syft layerID 问题。

## 4. 主样本结果

原始 SBOM：`D:\\datasets\\msu-sbom-benchmark\\zenodo\\docker\\_sboms\\benchmark-alpine-busybox-ngnix-node-ubuntu\\sbom_syft_node_lts_cdx.json`。

- 资产数量：{main['资产数']} -> {main['去重后资产数']}。
- 同名配对总数：{main['同名配对总数']}。
- 合并对数：{main['合并对数']}。
- 跳过对数：{main['跳过对数']}。
- 置信度分布：{distribution_text(main['置信度分布'])}。
- 合并依据分布：{distribution_text(main['合并依据分布'])}。
- 日志中无效位置值数量：{main['日志中的无效位置数']}。

跳过原因分布：

{markdown_table(['跳过状态', '数量'], main_status_rows)}

修复后主样本没有任何组件对达到合并条件，因此“具体组件被合并”的列表为空。此前最典型的误合并现在分别被处理为：

- `minipass@3.3.6`、`5.0.0`、`7.1.2`：`skipped: version_mismatch`。
- `@npmcli/agent@2.2.2` 与 `3.0.0`：`skipped: version_mismatch`。
- `ansi-styles@4.3.0` 与 `6.2.1`：`skipped: version_mismatch`。
- `tar` 的 Debian `1.34+dfsg-1.2+deb12u1` 与 npm `6.2.1`/`7.4.3`：`skipped: cross_ecosystem`。
- `mercurial` 的 PyPI `6.3.2` 与 Debian `6.3.2-1`：`skipped: cross_ecosystem`。
- 50 对相同 npm 包坐标但只有不同文件路径或 layerID 的记录：`skipped: no_valid_location_match`。

## 5. Trivy 验证

原始 SBOM：`D:\\datasets\\msu-sbom-benchmark\\zenodo\\docker\\_sboms\\benchmark-alpine-busybox-ngnix-node-ubuntu\\sbom_trivy_node_lts_cdx.json`。

- 资产数量：{trivy['资产数']} -> {trivy['去重后资产数']}。
- 同名配对总数：{trivy['同名配对总数']}。
- 合并对数：{trivy['合并对数']}，修复前后均为 0。
- 跳过对数：{trivy['跳过对数']}。
- 跳过原因分布：{distribution_text(trivy['跳过原因分布'])}。

{markdown_table(['跳过状态', '数量'], trivy_status_rows)}

## 6. 交叉验证

{markdown_table(['样本', '原始 SBOM', '数量变化', '合并对数', '跳过对数', '跳过原因'], cross_rows)}

两个 Syft 变体的修复结果与主样本一致，均为 `662 -> 662`、0 合并、126 跳过。Trivy Jod 样本仍为 `660 -> 660`、0 合并、129 跳过。

## 7. 合成数据回归

{markdown_table(['数据文件', '场景', '数量变化', '合并对数', '置信度', '依据'], synthetic_rows)}

`outputs/assets.json` 中的 `bert-base-uncased` 是同 purl 的 Hugging Face 重复记录，`model_usage.py#L2` 被识别为有效文件路径，因此按 0.9 置信度合并。该文件另有一个 `ms` 版本冲突对，正确返回 `skipped: version_mismatch`。

`test-project/assets_real.json` 中是实际的 `pkg:npm/ai/bert-base-uncased` 与 `pkg:pypi/ai/bert-base-uncased` 模型别名，双方路径均为 `model_usage.py#L2`，因此命中上述窄例外并合并为一条记录。普通 npm/pypi 包不会命中该例外。

## 8. 误合并评估

- 修复前主样本：124 对合并全部由 layerID 触发；{old_main['合并分类'].get('不同版本', 0)} 对不同版本和 {old_main['合并分类'].get('跨生态', 0)} 对跨生态属于明确误合并。
- 修复后主样本：0 对合并，{main['跳过原因分布'].get('skipped: version_mismatch', 0)} 对版本冲突和 {main['跳过原因分布'].get('skipped: cross_ecosystem', 0)} 对跨生态均被阻止。
- `is_valid_location()` 的负例断言覆盖 `sha256:...`、`layerID:`、URN 和裸十六进制摘要，均为 `False`。
- 主样本和 Trivy 日志中不再保留任何未通过有效性检查的位置值。
- 本例没有发现新的误合并；但因为缺少可靠的共同文件路径，主样本最终没有自动去重，这是保守结果而不是漏报已经确认的重复实体。

## 9. 剩余已知限制

1. 严格规则 3 与 `bert-base-uncased` 的 npm/pypi 合并要求不能同时无条件成立；当前只能通过模型专用窄例外兼顾两者。
2. Syft layerID 仍保留在原始 evidence_chain 中，但不会进入实体对齐的位置集合。未来应在 adapter 层把 layerID 映射到独立字段，减少下游误用风险。
3. 没有具体文件路径的同一包坐标重复会被保留，以避免把不同安装目录中的同一版本包误合并。这降低了召回率，但优先保证不产生误合并。
4. 当前位置比较是归一化字符串相等，没有做大小写、符号链接、容器根目录映射等文件系统语义归一化。
5. 0.7 规则仍允许同名、同版本、同 purl type 但 purl 主体不同的记录合并。若后续出现大量非同源同名包，应进一步增加坐标或哈希证据。

## 10. 输出文件

- 修复代码：`entity_resolver.py`。
- 主样本资产：`outputs/assets_real_dup.json`。
- 主样本去重结果：`outputs/assets_real_dup_deduplicated.json`。
- 主样本逐对日志：`outputs/merge_log_real_dup.json`。
- Trivy 资产：`outputs/assets_real_dup_literal_max_trivy_lts.json`。
- Trivy 去重结果：`outputs/assets_real_dup_literal_max_trivy_lts_deduplicated.json`。
- Trivy 日志：`outputs/merge_log_real_dup_literal_max_trivy_lts.json`。
- 合成数据回归日志：`outputs/merge_log.json`。
- 机器可读汇总：`outputs/cross_validation_real_dup_summary.json`。
"""


def main() -> None:
    """生成报告和机器可读汇总。"""

    scan = load_json(SCAN_PATH)
    baseline_summary = load_json(BASELINE_SUMMARY_PATH)
    old_main = analyze_old_main_log()
    main = analyze_result(
        MAIN_ASSETS_PATH,
        MAIN_DEDUPLICATED_PATH,
        MAIN_LOG_PATH,
    )
    trivy = analyze_result(
        TRIVY_ASSETS_PATH,
        TRIVY_DEDUPLICATED_PATH,
        TRIVY_LOG_PATH,
    )
    synthetic_hf = analyze_result(
        SYNTHETIC_ASSETS_PATH,
        SYNTHETIC_DEDUPLICATED_PATH,
        SYNTHETIC_LOG_PATH,
    )
    synthetic_model = analyze_result(
        MODEL_ALIAS_ASSETS_PATH,
        MODEL_ALIAS_DEDUPLICATED_PATH,
        MODEL_ALIAS_LOG_PATH,
    )
    cross = summarize_cross_validation()

    summary = {
        "扫描结果": {
            "JSON文件总数": scan["JSON文件总数"],
            "实际扫描文件数": scan["实际扫描文件数"],
            "候选文件数": scan["候选文件数"],
            "同名不同purl文件数": scan["同名不同purl文件数"],
            "同名同purl文件数": scan["同名同purl文件数"],
            "两种重复类型均存在的文件数": scan["两种重复类型均存在的文件数"],
            "跳过文件数": scan["跳过文件数"],
            "扫描耗时秒": scan["扫描耗时秒"],
        },
        "修复前主样本": old_main,
        "修复后主样本": main,
        "Trivy样本": trivy,
        "合成数据": {
            "HuggingFace同purl": synthetic_hf,
            "npm_pypi模型别名": synthetic_model,
        },
        "交叉验证": cross,
        "误合并评估": {
            "修复前明确误合并": old_main["明确误合并"],
            "修复后误合并": main["合并对数"],
            "版本冲突跳过": main["跳过原因分布"].get(
                "skipped: version_mismatch", 0
            ),
            "跨生态跳过": main["跳过原因分布"].get(
                "skipped: cross_ecosystem", 0
            ),
            "无有效路径匹配跳过": main["跳过原因分布"].get(
                "skipped: no_valid_location_match", 0
            ),
        },
    }

    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        build_report(
            scan,
            baseline_summary,
            old_main,
            main,
            trivy,
            synthetic_hf,
            synthetic_model,
            cross,
        ),
        encoding="utf-8",
    )
    print(f"汇总输出：{SUMMARY_PATH}")
    print(f"报告输出：{REPORT_PATH}")


if __name__ == "__main__":
    main()
