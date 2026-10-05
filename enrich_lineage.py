#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""enrich_lineage.py — 对 cdxgen 生成的空 BOM 做血缘补数据（三级降级策略）。

背景：cdxgen 扫某些 GGUF 仓库（如 TheBloke/Qwen2.5-0.5B-Instruct-GGUF）时
返回空 BOM（components=[]），无法从仓库解析出模型组件与 pedigree.ancestors，
导致下游血缘提取得到 0 节点、0 边。

本脚本在 generate_bom 之后、extract_hf_lineage 之前介入：对 components 为空的
BOM，按三级降级策略推断基座模型祖先并回填到 components[0].pedigree.ancestors：

    第一级：HF API 的 base_model / base_models 字段（首选，evidence_level=A，source=hf_api）
    第二级：关键词规则匹配 FAMILY_RULES（降级，evidence_level=C，source=keyword_rule）
    第三级：从模型卡文本正则提取（兜底，evidence_level=C，source=text_extraction）

三级都失败时，BOM 写 undetermined 字段（reason + suggestions）。

用法：
    python enrich_lineage.py --bom-dir outputs/lineage_scan \
        --model TheBloke/Qwen2.5-0.5B-Instruct-GGUF
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# 一级（HF API）查询超时（秒）。
HF_API_TIMEOUT = 5.0

# 三级全部失败时写入 BOM 的 undetermined 字段内容。
UNDETERMINED_REASON = "无法推断 base_model"
UNDETERMINED_SUGGESTIONS = [
    "检查模型卡 base_model 字段",
    "查看作者 GitHub 训练脚本",
    "联系模型作者",
]

# 已知模型家族：关键词 -> 推断的基座模型祖先（owner/name）。
# 注意：规则按顺序匹配、先命中先返回，因此更具体的关键词必须排在更泛化的关键词
# 之前（例如 "distilbert" 必须在 "bert-base" 之前，否则 distilbert-* 会被
# "bert-base" 抢先命中）。
FAMILY_RULES: list[tuple[str, str]] = [
    # Qwen 系列
    ("qwen2.5-0.5b", "Qwen/Qwen2.5-0.5B"),
    ("qwen2.5-7b", "Qwen/Qwen2.5-7B"),
    ("qwen2.5-1.5b", "Qwen/Qwen2.5-1.5B"),
    # Llama 系列
    ("llama-2", "meta-llama/Llama-2-7b"),
    ("llama2", "meta-llama/Llama-2-7b"),
    ("llama-3", "meta-llama/Meta-Llama-3-8B"),
    ("llama3", "meta-llama/Meta-Llama-3-8B"),
    # 其他 LLM 系列
    ("phi-3", "microsoft/Phi-3-mini-4k"),
    ("gemma-2", "google/gemma-2-2b"),
    ("mistral-7b", "mistralai/Mistral-7B-v0.1"),
    ("mixtral", "mistralai/Mixtral-8x7B-v0.1"),
    # 编码器 / 小型模型
    ("roberta-base", "FacebookAI/roberta-base"),
    ("distilbert", "google-bert/bert-base-uncased"),
    ("deberta-v3", "microsoft/deberta-v3-base"),
    ("minilm-l6", "nreimers/MiniLM-L6-H384-uncased"),
    # 序列到序列模型
    ("t5-base", "google/flan-t5-base"),
    ("flan-t5", "google/flan-t5-base"),
    # 其余原有规则（bert-base 放最后，避免抢占 distilbert 等更具体关键词）
    ("smollm2", "HuggingFaceTB/SmolLM2-135M"),
    ("bert-base", "google-bert/bert-base-uncased"),
]

# 三级文本提取的正则（不区分大小写）。
TEXT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"based\s+on\s+([\w\-./]+)", re.IGNORECASE),
    re.compile(r"fine-?tuned\s+from\s+([\w\-./]+)", re.IGNORECASE),
    re.compile(r"base\s+model:?\s+([\w\-./]+)", re.IGNORECASE),
    re.compile(r"derived\s+from\s+([\w\-./]+)", re.IGNORECASE),
]


@dataclass
class Inference:
    """一次推断结果：祖先模型 id、证据等级、证据来源。"""

    ancestor: str
    evidence_level: str
    source: str


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


def _is_self_loop(ancestor: str, model_name: str) -> bool:
    """判断推断出的祖先是否就是输入模型本身（自环）。"""
    return (ancestor or "").strip().lower() == (model_name or "").strip().lower()


def _model_id_from_base_models_entry(entry: object) -> str:
    """从 cardData.base_models 的条目里取模型 id（兼容 str / ModelInfo）。"""
    if isinstance(entry, str):
        return entry.strip()
    for attr in ("id", "modelId"):
        val = getattr(entry, attr, None)
        if val:
            return str(val).strip()
    return ""


