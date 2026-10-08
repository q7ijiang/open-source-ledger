#!/usr/bin/env python3
"""generate_bom.py — 输入 Hugging Face 模型名，自动调用 cdxgen 生成 CycloneDX BOM。

用法示例:
    python generate_bom.py "openai-community/gpt2"
    python generate_bom.py "meta-llama/Llama-2-7b-chat-hf" -o bom.json
    python generate_bom.py "TheBloke/Llama-2-7B-Chat-GGUF" -t ai
    python generate_bom.py "TheBloke/Llama-2-7B-Chat-GGUF" --recursive --outdir outputs/lineage_scan

依赖:
    本机需有可用的 cdxgen（Windows 下为 cdxgen.cmd）。
    可通过环境变量 CDXGEN_PATH 指定 cdxgen 可执行文件路径。
    可通过环境变量 HF_TOKEN / HUGGING_FACE_HUB_TOKEN 提供 HF 访问令牌
    （扫描 gated 模型元数据无需令牌；仅在需要读取 gated 文件内容时才有用）。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Windows 硬编码 fallback（便携版 Node 全局安装路径）；仅作为最后兜底。
_WINDOWS_FALLBACK_CDXGEN = (
    r"C:\Users\Qijiang\AppData\Local\Temp\cdxgen_node"
    r"\node-v24.19.0-win-x64\cdxgen.cmd"
)


def find_cdxgen():
    """跨平台定位 cdxgen：CDXGEN_PATH -> PATH -> Windows 兜底路径。

    按以下顺序查找：
    1. 环境变量 CDXGEN_PATH（存在且有效）
    2. shutil.which("cdxgen")（PATH 中）
    3. Windows 硬编码 fallback
    都找不到时抛出 RuntimeError，错误信息包含安装命令与 CDXGEN_PATH 提示。
    """
    # a. 环境变量 CDXGEN_PATH（存在且有效）
    env_bin = os.environ.get("CDXGEN_PATH")
    if env_bin and Path(env_bin).exists():
        return env_bin

    # b. PATH 中的 cdxgen
    found = shutil.which("cdxgen")
    if found:
        return found

    # c. Windows 硬编码 fallback
    if Path(_WINDOWS_FALLBACK_CDXGEN).exists():
        return _WINDOWS_FALLBACK_CDXGEN

    # d. 都找不到时报错
    raise RuntimeError(
        "cdxgen 未找到。\n"
        "请先安装：npm install -g @cyclonedx/cdxgen\n"
        "或将 cdxgen 加入 PATH；"
        "也可以设置环境变量 CDXGEN_PATH 指向 cdxgen 可执行文件。"
    )


def run_cdxgen(model, out_file, cdxgen_bin, asset_type, extra_args):
    """调用 cdxgen 生成 BOM，返回 CompletedProcess。"""
    cmd = [cdxgen_bin, "-t", asset_type, "-o", str(out_file), model]
    cmd.extend(extra_args or [])
    # Windows 下 .cmd/.bat 需要经 cmd.exe 执行。
    if cdxgen_bin.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c"] + cmd
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600)


def summarize_bom(bom_path):
    """读取生成的 BOM，返回人类可读的摘要。"""
    try:
        data = json.loads(Path(bom_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return f"  读取 BOM 失败: {exc}"

    comps = data.get("components", [])
    lines = [f"  components 数量: {len(comps)}"]
    for c in comps:
        name = f"{c.get('group', '')}/{c.get('name', '')}".lstrip("/")
        lines.append(f"    - {name} (type={c.get('type', '')})")
        if c.get("purl"):
            lines.append(f"      purl: {c['purl']}")
        if c.get("licenses"):
            for lic in c["licenses"]:
                info = lic.get("license", {})
                license_name = (
                    info.get("name")
                    or (("id" in info and f"SPDX:{info['id']}") or "(见 url)")
                )
                lines.append(f"      license: {license_name}")
        else:
            lines.append("      license: 无")
        lines.append("      modelCard: " + ("有" if c.get("modelCard") else "无"))
        ped = c.get("pedigree")
        ancestors = ped.get("ancestors", []) if isinstance(ped, dict) else []
        if ancestors:
            lines.append(f"      pedigree.ancestors: {len(ancestors)} 个")
            for a in ancestors:
                anc = f"{a.get('group', '')}/{a.get('name', '')}".lstrip("/")
                lines.append(f"        祖先: {anc}  purl={a.get('purl', '(无)')}")
        else:
            lines.append("      pedigree.ancestors: 无（基座模型或无血统信息）")
    return "\n".join(lines)


def ancestor_model_id(ancestor):
    """从祖先对象推断 HF 模型 id（group/name 优先，purl 兜底）。"""
    group = (ancestor.get("group") or "").strip()
    name = (ancestor.get("name") or "").strip()
    if name:
        return f"{group}/{name}" if group else name
    purl = ancestor.get("purl") or ""
    if purl.startswith("pkg:huggingface/"):
        body = purl.split(":", 1)[1].split("?", 1)[0].split("@", 1)[0]
        parts = [p for p in body.split("/") if p]
        if parts and parts[0] == "huggingface":
            parts = parts[1:]
        if len(parts) >= 2:
            return "/".join(parts[:2])
        if len(parts) == 1:
            return parts[0]
    return None


def extract_ancestors(bom_path):
    """从 BOM 中提取所有祖先模型 id（owner/name 形式）。"""
    try:
        data = json.loads(Path(bom_path).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    result = []
    for c in data.get("components", []):
        ped = c.get("pedigree")
        ancestors = ped.get("ancestors", []) if isinstance(ped, dict) else []
        for a in ancestors:
            model_id = ancestor_model_id(a)
            if model_id:
                result.append(model_id)
    return result


def bom_has_components(bom_path):
    """判断 BOM 是否至少包含一个组件（用于检测空 BOM）。"""
    try:
        data = json.loads(Path(bom_path).read_text(encoding="utf-8"))
        return bool(data.get("components"))
    except Exception:  # noqa: BLE001
        return False


def scan_lineage(model, outdir, cdxgen_bin, asset_type, extra_args, visited, depth, stats):
    """递归扫描模型及其祖先，所有 BOM 写入同一目录。"""
    if model in visited:
        return
    visited.add(model)

    out_file = outdir / (model.replace("/", "__") + ".json")
    proc = run_cdxgen(model, out_file, cdxgen_bin, asset_type, extra_args)
    # 冷启动偶发空 BOM：重试一次
    if proc.returncode == 0 and out_file.exists() and not bom_has_components(out_file):
        proc = run_cdxgen(model, out_file, cdxgen_bin, asset_type, extra_args)
    if proc.returncode != 0 or not out_file.exists():
        stats["failed"].append(model)
        return

    stats["models"].append(model)
    if depth > stats["max_depth"]:
        stats["max_depth"] = depth
    for anc in extract_ancestors(out_file):
        scan_lineage(anc, outdir, cdxgen_bin, asset_type, extra_args, visited, depth + 1, stats)


def run_lineage(args, cdxgen_bin):
    """递归扫描入口：把根模型及整条祖先链的 BOM 写入同一目录。"""
    outdir = Path(args.outdir) if args.outdir else Path("outputs") / "lineage_scan"
    outdir.mkdir(parents=True, exist_ok=True)

    # 扫描前清空输出目录中的旧 *.json，避免上次运行的残留 BOM 混入本次血缘图。
    removed = 0
    for stale in outdir.glob("*.json"):
        try:
            stale.unlink()
            removed += 1
        except OSError:
            pass
    if removed:
        print(f"已清空输出目录中 {removed} 个旧 *.json 文件")

    visited = set()
    stats = {"models": [], "failed": [], "max_depth": 0}

    print(f"cdxgen: {cdxgen_bin}")
    print(f"递归扫描根模型: {args.model}")
    print(f"输出目录: {outdir}")
    print("运行中 ...")
    scan_lineage(args.model, outdir, cdxgen_bin, args.type, args.extra, visited, 0, stats)

    print("")
    print("递归扫描完成:")
    print(f"  - 生成 BOM 数量: {len(stats['models'])}")
    print(f"  - 血缘层级（祖先层数）: {stats['max_depth']}")
    if stats["failed"]:
        print(f"  - 失败模型: {', '.join(stats['failed'])}")
    print("  - BOM 文件:")
    for m in stats["models"]:
        f = outdir / (m.replace("/", "__") + ".json")
        size = f.stat().st_size if f.exists() else 0
        print(f"      {m}  ->  {f.name}  ({size} 字节)")
    return 0 if args.model not in stats["failed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="输入 HF 模型名，自动调 cdxgen 生成 CycloneDX BOM"
    )
    parser.add_argument("model", help="Hugging Face 模型名，如 meta-llama/Llama-2-7b-chat-hf")
    parser.add_argument("-o", "--output", default=None, help="输出 BOM 文件路径（默认 outputs/<模型名>.json）")
    parser.add_argument("-t", "--type", default="ai", help="cdxgen 项目类型（默认 ai）")
    parser.add_argument("--extra", nargs="*", default=[], help="透传给 cdxgen 的额外参数")
    parser.add_argument("--recursive", action="store_true", help="递归扫描祖先链（pedigree.ancestors），BOM 写入同一目录")
    parser.add_argument("--outdir", default=None, help="递归扫描时的输出目录（默认 outputs/lineage_scan）")
    args = parser.parse_args(argv)

    try:
        cdxgen_bin = find_cdxgen()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.recursive:
        return run_lineage(args, cdxgen_bin)

    out_file = Path(args.output) if args.output else (
        Path("outputs") / (args.model.replace("/", "__") + ".json")
    )
    out_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"cdxgen: {cdxgen_bin}")
    print(f"扫描模型: {args.model}")
    print(f"输出文件: {out_file}")
    print("运行中 ...")
    proc = run_cdxgen(args.model, out_file, cdxgen_bin, args.type, args.extra)
    print(f"退出码: {proc.returncode}")

    if proc.returncode != 0:
        print("失败。输出片段:")
        print((proc.stdout or "")[-2000:])
        print((proc.stderr or "")[-2000:])
        return proc.returncode

    if not out_file.exists():
        print(f"警告: 未生成输出文件 {out_file}")
        return 1

    print(f"BOM 文件大小: {out_file.stat().st_size} 字节")
    print(summarize_bom(out_file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
