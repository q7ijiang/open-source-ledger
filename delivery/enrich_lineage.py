#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""enrich_lineage.py — 对 cdxgen 生成的空 BOM 做血缘补数据。

背景：cdxgen 扫某些 GGUF 仓库（如 TheBloke/Qwen2.5-0.5B-Instruct-GGUF）时
返回空 BOM（components=[]），无法从仓库解析出模型组件与 pedigree.ancestors，
导致下游血缘提取得到 0 节点、0 边。

本脚本在 generate_bom 之后、extract_hf_lineage 之前介入：对 components 为空的
BOM，从模型名提取关键词，匹配已知模型家族，推断基座模型祖先并回填到
components[0].pedigree.ancestors，证据等级标注为 C（推断所得）。
补不上的 BOM 加 undetermined_reason 字段。

用法：
    python enrich_lineage.py --bom-dir outputs/lineage_scan \
        --model TheBloke/Qwen2.5-0.5B-Instruct-GGUF
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EVIDENCE_LEVEL = "C"

# 已知模型家族：关键词 -> 推断的基座模型祖先（owner/name）。
FAMILY_RULES: list[tuple[str, str]] = [
    ("qwen2.5-0.5b", "Qwen/Qwen2.5-0.5B"),
    ("llama-2", "meta-llama/Llama-2-7b"),
    ("llama2", "meta-llama/Llama-2-7b"),
    ("smollm2", "HuggingFaceTB/SmolLM2-135M"),
    ("bert-base", "google-bert/bert-base-uncased"),
]


def split_model_id(model_id: str) -> tuple[str, str]:
    """把 owner/name 形式的模型 id 拆成 (group, name)。"""
    model_id = (model_id or "").strip().strip("/")
    if "/" in model_id:
        group, name = model_id.split("/", 1)
        return group, name
    return "", model_id


def hf_purl(model_id: str) -> str:
    """构造 Hugging Face purl：pkg:huggingface/<owner>/<name>。"""
    group, name = split_model_id(model_id)
    if group:
        return f"pkg:huggingface/{group}/{name}"
    return f"pkg:huggingface/{name}"


def infer_ancestor(model_name: str) -> str | None:
    """从模型名关键词推断祖先模型 id（owner/name）。"""
    lowered = (model_name or "").lower()
    for keyword, ancestor in FAMILY_RULES:
        if keyword in lowered:
            return ancestor
    return None


def model_name_from_bom(data: dict, bom_path: Path, fallback: str | None = None) -> str:
    """还原原始模型名：文件名优先（generate_bom 用 '__' 替换 '/'），metadata 兜底。"""
    from_file = bom_path.stem.replace("__", "/")
    if from_file:
        return from_file
    metadata = data.get("metadata") or {}
    component = metadata.get("component") or {}
    group = (component.get("group") or "").strip()
    name = (component.get("name") or "").strip()
    if group or name:
        return f"{group}/{name}".strip("/")
    return (fallback or "").strip()


def enrich_bom(bom_path: Path, model_override: str | None = None) -> tuple[str, str]:
    """对单个 BOM 做补数据。

    返回 (status, message)：
      status == "skip"          -> 组件非空，无需处理
      status == "enriched"      -> 已推断并回填祖先
      status == "undetermined"  -> 推断失败，已写 undetermined_reason
    """
    data = json.loads(bom_path.read_text(encoding="utf-8"))
    components = data.get("components")
    if isinstance(components, list) and components:
        return "skip", "components 非空，无需补数据"

    model_name = model_name_from_bom(data, bom_path, model_override)
    ancestor = infer_ancestor(model_name)
    if not ancestor:
        data["undetermined_reason"] = (
            f"无法从模型名 {model_name!r} 推断基座模型祖先（未命中已知家族）"
        )
        bom_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return "undetermined", f"未命中家族，已写 undetermined_reason（模型名：{model_name}）"

    group, name = split_model_id(model_name)
    anc_group, anc_name = split_model_id(ancestor)
    data["components"] = [
        {
            "group": group,
            "name": name,
            "type": "model",
            "purl": hf_purl(model_name),
            "pedigree": {
                "ancestors": [
                    {
                        "group": anc_group,
                        "name": anc_name,
                        "purl": hf_purl(ancestor),
                        "evidence_level": EVIDENCE_LEVEL,
                    }
                ]
            },
        }
    ]
    bom_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return "enriched", f"推断祖先 {ancestor}（evidence_level={EVIDENCE_LEVEL}）"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="对 cdxgen 空 BOM 做血缘补数据")
    parser.add_argument("--bom-dir", required=True, help="BOM 目录（generate_bom 递归输出目录）")
    parser.add_argument("--model", default=None, help="根模型名（owner/name），作为文件名解析失败时的兜底")
    args = parser.parse_args(argv)

    bom_dir = Path(args.bom_dir)
    if not bom_dir.is_dir():
        print(f"错误：BOM 目录不存在：{bom_dir}", file=sys.stderr)
        return 1

    bom_paths = sorted(bom_dir.glob("*.json"))
    enriched = undetermined = skipped = 0
    for bom_path in bom_paths:
        try:
            status, message = enrich_bom(bom_path, args.model)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  [跳过] {bom_path.name}：读取失败 {exc}")
            continue
        if status == "enriched":
            enriched += 1
        elif status == "undetermined":
            undetermined += 1
        else:
            skipped += 1
        print(f"  [{status}] {bom_path.name}：{message}")

    print(
        f"补数据完成：扫描 {len(bom_paths)} 个 BOM，"
        f"推断 {enriched} 个，未命中 {undetermined} 个，跳过 {skipped} 个"
    )
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
