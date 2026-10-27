# -*- coding: utf-8 -*-
"""AI 模型血缘许可证风险审计工具 — Streamlit 输入界面（答辩演示用）。

模式：
  项目    ：选择或输入项目目录 → main.py --project → 合并血缘风险图 + 中文报告
  时间对比：上传 t0 / t1 两个 BOM → main.py --diff + render_diff.py → 时间轴传播图 + 中文报告

单模型扫描仅保留在命令行内部诊断中，不作为 Streamlit 用户入口。

约束（对齐组长要求）：
  - 不重写任何数据管道逻辑，只通过 subprocess 调用 main.py 现有功能
  - 不写死路径：图由 render_graph.py / render_diff.py 的 --input/--before/--after 参数读取
  - 页面简洁，风险图居中展示
"""
import base64
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import main as ledger_main

ROOT = Path(__file__).resolve().parent
PY = sys.executable
ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"


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
    """内嵌 HTML 血缘图：优先内联本地 ECharts，缺失时回退 CDN。"""
    html = html_path.read_text(encoding="utf-8")
    local_echarts = html_path.parent / "echarts.min.js"
    if local_echarts.exists():
        payload = base64.b64encode(local_echarts.read_bytes()).decode("ascii")
        html = html.replace(
            'src="./echarts.min.js"',
            'src="data:text/javascript;base64,%s"' % payload,
        )
    else:
        html = html.replace('src="./echarts.min.js"', 'src="%s"' % ECHARTS_CDN)
    components.html(html, height=height, scrolling=True)


def _pick_project_directory(initial_path: str = "") -> str | None:
    """打开本机目录选择器；服务端无桌面环境时保留手工输入路径。"""
    root = None
    try:
        import tkinter as tk
        from tkinter import filedialog

        initial = Path(initial_path).expanduser() if initial_path.strip() else ROOT
        if initial.is_file():
            initial = initial.parent
        if not initial.is_dir():
            initial = ROOT

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(
            parent=root,
            initialdir=str(initial),
            title="选择项目目录",
            mustexist=True,
        )
        return selected or None
    except Exception as exc:
        st.warning("无法打开系统目录选择器：%s。你仍可手动输入项目路径。" % exc)
        return None
    finally:
        if root is not None:
            root.destroy()


def run_project(project: Path, enable_ai: bool = False) -> None:
    proj = project.resolve()
    out = ledger_main._project_output_dir(ROOT, proj)
    ai_flag = ["--ai"] if enable_ai else []
    _run([str(ROOT / "main.py"), "--project", str(proj), *ai_flag])
    graph, report = out / "graph.json", out / "report.md"
    _run([str(ROOT / "render_graph.py"), "--input", str(graph), "--output", str(out / "lineage.html"), "--report", str(report), "--title", proj.name])
    st.subheader("风险血缘图（交互式）")
    _embed_html(out / "lineage.html")
    st.subheader("中文审计报告")
    _show_report(report)


def run_diff(
    before_path: Path,
    after_path: Path,
    include_fixtures: bool = False,
    enable_ai: bool = False,
) -> None:
    flag = ["--include-fixtures"] if include_fixtures else []
    ai_flag = ["--ai"] if enable_ai else []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        report = tmp_dir / "diff_report.md"
        diff_html = tmp_dir / "diff_lineage.html"
        _run([str(ROOT / "main.py"), "--diff", "--before", str(before_path), "--after", str(after_path), "--output", str(report), *flag, *ai_flag])
        _run([str(ROOT / "render_diff.py"), "--before", str(before_path), "--after", str(after_path), "--output", str(diff_html), "--report", str(report), *flag])
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

mode = st.selectbox("模式", ["项目", "时间对比"], index=0)
enable_ai = st.checkbox(
    "启用 AI 语义证据（C 级，需人工确认）",
    value=False,
    help="调用配置的 OpenAI-compatible 模型抽取条款；默认关闭，不影响规则主链。",
)

if mode == "项目":
    path_col, browse_col = st.columns([5, 1])
    project = path_col.text_input(
        "项目路径",
        key="project_path",
        placeholder="请选择或输入项目目录，可填写绝对路径或相对仓库根的路径",
        help="目录下可包含 config.json、bom.json 或代码中的模型标识。",
    )
    if browse_col.button("浏览目录", use_container_width=True):
        selected = _pick_project_directory(project)
        if selected:
            st.session_state["project_path"] = selected
            st.rerun()

    if st.button("开始扫描", type="primary"):
        raw_path = project.strip()
        if not raw_path:
            st.error("请先选择或输入项目目录")
            st.stop()
        candidate = Path(raw_path).expanduser()
        proj = candidate.resolve() if candidate.is_absolute() else (ROOT / candidate).resolve()
        if not proj.is_dir():
            st.error("项目路径不存在：%s" % proj)
        else:
            with st.spinner("正在扫描项目模型并生成合并血缘图…"):
                run_project(proj, enable_ai)

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
                    run_diff(p0, p1, enable_ai=enable_ai)
