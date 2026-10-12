# -*- coding: utf-8 -*-
"""AI 模型血缘许可证风险审计工具 — Streamlit 输入界面（答辩演示用）。

模式：
  单模型  ：输入 ModelScope 模型名 → main.py --model → 血缘风险图 + 中文报告
  项目    ：输入项目路径 → main.py --project → 合并血缘风险图 + 中文报告
  时间对比：上传 t0 / t1 两个 BOM → main.py --diff + render_diff.py → 时间轴传播图 + 中文报告

约束（对齐组长要求）：
  - 不重写任何数据管道逻辑，只通过 subprocess 调用 main.py 现有功能
  - 不写死路径：图由 render_graph.py / render_diff.py 的 --input/--before/--after 参数读取
  - 页面简洁，风险图居中展示
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def _run(args: list[str]) -> None:
    """调用 main.py / render_graph.py / render_diff.py，stdout 实时展示。"""
    proc = subprocess.run(
        [PY, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    if proc.stdout:
        st.text(proc.stdout[-1200:])
    if proc.returncode != 0:
        st.error(proc.stderr[-1200:] if proc.stderr else "命令执行失败（exit %d）" % proc.returncode)
        st.stop()


def _embed_html(html_path: Path, height: int = 620) -> None:
    """内嵌 HTML 血缘图（自包含：echarts 已内联，无任何 CDN / 外部依赖）。"""
    html = html_path.read_text(encoding="utf-8")
    components.html(html, height=height, scrolling=True)


def run_model(model: str) -> None:
    safe = model.strip().strip("/").replace("/", "__")
    out = ROOT / "outputs" / safe
    _run(["main.py", "--model", model])
    graph, report = out / "graph.json", out / "report.md"
    _run(["render_graph.py", "--input", str(graph), "--output", str(out / "lineage.html"), "--title", safe])
    st.subheader("风险血缘图（交互式）")
    _embed_html(out / "lineage.html")
    st.subheader("中文审计报告")
    _show_report(report)


def run_project(project: str) -> None:
    proj = Path(project.strip().strip("/"))
    out = ROOT / "outputs" / proj.name
    _run(["main.py", "--project", str(proj)])
    graph, report = out / "graph.json", out / "report.md"
    _run(["render_graph.py", "--input", str(graph), "--output", str(out / "lineage.html"), "--title", proj.name])
    st.subheader("风险血缘图（交互式）")
    _embed_html(out / "lineage.html")
    st.subheader("中文审计报告")
    _show_report(report)


def run_diff(before_path: Path, after_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        report = tmp_dir / "diff_report.md"
        diff_html = tmp_dir / "diff_lineage.html"
        _run(["main.py", "--diff", "--before", str(before_path), "--after", str(after_path), "--output", str(report)])
        _run(["render_diff.py", "--before", str(before_path), "--after", str(after_path), "--output", str(diff_html)])
        st.subheader("时间轴风险传播图（t0 → t1）")
        _embed_html(diff_html, height=520)
        st.subheader("中文审计报告")
        _show_report(report)


def _show_report(report_path: Path) -> None:
    text = report_path.read_text(encoding="utf-8") if report_path.exists() else "_报告未生成_"
    st.markdown(text)
    st.download_button("下载 Markdown 报告", data=text, file_name="audit_report.md", mime="text/markdown")


st.set_page_config(page_title="AI 模型血缘许可证风险审计工具", layout="wide")
st.title("AI 模型血缘许可证风险审计工具")
st.caption("开源账本 · ModelScope 血缘风险审计（答辩演示）")

mode = st.selectbox("模式", ["单模型", "项目", "时间对比"], index=0)

if mode == "单模型":
    model = st.text_input("ModelScope 模型名", value="Qwen/Qwen-Image-2.1",
                          help="例如 Qwen/Qwen-Image-2.1、Qwen/Qwen2.5-7B-Instruct")
    if st.button("开始扫描", type="primary"):
        if not model.strip() or "/" not in model:
            st.error("请输入合法的模型名（命名空间/模型名）")
        else:
            with st.spinner("正在扫描 ModelScope 血缘并生成报告…"):
                run_model(model.strip())

elif mode == "项目":
    project = st.text_input("项目路径（相对仓库根）", value="example/multi_model_project",
                            help="例如 example/multi_model_project（目录下含 config.json / bom.json / 代码中的模型标识）")
    if st.button("开始扫描", type="primary"):
        proj = ROOT / project.strip().strip("/")
        if not proj.exists():
            st.error("项目路径不存在：%s" % proj)
        else:
            with st.spinner("正在扫描项目模型并生成合并血缘图…"):
                run_project(project)

else:  # 时间对比
    st.info("上传两个 CycloneDX BOM 文件（需含 pedigree.ancestors 固化的血缘边）")
    f0 = st.file_uploader("t0 BOM（基线）", type=["json"], key="t0")
    f1 = st.file_uploader("t1 BOM（当前）", type=["json"], key="t1")
    if st.button("开始对比", type="primary"):
        if f0 is None or f1 is None:
            st.error("请先上传 t0 与 t1 两个 BOM 文件")
        else:
            with tempfile.TemporaryDirectory() as tmp:
                p0 = Path(tmp) / "t0_bom.json"
                p1 = Path(tmp) / "t1_bom.json"
                p0.write_bytes(f0.getvalue())
                p1.write_bytes(f1.getvalue())
                with st.spinner("正在对比血缘变化并生成传播图…"):
                    run_diff(p0, p1)  # 必须在 tmp 生命周期内调用
