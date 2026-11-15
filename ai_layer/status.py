# -*- coding: utf-8 -*-
"""AI 常驻位的配置探测与降级状态。

Action 每次运行都会写一份 ai_status.json：
- 配置齐全时 ready=true，调用真实 AI；
- 缺少配置时 status=unavailable，规则链继续；
- AI_ENABLED=false 时显式关闭。
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def resolve_ai_status(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environ is None else environ
    enabled_flag = str(env.get("AI_ENABLED", "")).strip().lower()
    base_url = str(env.get("AI_BASE_URL", "")).strip()
    model = str(env.get("AI_MODEL", "")).strip()
    api_key = str(env.get("AI_API_KEY", "")).strip()

    reasons: list[str] = []
    if enabled_flag in FALSE_VALUES:
        status = "disabled"
        reasons.append("AI_ENABLED=false")
    else:
        if not base_url:
            reasons.append("missing AI_BASE_URL")
        if not model:
            reasons.append("missing AI_MODEL")
        if not api_key:
            reasons.append("missing AI_API_KEY")
        status = "ready" if not reasons else "unavailable"

    return {
        "schema_version": "ai-status/v1",
        "status": status,
        "ready": status == "ready",
        "provider": "openai-compatible",
        "model": model,
        "base_url": base_url,
        "api_key_present": bool(api_key),
        "reasons": reasons,
        "evaluated_at": _now(),
        "commit_sha": str(env.get("GITHUB_SHA", "")),
    }


def write_ai_status(path: Path, environ: Mapping[str, str] | None = None) -> dict[str, object]:
    status = resolve_ai_status(environ)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="探测 AI 配置并写入 ai_status.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    status = write_ai_status(args.output)
    print("true" if status["ready"] else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
