# -*- coding: utf-8 -*-
"""根目录渲染回归测试：脚本与 echarts.min.js 同目录时不得抛 SameFileError。

历史问题：render_graph.py / render_diff.py 无条件执行
``shutil.copy(cand, local_echarts)``。当 ``--output out.html`` 落在仓库根
（与脚本、echarts.min.js 同目录）时，cand 与 local_echarts 指向同一个文件，
shutil 直接抛 ``SameFileError``，报告 5.6 节「离线断网可开」在根目录落盘时必然失败。

两个脚本已改为先 ``resolve()`` 比较再复制。这里把脚本与 echarts.min.js 复制到
临时目录复现「输出落在根目录」的布局，锁死该行为，同时守住「输出到子目录时
仍然要把 echarts.min.js 复制过去」这条正常路径。
"""

import json
import os
import shutil
import subprocess
import sys

from conftest import REPO_ROOT

ECHARTS = REPO_ROOT / "echarts.min.js"
FIXTURE_ROOT = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "projects"
    / "qwen_image_license_tightening"
    / "upstream"
)
T0_BOM = FIXTURE_ROOT / "t0_bom.json"
T1_BOM = FIXTURE_ROOT / "t1_bom.json"


def _stage(tmp_path, *scripts):
    """把渲染脚本与 echarts.min.js 放进同一目录，复现"输出落在根目录"的布局。"""
    for name in scripts:
        shutil.copy(REPO_ROOT / name, tmp_path / name)
    shutil.copy(ECHARTS, tmp_path / "echarts.min.js")
    return tmp_path


def _run(script, *args):
    env = os.environ.copy()
    # 脚本按自身所在目录找 echarts.min.js，按 PYTHONPATH 找仓库根下的引擎模块
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(script.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def test_render_graph_root_output_does_not_copy_onto_itself(tmp_path):
    """render_graph.py --input graph.json --output out.html 必须成功，且不抛 SameFileError。"""
    root = _stage(tmp_path, "render_graph.py")
    graph = root / "graph.json"
    graph.write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "model:modelscope/qwen/Qwen2.5-7B@v1", "name": "Qwen2.5-7B", "decision": "SAFE"}
                ],
                "edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    echarts_before = (root / "echarts.min.js").stat().st_size

    proc = _run(root / "render_graph.py", "--input", str(graph), "--output", str(root / "out.html"))

    assert proc.returncode == 0, proc.stderr
    assert "SameFileError" not in proc.stderr
    html = (root / "out.html").read_text(encoding="utf-8")
    assert '<script src="./echarts.min.js"></script>' in html
    # 自拷贝不得把依赖文件截断成 0 字节
    assert (root / "echarts.min.js").stat().st_size == echarts_before


def test_render_diff_root_output_does_not_copy_onto_itself(tmp_path):
    """render_diff.py --before t0.json --after t1.json --output diff.html 必须成功出图。"""
    root = _stage(tmp_path, "render_diff.py")
    echarts_before = (root / "echarts.min.js").stat().st_size

    proc = _run(
        root / "render_diff.py",
        "--before",
        str(T0_BOM),
        "--after",
        str(T1_BOM),
        "--output",
        str(root / "diff.html"),
    )

    assert proc.returncode == 0, proc.stderr
    assert "SameFileError" not in proc.stderr
    html = (root / "diff.html").read_text(encoding="utf-8")
    assert '<script src="./echarts.min.js"></script>' in html
    assert (root / "echarts.min.js").stat().st_size == echarts_before


def test_render_graph_subdir_output_still_copies_echarts(tmp_path):
    """输出到子目录时仍需把 echarts.min.js 复制过去，离线打开才不回落 CDN。"""
    root = _stage(tmp_path, "render_graph.py")
    graph = root / "graph.json"
    graph.write_text(
        json.dumps({"nodes": [{"id": "m1", "name": "n1", "decision": "SAFE"}], "edges": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    out_dir = root / "sub"
    out_dir.mkdir()

    proc = _run(root / "render_graph.py", "--input", str(graph), "--output", str(out_dir / "out.html"))

    assert proc.returncode == 0, proc.stderr
    copied = out_dir / "echarts.min.js"
    assert copied.exists()
    assert copied.stat().st_size == ECHARTS.stat().st_size
    assert '<script src="./echarts.min.js"></script>' in (out_dir / "out.html").read_text(encoding="utf-8")
