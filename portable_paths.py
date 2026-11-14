# -*- coding: utf-8 -*-
"""把生成产物中的本机绝对路径转换为可公开的相对路径。

渲染器会把 BOM 中的 ``source_file``、AI 上下文里的 ``project_path`` 等字段
原样嵌入 HTML；这些字段可能来自扫描机器，直接公开会泄露用户名和目录结构。
本模块只做展示层清洗，不改变 BOM、Delta、风险判定或路径证书。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
HOME_ROOT = Path.home().resolve()

# 未识别的 Windows 用户目录 / POSIX 用户目录统一折叠成 ~，避免泄露用户名。
_WINDOWS_HOME_RE = re.compile(r"[A-Za-z]:\\Users\\[^\\\r\n]+\\")
_POSIX_HOME_RE = re.compile(r"/(?:Users|home)/[^/\s\"']+/")


def _root_prefixes(root: Path) -> tuple[str, ...]:
    text = str(root).rstrip("\\/")
    posix = text.replace("\\", "/")
    windows = text.replace("/", "\\")
    return tuple(dict.fromkeys((text, posix, windows)))


_ROOTS = (*_root_prefixes(REPO_ROOT), *_root_prefixes(HOME_ROOT))


def sanitize_text(value: str) -> str:
    """移除仓库根目录和用户主目录前缀，保留其余路径语义。"""

    text = value
    for root in _ROOTS:
        pattern = re.compile(re.escape(root) + r"(?=[\\/]|$)[\\/]?", re.IGNORECASE)
        text = pattern.sub("", text)
    text = _WINDOWS_HOME_RE.sub(lambda _match: "~\\", text)
    text = _POSIX_HOME_RE.sub("~/", text)
    return text


def sanitize_value(value: Any) -> Any:
    """递归清洗可 JSON 序列化的结构。"""

    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_value(item) for item in value)
    if isinstance(value, dict):
        return {key: sanitize_value(item) for key, item in value.items()}
    return value
