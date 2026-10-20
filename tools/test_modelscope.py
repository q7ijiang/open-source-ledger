#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第一阶段：ModelScope API 探测脚本（自包含）。

用途：
    1. 读取项目根目录 `.env` 中的 `MODELSCOPE_API_KEY`；
    2. 以 `Authorization: Bearer <key>` 请求 ModelScope 真实 API；
    3. 将每个端点的原始 JSON 响应保存到 `outputs/modelscope_validation/`；
    4. 打印 HTTP 状态码、顶层字段与响应摘要，供第二阶段字段映射核对。

用法：
    python test_modelscope.py

说明：
    本脚本只做“探测 + 落盘”，不修改 main.py 的任何逻辑。

    注意：ModelScope 的血缘接口不是 ``/models/lineage/list``（该路径对任意
    参数都返回 404），而是挂在模型路径下的 ``/models/{ns}/{name}/lineage``。
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs" / "modelscope_validation"
API_BASE = "https://www.modelscope.cn/api/v1"

# 测试模型：namespace/name
MODELS = [
    "Qwen/Qwen-Image-2.1",
    "iic/nlp_structbert_sentiment-classification_chinese-base",
]

TIMEOUT = 30          # 单个请求超时（秒）
MAX_WORKERS = 4       # 并发线程数


def load_api_key() -> str:
    """读取 .env 中的 MODELSCOPE_API_KEY，缺失时给出明确错误。"""
    env_path = ROOT / ".env"
    if not env_path.exists():
        raise FileNotFoundError(
            f"未找到 .env：{env_path}\n"
            "请先创建 .env 并写入：MODELSCOPE_API_KEY=你的密钥"
        )
    load_dotenv(env_path)
    key = os.getenv("MODELSCOPE_API_KEY", "").strip()
    if not key:
        raise ValueError(".env 中未配置 MODELSCOPE_API_KEY")
    return key


def _slug(model_id: str) -> str:
    """把 namespace/name 转成安全的文件名字符。"""
    return model_id.replace("/", "__").replace("\\", "__").replace(" ", "_")


def build_tasks() -> list[dict[str, Any]]:
    """构造全部待探测端点。"""
    tasks: list[dict[str, Any]] = []
    for model_id in MODELS:
        ns, name = model_id.split("/", 1)
        tasks.append({
            "key": f"detail_{_slug(model_id)}",
            "label": f"模型详情 {model_id}",
            "url": f"{API_BASE}/models/{ns}/{name}",
            "params": None,
        })
        tasks.append({
            "key": f"files_{_slug(model_id)}",
            "label": f"模型文件列表 {model_id}",
            "url": f"{API_BASE}/models/{ns}/{name}/repo/files",
            "params": {"Recursive": "true"},
        })
        tasks.append({
            "key": f"lineage_{_slug(model_id)}",
            "label": f"模型血缘列表 {model_id}",
            "url": f"{API_BASE}/models/{ns}/{name}/lineage",
            "params": None,
        })
    return tasks


def request_one(headers: dict[str, str], task: dict[str, Any]) -> dict[str, Any]:
    """发起单个 GET 请求并捕获一切异常。"""
    result: dict[str, Any] = {
        "key": task["key"],
        "label": task["label"],
        "url": task["url"],
        "params": task["params"],
        "status": None,
        "ok": False,
        "body": None,
        "error": None,
    }
    try:
        resp = requests.get(
            task["url"], headers=headers, params=task["params"], timeout=TIMEOUT
        )
        result["status"] = resp.status_code
        result["ok"] = 200 <= resp.status_code < 300
        try:
            result["body"] = resp.json()
        except ValueError:
            # 非 JSON 响应，保留纯文本前 2000 字符供排查
            result["body"] = {"_raw_text": resp.text[:2000]}
    except Exception as exc:  # noqa: BLE001 —— 探测脚本需捕获一切网络异常
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def save_raw_json(r: dict[str, Any]) -> Path:
    """把原始响应写到输出目录，返回文件路径。"""
    body = r["body"]
    out_path = OUTPUT_DIR / f"{r['key']}.json"
    if isinstance(body, (dict, list)):
        out_path.write_text(
            json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        out_path.write_text(str(body), encoding="utf-8")
    return out_path


def main() -> int:
    try:
        api_key = load_api_key()
    except (FileNotFoundError, ValueError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    tasks = build_tasks()
    print(f"待探测端点：{len(tasks)} 个")
    print(f"输出目录：{OUTPUT_DIR}\n")

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_task = {pool.submit(request_one, headers, t): t for t in tasks}
        for future in as_completed(future_to_task):
            results.append(future.result())

    # 按构造顺序稳定输出
    order = {t["key"]: i for i, t in enumerate(tasks)}
    results.sort(key=lambda r: order.get(r["key"], 0))

    success = 0
    for r in results:
        print("=" * 76)
        print(f"[{r['label']}]  {r['url']}")
        if r["params"]:
            print(f"  params = {r['params']}")
        if r["error"]:
            print(f"  ✗ 异常：{r['error']}")
            continue
        print(f"  HTTP 状态码：{r['status']}")
        if r["ok"]:
            success += 1

        body = r["body"]
        if isinstance(body, dict):
            keys = list(body.keys())
            print(f"  顶层字段（{len(keys)}）：{keys[:40]}")
            preview = json.dumps(body, ensure_ascii=False, indent=2)
        elif isinstance(body, list):
            print(f"  顶层为列表，元素数：{len(body)}")
            preview = json.dumps(body, ensure_ascii=False, indent=2)
        else:
            preview = str(body)

        out_path = save_raw_json(r)
        print("  响应摘要（前 600 字符）：")
        print("    " + preview[:600].replace("\n", "\n    "))
        print(f"  ✓ 原始 JSON 已保存：{out_path}")

    print("\n" + "=" * 76)
    print(f"探测完成：{success}/{len(tasks)} 个请求返回 2xx")
    return 0 if success == len(tasks) else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