def infer_from_hf_api(model_name: str) -> Inference | None:
    """第一级：查 HF API 的 base_model / base_models 字段。

    任何异常（网络 / 超时 / 401 / 离线）都不崩溃，打印警告后返回 None。
    """
    try:
        from huggingface_hub import model_info
    except ImportError:
        print("警告：未安装 huggingface_hub，跳过 HF API 一级推断", file=sys.stderr)
        return None

    try:
        info = model_info(
            model_name,
            token=os.environ.get("HF_TOKEN"),
            timeout=HF_API_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"警告：HF API 查询失败（{model_name}）：{exc}", file=sys.stderr)
        return None

    card = getattr(info, "card_data", None)
    if not card:
        return None

    base = getattr(card, "base_model", None)
    if base and str(base).strip() and not _is_self_loop(str(base), model_name):
        return Inference(str(base).strip(), "A", "hf_api")

    bases = getattr(card, "base_models", None) or []
    for entry in bases:
        candidate = _model_id_from_base_models_entry(entry)
        if candidate and not _is_self_loop(candidate, model_name):
            return Inference(candidate, "A", "hf_api")

    return None


def infer_from_keyword(model_name: str) -> Inference | None:
    """第二级：关键词规则匹配（降级）。

    命中则返回；若推断出的祖先与输入模型本身相同（自环），视为失败返回 None。
    """
    lowered = (model_name or "").strip().lower()
    for keyword, ancestor in FAMILY_RULES:
        if keyword in lowered:
            if _is_self_loop(ancestor, model_name):
                return None
            return Inference(ancestor, "C", "keyword_rule")
    return None


def _collect_descriptions(data: dict) -> list[str]:
    """从 BOM 收集可用于文本提取的描述（metadata.component.description / modelCard）。"""
    texts: list[str] = []
    metadata = data.get("metadata") or {}
    component = metadata.get("component") or {}

    description = component.get("description")
    if isinstance(description, str) and description.strip():
        texts.append(description.strip())

    model_card = component.get("modelCard")
    if isinstance(model_card, str) and model_card.strip():
        texts.append(model_card.strip())
    elif isinstance(model_card, dict):
        for key in ("description", "text", "content", "summary"):
            val = model_card.get(key)
            if isinstance(val, str) and val.strip():
                texts.append(val.strip())

    return texts


def infer_from_text(model_name: str, data: dict | None) -> Inference | None:
    """第三级：从模型卡文本正则提取基座模型（兜底）。"""
    if not data:
        return None
    for text in _collect_descriptions(data):
        for pattern in TEXT_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            candidate = match.group(1).strip().strip("/.")
            if candidate and not _is_self_loop(candidate, model_name):
                return Inference(candidate, "C", "text_extraction")
    return None


def infer_ancestor(model_name: str, data: dict | None = None) -> Inference | None:
    """按三级降级顺序推断祖先：HF API → 关键词规则 → 文本提取。

    全部失败返回 None。
    """
    result = infer_from_hf_api(model_name)
    if result:
        return result
    result = infer_from_keyword(model_name)
    if result:
        return result
    return infer_from_text(model_name, data)


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
      status == "undetermined"  -> 三级推断均失败，已写 undetermined 字段
    """
    data = json.loads(bom_path.read_text(encoding="utf-8"))
    components = data.get("components")
    if isinstance(components, list) and components:
        return "skip", "components 非空，无需补数据"

    model_name = model_name_from_bom(data, bom_path, model_override)
    inference = infer_ancestor(model_name, data)
    if not inference:
        data["undetermined"] = {
            "reason": UNDETERMINED_REASON,
            "suggestions": UNDETERMINED_SUGGESTIONS,
        }
        bom_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return "undetermined", f"三级推断均失败，已写 undetermined（模型名：{model_name}）"

    ancestor = inference.ancestor
    group, name = split_model_id(model_name)
    anc_group, anc_name = split_model_id(ancestor)
    data["components"] = [
        {
            "group": group,
            "name": name,
            "type": "machine-learning-model",
            "purl": hf_purl(model_name),
            "pedigree": {
                "ancestors": [
                    {
                        "group": anc_group,
                        "name": anc_name,
                        "purl": hf_purl(ancestor),
                        "evidence_level": inference.evidence_level,
                        "source": inference.source,
                    }
                ]
            },
        }
    ]
    bom_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return (
        "enriched",
        f"推断祖先 {ancestor}（source={inference.source}，"
        f"evidence_level={inference.evidence_level}）",
    )


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
