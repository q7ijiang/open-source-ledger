#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_project.py — 扫描一个项目仓库，识别其中用到的 Hugging Face 模型名。

背景：
    cdxgen 能扫项目（cdxgen -t ai -t python <项目路径>），识别出项目里用到的
    HF 模型名，但项目 BOM 里模型组件只有 name、没有 pedigree.ancestors，无法
    直接用于血缘提取。因此本脚本只负责「识别模型名」，随后由 main.py 对每个
    模型名重新调用 --model 模式递归扫祖先链。

逻辑：
    1. 调 cdxgen -t ai -t python --no-install-deps -o <临时BOM> <项目路径>
       （--no-install-deps 避免在用户项目里安装依赖）；
    2. 读 BOM，遍历 components；
    3. 筛出 type == "machine-learning-model" 的组件；
    4. 对每个组件按 evidence.occurrences[].location 打开源码、正则提取完整模型名，
       提取失败时回退用 BOM 里的 name；最后去重（同一模型可能出现两次：npm 与 pypi 各一份）；
    5. 输出模型名列表到 stdout（JSON 格式），并写入 --output 文件。

用法：
    python scan_project.py --project <项目路径> --output <模型名列表.json>
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# 复用 generate_bom.py 的 cdxgen 定位逻辑（CDXGEN_PATH -> PATH -> Windows 兜底）。
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_bom  # noqa: E402

# 与 main.py 保持一致的模型组件类型集合。
ML_MODEL_TYPES = {"machine-learning-model", "model"}

# 匹配 from_pretrained("模型名") / from_pretrained('模型名')，提取完整模型名。
FROM_PRETRAINED_RE = re.compile(r"""from_pretrained\(\s*["']([^"']+)["']""")

# 匹配 pipeline(..., model="owner/model") 等 model= 关键字传参。
MODEL_KWARG_RE = re.compile(r"""\bmodel\s*=\s*["']([^"']+)["']""")


def run_project_scan(project_path: Path, out_file: Path) -> subprocess.CompletedProcess:
    """调 cdxgen 扫描项目，把 BOM 写到 out_file。"""
    cdxgen_bin = generate_bom.find_cdxgen()
    cmd = [
        cdxgen_bin,
        "-t", "ai",
        "-t", "python",
        "--no-install-deps",
        "-o", str(out_file),
        str(project_path),
    ]
    # Windows 下 .cmd/.bat 需要经 cmd.exe 执行。
    if cdxgen_bin.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c"] + cmd
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600)


def _split_location(location: str) -> tuple[str | None, int | None]:
    """解析 occurrence.location，如 "model_usage.py#L2" -> ("model_usage.py", 2)。

    无法解析时返回 (None, None)。兼容 "file.py#L2-L5" 之类的范围写法。
    """
    location = (location or "").strip()
    if not location:
        return None, None
    file_part, sep, line_part = location.partition("#")
    if not sep or not file_part.strip():
        return None, None
    line_no: int | None = None
    for token in line_part.split("-"):
        token = token.strip()
        if token and token[0] in "Ll":
            try:
                line_no = int(token[1:])
            except ValueError:
                continue
            break
    return file_part.strip(), line_no


def _read_model_from_source(project_path: Path, location: str) -> str | None:
    """按 occurrence.location 打开源码、读取对应行，正则提取完整模型名。

    失败（文件不存在、行号越界、正则不匹配）时返回 None。
    """
    file_part, line_no = _split_location(location)
    if not file_part or line_no is None:
        return None
    src_path = project_path / file_part
    try:
        lines = src_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if line_no < 1 or line_no > len(lines):
        return None
    match = FROM_PRETRAINED_RE.search(lines[line_no - 1])
    if not match:
        match = MODEL_KWARG_RE.search(lines[line_no - 1])
    if not match:
        return None
    return match.group(1).strip() or None


def _component_from_static_asset(project_path: Path | None, component: dict) -> bool:
    """判断组件是否由 huggingface.co 静态资源 URL 误报而来。

    cdxgen 会把源码里的静态资源 URL（如
    https://huggingface.co/front/assets/homepage/hugs-mobile.svg）误识别为
    machine-learning-model（group=front、name=assets）。若组件任一 occurrence
    所在源码行是 URL，则视为静态资源误报，不作为模型。
    """
    if project_path is None:
        return False
    evidence = component.get("evidence") or {}
    occurrences = evidence.get("occurrences", []) if isinstance(evidence, dict) else []
    for occ in occurrences or []:
        if not isinstance(occ, dict):
            continue
        file_part, line_no = _split_location(occ.get("location") or "")
        if not file_part or line_no is None:
            continue
        try:
            lines = (project_path / file_part).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        if line_no < 1 or line_no > len(lines):
            continue
        if "://" in lines[line_no - 1]:
            return True
    return False


def _complete_model_org(component: dict, name: str) -> str:
    """为缺少 org 前缀的模型名补全 org。

    当源码只给出裸模型名（如 pipeline(model="gpt2")）或经变量传参时，
    从 BOM 的 group 或 externalReferences 中补全。仅当 purl 为
    pkg:huggingface/<org>/<name> 时，group 才是真实 org；
    pkg:npm/pypi/huggingface/<name> 的 group 是占位符（如 gpt2 的 huggingface）。
    """
    name = (name or "").strip()
    if not name or "/" in name:
        return name

    group = str(component.get("group") or "").strip()
    purl = str(component.get("purl") or "")
    if purl.lower().startswith("pkg:huggingface/") and group:
        return f"{group}/{name}"

    for ref in component.get("externalReferences", []) or []:
        if not isinstance(ref, dict):
            continue
        url = str(ref.get("url") or "")
        m = re.search(r"huggingface\.co/([^/]+)/([^/?#]+)", url)
        if m and m.group(2) == name:
            return f"{m.group(1)}/{name}"

    return name


def extract_model_names(bom_path: Path, project_path: Path | None = None) -> list[str]:
    """从项目 BOM 中提取去重后的 machine-learning-model 名称列表。

    优先按 evidence.occurrences[].location 打开源码、用正则提取完整模型名
    （如 "allenai/Llama-3.1-Tulu-3-8B"）；提取失败（文件不存在、正则不匹配）
    时回退用 BOM 里的 name。
    """
    data = json.loads(bom_path.read_text(encoding="utf-8"))
    names: list[str] = []
    seen: set[str] = set()
    for component in data.get("components", []) or []:
        if not isinstance(component, dict):
            continue
        if component.get("type") not in ML_MODEL_TYPES:
            continue
        purl = str(component.get("purl") or "")
        if "huggingface" not in purl.lower():
            continue
        if _component_from_static_asset(project_path, component):
            continue
        name = (component.get("name") or "").strip()
        if not name:
            continue

        resolved: str | None = None
        if project_path is not None:
            evidence = component.get("evidence") or {}
            occurrences = (
                evidence.get("occurrences", []) if isinstance(evidence, dict) else []
            )
            for occ in occurrences or []:
                if not isinstance(occ, dict):
                    continue
                resolved = _read_model_from_source(
                    project_path, occ.get("location") or ""
                )
                if resolved:
                    break

        final_name = _complete_model_org(component, resolved or name)
        if final_name in seen:
            continue
        seen.add(final_name)
        names.append(final_name)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="扫描项目仓库，识别 HF 模型名")
    parser.add_argument("--project", required=True, help="项目路径")
    parser.add_argument("--output", required=True, help="输出模型名列表 JSON 文件路径")
    args = parser.parse_args(argv)

    project_path = Path(args.project)
    if not project_path.exists():
        print(f"错误：项目路径不存在：{project_path}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="scan_project_") as tmp:
        bom_file = Path(tmp) / "project_bom.json"
        print(f"cdxgen 扫描项目：{project_path}", file=sys.stderr)
        proc = run_project_scan(project_path, bom_file)
        if proc.returncode != 0 or not bom_file.exists():
            print("cdxgen 扫描失败。输出片段：", file=sys.stderr)
            print((proc.stdout or "")[-2000:], file=sys.stderr)
            print((proc.stderr or "")[-2000:], file=sys.stderr)
            return 1
        models = extract_model_names(bom_file, project_path)

    # 写文件（带缩进，便于人工查看）。
    output_path.write_text(
        json.dumps(models, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # stdout 只输出纯 JSON，供 main.py 等调用方解析。
    print(json.dumps(models, ensure_ascii=False))
    print(f"识别到 {len(models)} 个 HF 模型，已写入 {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
